#!/usr/bin/env python3
"""Root-run relay from the Dirac V2 container to protected V1 Ollama.

V2 and V1 are separate rootless engines, so the Dirac container can reach neither
the host loopback nor the other engine's bridge. This helper binds one private
address - the V2 instance's outbound bridge gateway, inside the V2 daemon's
network namespace - and forwards each accepted connection into the current
network namespace of the selected protected V1 Ollama container's loopback. The
target PID is resolved read-only per connection, so a V1 recreate is followed.

Only POST /api/embed, /api/embeddings and /v1/embeddings are forwarded. Headers
are validated, body bytes and query parameters are preserved, and framing is
normalized to one Content-Length plus Connection: close. Exactly the declared
body is streamed; pipelined bytes are not forwarded. Chunked requests and Expect
handshakes are intentionally unsupported rather than implementing a general proxy.

This blocks model-management routes, not resource effects of permitted embedding
requests: embedding arguments remain client-controlled. It is not a separate
model server, a model-name policy or a resource quota.

The namespace the relay binds in is watched. If the V2 daemon is replaced, the
running relay is still bound to the retired namespace and would answer on a
gateway the new daemon's containers no longer use, so it fails closed and exits
for systemd to restart in the new namespace instead of serving a stale bridge.

Every Docker call runs as the mapped service account against that account's own
validated socket and is read-only (`info`/`inspect`); only the relay process
itself keeps host root, and only for `setns` and `nsenter`. There is no proxy
command, no user-supplied target, no V1 mutation and no published host port. Run
it as host root under its own unit with an isolated interpreter (`-I -S -B`); see
`phase-II_v2/DIRAC_RUNTIME_OPS.md`.
"""

import argparse
import ipaddress
import json
import os
import pwd
import signal
import socket
import stat
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

RUNUSER, ENV, DOCKER = "/usr/sbin/runuser", "/usr/bin/env", "/usr/bin/docker"
DOCKER_CONFIG, PATH_VALUE = "/nonexistent", "/usr/local/bin:/usr/bin:/bin"
NSENTER = "/usr/bin/nsenter"
TARGET_PORT, BACKLOG, MAX_HELPERS = 11434, 64, 32
DOCKER_ROOT = ".local/share/docker"
V2_ACCOUNT, V1_ACCOUNT = "dame-curie", "maxwell-curie"
V2_PROJECT = V2_ACCOUNT
V1_CONTAINER, V1_PROJECT, V1_SERVICE = "maxwell-curie-ollama-1", "maxwell-curie", "ollama"
TARGET_FORMAT = (
    "{{.State.Pid}}|{{.State.Running}}"
    '|{{index .Config.Labels "com.docker.compose.project"}}'
    '|{{index .Config.Labels "com.docker.compose.service"}}'
)

# The one HTTP boundary. Only these exact paths are embedding endpoints; methods
# other than POST and every other path are answered locally and never forwarded.
EMBED_PATHS = ("/api/embed", "/api/embeddings", "/v1/embeddings")
# 64 KiB bounds one request head: a request line plus a handful of headers. The
# relay has no matching V1 value for a request body, so the body has no cap and
# is streamed through instead of being buffered.
HEAD_LIMIT = 64 * 1024
COPY_CHUNK, READ_TIMEOUT = 64 * 1024, 60.0
DOCKER_TIMEOUT, HELPER_SOCKET_TIMEOUT = 30.0, 180.0
HEADER_NAME_BYTES = frozenset(b"!#$%&'*+-.^_`|~" + bytes(range(48, 58)) + bytes(range(65, 91)) + bytes(range(97, 123)))
# A replaced daemon is noticed within one poll; the operator CLI already polls
# readiness at this same interval, so no new timing scale is introduced.
WATCHDOG_SECONDS = 5.0
STOPPING = threading.Event()

# The helper enters V1's network namespace and speaks to its loopback with the
# stdlib only. It knows nothing about HTTP: it copies this process's pipes to the
# socket, half-closes the write side so the upstream request is framed complete,
# and copies the response back until the upstream closes.
HELPER_PROGRAM = (
    "import os,socket,sys\n"
    "s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=float(sys.argv[3]))\n"
    "while (d:=os.read(0,65536)): s.sendall(d)\n"
    "s.shutdown(socket.SHUT_WR)\n"
    "while (d:=s.recv(65536)): os.write(1,d)\n"
)

