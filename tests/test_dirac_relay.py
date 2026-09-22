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


def test_target_pid_requires_running_v1_ollama(relay, monkeypatch):
    def query() -> int | None:
        return relay.target_pid("unix:///run/user/1003/docker.sock", "maxwell-curie-ollama-1",
                                "maxwell-curie", "ollama")

    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "3689769|true|maxwell-curie|ollama\n"))
    assert query() == 3689769
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "3689769|false|maxwell-curie|ollama\n"))
    assert query() is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "3689769|true|other|ollama\n"))
    assert query() is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "3689769|true|maxwell-curie|web\n"))
    assert query() is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(0, "not-a-pid|true|maxwell-curie|ollama\n"))
    assert query() is None
    monkeypatch.setattr(relay.subprocess, "run", fake_run(1, ""))
    assert query() is None


def test_bridge_gateway_requires_a_private_address(relay, monkeypatch):
    monkeypatch.setattr(relay, "docker_query", lambda *args, **kwargs: "172.23.0.1\n")
    assert relay.bridge_gateway("unix:///run/user/1005/docker.sock", "dame-curie_outbound") == "172.23.0.1"
    monkeypatch.setattr(relay, "docker_query", lambda *args, **kwargs: "8.8.8.8\n")
    with pytest.raises(ValueError, match="non-private"):
        relay.bridge_gateway("unix:///run/user/1005/docker.sock", "dame-curie_outbound")


def test_engine_netns_refuses_the_callers_namespace(relay):
    with pytest.raises(ValueError, match="caller's own"):
        relay.engine_netns(None, "/proc/self/ns/net", os.getuid())


def test_engine_pid_file_requires_a_pid(relay, tmp_path):
    pid_file = tmp_path / "docker.pid"
    pid_file.write_text("dockerd\n")
    with pytest.raises(ValueError, match="engine PID"):
        relay.engine_netns(pid_file, None, os.getuid())


def test_engine_socket_uses_the_resolved_uid(relay, monkeypatch):
    class Account:
        pw_uid = 1003

    monkeypatch.setattr(relay.pwd, "getpwnam", lambda name: Account())
    assert relay.engine_socket("maxwell-curie") == (1003, "unix:///run/user/1003/docker.sock")
    Account.pw_uid = 0
    with pytest.raises(ValueError, match="cannot be root"):
        relay.engine_socket("root")
