import asyncio
import json
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

import bot as bot_module
import control_defaults
from bot import MaxwellBot
from control_defaults import DEFAULT_CONTROL, update_deepseek_reasoning
from providers import OllamaProvider
from utils import FileLock, FileLockTimeout, _atomic_json_write_sync


class Channel:
    id = 23

    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        assert len(content) <= 2000
        self.sent.append(content)


def reasoning_bot(tmp_path, *, admin=True, direct=False):
    bot = SimpleNamespace(
        _control=dict(DEFAULT_CONTROL), _control_mtime=-1,
        config=SimpleNamespace(DATA_DIR=str(tmp_path), MAXWELL_PROMPTS_DIR="external"),
        command_prefix="!", _is_admin=lambda uid: admin, _ai_concurrency=2,
        _apply_x_control=Mock(), _sync_audio_input_flags=Mock(),
        _conversation_watch_enabled=lambda: True,
    )
    bot._load_control = MethodType(MaxwellBot._load_control, bot)
    bot._handle_reasoning_command = MethodType(MaxwellBot._handle_reasoning_command, bot)
    bot.ai_provider = OllamaProvider(
        "https://api.deepseek.com/v1" if direct else "https://openrouter.ai/api/v1",
        "deepseek-flash" if direct else "deepseek/deepseek-v4.1-flash", 8192, 0.6,
        extra_body={"provider": {"only": ["deepseek"]}},
        reasoning_control=lambda: bot._control.get("deepseek_reasoning", ""),
    )
    return bot


def command(bot, content):
    message = SimpleNamespace(content=content, channel=Channel(), author=SimpleNamespace(id=7), guild=None)
    asyncio.run(MaxwellBot._handle_command(bot, message))
    return "\n".join(message.channel.sent)


@pytest.mark.parametrize("name", ["reasoning", "effort"])
@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("direct", [False, True])
def test_reports_show_explicit_effective_defaults_without_writing(tmp_path, name, admin, direct):
    bot = reasoning_bot(tmp_path, admin=admin, direct=direct)
    text = command(bot, f"!{name}")
    assert text.startswith("```\nDeepSeek V4.1 Flash")
    assert text.endswith("\n```") and text.count("```") == 2
    assert "effective reasoning: high" in text
    assert "75/100 reference preset" in text
    assert "reasoning_effort=high" in text if direct else "reasoning.effort=high" in text
    assert not (tmp_path / "bot_control.json").exists()
    if name == "effort":
        assert ("Direct API presets" if direct else "every integer 1..100 is sent unchanged") in text


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("setting,expected", [
    ("reasoning low", "low"), ("reasoning high", "high"), ("reasoning max", "max"),
    ("reasoning off", "off"), ("effort 50", "low"), ("effort 75", "high"), ("effort 100", "max"),
])
def test_admin_changes_persist_only_requested_key_and_apply_immediately(tmp_path, direct, setting, expected):
    path = tmp_path / "bot_control.json"
    _atomic_json_write_sync(path, {"footer_enabled": False, "unrelated": "keep"})
    bot = reasoning_bot(tmp_path, direct=direct)
    if not direct and setting.startswith("effort "):
        expected = int(setting.split()[1])
    text = command(bot, "!" + setting)
    assert text.startswith("```\n") and text.endswith("\n```")
    assert text.count("```") == 2
    assert f"effective reasoning: {expected}" in text
    assert json.loads(path.read_text()) == {"footer_enabled": False, "unrelated": "keep", "deepseek_reasoning": expected}
    assert bot._control["footer_enabled"] is False
    assert "base_personality" not in bot._control
    restarted = reasoning_bot(tmp_path, direct=direct)
    restarted._load_control(force=True)
    assert restarted.ai_provider.deepseek_reasoning_level(restarted.ai_provider._endpoints[0]) == expected
    assert Path(str(path) + ".lock").exists()


