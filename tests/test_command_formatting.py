import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import MaxwellBot
from response_observability import FOOTER_MARKER


@pytest.fixture
def command_report():
    detail = "synthetic ```data``` @everyone\n" * 150
    facts = [{"id": "fact-1", "scope": "channel", "visibility": "public", "importance": 2, "content": detail}]
    runs = [{"ts": "synthetic-time", "turns_used": 3, "events": 2, "audit": detail}] * 20
    status = {"enabled": True, "running": False, "interval_s": 300, "model": "synthetic", "last_run": None, "events_buffered": 2, "last_audit_preview": detail}
    store = SimpleNamespace(
        load_state=AsyncMock(return_value={"last_error": detail}),
        load_log=AsyncMock(return_value=[{"timestamp": "synthetic-time", "action_kind": "test", "content_summary": "synthetic", "result": detail}]),
    )
    bot = SimpleNamespace(
        _control={"footer_enabled": True}, _split_response=MaxwellBot._split_response,
        _is_admin=lambda uid: True, config=SimpleNamespace(ENABLE_VC=True),
        x_client=SimpleNamespace(status=lambda: detail, budget=SimpleNamespace(check=AsyncMock(return_value=""))),
        _vc_get_client=lambda guild, channel: None, _vc_is_listening=lambda vc: False,
        memory=SimpleNamespace(get_relevant_shared_context=AsyncMock(return_value=facts), list_shared_context=AsyncMock(return_value=facts)),
        _rem_status=AsyncMock(return_value=status), rem_store=SimpleNamespace(load_runs=AsyncMock(return_value=runs)),
        autonomy_engine=SimpleNamespace(store=store, _floor_verdicts={}),
    )
    message = SimpleNamespace(channel=SimpleNamespace(id=23, send=AsyncMock()), author=SimpleNamespace(id=7), guild=None)
    return bot, message


@pytest.mark.parametrize("footer_enabled", [False, True])
@pytest.mark.parametrize("handler,args,heading", [
    ("_handle_x_command", "status", "X:"),
    ("_handle_vc_command", "status", "connected: False\nchannel: none\nlistening: False"),
    ("_handle_context_command", "", "Relevant context facts"),
    ("_handle_context_command", "all", "Recent context facts"),
    ("_handle_rem_command", "", "REM status"),
    ("_handle_rem_command", "audit 20", "synthetic-time turns=3 events=2"),
    ("_handle_autonomy_command", "", "Autonomy status"),
    ("_handle_autonomy_command", "log", "synthetic-time [test]"),
])
def test_dense_reports_emit_balanced_bounded_code_blocks(command_report, footer_enabled, handler, args, heading):
    bot, message = command_report
    bot._control["footer_enabled"] = footer_enabled
    asyncio.run(getattr(MaxwellBot, handler)(bot, message, args))
    calls = message.channel.send.await_args_list
    assert calls and heading in calls[0].args[0]
    assert len(calls) > 1 if handler != "_handle_vc_command" else len(calls) == 1
    for call in calls:
        content = call.args[0]
        assert content.startswith("```\n") and content.endswith("\n```")
        assert content.count("```") == 2 and len(content) <= 2000
        assert FOOTER_MARKER not in content and "**" not in content
        assert not call.kwargs["allowed_mentions"].everyone
    if handler != "_handle_vc_command":
        assert "`\u200b`\u200b`data" in "".join(call.args[0] for call in calls)


@pytest.mark.parametrize("handler,args,expected", [
    ("_handle_context_command", "", "No shared context facts."),
    ("_handle_rem_command", "audit", "No REM runs yet."),
    ("_handle_autonomy_command", "log", "No autonomy actions yet."),
    ("_handle_x_command", "budget", "X budget: room to post"),
])
def test_short_command_responses_stay_plain(command_report, handler, args, expected):
    bot, message = command_report
    bot.memory.get_relevant_shared_context.return_value = []
    bot.rem_store.load_runs.return_value = []
    bot.autonomy_engine.store.load_log.return_value = []
    asyncio.run(getattr(MaxwellBot, handler)(bot, message, args))
    message.channel.send.assert_awaited_once_with(expected)


def test_link_and_command_help_keeps_inline_markdown(command_report):
    bot, message = command_report
    asyncio.run(MaxwellBot._handle_vc_command(bot, message, "help"))
    content = message.channel.send.await_args.args[0]
    assert "`,vc join`" in content and "```" not in content
