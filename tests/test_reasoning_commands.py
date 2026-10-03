import asyncio
import json
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

import bot as bot_module
from bot import MaxwellBot
from control_defaults import DEFAULT_CONTROL
from providers import OpenAICompatibleProvider
from utils import FileLock


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
        config=SimpleNamespace(DATA_DIR=str(tmp_path), DAME_CURIE_PROMPTS_DIR="external"),
        command_prefix="!", _is_admin=lambda uid: admin, _ai_concurrency=2,
        _sync_audio_input_flags=Mock(),
        _conversation_watch_enabled=lambda: True,
    )
    bot._load_control = MethodType(MaxwellBot._load_control, bot)
    bot._handle_reasoning_command = MethodType(MaxwellBot._handle_reasoning_command, bot)
    bot.ai_provider = OpenAICompatibleProvider(
        "https://api.deepseek.com/v1" if direct else "https://openrouter.ai/api/v1",
        "deepseek-flash" if direct else "deepseek/deepseek-v4.1-flash", 64000, 0.6,
        extra_body={"provider": {"only": ["deepseek"]}, "reasoning": {"effort": 37}},
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
    assert "active provider configuration" in text
    assert "No setting changed" in text
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("setting", [
    "reasoning low", "reasoning high", "reasoning max", "reasoning off",
    "effort 50", "effort 75", "effort 100",
])
def test_admin_changes_persist_only_requested_key_and_apply_immediately(tmp_path, direct, setting):
    path = tmp_path / "bot_control.json"
    original = '{"footer_enabled":false,"unrelated":"keep","deepseek_reasoning":"low"}'
    path.write_text(original)
    bot = reasoning_bot(tmp_path, direct=direct)
    text = command(bot, "!" + setting)
    assert "No setting changed" in text
    assert path.read_text() == original
    assert bot.ai_provider.extra_body["reasoning"] == {"effort": 37}


@pytest.mark.parametrize("setting", ["reasoning low", "reasoning off", "effort 50", "effort 75", "effort 100", "effort 1"])
def test_nonadmins_cannot_change_settings(tmp_path, setting):
    bot = reasoning_bot(tmp_path, admin=False)
    assert command(bot, "!" + setting) == "not authorized"
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("number", ["0", "101", "-1", "75.0", "off", "high", "1 100", "true", "５０"])
def test_unsupported_numeric_effort_is_not_rounded_or_saved(tmp_path, number):
    bot = reasoning_bot(tmp_path)
    assert "No setting changed" in command(bot, "!effort " + number)
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("number", range(1, 101))
def test_every_openrouter_integer_persists_reloads_and_is_sent_exactly(tmp_path, number):
    path = tmp_path / "bot_control.json"
    original = '{"unrelated":"keep","footer_enabled":false}'
    path.write_text(original)
    bot = reasoning_bot(tmp_path)
    bot.ai_provider.extra_body["reasoning"] = {"effort": number}
    assert "No setting changed" in command(bot, f"!effort {101 - number}")
    assert path.read_text() == original
    payload = bot.ai_provider._request_payload(bot.ai_provider._endpoints[0], [])
    wire = json.loads(json.dumps(payload))
    assert type(wire["reasoning"]["effort"]) is int
    assert wire["reasoning"] == {"effort": number}
    assert wire["provider"] == {"only": ["deepseek"]}
    assert wire["max_tokens"] == 64000


@pytest.mark.parametrize("number", [1, 49, 51, 74, 76, 99])
def test_direct_api_numeric_command_behavior_is_unchanged(tmp_path, number):
    text = command(reasoning_bot(tmp_path, direct=True), f"!effort {number}")
    assert "No setting changed" in text
    assert not (tmp_path / "bot_control.json").exists()


@pytest.mark.parametrize("value", [0, 101, -1, True, False, 75.0, "37", None, {}])
def test_invalid_persisted_effort_values_never_write(tmp_path, value):
    path = tmp_path / "bot_control.json"
    original = json.dumps({"unrelated": "keep", "deepseek_reasoning": value})
    path.write_text(original)
    bot = reasoning_bot(tmp_path)
    bot._control["deepseek_reasoning"] = value
    assert "No setting changed" in command(bot, "!reasoning low")
    assert path.read_text() == original
    assert bot.ai_provider.extra_body["reasoning"] == {"effort": 37}


@pytest.mark.parametrize("level", ["on", "medium", "minimal", "xhigh", "ultra", "50", "low extra"])
def test_unknown_tier_does_not_mutate_settings(tmp_path, level):
    bot = reasoning_bot(tmp_path)
    assert "No setting changed" in command(bot, "!reasoning " + level)
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
    assert "active provider configuration" in text
    assert "effective reasoning:" not in text
    assert "Wire:" not in text
    path = tmp_path / "bot_control.json"
    assert not path.exists()
    existing = '{"deepseek_reasoning":"low","unrelated":"keep"}'
    path.write_text(existing, encoding="utf-8")
    bot._control["deepseek_reasoning"] = "low"
    assert command(bot, "!" + setting) == text
    assert path.read_text(encoding="utf-8") == existing


def test_off_report_is_not_claimed_to_be_numeric_minimum(tmp_path):
    text = command(reasoning_bot(tmp_path), "!reasoning off")
    assert "No setting changed" in text
    assert "reasoning.enabled=false" not in text
    assert "1/100" not in text


def test_help_lists_configured_prefix_and_numeric_openrouter_control(tmp_path):
    text = command(reasoning_bot(tmp_path), "!help")
    assert "`!reasoning` / `!effort`" in text
    assert "provider configuration guidance" in text
    assert "exact numeric effort on OpenRouter" not in text


@pytest.mark.parametrize("original", ["broken json", "", "[]", "null", "false", '"text"'])
def test_invalid_persisted_document_is_not_overwritten(tmp_path, original):
    path = tmp_path / "bot_control.json"
    path.write_text(original)
    assert "No setting changed" in command(reasoning_bot(tmp_path), "!reasoning low")
    assert path.read_text() == original


def test_missing_file_persists_no_derived_defaults(tmp_path):
    assert "No setting changed" in command(reasoning_bot(tmp_path / "new"), "!reasoning max")
    assert not (tmp_path / "new").exists()


def test_persistence_uses_same_api_lock(tmp_path, monkeypatch):
    path = tmp_path / "bot_control.json"
    path.write_text('{"footer_enabled":false}')
    with FileLock(path):
        assert "No setting changed" in command(reasoning_bot(tmp_path), "!reasoning low")
    assert json.loads(path.read_text()) == {"footer_enabled": False}


def test_dashboard_update_reload_changes_future_requests(tmp_path):
    bot = reasoning_bot(tmp_path)
    first = bot.ai_provider._request_payload(bot.ai_provider._endpoints[0], [])
    bot._control["deepseek_reasoning"] = "max"
    assert bot.ai_provider._request_payload(bot.ai_provider._endpoints[0], []) == first
    assert first["reasoning"] == {"effort": 37}


@pytest.mark.parametrize("max_tokens", [64000, None])
def test_main_constructor_wires_live_control_callback(tmp_path, monkeypatch, max_tokens):
    captured = {}
    monkeypatch.setattr(bot_module, "OpenAICompatibleProvider", lambda **kwargs: captured.update(kwargs) or SimpleNamespace())
    config = dict.fromkeys(("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY"), "")
    config.update(OPENAI_MAX_TOKENS=max_tokens, OPENAI_TEMPERATURE=0.6, OPENAI_TOP_P=0.95,
                  OPENAI_TOP_K=20, OPENAI_RETRY_ATTEMPTS=1, OPENAI_EXTRA_HEADERS={},
                  OPENAI_EXTRA_BODY={"reasoning": {"effort": 37}}, ENABLE_AUDIO_INPUT=False)
    bot = SimpleNamespace(config=SimpleNamespace(**config), _control={"deepseek_reasoning": "low"})
    bot._create_main_provider = MethodType(MaxwellBot._create_main_provider, bot)
    MaxwellBot._setup_ai(bot)
    assert "reasoning_control" not in captured
    assert "disable_reasoning" not in captured
    assert captured["max_tokens"] == max_tokens
    assert captured["temperature"] == 0.6
    assert captured["extra_body"] == {"reasoning": {"effort": 37}}
    bot._control = {"deepseek_reasoning": "max"}
    assert captured["extra_body"] == {"reasoning": {"effort": 37}}
