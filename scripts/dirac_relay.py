#!/usr/bin/env python3
"""Root-run relay from the Dirac V2 container to protected V1 Ollama.

V2 and V1 are separate rootless engines, so the Dirac container can reach neither
the host loopback nor the other engine's bridge. This helper binds one private
address - the V2 instance's outbound bridge gateway, inside the V2 daemon's
network namespace - and forwards each accepted connection into the current
network namespace of the selected protected V1 Ollama container's loopback. The
target PID is resolved read-only per connection, so a V1 recreate is followed.

Every Docker call runs as the mapped service account against that account's own
validated socket and is read-only (`info`/`inspect`); only the relay process
itself keeps host root, and only for `setns` and `nsenter`. There is no proxy
command, no user-supplied target, no V1 mutation and no published host port, but
the forwarded bytes are neither inspected nor filtered: whatever can reach the
bound gateway can use Ollama's local API. Run it as host root under its own unit;
see `phase-II_v2/DIRAC_RUNTIME_OPS.md`.
"""

import argparse
import ipaddress
import json
import os
import pwd
import socket
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RUNUSER, ENV, DOCKER = "/usr/sbin/runuser", "/usr/bin/env", "/usr/bin/docker"
DOCKER_CONFIG, PATH_VALUE = "/nonexistent", "/usr/local/bin:/usr/bin:/bin"
NSENTER, SOCAT = "/usr/bin/nsenter", "/usr/bin/socat"
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
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"docker {args[0]} failed on the {self.account} engine")
        return result.stdout


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


def engine_netns(pid_file: Path | None, netns: str | None, expected_uid: int) -> str:
    """Resolve the parent-verified daemon network namespace and refuse the caller's own."""
    if netns is None:
        pid = pid_file.read_text().strip()
        if not pid.isdigit():
            raise ValueError(f"{pid_file} does not contain an engine PID")
    else:
        parts = Path(netns).parts
        if len(parts) != 5 or parts[1] != "proc" or parts[3] != "ns" or parts[4] != "net" or not parts[2].isdigit():
            raise ValueError("--engine-netns must be an explicit /proc/<pid>/ns/net path")
        pid = parts[2]
    if os.stat(f"/proc/{pid}").st_uid != expected_uid:
        raise ValueError("engine process is not owned by the V2 service account")
    path = f"/proc/{pid}/ns/net"
    current = os.stat("/proc/self/ns/net")
    target = os.stat(path)
    if (current.st_dev, current.st_ino) == (target.st_dev, target.st_ino):
        raise ValueError("engine namespace is the caller's own; refusing to bind in it")
    return path


def forward_argv(pid: int) -> list[str]:
    """The one fixed helper: enter the V1 container namespace and speak to its loopback."""
    return [NSENTER, f"--net=/proc/{pid}/ns/net", "--", SOCAT, "-", f"TCP4:127.0.0.1:{TARGET_PORT}"]


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


def serve(listener: socket.socket, engine: Engine, container: str, project: str, service: str) -> None:
    """Forward connections until stopped; each one re-resolves its target under a live-helper cap."""
    helpers: list[subprocess.Popen] = []
    while True:
        connection, _ = listener.accept()
        helpers = [helper for helper in helpers if helper.poll() is None]
        if len(helpers) >= MAX_HELPERS:
            print(f"{len(helpers)} helpers are still forwarding; refusing the connection", file=sys.stderr, flush=True)
            connection.close()
            continue
        pid = target_pid(engine, container, project, service)
        if pid is None:
            print(f"no running {container} in project {project}; refusing the connection", file=sys.stderr, flush=True)
            connection.close()
            continue
        helpers.append(subprocess.Popen(forward_argv(pid), stdin=connection, stdout=connection))
        connection.close()


def main() -> None:
    """Enter the V2 daemon namespace, bind the private gateway, then forward fixed targets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-account", default=V2_ACCOUNT, help="V2 service account owning the daemon")
    parser.add_argument("--v2-project", default=V2_PROJECT, help="V2 compose project owning the bridge")
    parser.add_argument("--v2-engine-id", help="optional pinned V2 engine ID to require")
    parser.add_argument("--network", required=True, help="V2 instance outbound bridge name")
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
    fd = os.open(engine_netns(args.engine_pid_file, args.engine_netns, v2.uid), os.O_RDONLY)
    os.setns(fd)
    os.close(fd)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((gateway, TARGET_PORT))
    listener.listen(BACKLOG)
    print(f"dirac relay bound {gateway}:{TARGET_PORT} -> {args.v1_container} loopback", flush=True)
    serve(listener, v1, args.v1_container, args.v1_project, args.v1_service)


if __name__ == "__main__":
    main()
