import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bot import MaxwellBot
import response_observability as observability


SNAPSHOT = {
    "commit": "a" * 40,
    "branch": "work/current-branch",
    "date": "2026-09-11T06:00:00+02:00",
    "subject": "snapshot, including docs-only changes",
    "dirty": False,
}


@contextmanager
def snapshot_server(replies):
    with tempfile.TemporaryDirectory(prefix="s", dir=Path(__file__).resolve().parents[1]) as directory:
        path = str(Path(directory) / "snapshot.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen()
            listener.settimeout(3)
            connections = []

            def respond():
                for reply in replies:
                    connection, _ = listener.accept()
                    with connection:
                        connections.append(True)
                        connection.sendall(reply)

            thread = threading.Thread(target=respond, daemon=True)
            thread.start()
            yield path, connections
            thread.join(3)
            assert not thread.is_alive()


def test_real_socket_snapshot_is_frozen_until_next_boot(monkeypatch, tmp_path):
    changed = {**SNAPSHOT, "commit": "b" * 40, "branch": "another-branch", "dirty": True}
    with snapshot_server([json.dumps(SNAPSHOT).encode(), json.dumps(changed).encode()]) as (path, connections):
        monkeypatch.setenv("MAXWELL_STARTUP_GIT_SOCKET", path)
        monkeypatch.setenv("MAXWELL_BUILD_COMMIT", "c" * 40)
        first = observability.capture_running_build(tmp_path)
        report = first.format()
        assert first.commit == SNAPSHOT["commit"]
        assert first.branch == SNAPSHOT["branch"] and first.dirty is False
        assert first.date == "2026-09-11T04:00:00+00:00"
        assert "c" * 40 not in report
        assert first.format() == report and len(connections) == 1
        second = observability.capture_running_build(tmp_path)
        assert second.commit == changed["commit"]
        assert second.branch == changed["branch"] and second.dirty is True
        assert first.format() == report and len(connections) == 2


def test_actual_version_dispatch_only_uses_frozen_boot_snapshot(monkeypatch, tmp_path):
    with snapshot_server([json.dumps(SNAPSHOT).encode()]) as (path, connections):
        monkeypatch.setenv("MAXWELL_STARTUP_GIT_SOCKET", path)
        frozen = observability.capture_running_build(tmp_path)
    sent = []

    async def send(content, **kwargs):
        sent.append(content)

    bot = SimpleNamespace(command_prefix="!", _control={"footer_enabled": False},
                          _is_admin=lambda uid: True, _running_build=frozen)
    message = SimpleNamespace(content="!version", author=SimpleNamespace(id=7),
                              channel=SimpleNamespace(id=8, send=send), guild=None)
    monkeypatch.setattr(observability, "read_startup_git_snapshot", Mock(side_effect=AssertionError("queried after boot")))
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert len(connections) == 1
    assert sent[0].startswith("```\nCheckout at boot:")
    assert sent[0].endswith("\n```")
    assert SNAPSHOT["commit"] in sent[0] and SNAPSHOT["branch"] in sent[0]


@pytest.mark.parametrize("change", [
    {"commit": "unknown"}, {"commit": 123}, {"branch": ""}, {"branch": None},
    {"dirty": "false"}, {"dirty": 0}, {"dirty": None}, {"date": "invalid"},
    {"date": "2026-09-11T04:00:00"},
    {"subject": {}}, {"extra": "unexpected"},
])
def test_invalid_socket_snapshot_never_becomes_provenance(change):
    with snapshot_server([json.dumps({**SNAPSHOT, **change}).encode()]) as (path, _):
        with pytest.raises(ValueError):
            observability.read_startup_git_snapshot(path)


@pytest.mark.parametrize("reply", [b"", b"broken json", b"[]", b"null", b"{}", b"x" * 65537])
def test_missing_malformed_or_oversized_response_is_rejected(reply):
    with snapshot_server([reply]) as (path, _):
        with pytest.raises(ValueError):
            observability.read_startup_git_snapshot(path)


def test_configured_socket_failure_never_falls_back_to_image_or_other_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv("MAXWELL_STARTUP_GIT_SOCKET", str(Path(__file__).resolve().parents[1] / "no-git.sock"))
    monkeypatch.setenv("MAXWELL_BUILD_COMMIT", "c" * 40)
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(observability.subprocess, "run", Mock(side_effect=AssertionError("fell back to another checkout")))
    with pytest.raises(FileNotFoundError):
        observability.capture_running_build(tmp_path)


def test_socket_read_uses_total_deadline(monkeypatch):
    connection = Mock()
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=connection)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(observability.socket, "socket", factory)
    monkeypatch.setattr(observability, "time", SimpleNamespace(monotonic=Mock(side_effect=[0, 11])))
    with pytest.raises(TimeoutError, match="startup Git snapshot timed out"):
        observability.read_startup_git_snapshot("/synthetic/snapshot.sock")
    connection.recv.assert_not_called()


def test_fragmented_snapshot_is_assembled_before_parsing(monkeypatch):
    payload = json.dumps(SNAPSHOT).encode()
    connection = Mock()
    connection.recv.side_effect = [payload[:9], payload[9:40], payload[40:], b""]
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=connection)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(observability.socket, "socket", factory)
    assert observability.read_startup_git_snapshot("/synthetic/snapshot.sock")["commit"] == SNAPSHOT["commit"]
