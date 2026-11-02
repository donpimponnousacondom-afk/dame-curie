import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import bot as bot_mod
from bot import DameCurieBot


@pytest.fixture
def shared_bot():
    bot = DameCurieBot.__new__(DameCurieBot)
    bot.config = SimpleNamespace(
        AUX_BASE_URL="",
        AUX_API_KEY=None,
        AUX_MODEL="",
        AUX_DISABLE_REASONING=True,
        AUTONOMY_BASE_URL="",
        AUTONOMY_API_KEY=None,
        AUTONOMY_MODEL="",
        AUTONOMY_DISABLE_REASONING=False,
        OPENAI_TEMPERATURE=0.6,
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
    assert set(kwargs) == {"timeout"}
    assert 119 < kwargs["timeout"] <= 120
    assert bot.ai_provider.temperature == 0.6
    assert bot.ai_provider.disable_reasoning is False
    bot._release_ai_slot.assert_awaited_once()


def _watcher_message():
    return SimpleNamespace(
        content="I prefer Python for my projects.",
        author=SimpleNamespace(id=7, display_name="root"),
        channel=SimpleNamespace(id=8),
        guild=SimpleNamespace(id=9),
        attachments=[],
        embeds=[],
    )


def test_context_watcher_limit_covers_slow_provider_with_one_request(shared_bot, caplog):
    """A provider slower than the watcher limit gets one request, stopped at the limit."""
    bot = shared_bot
    bot._control = {"cross_context_extract_timeout_seconds": 5}

    async def slow_answer(messages, *, timeout):
        await asyncio.sleep(30)

    bot.ai_provider.generate_response = AsyncMock(side_effect=slow_answer)
    caplog.set_level("INFO", logger="bot")

    elapsed = asyncio.run(_timed(bot._extract_shared_context_fact(_watcher_message())))

    assert elapsed < 9
    bot.ai_provider.generate_response.assert_awaited_once()
    assert 4 < bot.ai_provider.generate_response.await_args.kwargs["timeout"] <= 5
    bot._release_ai_slot.assert_awaited_once()
    assert (
        "Context extraction error: TimeoutError: the provider call did not "
        "finish in the 5 s watcher limit and its 2 s guard"
    ) in caplog.text
    assert "reason=error" in caplog.text


def test_context_watcher_lets_the_provider_timeout_fire_first(shared_bot, caplog):
    """The provider's own attempt timeout reports first; the guard does not hide it."""
    bot = shared_bot
    bot._control = {"cross_context_extract_timeout_seconds": 5}

    async def provider_timeout(messages, *, timeout):
        await asyncio.sleep(timeout)
        raise RuntimeError(f"Provider request timed out after {timeout}s")

    bot.ai_provider.generate_response = AsyncMock(side_effect=provider_timeout)
    caplog.set_level("INFO", logger="bot")

    asyncio.run(bot._extract_shared_context_fact(_watcher_message()))

    assert "Context extraction error: RuntimeError: Provider request timed out after" in caplog.text
    assert "watcher limit" not in caplog.text
    bot._release_ai_slot.assert_awaited_once()


@pytest.mark.parametrize(
    "setup_seconds, cause",
    [
        (4.5, "the slot wait and the provider setup left less than 1 s of the 5 s watcher limit"),
        (30, "the provider setup did not finish in the 5 s watcher limit and its 2 s guard"),
    ],
    ids=["less-than-1-s-left", "setup-cut-by-guard"],
)
def test_context_watcher_limit_used_before_the_provider_call(
    shared_bot, caplog, setup_seconds, cause
):
    bot = shared_bot
    bot._control = {"cross_context_extract_timeout_seconds": 5}

    async def late_provider():
        await asyncio.sleep(setup_seconds)
        return bot.ai_provider

    bot._get_aux_provider = late_provider
    caplog.set_level("INFO", logger="bot")

    elapsed = asyncio.run(_timed(bot._extract_shared_context_fact(_watcher_message())))

    assert elapsed < 9
    bot.ai_provider.generate_response.assert_not_awaited()
    bot._release_ai_slot.assert_awaited_once()
    assert f"Context extraction error: TimeoutError: {cause}" in caplog.text


def test_context_watcher_slot_wait_failure_names_its_cause(shared_bot, caplog):
    bot = shared_bot
    bot._acquire_ai_slot = AsyncMock(side_effect=TimeoutError())
    caplog.set_level("INFO", logger="bot")

    asyncio.run(bot._extract_shared_context_fact(_watcher_message()))

    bot.ai_provider.generate_response.assert_not_awaited()
    bot._release_ai_slot.assert_not_awaited()
    assert bot._acquire_ai_slot.await_args.kwargs["timeout"] == 120
    assert (
        "Context extraction error: TimeoutError: "
        "no background model slot became free in 120 s"
    ) in caplog.text


async def _timed(coro):
    loop = asyncio.get_running_loop()
    start = loop.time()
    await coro
    return loop.time() - start


@pytest.mark.parametrize("night_fallback", [False, True])
def test_ltm_summary_overrides_shared_main_policy(monkeypatch, shared_bot, night_fallback):
    bot = shared_bot
    bot.config.DATA_DIR = "unused"
    bot.config.MEMORY_MESSAGE_LIMIT = 100
    bot.config.REM_EVENT_BUFFER_MAX = 10
    bot.config.REM_RUN_HISTORY = 5
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
    assert kwargs == {}
    assert bot.ai_provider.temperature == 0.6
    assert bot.ai_provider.disable_reasoning is False


def test_rem_guard_forwards_aux_policy_on_shared_main(monkeypatch, aux_policy):
    bot, expected_disabled = aux_policy
    bot.config.DATA_DIR = "unused"
    bot.config.OPENAI_REM_MODEL = "rem-model"
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
    assert not {"disable_reasoning", "model", "max_tokens", "temperature"} & kwargs.keys()
    assert bot._rem_running is False
    bot._release_ai_slot.assert_awaited_once()
    bot.ai_provider.generate_response.assert_not_awaited()


HER_ID = 1545541390392369165
LOKI = SimpleNamespace(id=1548576826778194011, display_name="_LOKI_", name="_LOKI_", bot=True)
ROOT = SimpleNamespace(id=1482143139828596916, display_name="SirRooT", name="SirRooT", bot=False)
HER = SimpleNamespace(id=HER_ID, display_name="Red Queen", name="Red Queen", bot=True)


def _discord_message(content, author, mentions=(), reply_to=None):
    reference = None
    if reply_to is not None:
        reference = SimpleNamespace(message_id=reply_to.id, resolved=reply_to)
    return SimpleNamespace(
        id=1566879296734367795,
        content=content,
        author=author,
        channel=SimpleNamespace(id=1548588998983946290),
        guild=SimpleNamespace(id=1545673830960340992),
        attachments=[],
        embeds=[],
        stickers=[],
        mentions=list(mentions),
        role_mentions=[],
        channel_mentions=[],
        reference=reference,
    )


def test_watcher_prompt_names_who_a_reply_to_another_bot_speaks_to(shared_bot):
    """Root, 2 November 2026: "your cot" in a reply to _LOKI_ was read as words to her."""
    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    loki_message = _discord_message("ah THAT. locked in the iron vault", LOKI)
    message = _discord_message(
        "(i am reading your cot idiot)", ROOT, mentions=[LOKI], reply_to=loki_message
    )

    asyncio.run(bot._extract_shared_context_fact(message))

    system, user = [m["content"] for m in bot.ai_provider.generate_response.await_args.args[0]]
    assert "Author: SirRooT (1482143139828596916)\n" in user
    assert (
        'Replying to: _LOKI_(1548576826778194011) [bot]. That message said: '
        '"ah THAT. locked in the iron vault"'
    ) in user
    assert "Mentions: _LOKI_(1548576826778194011) [bot]" in user
    assert "Addressed to dame_curie: no" in user
    assert "They mean dame_curie only when 'Addressed to dame_curie' is yes." in system
    assert "never write 'you', 'I' or 'me'" in system


@pytest.mark.parametrize(
    ("mentions", "reply_author", "verdict"),
    [
        ([], HER, "yes"),
        ([HER], None, "yes"),
        ([LOKI, HER], LOKI, "yes"),
        ([], LOKI, "no"),
        ([LOKI], None, "no"),
        ([], None, "not stated (no reply and no mention)"),
    ],
)
def test_watcher_addressing_verdict_comes_from_discord_data(shared_bot, mentions, reply_author, verdict):
    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    reply_to = _discord_message("an earlier message", reply_author) if reply_author else None
    lines = bot._watcher_addressing(
        _discord_message("you did well", ROOT, mentions=mentions, reply_to=reply_to)
    )
    assert lines.splitlines()[-1] == f"Addressed to dame_curie: {verdict}"
    if HER in mentions:
        assert f"dame_curie({HER_ID})" in lines


def test_a_private_dm_is_addressed_to_her(shared_bot):
    """A 1:1 DM has only her and the author; "call me Max" there is to her."""
    import discord

    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    message = _discord_message("call me Max from now on", ROOT)
    message.channel = Mock(spec=discord.DMChannel)
    assert bot._watcher_addressing(message).splitlines()[-1] == "Addressed to dame_curie: yes"


def test_her_mention_after_ten_others_still_counts(shared_bot):
    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    others = [SimpleNamespace(id=100 + i, display_name=f"u{i}", name=f"u{i}", bot=False) for i in range(10)]
    lines = bot._watcher_addressing(_discord_message("hi all", ROOT, mentions=[*others, HER]))
    assert lines.splitlines()[-1] == "Addressed to dame_curie: yes"


def test_an_unloaded_reply_target_is_named_and_not_called_a_message_without_reply(shared_bot):
    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    message = _discord_message("you were wrong", ROOT)
    message.reference = SimpleNamespace(message_id=42, resolved=None)
    lines = bot._watcher_addressing(message).splitlines()
    assert lines == [
        "Replying to: a message that could not be loaded",
        "Addressed to dame_curie: not stated (the reply target could not be loaded)",
    ]


def test_a_quote_with_double_quotes_cannot_end_the_quote(shared_bot):
    bot = shared_bot
    bot._connection = SimpleNamespace(user=SimpleNamespace(id=HER_ID))
    loki_message = _discord_message('he said "stop" twice', LOKI)
    lines = bot._watcher_addressing(_discord_message("lol", ROOT, reply_to=loki_message))
    assert "That message said: \"he said 'stop' twice\"" in lines