@pytest.mark.parametrize("setting", ["reasoning low", "reasoning off", "effort 50", "effort 75", "effort 100", "effort 1"])
def test_nonadmins_cannot_change_settings(tmp_path, setting):
    bot = reasoning_bot(tmp_path, admin=False)
    assert command(bot, "!" + setting) == "not authorized"
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("number", ["0", "101", "-1", "75.0", "off", "high", "1 100", "true", "５０"])
def test_unsupported_numeric_effort_is_not_rounded_or_saved(tmp_path, number):
    bot = reasoning_bot(tmp_path)
    text = command(bot, "!effort " + number)
    assert text.startswith("```\nUnsupported setting; unchanged.\n")
    assert text.endswith("\n```") and text.count("```") == 2
    assert "effective reasoning: high" in text
    assert "every integer 1..100 is sent unchanged" in text
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("number", range(1, 101))
def test_every_openrouter_integer_persists_reloads_and_is_sent_exactly(tmp_path, number):
    path = tmp_path / "bot_control.json"
    path.write_text('{"unrelated":"keep","footer_enabled":false}')
    bot = reasoning_bot(tmp_path)
    text = command(bot, f"!effort {number}")
    assert text.startswith("```\n") and text.endswith("\n```")
    assert f"Effort: {number}/100 (sent unchanged as an integer)" in text
    assert f"reasoning.effort={number}" in text
    assert json.loads(path.read_text()) == {
        "unrelated": "keep", "footer_enabled": False, "deepseek_reasoning": number,
    }
    restarted = reasoning_bot(tmp_path)
    restarted._load_control(force=True)
    payload = restarted.ai_provider._request_payload(restarted.ai_provider._endpoints[0], [])
    wire = json.loads(json.dumps(payload))
    assert type(wire["reasoning"]["effort"]) is int
    assert wire["reasoning"] == {"enabled": True, "effort": number}
    assert wire["provider"] == {"only": ["deepseek"]}
    assert "sent unchanged as an integer" in command(restarted, "!reasoning")


@pytest.mark.parametrize("number", [1, 49, 51, 74, 76, 99])
def test_direct_api_numeric_command_behavior_is_unchanged(tmp_path, number):
    text = command(reasoning_bot(tmp_path, direct=True), f"!effort {number}")
    assert "Unsupported setting; unchanged" in text
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("value", [0, 101, -1, True, False, 75.0, "37", None, {}])
def test_invalid_persisted_effort_values_never_write(tmp_path, value):
    path = tmp_path / "bot_control.json"
    path.write_text('{"unrelated":"keep"}')
    with pytest.raises(ValueError, match="DeepSeek reasoning"):
        update_deepseek_reasoning(path, value)
    assert path.read_text() == '{"unrelated":"keep"}'


@pytest.mark.parametrize("level", ["on", "medium", "minimal", "xhigh", "ultra", "50", "low extra"])
def test_unknown_tier_does_not_mutate_settings(tmp_path, level):
    bot = reasoning_bot(tmp_path)
    text = command(bot, "!reasoning " + level)
    assert text.startswith("```\nUnsupported setting; unchanged.\n")
    assert text.endswith("\n```") and text.count("```") == 2
    assert "!reasoning [low|high|max|off]" in text
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("name", ["reasoning", "effort"])
def test_disabled_commands_remain_disabled(tmp_path, name):
    bot = reasoning_bot(tmp_path)
    bot._control["disabled_commands"] = [name]
    assert command(bot, f"!{name} 50") == ""
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("setting", ["reasoning", "reasoning off", "effort", "effort 50"])
def test_other_models_are_explicitly_unsupported(tmp_path, setting):
    bot = reasoning_bot(tmp_path)
    bot.ai_provider.model = "google/gemini-3.7-flash"
    text = command(bot, "!" + setting)
    assert "verified only for DeepSeek V4.1 Flash" in text
    assert "Current model unchanged" in text
    assert not (tmp_path / "bot_control.json").exists()


