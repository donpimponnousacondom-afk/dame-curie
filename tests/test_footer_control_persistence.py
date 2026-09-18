import asyncio
import json
from pathlib import Path
import threading
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

import bot as bot_module
from bot import MaxwellBot
import response_observability as observability
from response_observability import update_footer_control
from utils import FileLock, FileLockTimeout, _atomic_json_write_sync


class Channel:
    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append(content)


def control_bot(tmp_path):
    bot = SimpleNamespace(
        _control={
            "bot_enabled": True,
            "footer_enabled": True,
            "footer_format": "old",
            "base_personality": "derived external persona, never persist",
        },
        config=SimpleNamespace(DATA_DIR=str(tmp_path), MAXWELL_PROMPTS_DIR="external"),
        command_prefix="!",
        bot_name="Maxwell",
        _is_admin=lambda uid: True,
        _ai_concurrency=2,
        _apply_x_control=Mock(),
        _sync_audio_input_flags=Mock(),
        _conversation_watch_enabled=lambda: True,
    )
    bot._load_control = MethodType(MaxwellBot._load_control, bot)
    return bot


def test_footer_updates_retain_api_patch_and_refresh_after_delayed_completion(
    tmp_path, monkeypatch
):
    path = tmp_path / "bot_control.json"
    _atomic_json_write_sync(
        path,
        {
            "bot_enabled": True,
            "footer_enabled": True,
            "footer_format": "old",
            "unrelated": "keep",
        },
    )
    format_written = threading.Event()
    release_format = threading.Event()
    locks = []
    updates = []

    def tracked_lock(control_path):
        lock = FileLock(control_path)
        locks.append(lock.lock_path)
        return lock

    def delayed_update(control_path, key, value):
        updates.append((key, value))
        update_footer_control(control_path, key, value)
        if key == "footer_format":
            format_written.set()
            assert release_format.wait(timeout=5)

    monkeypatch.setattr(observability, "FileLock", tracked_lock)
    monkeypatch.setattr(bot_module, "update_footer_control", delayed_update)

    async def scenario():
        bot = control_bot(tmp_path)
        message = SimpleNamespace(author=SimpleNamespace(id=7), channel=Channel())
        format_task = asyncio.create_task(
            MaxwellBot._handle_footer_command(bot, message, "format {{MODEL}}")
        )
        assert await asyncio.to_thread(format_written.wait, 5)
        with FileLock(path) as api_lock:
            current = json.loads(path.read_text(encoding="utf-8"))
            current["bot_enabled"] = False
            _atomic_json_write_sync(path, current)
            assert api_lock.lock_path == Path(str(path) + ".lock")
        await MaxwellBot._handle_footer_command(bot, message, "off")
        assert bot._control["bot_enabled"] is False
        assert bot._control["footer_enabled"] is False
        release_format.set()
        await format_task
        assert bot._control["bot_enabled"] is False
        assert bot._control["footer_enabled"] is False
        assert bot._control["footer_format"] == "{{MODEL}}"
        assert "base_personality" not in bot._control

    asyncio.run(scenario())
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "bot_enabled": False,
        "footer_enabled": False,
        "footer_format": "{{MODEL}}",
        "unrelated": "keep",
    }
    assert updates == [("footer_format", "{{MODEL}}"), ("footer_enabled", False)]
    assert locks == [Path(str(path) + ".lock")] * 2


def test_missing_control_file_starts_with_only_requested_footer_key(tmp_path):
    path = tmp_path / "new" / "bot_control.json"
    update_footer_control(path, "footer_format", "{{MODEL}}")
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "footer_format": "{{MODEL}}"
    }
    assert Path(str(path) + ".lock").exists()
    update_footer_control(path, "footer_enabled", False)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "footer_format": "{{MODEL}}",
        "footer_enabled": False,
    }


@pytest.mark.parametrize(
    "original", ["broken json", "", "[]", "null", "false", '"text"']
)
def test_malformed_or_nonobject_control_is_never_overwritten(tmp_path, original):
    path = tmp_path / "bot_control.json"
    path.write_text(original, encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        update_footer_control(path, "footer_enabled", False)
    assert path.read_text(encoding="utf-8") == original


def test_footer_update_cannot_bypass_api_sidecar_lock(tmp_path, monkeypatch):
    path = tmp_path / "bot_control.json"
    original = '{"bot_enabled":false}'
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        observability, "FileLock", lambda path: FileLock(path, timeout=0)
    )
    with FileLock(path):
        with pytest.raises(FileLockTimeout):
            update_footer_control(path, "footer_enabled", True)
        assert path.read_text(encoding="utf-8") == original