STATUS_TEXT = {
    400: "Bad Request",
    403: "Forbidden",
    405: "Method Not Allowed",
    411: "Length Required",
    417: "Expectation Failed",
    431: "Request Header Fields Too Large",
    503: "Service Unavailable",
}


class Refused(Exception):
    """One locally answered refusal: the status to send and the reason to log."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class Engine:
    """One service account's validated private rootless endpoint."""

    account: str
    home: str
    uid: int
    socket: str

    def query(self, *args: str) -> str:
        """Run one Docker query as the mapped account, with an explicit endpoint and no inherited client config."""
        result = subprocess.run(
            [RUNUSER, "-u", self.account, "--", ENV, "-i",
             f"HOME={self.home}", f"PATH={PATH_VALUE}", f"DOCKER_CONFIG={DOCKER_CONFIG}",
             DOCKER, "--host", self.socket, *args],
            capture_output=True, text=True, timeout=DOCKER_TIMEOUT,
        )
        if result.returncode:
            raise RuntimeError(f"docker {args[0]} failed on the {self.account} engine")
        return result.stdout


@dataclass(frozen=True)
class BoundEngine:
    """The daemon this relay bound for: the identity that makes its namespace stale if replaced."""

    uid: int
    pid: int
    start_time: str
    netns: str

    def retired(self, pid_file: Path | None) -> str:
        """The reason this binding is stale, or an empty string while the bound daemon is unchanged."""
        try:
            if pid_file is not None and int(pid_file.read_text().strip()) != self.pid:
                return "the engine PID file names a different daemon"
            if os.stat(f"/proc/{self.pid}").st_uid != self.uid:
                return "the engine process this relay bound for is gone"
            if process_start_time(self.pid) != self.start_time:
                return "the engine PID was reused by a different process"
            current = os.stat("/proc/self/ns/net")
            bound = os.stat(self.netns)
        except (OSError, ValueError) as error:
            return f"the bound engine can no longer be checked ({error.__class__.__name__})"
        if (current.st_dev, current.st_ino) != (bound.st_dev, bound.st_ino):
            return "this relay's own namespace is no longer the bound engine's"
        return ""


def checked_socket(path: Path, uid: int) -> Path:
    """Require a real, unsymlinked engine socket owned by the account that is supposed to own it."""
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError(f"engine socket path contains a symlink: {path}")
    if not path.exists():
        raise ValueError(f"missing engine socket: {path}")
    info = path.stat()
    if not stat.S_ISSOCK(info.st_mode):
        raise ValueError(f"engine endpoint is not a socket: {path}")
    if info.st_uid != uid:
        raise ValueError(f"engine socket is not owned by the mapped service account: {path}")
    return path


def open_engine(account_name: str) -> Engine:
    """Resolve one service account and validate its own private rootless endpoint; no fallback exists."""
    account = pwd.getpwnam(account_name)
    if account.pw_uid == 0:
        raise ValueError("service account cannot be root")
    endpoint = checked_socket(Path(f"/run/user/{account.pw_uid}/docker.sock"), account.pw_uid)
    return Engine(account_name, account.pw_dir, account.pw_uid, f"unix://{endpoint}")


def validate_engine(engine: Engine, engine_id: str | None) -> None:
    """Require that account's own rootless engine, its private Docker root and any pinned identity."""
    info = json.loads(engine.query("info", "--format", "{{json .}}"))
    options = info.get("SecurityOptions") or []
    if not any(option == "name=rootless" or option.startswith("name=rootless,") for option in options):
        raise ValueError(f"{engine.account} endpoint is not rootless; refusing a rootful fallback")
    expected = f"{engine.home}/{DOCKER_ROOT}"
    if info.get("DockerRootDir") != expected:
        raise ValueError(f"{engine.account} engine does not use its expected private Docker root")
    if engine_id is not None and info.get("ID") != engine_id:
        raise ValueError(f"{engine.account} engine identity does not match the pinned engine ID")


def bridge_gateway(engine: Engine, network: str, project: str) -> str:
    """Read the private gateway of the validated V2 instance outbound bridge."""
    fields = engine.query(
        "network", "inspect", network, "--format",
        '{{index .Labels "com.docker.compose.project"}}'
        '|{{index .Labels "com.docker.compose.network"}}'
        "|{{(index .IPAM.Config 0).Gateway}}",
    ).strip().split("|")
    if fields[:2] != [project, "outbound"]:
        raise ValueError(f"{network} is not the {project} outbound bridge")
    gateway = fields[2]
    address = ipaddress.ip_address(gateway)
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError(f"refusing to bind non-private gateway {gateway}")
    return gateway


