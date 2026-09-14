import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import bot as bot_mod
from bot import MaxwellBot


@pytest.fixture
def shared_bot():
    bot = MaxwellBot.__new__(MaxwellBot)
    bot.config = SimpleNamespace(
        AUX_BASE_URL="",
        AUX_API_KEY="",
        AUX_MODEL="",
        AUX_DISABLE_REASONING=True,
        AUTONOMY_BASE_URL="",
        AUTONOMY_API_KEY="",
        AUTONOMY_MODEL="",
        AUTONOMY_DISABLE_REASONING=False,
        OLLAMA_TEMPERATURE=0.6,
    )
    bot.bot_name = "dame_curie"
    bot._control = {}
    bot.ai_provider = SimpleNamespace(
        available=True,
        temperature=0.6,
        disable_reasoning=False,
        generate_response=AsyncMock(return_value='{"should_store": false}'),
    )
    bot.aux_provider = None
    bot._aux_provider_sig = ""
    bot.autonomy_provider = None
    bot._autonomy_provider_sig = ""
    bot._night_fallback_active = Mock(return_value=False)
    bot._acquire_ai_slot = AsyncMock()
    bot._release_ai_slot = AsyncMock()
    bot._is_admin = Mock(return_value=False)
    return bot


@pytest.fixture(
    params=[
        (True, {}, True),
        (False, {}, False),
        (False, {"aux_disable_reasoning": True}, True),
        (True, {"aux_disable_reasoning": False}, False),
    ],
    ids=["env-disabled", "env-native", "control-disabled", "control-native"],
)
def aux_policy(shared_bot, request):
    env_disabled, control, expected = request.param
    shared_bot.config.AUX_DISABLE_REASONING = env_disabled
    shared_bot._control = dict(control)
    return shared_bot, expected


@pytest.mark.parametrize("night_fallback", [False, True])
def test_context_watcher_overrides_shared_main_policy(aux_policy, night_fallback):
    bot, expected_disabled = aux_policy
    bot._night_fallback_active.return_value = night_fallback
    message = SimpleNamespace(
        content="I prefer Python for my projects.",
        author=SimpleNamespace(id=7, display_name="root"),
        channel=SimpleNamespace(id=8),
        guild=SimpleNamespace(id=9),
        attachments=[],
        embeds=[],
    )

    asyncio.run(bot._extract_shared_context_fact(message))

    bot.ai_provider.generate_response.assert_awaited_once()
    kwargs = bot.ai_provider.generate_response.await_args.kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["disable_reasoning"] is expected_disabled
    assert kwargs["model"] is None
    assert kwargs.get("prefer_fallback", False) is night_fallback
    assert bot.ai_provider.temperature == 0.6
    assert bot.ai_provider.disable_reasoning is False
    bot._release_ai_slot.assert_awaited_once()


@pytest.mark.parametrize("night_fallback", [False, True])
def test_ltm_summary_overrides_shared_main_policy(monkeypatch, shared_bot, night_fallback):
    bot = shared_bot
    bot.config.DATA_DIR = "unused"
    bot.config.MEMORY_MESSAGE_LIMIT = 100
    bot.config.REM_EVENT_BUFFER_MAX = 10
    bot.config.REM_RUN_HISTORY = 5
    bot.config.ENABLE_EMAIL_TOOLS = False
    bot.config.ENABLE_X = False
    bot._night_fallback_active.return_value = night_fallback
    bot.ai_provider.generate_response.return_value = '{"facts": ["root prefers Python"]}'
    memory = SimpleNamespace()
    monkeypatch.setattr(bot_mod, "RAGMemoryManager", Mock(return_value=memory))
    monkeypatch.setattr(bot_mod, "RemEventLog", Mock(return_value=SimpleNamespace()))
    monkeypatch.setattr(bot_mod, "RemStore", Mock(return_value=SimpleNamespace()))
    monkeypatch.setattr(bot_mod, "InboxStore", Mock(return_value=SimpleNamespace()))
    bot._setup_memory()

    facts = asyncio.run(bot.memory._ltm_summarizer_fn("root: I prefer Python"))

    assert facts == ["root prefers Python"]
    bot.ai_provider.generate_response.assert_awaited_once()
    kwargs = bot.ai_provider.generate_response.await_args.kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["disable_reasoning"] is True
    assert kwargs["max_tokens"] == 1200
    assert kwargs.get("prefer_fallback", False) is night_fallback
    assert bot.ai_provider.temperature == 0.6
    assert bot.ai_provider.disable_reasoning is False


def test_rem_guard_forwards_aux_policy_on_shared_main(monkeypatch, aux_policy):
    bot, expected_disabled = aux_policy
    bot.config.DATA_DIR = "unused"
    bot.config.OLLAMA_REM_MODEL = "rem-model"
    bot.config.REM_RUN_HISTORY = 5
    bot._rem_running = False
    bot.rem_max_turns = 3
    bot.rem_prompt_body = "Assimilate the recent facts."
    bot.memory = SimpleNamespace()
    bot.rem_log = SimpleNamespace()
    bot.rem_store = SimpleNamespace(patch_state=AsyncMock())
    run = {"audit": "no changes"}
    runner = AsyncMock(return_value=run)
    monkeypatch.setattr(bot_mod, "run_rem_once", runner)

    result = asyncio.run(bot._run_rem_once_guarded())

    assert result == (True, "ok", run)
    runner.assert_awaited_once()
    kwargs = runner.await_args.kwargs
    assert kwargs["provider"] is bot.ai_provider
    assert kwargs["disable_reasoning"] is expected_disabled
    assert kwargs["model"] == "rem-model"
    assert kwargs["max_tokens"] == 8192
    assert bot._rem_running is False
    bot._release_ai_slot.assert_awaited_once()
    bot.ai_provider.generate_response.assert_not_awaited()
