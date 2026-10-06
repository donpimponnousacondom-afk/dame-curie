"""One final chunk must settle inside the observed foreground turn."""

import asyncio
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot as bot_module
from bot import MaxwellBot
from dirac_runtime import _TurnObserver
from message_pipeline import ReplyQueue
from provider_reload import providers_idle
from providers import ProviderResult
from response_observability import TURN_INPUT
from test_foreground_observability import Message, foreground_bot, tool_call
from tool_progress import ToolProgress


@pytest.fixture
def final_round(foreground_bot: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    bot = foreground_bot
    message = Message()
    observer = _TurnObserver()
    bot._turn_observer = observer
    bot._handle_message = MethodType(MaxwellBot._handle_message, bot)
    bot._preserve_input_actor = MaxwellBot._preserve_input_actor
    bot._progress_enabled = lambda guild: True
    bot._control["footer_enabled"] = False
    initial, final = ToolProgress(message), ToolProgress(message)
    initial.start_defer = AsyncMock()
    edit_started, release = asyncio.Event(), asyncio.Event()

    async def post_final_progress() -> None:
        posted = await message.channel.send("working on it…")
        final._posted = posted

        async def blocked_edit(*, content: str) -> None:
            edit_started.set()
            await release.wait()
            posted.content = content

        posted.edit = blocked_edit

    final.start_defer = post_final_progress
    progresses = iter((initial, final))
    monkeypatch.setattr(bot_module, "_make_tool_progress", lambda _: next(progresses))
    responses = iter((
        ProviderResult("", tool_calls=[tool_call("web_search", query="synthetic")]),
        ProviderResult("Answer."),
    ))

    async def generate(*args: object, **kwargs: object) -> ProviderResult:
        result = next(responses)
        observer.model_result(TURN_INPUT.get(), True)
        return result

    bot._generate_response = AsyncMock(side_effect=generate)
    bot._dispatch_tool_calls = AsyncMock(side_effect=[
        ("", ["Tool web_search: synthetic result"], []),
        ("Answer.", [], []),
    ])
    return SimpleNamespace(
        bot=bot, message=message, observer=observer, edit_started=edit_started, release=release,
    )


def test_final_delivery_owns_observer_and_reload_idle_boundary(
    final_round: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    bot = final_round.bot
    bot.ai_slot_stats = lambda: {"active": 0, "waiting": 0}
    bot._inflight_context = {}
    bot._reply_queue = ReplyQueue()
    bot._vc_active_tasks = {}
    bot._context_tasks = set()
    bot.bg_jobs = SimpleNamespace(_tasks={}, active_count=lambda: 0)
    bot._rem_running = False
    bot.autonomy_engine = SimpleNamespace(_tick_in_flight=False)
    bot._provider_rounds_active = 0
    bot.ai_provider = bot.autonomy_provider = bot.aux_provider = None
    bot._retired_providers = []

    async def run() -> None:
        message, observer = final_round.message, final_round.observer
        turn = observer.open(str(message.id), str(message.channel.id))
        task = asyncio.create_task(MaxwellBot._run_queued_reply(bot, message))
        await asyncio.wait_for(final_round.edit_started.wait(), timeout=1)
        assert not task.done() and not turn.done.is_set()
        assert turn.model_ok and turn.output == [] and turn.delivered == []
        assert len(message.channel.sent) == 1
        posted = message.channel.sent[0]
        assert posted.content == "working on it…"
        assert bot._delivery_measurements.lookup("100") is None
        assert providers_idle(bot) is False

        final_round.release.set()
        await asyncio.wait_for(task, timeout=1)
        assert turn.done.is_set() and turn.returned
        assert turn.output == turn.delivered == [str(posted.id)]
        assert message.channel.sent == [posted] and posted.content == "Answer."
        assert bot._generate_response.await_count == 2
        assert bot._dispatch_tool_calls.await_count == 2
        assert providers_idle(bot) is True
        assert not any("Media extraction failed" in record.getMessage() for record in caplog.records)

    asyncio.run(run())