def engine_pid(pid_file: Path | None, netns: str | None, expected_uid: int) -> int:
    """Resolve the parent-verified engine PID from its PID file or from an explicit namespace path."""
    if netns is not None:
        parts = Path(netns).parts
        if len(parts) != 5 or parts[1] != "proc" or parts[3] != "ns" or parts[4] != "net" or not parts[2].isdigit():
            raise ValueError("--engine-netns must be an explicit /proc/<pid>/ns/net path")
        pid = int(parts[2])
    elif pid_file is not None:
        text = pid_file.read_text().strip()
        if not text.isdigit():
            raise ValueError(f"{pid_file} does not contain an engine PID")
        pid = int(text)
    else:
        raise ValueError("one of --engine-pid-file or --engine-netns is required")
    if os.stat(f"/proc/{pid}").st_uid != expected_uid:
        raise ValueError("engine process is not owned by the V2 service account")
    return pid


def process_start_time(pid: int) -> str:
    """Field 22 of /proc/<pid>/stat: an identity that survives PID reuse for as long as the boot lives."""
    return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]

def engine_netns(pid_file: Path | None, netns: str | None, expected_uid: int) -> str:
    """Resolve the parent-verified daemon network namespace and refuse the caller's own."""
    path = f"/proc/{engine_pid(pid_file, netns, expected_uid)}/ns/net"
    current = os.stat("/proc/self/ns/net")
    target = os.stat(path)
    if (current.st_dev, current.st_ino) == (target.st_dev, target.st_ino):
        raise ValueError("engine namespace is the caller's own; refusing to bind in it")
    return path


def helper_argv(pid: int, python: str) -> list[str]:
    """The one fixed helper: enter the V1 container namespace and reach its loopback."""
    return [
        NSENTER, f"--net=/proc/{pid}/ns/net", "--",
        python, "-I", "-S", "-B", "-c", HELPER_PROGRAM,
        "127.0.0.1", str(TARGET_PORT), str(HELPER_SOCKET_TIMEOUT),
    ]


def target_pid(engine: Engine, container: str, project: str, service: str) -> int | None:
    """Resolve the running V1 Ollama PID read-only; None when it is absent, stopped, foreign or not V1's."""
    fields = engine.query(
        "inspect", "--type", "container", "--format", TARGET_FORMAT, container,
    ).strip().split("|")
    if len(fields) != 4 or fields[1] != "true":
        return None
    if fields[2] != project or fields[3] != service or not fields[0].isdigit():
        return None
    pid = int(fields[0])
    if pid <= 0:
        return None
    try:
        owner = os.stat(f"/proc/{pid}").st_uid
    except OSError:  # the target can exit between the inspect and the stat
        return None
    return pid if owner == engine.uid else None


def refusal(status: int, reason: str) -> bytes:
    """One complete locally generated response; the caller closes the connection after sending it."""
    body = f"{status} {STATUS_TEXT[status]}: {reason}\n".encode()
    allow = "Allow: POST\r\n" if status == 405 else ""
    head = (
        f"HTTP/1.1 {status} {STATUS_TEXT[status]}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"{allow}Connection: close\r\n"
    )
    return head.encode() + b"\r\n" + body


def read_request_head(connection: socket.socket) -> tuple[str, str, str, list[tuple[str, str]], bytes]:
    """Read one request line and its headers; return them with the body bytes that arrived with the head."""
    head = b""
    while b"\r\n\r\n" not in head:
        block = connection.recv(4096)
        if not block:
            raise Refused(400, "the client closed before sending a complete request head")
        head += block
        if len(head) > HEAD_LIMIT:
            raise Refused(431, "the request head exceeded the relay's read limit")
    block, body = head.split(b"\r\n\r\n", 1)
    lines = block.decode("latin-1").split("\r\n")
    fields = lines[0].split(" ")
    if len(fields) != 3 or fields[2] not in ("HTTP/1.0", "HTTP/1.1"):
        raise Refused(400, "the request line is not one HTTP/1.0 or HTTP/1.1 method, target and version")
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line or line[0] in " \t" or ":" not in line:
            raise Refused(400, "a header line is empty, folded or has no colon")
        name, value = line.split(":", 1)
        if not checked_header_name(name):
            raise Refused(400, "a header name is not one HTTP token or has surrounding whitespace")
        if not checked_header_value(value):
            raise Refused(400, "a header value carries a control character")
        headers.append((name, value.strip(" \t")))
    return fields[0], fields[1], fields[2], headers, body


