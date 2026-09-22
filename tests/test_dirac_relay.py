"""Isolated unit checks for the Dirac relay helper.

No namespace is entered, no engine is contacted and no V1 resource is read.
"""

import importlib.util
import os
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


def fake_run(returncode: int, stdout: str):
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args[0], returncode, stdout, "")

    return run


def test_forward_argv_is_fixed(relay):
    assert relay.forward_argv(3689769) == [
        "/usr/bin/nsenter", "--net=/proc/3689769/ns/net", "--",
        "/usr/bin/socat", "-", "TCP4:127.0.0.1:11434",
    ]


def test_target_pid_requires_a_running_v1_ollama_owned_by_v1(relay, monkeypatch):
    def query(uid: int) -> int | None:
        return relay.target_pid("unix:///run/user/1003/docker.sock", "maxwell-curie-ollama-1",
                                "maxwell-curie", "ollama", uid)

    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, f"{os.getpid()}|true|maxwell-curie|ollama\n"))
    assert query(os.getuid()) == os.getpid()
    assert query(os.getuid() + 1) is None  # not owned by the V1 service account
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, f"{os.getpid()}|false|maxwell-curie|ollama\n"))
    assert query(os.getuid()) is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, f"{os.getpid()}|true|other|ollama\n"))
    assert query(os.getuid()) is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, f"{os.getpid()}|true|maxwell-curie|web\n"))
    assert query(os.getuid()) is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "not-a-pid|true|maxwell-curie|ollama\n"))
    assert query(os.getuid()) is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(1, ""))
    assert query(os.getuid()) is None


def test_bridge_gateway_requires_this_project_and_a_private_address(relay, monkeypatch):
    monkeypatch.setattr(relay, "docker_query", lambda *args, **kwargs: "dame-curie|outbound|172.23.0.1\n")
    assert relay.bridge_gateway("unix:///run/user/1005/docker.sock", "dame-curie_outbound", "dame-curie") == "172.23.0.1"
    monkeypatch.setattr(relay, "docker_query", lambda *args, **kwargs: "other|outbound|172.23.0.1\n")
    with pytest.raises(ValueError, match="outbound bridge"):
        relay.bridge_gateway("unix:///run/user/1005/docker.sock", "dame-curie_outbound", "dame-curie")
    monkeypatch.setattr(relay, "docker_query", lambda *args, **kwargs: "dame-curie|outbound|8.8.8.8\n")
    with pytest.raises(ValueError, match="non-private"):
        relay.bridge_gateway("unix:///run/user/1005/docker.sock", "dame-curie_outbound", "dame-curie")


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


def test_engine_socket_uses_the_resolved_uid(relay, monkeypatch):
    class Account:
        pw_uid = 1003

    monkeypatch.setattr(relay.pwd, "getpwnam", lambda name: Account())
    assert relay.engine_socket("maxwell-curie") == (1003, "unix:///run/user/1003/docker.sock")
    Account.pw_uid = 0
    with pytest.raises(ValueError, match="cannot be root"):
        relay.engine_socket("root")