def test_off_report_is_not_claimed_to_be_numeric_minimum(tmp_path):
    bot = reasoning_bot(tmp_path)
    text = command(bot, "!reasoning off")
    assert "effective reasoning: off" in text
    assert "Effort: inactive" in text
    assert "reasoning.enabled=false, reasoning.effort=none" in text
    assert "1/100" not in text
    assert "Per-call overrides" in text


def test_help_lists_configured_prefix_and_numeric_openrouter_control(tmp_path):
    text = command(reasoning_bot(tmp_path), "!help")
    assert "!reasoning [low|high|max|off]" in text
    assert "!effort [1..100]" in text
    assert "exact numeric effort on OpenRouter" in text


@pytest.mark.parametrize("original", ["broken json", "", "[]", "null", "false", '"text"'])
def test_invalid_persisted_document_is_not_overwritten(tmp_path, original):
    path = tmp_path / "bot_control.json"
    path.write_text(original)
    with pytest.raises((ValueError, TypeError)):
        update_deepseek_reasoning(path, "low")
    assert path.read_text() == original


def test_missing_file_persists_no_derived_defaults(tmp_path):
    path = tmp_path / "new" / "bot_control.json"
    update_deepseek_reasoning(path, "max")
    assert json.loads(path.read_text()) == {"deepseek_reasoning": "max"}


def test_persistence_uses_same_api_lock(tmp_path, monkeypatch):
    path = tmp_path / "bot_control.json"
    path.write_text('{"footer_enabled":false}')
    monkeypatch.setattr(control_defaults, "FileLock", lambda path: FileLock(path, timeout=0))
    with FileLock(path):
        with pytest.raises(FileLockTimeout):
            update_deepseek_reasoning(path, "low")
    assert json.loads(path.read_text()) == {"footer_enabled": False}


def test_dashboard_update_reload_changes_future_requests(tmp_path):
    bot = reasoning_bot(tmp_path)
    command(bot, "!reasoning low")
    first = bot.ai_provider._request_payload(bot.ai_provider._endpoints[0], [])
    update_deepseek_reasoning(tmp_path / "bot_control.json", "max")
    bot._load_control(force=True)
    assert bot.ai_provider._request_payload(bot.ai_provider._endpoints[0], [])["reasoning"]["effort"] == "max"
    assert first["reasoning"]["effort"] == "low"


def test_main_constructor_wires_live_control_callback(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(bot_module, "OllamaProvider", lambda **kwargs: captured.update(kwargs) or SimpleNamespace())
    config = dict.fromkeys((
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_API_KEY", "OLLAMA_FALLBACK_BASE_URL",
        "OLLAMA_FALLBACK_MODEL", "OLLAMA_FALLBACK_API_KEY", "OLLAMA_VISION_BASE_URL",
        "OLLAMA_VISION_MODEL", "OLLAMA_VISION_API_KEY",
    ), "")
    config.update(OLLAMA_MAX_TOKENS=8192, OLLAMA_TEMPERATURE=0.6, OLLAMA_TOP_P=0.95,
                  OLLAMA_TOP_K=20, OLLAMA_DISABLE_REASONING=False, OLLAMA_FALLBACK_DISABLE_REASONING=True,
                  OLLAMA_VISION_DISABLE_REASONING=True, OLLAMA_RETRY_ATTEMPTS=1,
                  OLLAMA_EXTRA_HEADERS={}, OLLAMA_EXTRA_BODY={}, ENABLE_AUDIO_INPUT=False)
    bot = SimpleNamespace(config=SimpleNamespace(**config), _control={"deepseek_reasoning": "low"})
    MaxwellBot._setup_ai(bot)
    assert captured["reasoning_control"]() == "low"
    bot._control = {"deepseek_reasoning": "max"}
    assert captured["reasoning_control"]() == "max"
