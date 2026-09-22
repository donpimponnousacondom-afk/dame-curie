"""Isolated end-to-end checks for the relay's embedding HTTP boundary.

No namespace is entered, no engine is contacted and no V1 resource is read. The
upstream is a loopback thread that speaks the same HTTP bytes Ollama would, and
the relay's own helper program is started directly against it, so the real
parser, allowlist, framing, helper argv and forwarding loop all run. Only the
`nsenter` namespace hop and the real engine are replaced.

Not covered here: real Ollama responses, a real V1 loopback, the root-only
`setns` bind, and systemd restart behaviour after a daemon replacement. Those
need the coordinator's isolated runtime.
"""

import importlib.util
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BODY = b'{"model":"qwen3-embedding:0.6b","input":"hello","truncate":false}'
UPSTREAM_BODY = b'{"embeddings":[[0.1,0.2,0.3]]}'
UPSTREAM_RESPONSE = (
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
    b"Content-Length: " + str(len(UPSTREAM_BODY)).encode() + b"\r\nConnection: close\r\n\r\n" + UPSTREAM_BODY
)
CONTAINER, PROJECT, SERVICE = "maxwell-curie-ollama-1", "maxwell-curie", "ollama"
REFUSAL_MID_HEAD = b"400 Bad Request: the client closed before sending a complete request head\n"


