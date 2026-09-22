"""Isolated unit checks for the Dirac relay helper.

No namespace is entered, no engine is contacted and no V1 resource is read.
"""

import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def relay() -> ModuleType:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("dirac_relay", ROOT / "scripts" / "dirac_relay.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class FakeEngine:
    """Scripted engine: records queries and replays canned Docker output."""

    def __init__(self, replies: dict[str, str]) -> None:
        self.account = "maxwell-curie"
        self.home = "/home/maxwell-curie"
        self.uid = os.getuid()
        self.socket = "unix:///run/user/1003/docker.sock"
        self.replies = replies
        self.calls: list[tuple[str, ...]] = []

    def query(self, *args: str) -> str:
        self.calls.append(args)
        for key, reply in self.replies.items():
            if args and args[0] == key:
                return reply
        raise AssertionError(f"unexpected engine query: {args}")


def info_json(**overrides: object) -> str:
    payload = {
        "ID": "91b4c99d-2d68-41d7-a583-57c2dcb0b6cf",
        "DockerRootDir": "/home/maxwell-curie/.local/share/docker",
        "SecurityOptions": ["name=rootless", "name=seccomp,profile=builtin"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_engine_query_runs_as_the_mapped_account_with_a_scrubbed_environment(relay, monkeypatch):
    captured: dict[str, object] = {}

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    monkeypatch.setattr(relay.subprocess, "run", run)
    engine = relay.Engine("maxwell-curie", "/home/maxwell-curie", 1003, "unix:///run/user/1003/docker.sock")
    assert engine.query("ps", "-a") == "ok\n"
    assert captured["argv"] == [
        "/usr/sbin/runuser", "-u", "maxwell-curie", "--", "/usr/bin/env", "-i",
        "HOME=/home/maxwell-curie", "PATH=/usr/local/bin:/usr/bin:/bin", "DOCKER_CONFIG=/nonexistent",
        "/usr/bin/docker", "--host", "unix:///run/user/1003/docker.sock", "ps", "-a",
    ]

    def failing(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(argv, 1, "", "permission denied")

    monkeypatch.setattr(relay.subprocess, "run", failing)
    with pytest.raises(RuntimeError, match="maxwell-curie engine"):
        engine.query("ps")


def test_checked_socket_requires_a_real_owned_socket(relay, tmp_path):
    endpoint = tmp_path / "docker.sock"
    listener = socket.socket(socket.AF_UNIX)
    try:
        listener.bind(str(endpoint))
        assert relay.checked_socket(endpoint, os.getuid()) == endpoint
        with pytest.raises(ValueError, match="not owned"):
            relay.checked_socket(endpoint, os.getuid() + 1)
    finally:
        listener.close()
    regular = tmp_path / "docker.pid"
    regular.write_text("1\n")
    with pytest.raises(ValueError, match="not a socket"):
        relay.checked_socket(regular, os.getuid())
    link = tmp_path / "link.sock"
    link.symlink_to(endpoint)
    with pytest.raises(ValueError, match="symlink"):
        relay.checked_socket(link, os.getuid())
    with pytest.raises(ValueError, match="missing"):
        relay.checked_socket(tmp_path / "absent.sock", os.getuid())


def test_open_engine_uses_the_resolved_account_and_refuses_root(relay, monkeypatch):
    class Account:
        pw_uid = 1003
        pw_dir = "/home/maxwell-curie"

    monkeypatch.setattr(relay.pwd, "getpwnam", lambda name: Account())
    monkeypatch.setattr(relay, "checked_socket", lambda path, uid: path)
    engine = relay.open_engine("maxwell-curie")
    assert (engine.account, engine.uid, engine.socket) == (
        "maxwell-curie", 1003, "unix:///run/user/1003/docker.sock",
    )
    Account.pw_uid = 0
    with pytest.raises(ValueError, match="cannot be root"):
        relay.open_engine("root")


def test_validate_engine_requires_rootless_private_root_and_pinned_identity(relay):
    relay.validate_engine(FakeEngine({"info": info_json()}), None)
    relay.validate_engine(FakeEngine({"info": info_json()}), "91b4c99d-2d68-41d7-a583-57c2dcb0b6cf")
    with pytest.raises(ValueError, match="not rootless"):
        relay.validate_engine(FakeEngine({"info": info_json(SecurityOptions=[])}), None)
    with pytest.raises(ValueError, match="private Docker root"):
        relay.validate_engine(FakeEngine({"info": info_json(DockerRootDir="/var/lib/docker")}), None)
    with pytest.raises(ValueError, match="pinned engine ID"):
        relay.validate_engine(FakeEngine({"info": info_json()}), "someone-elses-engine")


def test_forward_argv_is_fixed(relay):
    assert relay.forward_argv(3689769) == [
        "/usr/bin/nsenter", "--net=/proc/3689769/ns/net", "--",
        "/usr/bin/socat", "-", "TCP4:127.0.0.1:11434",
    ]


def test_target_pid_requires_a_running_v1_ollama_owned_by_v1(relay):
    container, project, service = "maxwell-curie-ollama-1", "maxwell-curie", "ollama"

    def resolve(reply: str, uid: int | None = None) -> int | None:
        engine = FakeEngine({"inspect": reply})
        if uid is not None:
            engine.uid = uid
        return relay.target_pid(engine, container, project, service)

    assert resolve(f"{os.getpid()}|true|maxwell-curie|ollama\n") == os.getpid()
    assert resolve(f"{os.getpid()}|true|maxwell-curie|ollama\n", os.getuid() + 1) is None
    assert resolve(f"{os.getpid()}|false|maxwell-curie|ollama\n") is None
    assert resolve(f"{os.getpid()}|true|other|ollama\n") is None
    assert resolve(f"{os.getpid()}|true|maxwell-curie|web\n") is None
    assert resolve("not-a-pid|true|maxwell-curie|ollama\n") is None
    assert resolve("0|true|maxwell-curie|ollama\n") is None


def test_bridge_gateway_requires_this_project_and_a_private_address(relay):
    def gateway(reply: str) -> str:
        return relay.bridge_gateway(FakeEngine({"network": reply}), "dame-curie_outbound", "dame-curie")

    assert gateway("dame-curie|outbound|172.23.0.1\n") == "172.23.0.1"
    with pytest.raises(ValueError, match="outbound bridge"):
        gateway("other|outbound|172.23.0.1\n")
    with pytest.raises(ValueError, match="outbound bridge"):
        gateway("dame-curie|internal|172.23.0.1\n")
    with pytest.raises(ValueError, match="non-private"):
        gateway("dame-curie|outbound|8.8.8.8\n")


def test_engine_netns_requires_a_parent_verified_pid(relay, tmp_path):
    expected_uid = os.getuid() + 1
    with pytest.raises(ValueError, match="explicit /proc"):
        relay.engine_netns(None, "/proc/self/ns/net", expected_uid)
    with pytest.raises(ValueError, match="explicit /proc"):
        relay.engine_netns(None, "/run/user/1005/docker.pid", expected_uid)
    pid_file = tmp_path / "docker.pid"
    pid_file.write_text("dockerd\n")
    with pytest.raises(ValueError, match="engine PID"):
        relay.engine_netns(pid_file, None, expected_uid)
    pid_file.write_text("1\n")
    with pytest.raises(ValueError, match="not owned"):
        relay.engine_netns(pid_file, None, expected_uid)
    with pytest.raises(ValueError, match="not owned"):
        relay.engine_netns(None, "/proc/1/ns/net", expected_uid)