def checked_header_name(name: str) -> bool:
    """Whether this is one HTTP token: a bare LF or CR smuggling a second request is not a token byte."""
    return bool(name) and all(byte in HEADER_NAME_BYTES for byte in name.encode("latin-1"))


def checked_header_value(value: str) -> bool:
    """Whether this field value is free of CR, LF and the other control characters, allowing HTAB."""
    return all(
        character == "\t" or (ord(character) >= 0x20 and ord(character) != 0x7f)
        for character in value
    )


def request_body_length(headers: list[tuple[str, str]]) -> int:
    """Require one unambiguous request framing: at most one Content-Length and no Transfer-Encoding."""
    values = {value.strip(" \t") for name, value in headers if name.lower() == "content-length"}
    if any(name.lower() == "expect" for name, _ in headers):
        raise Refused(417, "Expect handshakes are not supported")
    if len(values) > 1:
        raise Refused(400, "conflicting Content-Length headers are not accepted")
    if any(name.lower() == "transfer-encoding" for name, _ in headers):
        raise Refused(411, "chunked or otherwise transfer-encoded requests are not decoded")
    if not values:
        return 0
    length = values.pop()
    if not length.isascii() or not length.isdecimal():
        raise Refused(400, "Content-Length is not an ASCII decimal byte count")
    try:
        return int(length)
    except ValueError as error:
        raise Refused(400, "Content-Length exceeds integer parsing limits") from error


def request_target(target: str) -> tuple[str, str]:
    """The full target to forward (query preserved) and the bare path the allowlist matches."""
    if "#" in target or any(ord(character) <= 0x20 or ord(character) == 0x7f for character in target):
        raise Refused(400, "the request target contains a fragment or control character")
    if not target.startswith("/"):
        if not target.lower().startswith(("http://", "https://")):
            raise Refused(400, "the request target is neither origin-form nor HTTP absolute-form")
        target = "/" + target.split("://", 1)[1].partition("/")[2]
    return target, target.split("?", 1)[0]