def load_relay() -> ModuleType:
    """Load the relay module without importing the application package."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("dirac_relay", ROOT / "scripts" / "dirac_relay.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


RELAY_MODULE = load_relay()


@pytest.fixture(scope="module")
def relay() -> ModuleType:
    return RELAY_MODULE


class FakeEngine:
    """The scripted V1 engine: it answers the one inspect the relay makes."""

    account = "maxwell-curie"
    home = "/home/maxwell-curie"
    uid = os.getuid()
    socket = "unix:///run/user/1003/docker.sock"

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply or f"{os.getpid()}|true|{PROJECT}|{SERVICE}\n"
        self.calls: list[tuple[str, ...]] = []

    def query(self, *args: str) -> str:
        self.calls.append(args)
        return self.reply


class Upstream:
    """A loopback stand-in for V1 Ollama that records the exact request it received."""

    def __init__(self) -> None:
        self.received: list[bytes] = []
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.port = self.listener.getsockname()[1]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _read_head(self, connection: socket.socket) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data:
            block = connection.recv(4096)
            if not block:
                return data
            data += block
        return data

    def _pump(self) -> None:
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            with connection:
                data = self._read_head(connection)
                if not data:
                    continue
                head, _, body = data.partition(b"\r\n\r\n")
                length = 0
                for line in head.decode("latin-1").split("\r\n")[1:]:
                    if line.lower().startswith("content-length:"):
                        length = int(line.split(":", 1)[1])
                while len(body) < length:
                    block = connection.recv(4096)
                    if not block:
                        break
                    body += block
                self.received.append(head + b"\r\n\r\n" + body)
                connection.sendall(UPSTREAM_RESPONSE)
                connection.shutdown(socket.SHUT_WR)

    def close(self) -> None:
        self.stop.set()
        self.listener.close()


@pytest.fixture
def upstream():
    server = Upstream()
    try:
        yield server
    finally:
        server.close()


def start_helper(port: int) -> subprocess.Popen:
    """The relay's own helper program started directly: only the nsenter namespace hop is missing.

    The child runs the real `HELPER_PROGRAM` against the loopback stand-in instead
    of V1's loopback, so the relay still sees a real Popen with real pipes and the
    same copy-to-EOF behaviour a forwarded request depends on.
    """
    return subprocess.Popen(
        [sys.executable, "-I", "-S", "-B", "-c", RELAY_MODULE.HELPER_PROGRAM,
         "127.0.0.1", str(port), str(RELAY_MODULE.HELPER_SOCKET_TIMEOUT)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
    )


def helper_starting_subprocess(port: int) -> SimpleNamespace:
    """A `subprocess` stand-in whose Popen is the helper child, without mutating the real module."""
    return SimpleNamespace(
        Popen=lambda argv, **kwargs: start_helper(port),
        PIPE=subprocess.PIPE,
        TimeoutExpired=subprocess.TimeoutExpired,
    )


def exchange(
    relay: ModuleType, request: bytes, port: int, engine: FakeEngine | None = None, half_close: bool = False,
) -> tuple[int, bytes]:
    """Serve one client request through the real handler; return the status and body the client read.

    The client parses the response the way `http.client` does, so a forwarded body
    is compared as a body rather than as whatever one recv happened to catch. The
    relay gets a fresh helper child per request, exactly as it does in production.
    The relay's own `subprocess` reference is replaced rather than the stdlib
    module's attribute, which every other caller shares.
    """
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.socket()
    client.settimeout(10)
    client.connect(listener.getsockname())
    server, _ = listener.accept()
    listener.close()
    relay.subprocess = helper_starting_subprocess(port)
    worker = threading.Thread(
        target=relay.handle_connection,
        args=(server, engine or FakeEngine(), CONTAINER, PROJECT, SERVICE, sys.executable),
        daemon=True,
    )
    worker.start()
    client.sendall(request)
    if half_close:
        client.shutdown(socket.SHUT_WR)
    reader = client.makefile("rb")
    status_line = reader.readline()
    header_block = b""
    while (line := reader.readline()) not in (b"\r\n", b""):
        header_block += line
    lengths = [int(line.split(b":", 1)[1]) for line in header_block.split(b"\r\n") if line.lower().startswith(b"content-length:")]
    body = reader.read(lengths[0]) if lengths else b""
    reader.close()
    worker.join(10)
    client.close()
    return (int(status_line.split(b" ", 2)[1]) if status_line.startswith(b"HTTP/") else 0), body



def request(method: str, target: str, body: bytes = BODY) -> bytes:
    return (
        f"{method} {target} HTTP/1.1\r\nHost: 172.23.0.1:11434\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
    ).encode() + body


@pytest.mark.parametrize("path", ["/api/embed", "/api/embeddings", "/v1/embeddings"])
def test_every_embedding_endpoint_is_forwarded_unchanged(relay, upstream, path):
    code, body = exchange(relay, request("POST", path), upstream.port)
    assert code == 200
    assert body == UPSTREAM_BODY
    forward = upstream.received[0]
    assert forward.split(b" ", 2)[:2] == [b"POST", path.encode()]
    assert forward.split(b"\r\n\r\n", 1)[1] == BODY
    assert b"Content-Length: " + str(len(BODY)).encode() + b"\r\n" in forward
    assert b"Connection: close\r\n" in forward


@pytest.mark.parametrize("target", ["/v1/embeddings?x=1", "/v1/embeddings?source=http://example.invalid/input"])
def test_the_query_string_is_preserved_on_the_forwarded_target(relay, upstream, target):
    code, _ = exchange(relay, request("POST", target), upstream.port)
    assert code == 200
    assert upstream.received[0].split(b" ")[1] == target.encode()


def test_an_absolute_form_target_is_forwarded_as_its_path(relay, upstream):
    code, _ = exchange(relay, request("POST", "http://169.254.1.1:11434/api/embed"), upstream.port)
    assert code == 200
    assert upstream.received[0].split(b" ")[1] == b"/api/embed"


@pytest.mark.parametrize("target", ["/api/tags", "/api/pull", "/api/delete", "/api/ps", "/api/embed/", "/api/embed/x", "/"])
def test_model_management_and_lookalike_paths_never_reach_upstream(relay, upstream, target):
    code, _ = exchange(relay, request("POST", target), upstream.port)
    assert code == 403
    assert upstream.received == []


@pytest.mark.parametrize("method", ["GET", "HEAD", "DELETE", "PUT", "PATCH", "OPTIONS"])
def test_only_post_is_accepted_on_the_boundary(relay, upstream, method):
    code, _ = exchange(relay, request(method, "/api/embed", b""), upstream.port)
    assert code == 405
    assert upstream.received == []


def test_a_refusal_is_locally_generated_and_closes_the_connection(relay, upstream):
    code, body = exchange(relay, request("POST", "/api/tags"), upstream.port)
    assert code == 403
    assert b"not one of the three embedding endpoints" in body
    assert upstream.received == []


@pytest.mark.parametrize(
    ("request_bytes", "wanted"),
    [
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n", 411),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nContent-Length: 4\r\n\r\n", 411),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nContent-Length: 4\r\nContent-Length: 5\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nContent-Length: 4x\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nContent-Length: -1\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nContent-Length: \xb2\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nContent-Length: " + b"9" * 5000 + b"\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\nExpect: 100-continue\r\n\r\n", 417),
        (b"POST /api/embed#fragment HTTP/1.1\r\nHost: x\r\n\r\n", 400),
        (b"POST /api/embed?x\n HTTP/1.1\r\nHost: x\r\n\r\n", 400),
        (b"POST /api/embed HTTP/2.0\r\nHost: x\r\n\r\n", 400),
        (b"POST/api/embed HTTP/1.1\r\nHost: x\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\n continuation\r\n\r\n", 400),
        (b"POST /api/embed HTTP/1.1\r\nHost: x\r\n: v\r\n\r\n", 400),
        (b"CONNECT 172.23.0.1:11434 HTTP/1.1\r\nHost: x\r\n\r\n", 405),
    ],
)
def test_malformed_and_ambiguous_framing_is_refused_locally(relay, upstream, request_bytes, wanted):
    code, _ = exchange(relay, request_bytes, upstream.port)
    assert code == wanted
    assert upstream.received == []


def test_an_oversized_request_head_is_refused(relay, upstream):
    oversized = b"POST /api/embed HTTP/1.1\r\nHost: x\r\nX: " + b"a" * (relay.HEAD_LIMIT + 100) + b"\r\n\r\n"
    code, _ = exchange(relay, oversized, upstream.port)
    assert code == 431
    assert upstream.received == []


def test_a_pipelined_second_request_is_not_forwarded(relay, upstream):
    pipelined = request("POST", "/api/embed") + b"POST /api/delete HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n"
    code, _ = exchange(relay, pipelined, upstream.port)
    assert code == 200
    assert len(upstream.received) == 1
    assert b"delete" not in upstream.received[0]


def test_a_client_that_stops_mid_head_gets_no_upstream_request(relay, upstream):
    """The head never completes, so the relay forwards nothing; the reaction to the close is its own."""
    code, body = exchange(relay, b"POST /api/embed HTTP/1.1\r\n", upstream.port, half_close=True)
    assert code in (0, 400)
    assert body in (b"", REFUSAL_MID_HEAD)
    assert upstream.received == []


def test_a_failing_target_resolution_refuses_only_that_connection(relay, upstream):
    empty, _ = exchange(relay, request("POST", "/api/embed"), upstream.port, FakeEngine(reply="\n"))
    assert empty == 503
    assert upstream.received == []
    stopped, _ = exchange(relay, request("POST", "/api/embed"), upstream.port, FakeEngine(reply="1|false|maxwell-curie|ollama\n"))
    assert stopped == 503
    assert upstream.received == []


@pytest.mark.parametrize("error", [RuntimeError("engine unavailable"), subprocess.TimeoutExpired("inspect", 30)])
def test_an_engine_query_error_returns_503_without_stopping_later_requests(relay, upstream, error):
    class FailingEngine(FakeEngine):
        def query(self, *args):
            raise error

    code, _ = exchange(relay, request("POST", "/api/embed"), upstream.port, FailingEngine())
    assert code == 503
    assert upstream.received == []
    code, _ = exchange(relay, request("POST", "/api/embed"), upstream.port)
    assert code == 200


def test_bound_engine_detects_a_replaced_pid_file(relay, tmp_path):
    pid = os.getpid()
    pid_file = tmp_path / "docker.pid"
    pid_file.write_text(str(pid))
    bound = relay.BoundEngine(os.getuid(), pid, relay.process_start_time(pid), f"/proc/{pid}/ns/net")
    assert bound.retired(pid_file) == ""
    pid_file.write_text(str(pid + 1))
    assert "different daemon" in bound.retired(pid_file)


def test_namespace_checks_are_not_starved_by_continuous_connections(relay, monkeypatch):
    checks = []
    accepted = []

    def retired(_):
        checks.append(True)
        return "daemon replaced" if len(checks) > 1 else ""

    def accept():
        accepted.append(True)
        return object(), None

    worker = SimpleNamespace(start=lambda: None, is_alive=lambda: True)
    monkeypatch.setattr(relay, "STOPPING", threading.Event())
    monkeypatch.setattr(relay, "threading", SimpleNamespace(Thread=lambda **kwargs: worker))
    listener = SimpleNamespace(settimeout=lambda timeout: None, accept=accept)
    with pytest.raises(SystemExit) as stopped:
        relay.serve(listener, FakeEngine(), CONTAINER, PROJECT, SERVICE, sys.executable,
                    SimpleNamespace(retired=retired), None)
    assert stopped.value.code == 75
    assert len(checks) == 2
    assert len(accepted) == 1


def test_a_disconnected_capacity_refusal_does_not_kill_the_accept_loop(relay, monkeypatch):
    stopping = threading.Event()

    class DepartedClient:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def sendall(self, payload):
            stopping.set()
            raise ConnectionResetError("peer left")

    connection = DepartedClient()
    monkeypatch.setattr(relay, "STOPPING", stopping)
    monkeypatch.setattr(relay, "MAX_HELPERS", 0)
    listener = SimpleNamespace(settimeout=lambda timeout: None, accept=lambda: (connection, None))
    relay.serve(listener, FakeEngine(), CONTAINER, PROJECT, SERVICE, sys.executable,
                SimpleNamespace(retired=lambda path: ""), None)
    assert connection.closed


def test_the_helper_argv_is_the_one_fixed_namespace_hop(relay):
    assert relay.helper_argv(3689769, "/usr/bin/python3") == [
        "/usr/bin/nsenter", "--net=/proc/3689769/ns/net", "--",
        "/usr/bin/python3", "-I", "-S", "-B", "-c", relay.HELPER_PROGRAM,
        "127.0.0.1", "11434", str(relay.HELPER_SOCKET_TIMEOUT),
    ]


def test_the_allowlist_is_exactly_the_three_embedding_paths(relay):
    assert relay.EMBED_PATHS == ("/api/embed", "/api/embeddings", "/v1/embeddings")


@pytest.mark.parametrize(
    "injected",
    [
        b"POST /api/embed HTTP/1.1\r\nHost: x\r\nX-Bad: v\n\nPOST /api/delete HTTP/1.1\r\nHost: x\r\n\r\n",
        b"POST /api/embed HTTP/1.1\r\nHost: x\r\nX-Bad: v\rPOST /api/delete HTTP/1.1\r\n\r\n",
        b"POST /api/embed HTTP/1.1\r\nX-Bad: v\x00\r\nHost: x\r\n\r\n",
        b"POST /api/embed HTTP/1.1\r\nX-Bad: v\x7f\r\nHost: x\r\n\r\n",
        b"POST /api/embed HTTP/1.1\r\nHost: x\r\nBad Name: v\r\n\r\n",
        b"POST /api/embed HTTP/1.1\r\nHost: x\r\nBad\tName: v\r\n\r\n",
    ],
)
def test_a_bare_lf_or_control_character_in_a_header_never_reaches_the_helper(relay, upstream, injected):
    code, _ = exchange(relay, injected, upstream.port)
    assert code == 400
    assert upstream.received == []


def test_a_tab_inside_a_header_value_is_still_accepted(relay, upstream):
    head = b"POST /api/embed HTTP/1.1\r\nHost: x\r\nX-Note:\tv\r\nContent-Length: " + str(len(BODY)).encode() + b"\r\n\r\n"
    code, body = exchange(relay, head + BODY, upstream.port)
    assert code == 200
    assert body == UPSTREAM_BODY
    assert b"X-Note: v\r\n" in upstream.received[0]


def test_pipelined_bytes_are_not_forwarded_as_part_of_the_body(relay, upstream):
    """The declared length is what the helper receives, so a pipelined request cannot ride along."""
    extra = b"POST /api/delete HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n"
    code, _ = exchange(relay, request("POST", "/api/embed") + extra, upstream.port)
    assert code == 200
    assert len(upstream.received) == 1
    assert upstream.received[0].split(b"\r\n\r\n", 1)[1] == BODY
    assert b"delete" not in upstream.received[0]