def upstream_request(
    method: str, path: str, version: str, headers: list[tuple[str, str]], length: int,
) -> bytes:
    """One forwarded request: the client's own headers, minus framing, plus this relay's framing."""
    lines = [f"{method} {path} {version}"]
    for name, value in headers:
        if name.lower() not in ("content-length", "connection", "transfer-encoding"):
            lines.append(f"{name}: {value}")
    lines.append(f"Content-Length: {length}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


def stream_request(
    connection: socket.socket, child: subprocess.Popen, request: bytes, body: bytes, length: int,
) -> None:
    """Send the framed request and its measured body, then half-close so upstream sees it complete."""
    assert child.stdin is not None
    child.stdin.write(request)
    child.stdin.write(body[:length])
    remaining = length - len(body[:length])
    while remaining > 0:
        block = connection.recv(min(COPY_CHUNK, remaining))
        if not block:
            raise OSError("the client closed before sending the body it declared")
        child.stdin.write(block)
        remaining -= len(block)
    child.stdin.close()


def forward(connection: socket.socket, child: subprocess.Popen) -> None:
    """Copy the helper's upstream response back to the client until the helper closes."""
    assert child.stdout is not None
    while block := child.stdout.read(COPY_CHUNK):
        connection.sendall(block)


def handle_connection(
    connection: socket.socket, engine: Engine, container: str, project: str, service: str, python: str,
) -> None:
    """Filter one request, forward it when allowed, and close; a refusal never reaches the helper."""
    connection.settimeout(READ_TIMEOUT)
    with connection:
        try:
            method, target, version, headers, body = read_request_head(connection)
            if method != "POST":
                raise Refused(405, f"{method} is not accepted on the embedding boundary")
            forwarded_target, path = request_target(target)
            if path not in EMBED_PATHS:
                raise Refused(403, f"{method} {path} is not one of the three embedding endpoints")
            length = request_body_length(headers)
            try:
                pid = target_pid(engine, container, project, service)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                raise Refused(503, "the embedding target could not be resolved") from error
            if pid is None:
                raise Refused(503, f"no running {container} in project {project}")
            child = subprocess.Popen(
                helper_argv(pid, python), stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
            )
            request = upstream_request(method, forwarded_target, version, headers, length)
            try:
                stream_request(connection, child, request, body, length)
                forward(connection, child)
            finally:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:  # the helper already finished, which is the normal exit
                    pass
                child.wait()
        except Refused as refused:
            print(f"refused {refused.status} {refused.reason}", file=sys.stderr, flush=True)
            connection.sendall(refusal(refused.status, refused.reason))
        except OSError as error:
            print(f"connection closed during forwarding: {error}", file=sys.stderr, flush=True)


def serve(
    listener: socket.socket, engine: Engine, container: str, project: str, service: str,
    python: str, bound: BoundEngine, pid_file: Path | None,
) -> None:
    """Accept and filter until stopped, re-resolving the V1 target under a live-helper cap."""
    helpers: list[threading.Thread] = []
    listener.settimeout(WATCHDOG_SECONDS)
    while not STOPPING.is_set():
        retired = bound.retired(pid_file)
        if retired:
            print(f"{retired}; exiting so systemd rebinds the relay", file=sys.stderr, flush=True)
            sys.exit(75)
        try:
            connection, _ = listener.accept()
        except TimeoutError:
            continue
        helpers = [helper for helper in helpers if helper.is_alive()]
        if len(helpers) >= MAX_HELPERS:
            print(f"{len(helpers)} helpers are still forwarding; refusing the connection", file=sys.stderr, flush=True)
            try:
                with connection:
                    connection.sendall(refusal(503, "the relay is at its forwarding cap"))
            except OSError:
                pass
            continue
        helper = threading.Thread(
            target=handle_connection,
            args=(connection, engine, container, project, service, python),
            daemon=True,
        )
        helpers.append(helper)
        helper.start()


def main() -> None:
    """Enter the V2 daemon namespace, bind the private gateway, then filter and forward fixed targets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-account", default=V2_ACCOUNT, help="V2 service account owning the daemon")
    parser.add_argument("--v2-project", default=V2_PROJECT, help="V2 compose project owning the bridge")
    parser.add_argument("--v2-engine-id", help="optional pinned V2 engine ID to require")
    parser.add_argument("--network", required=True, help="V2 instance outbound bridge name")
    parser.add_argument("--python", default=sys.executable, help="interpreter the fixed helper execs in V1's namespace")
    namespace = parser.add_mutually_exclusive_group(required=True)
    namespace.add_argument("--engine-pid-file", type=Path, help="parent-verified rootless engine PID file")
    namespace.add_argument("--engine-netns", help="parent-verified /proc/<pid>/ns/net path")
    parser.add_argument("--v1-account", default=V1_ACCOUNT, help="protected V1 service account")
    parser.add_argument("--v1-engine-id", help="optional pinned V1 engine ID to require")
    parser.add_argument("--v1-container", default=V1_CONTAINER)
    parser.add_argument("--v1-project", default=V1_PROJECT)
    parser.add_argument("--v1-service", default=V1_SERVICE)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("the relay requires host root for setns and nsenter")
    v2 = open_engine(args.v2_account)
    v1 = open_engine(args.v1_account)
    validate_engine(v2, args.v2_engine_id)
    validate_engine(v1, args.v1_engine_id)
    gateway = bridge_gateway(v2, args.network, args.v2_project)
    pid = engine_pid(args.engine_pid_file, args.engine_netns, v2.uid)
    bound = BoundEngine(v2.uid, pid, process_start_time(pid), engine_netns(args.engine_pid_file, args.engine_netns, v2.uid))
    fd = os.open(bound.netns, os.O_RDONLY)
    os.setns(fd)
    os.close(fd)
    for received in (signal.SIGTERM, signal.SIGINT):
        signal.signal(received, lambda *_: STOPPING.set())
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((gateway, TARGET_PORT))
    listener.listen(BACKLOG)
    print(f"dirac embedding relay bound {gateway}:{TARGET_PORT} -> {args.v1_container} loopback", flush=True)
    if args.engine_pid_file is None:
        print("--engine-netns pins the daemon PID; a replacement daemon is only noticed when that PID goes", file=sys.stderr, flush=True)
    serve(listener, v1, args.v1_container, args.v1_project, args.v1_service, args.python, bound, args.engine_pid_file)


if __name__ == "__main__":
    main()
