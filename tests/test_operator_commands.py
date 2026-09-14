import asyncio
import copy
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

import bot as bot_module
import error_reporting
from bot import MaxwellBot
from bot_tools import ToolFailure
from error_reporting import PUBLIC_ERROR_TEXT, IncidentLoggingHandler, configure_incident_store
from operator_commands import (
    PRIVATE_ERROR_REPORT_MARKER,
    handle_error_command,
    handle_forward_command,
    ignore_operator_message,
    is_private_error_report,
    send_public_error,
)
from plugin_manager import PluginReloadFailure
from response_observability import FOOTER_MARKER


class Channel:
    def __init__(self, channel_id):
        self.id = channel_id
        self.sent = []
        self.messages = []
        self.history_calls = []

    async def send(self, content, **kwargs):
        assert len(content) <= 2000
        payload = {"content": content, **kwargs}
        attachment = kwargs.get("file")
        if attachment is not None:
            payload["file_bytes"] = attachment.fp.read()
            payload["filename"] = attachment.filename
        self.sent.append(payload)
        return SimpleNamespace(id=10000 + len(self.sent), channel=self)

    async def history(self, *, limit, before):
        self.history_calls.append((limit, before.id))
        for message in sorted(list(self.messages), key=lambda item: item.id, reverse=True):
            if message.id < before.id:
                yield message


@pytest.fixture
def operator_case(tmp_path, monkeypatch):
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    store = configure_incident_store(tmp_path / "error_history.json", secrets=["synthetic-credential"])
    channel, dm = Channel(23), Channel(71)
    author = SimpleNamespace(id=7, bot=False, create_dm=AsyncMock(return_value=dm))
    bot = SimpleNamespace(
        user=SimpleNamespace(id=42, bot=False), command_prefix="!", bot_name="Curie",
        _control={"error_replies": True, "error_details": True, "footer_enabled": True},
        _is_admin=lambda uid: uid == 7, _forward_locks={}, _forward_delete_ids=set(),
        _split_response=MaxwellBot._split_response, tools={},
        memory={"messages": ["sacred"], "embeddings": [1, 2, 3]},
        rem_store={"events": ["sacred"]}, _media_context={"23": ["sacred"]},
        tool_history=["sacred"], _message_snapshots={"existing": "sacred"},
    )
    message = SimpleNamespace(
        id=100, content="!error 0", channel=channel, author=author,
        guild=SimpleNamespace(id=31), reference=None,
    )
    handler = IncidentLoggingHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield bot, message, dm, store
    finally:
        root.removeHandler(handler)
        handler.close()


def own_message(bot, channel, message_id, *, content="ordinary own message"):
    message = SimpleNamespace(id=message_id, channel=channel, author=bot.user, content=content)

    async def delete():
        channel.messages.remove(message)
        await MaxwellBot.on_message_delete(bot, message)
        await MaxwellBot.on_message_delete(bot, message)

    message.delete = AsyncMock(side_effect=delete)
    return message


@pytest.mark.parametrize("guild", [None, SimpleNamespace(id=31)])
def test_error_always_uses_requesting_admin_dm_with_fences_and_no_footer(operator_case, guild):
    bot, message, dm, store = operator_case
    message.guild = guild
    incident_id = store.record("provider", "failed @everyone", details="body ```embedded``` synthetic-credential END")
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert not message.channel.sent
    message.author.create_dm.assert_awaited_once()
    content = dm.sent[0]["content"]
    report = content.removesuffix("\n" + PRIVATE_ERROR_REPORT_MARKER)
    assert report.startswith("```\n") and report.endswith("\n```")
    assert report.count("```") == 2
    assert incident_id in report and "END" in report
    assert "synthetic-credential" not in report
    assert FOOTER_MARKER not in content
    assert not dm.sent[0]["allowed_mentions"].everyone
    assert not dm.sent[0]["allowed_mentions"].users


@pytest.mark.parametrize("command", ["!error 0", "!forward 1"])
def test_guild_administrator_is_not_implicitly_bot_admin(operator_case, command):
    bot, message, dm, store = operator_case
    message.author.id = 8
    message.author.guild_permissions = SimpleNamespace(administrator=True)
    message.content = command
    store.record("private", "never disclose")
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert [item["content"] for item in message.channel.sent] == ["not authorized"]
    assert not dm.sent and not message.channel.history_calls
    message.author.create_dm.assert_not_awaited()


def test_bare_error_keeps_roots_requested_usage_text_private(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!error"
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert not message.channel.sent
    text = dm.sent[0]["content"]
    assert text == (
        "You need to use !error 0 to 9 to recover the last error; "
        "root made this call because is lazy and one extra number doesn't hurt as much "
        "as losing time and asking the agent again what was the syntax he made up in a rush\n"
        + PRIVATE_ERROR_REPORT_MARKER
    )
    assert store.get(0) is None


@pytest.mark.parametrize("argument", ["10", "100", "-1", "+1", "01", "1.0", "0 1", "９"])
def test_error_requires_exact_index_zero_through_nine(operator_case, argument):
    bot, message, dm, store = operator_case
    asyncio.run(handle_error_command(bot, message, argument))
    assert not message.channel.sent
    assert "0–9" in dm.sent[0]["content"]
    assert "0 is newest, 9 is oldest" in dm.sent[0]["content"]
    assert store.get(0) is None


def test_error_snapshot_is_fixed_before_any_discord_send(operator_case):
    bot, message, dm, store = operator_case
    selected = store.record("original", "selected report")

    async def create_dm():
        for index in range(12):
            store.record("later", str(index))
        return dm

    message.author.create_dm.side_effect = create_dm
    asyncio.run(handle_error_command(bot, message, "0"))
    assert selected in dm.sent[0]["content"]
    assert "selected report" in dm.sent[0]["content"]
    assert store.get(0).incident_id != selected


def test_large_reports_are_complete_utf8_attachments_in_bounded_parts(operator_case):
    bot, message, dm, store = operator_case
    body = "BEGIN\n" + "🕊" * 2_000_010 + "\nEND @everyone ```"
    store.record("large", "complete report", details=body)
    expected = store.get(0).format_report()
    asyncio.run(handle_error_command(bot, message, "0"))
    assert not message.channel.sent
    assert len(dm.sent) == 3
    combined = "".join(item["file_bytes"].decode("utf-8") for item in dm.sent)
    assert combined == expected
    for item in dm.sent:
        assert len(item["file_bytes"].decode("utf-8")) <= 1_000_000
        assert item["filename"].endswith(".txt")
        assert item["file"].fp.closed
        assert item["content"].startswith("```\n")
        assert item["content"].count("```") == 2
        assert PRIVATE_ERROR_REPORT_MARKER in item["content"]
        assert FOOTER_MARKER not in item["content"]
        assert not item["allowed_mentions"].everyone


def test_report_attachment_buffer_closes_when_discord_send_fails(operator_case):
    bot, message, dm, store = operator_case
    store.record("private", "private attachment", details="PRIVATE-BODY " * 2000)
    attachments = []

    async def failed_send(content, **kwargs):
        attachments.append(kwargs["file"])
        raise RuntimeError("synthetic attachment delivery failure")

    dm.send = failed_send
    asyncio.run(handle_error_command(bot, message, "0"))
    assert len(attachments) == 1 and attachments[0].fp.closed
    assert [item["content"] for item in message.channel.sent] == [PUBLIC_ERROR_TEXT]
    assert all("file" not in item for item in message.channel.sent)
    assert "synthetic attachment delivery failure" in store.get(0).traceback


@pytest.mark.parametrize("error_replies", [False, True])
def test_blocked_report_dm_never_falls_back_to_public_details(operator_case, error_replies):
    bot, message, dm, store = operator_case
    bot._control["error_replies"] = error_replies
    store.record("private", "SECRET REPORT BODY")
    message.author.create_dm.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "synthetic DM blocked"
    )
    asyncio.run(handle_error_command(bot, message, "0"))
    assert not dm.sent
    assert [item["content"] for item in message.channel.sent] == ([PUBLIC_ERROR_TEXT] if error_replies else [])
    assert all("file" not in item for item in message.channel.sent)
    assert store.get(0).source == "discord.error-report"
    assert "synthetic DM blocked" in store.get(0).traceback


def test_report_and_notice_send_failures_are_captured_without_recursion(operator_case):
    bot, message, dm, store = operator_case
    message.author.create_dm.side_effect = RuntimeError("synthetic DM failure")
    message.channel.send = AsyncMock(side_effect=RuntimeError("synthetic notice failure"))
    asyncio.run(handle_error_command(bot, message, "0"))
    message.author.create_dm.assert_awaited_once()
    assert message.channel.send.await_count == 1
    call = message.channel.send.await_args
    assert call.args == (PUBLIC_ERROR_TEXT,)
    assert set(call.kwargs) == {"allowed_mentions"}
    assert not call.kwargs["allowed_mentions"].everyone
    assert not call.kwargs["allowed_mentions"].users
    assert not dm.sent and not message.channel.sent
    incident = store.get(0)
    assert "RuntimeError: synthetic notice failure" in incident.traceback
    assert "RuntimeError: synthetic DM failure" in incident.traceback
    report = incident.format_report()
    assert "synthetic notice failure" in report and "synthetic DM failure" in report
    assert store.get(1) is None


def test_marked_own_reports_skip_create_edit_raw_edit_and_memory(operator_case):
    bot, message, dm, store = operator_case
    report = own_message(bot, dm, 90, content="private body\n" + PRIVATE_ERROR_REPORT_MARKER)
    bot._dispatch_plugin_event = Mock()
    bot._on_message_impl = AsyncMock()
    bot._inbound_dedup = Mock()
    bot._load_control = Mock()
    bot._refresh_edited_message = AsyncMock()
    bot._message_from_raw_update = AsyncMock(return_value=report)
    bot._mem_kwargs = Mock()
    bot._observe_message_author = AsyncMock()
    bot.memory = SimpleNamespace(add_to_channel_memory=AsyncMock())
    bot.rem_log = SimpleNamespace(record=AsyncMock())

    async def run():
        await MaxwellBot.on_message(bot, report)
        await MaxwellBot.on_message_edit(bot, report, report)
        await MaxwellBot.on_raw_message_edit(bot, SimpleNamespace(cached_message=report))
        bot._message_from_raw_update.assert_not_awaited()
        await MaxwellBot.on_raw_message_edit(bot, SimpleNamespace(cached_message=None))
        await MaxwellBot._refresh_edited_message(bot, report)
        await MaxwellBot.add_message_to_memory(bot, "71", {"content": "private"}, report)
        await MaxwellBot._record_rem_event(bot, report, "assistant", "private")

    asyncio.run(run())
    bot._dispatch_plugin_event.assert_not_called()
    bot._on_message_impl.assert_not_awaited()
    bot._inbound_dedup.check_and_add.assert_not_called()
    bot._refresh_edited_message.assert_not_awaited()
    bot.memory.add_to_channel_memory.assert_not_awaited()
    bot._mem_kwargs.assert_not_called()
    bot.rem_log.record.assert_not_awaited()


@pytest.mark.parametrize("admins,expected_recipients", [({"7", "8"}, ["7", "8"]), (set(), ["99"])])
def test_global_captcha_notice_stays_private_without_changing_solver_link(operator_case, admins, expected_recipients):
    bot, message, dm, store = operator_case
    bot._admins = admins
    bot.config = SimpleNamespace(CAPTCHA_FALLBACK_USER_ID="99")
    bot._is_admin = lambda uid: False
    bot._captcha_recipient_ids = lambda: MaxwellBot._captcha_recipient_ids(bot)
    bot._captcha_summary = lambda exception: MaxwellBot._captcha_summary(bot, exception)
    users = {uid: SimpleNamespace(send=AsyncMock()) for uid in expected_recipients}
    bot._captcha_resolve_user = AsyncMock(side_effect=lambda uid: users[uid])
    bot._dispatch_plugin_event = Mock()
    bot._on_message_impl = AsyncMock()
    bot._generate_response = AsyncMock()
    bot._inbound_dedup = Mock()
    bot.memory = SimpleNamespace(add_to_channel_memory=AsyncMock())
    bot.rem_log = SimpleNamespace(record=AsyncMock())
    url = "http://127.0.0.1:8790/solve/synthetic-challenge?token=synthetic-solve-token"
    challenge = SimpleNamespace(
        errors=["synthetic captcha-required"], service="hcaptcha", sitekey="synthetic-sitekey",
        rqdata="synthetic-challenge-data @everyone", should_serve_invisible=True,
    )

    async def run():
        await MaxwellBot._notify_captcha_link(bot, url, challenge)
        for index, user in enumerate(users.values()):
            user.send.assert_awaited_once()
            call = user.send.await_args
            payload = call.args[0]
            assert url in payload and "synthetic-challenge-data" in payload
            assert payload.endswith("\n" + PRIVATE_ERROR_REPORT_MARKER)
            assert FOOTER_MARKER not in payload
            assert not call.kwargs["allowed_mentions"].everyone
            assert not call.kwargs["allowed_mentions"].users
            gateway_message = own_message(bot, dm, 90 + index, content=payload)
            await MaxwellBot.on_message(bot, gateway_message)
            await MaxwellBot._on_message_impl(bot, gateway_message)

    asyncio.run(run())
    assert [call.args[0] for call in bot._captcha_resolve_user.await_args_list] == expected_recipients
    assert not message.channel.sent
    bot._dispatch_plugin_event.assert_not_called()
    bot._on_message_impl.assert_not_awaited()
    bot._generate_response.assert_not_awaited()
    bot._inbound_dedup.check_and_add.assert_not_called()
    bot.memory.add_to_channel_memory.assert_not_awaited()
    bot.rem_log.record.assert_not_awaited()
    assert store.get(0) is None


@pytest.mark.parametrize("content", ["!error 0", "!forward 2"])
def test_operator_command_ingress_bypasses_plugins_and_memory_but_dispatches(operator_case, content):
    bot, message, dm, store = operator_case
    message.content = content
    bot._dispatch_plugin_event = Mock()
    bot._on_message_impl = AsyncMock()
    bot._inbound_dedup = SimpleNamespace(check_and_add=Mock(return_value=True))
    bot._watermarks = SimpleNamespace(note=Mock())
    bot.memory = SimpleNamespace(add_to_channel_memory=AsyncMock())
    bot._mem_kwargs = Mock()
    bot.rem_log = SimpleNamespace(record=AsyncMock())

    async def run():
        await MaxwellBot.on_message(bot, message)
        await MaxwellBot.on_message_edit(bot, message, message)
        await MaxwellBot.add_message_to_memory(bot, "23", {"content": content}, message)
        await MaxwellBot._record_rem_event(bot, message, "user", content)

    asyncio.run(run())
    bot._dispatch_plugin_event.assert_not_called()
    bot._on_message_impl.assert_awaited_once_with(message)
    bot.memory.add_to_channel_memory.assert_not_awaited()
    bot.rem_log.record.assert_not_awaited()


def test_marker_cannot_hide_other_users_or_intentional_admin_references(operator_case):
    bot, message, dm, store = operator_case
    report = own_message(bot, dm, 90, content="report\n" + PRIVATE_ERROR_REPORT_MARKER)
    assert is_private_error_report(report, bot.user.id)
    message.content = "Please inspect this quoted report " + PRIVATE_ERROR_REPORT_MARKER
    message.reference = SimpleNamespace(resolved=report, message_id=report.id)
    assert not is_private_error_report(message, bot.user.id)
    assert not ignore_operator_message(bot, message)
    assert message.reference.resolved.content == report.content
    model_quote = own_message(bot, dm, 91, content="!error 0 is the command syntax")
    assert not ignore_operator_message(bot, model_quote)


def test_forward_deletes_only_own_prior_posts_and_preserves_all_memory(operator_case, tmp_path):
    bot, message, dm, store = operator_case
    message.content = "!forward 2"
    state_path = tmp_path / "synthetic-memory.json"
    state_path.write_text('{"memory":"sacred"}')
    state_before = state_path.read_bytes()
    state = {name: copy.deepcopy(getattr(bot, name)) for name in (
        "memory", "rem_store", "_media_context", "tool_history", "_message_snapshots",
    )}
    plugin = Mock(side_effect=lambda event, item: bot.memory.clear())
    bot._dispatch_plugin_event = plugin
    old = own_message(bot, message.channel, 10)
    first, second = own_message(bot, message.channel, 80), own_message(bot, message.channel, 70)
    future = own_message(bot, message.channel, 101)
    other = SimpleNamespace(id=90, author=SimpleNamespace(id=8, bot=True), channel=message.channel)
    foreign = own_message(bot, dm, 95)
    message.channel.messages = [old, first, second, future, other, message, foreign]
    asyncio.run(MaxwellBot._handle_command(bot, message))
    first.delete.assert_awaited_once()
    second.delete.assert_awaited_once()
    old.delete.assert_not_awaited()
    future.delete.assert_not_awaited()
    foreign.delete.assert_not_awaited()
    assert bot._forward_delete_ids == {80, 70}
    assert not message.channel.sent and not dm.sent
    assert plugin.call_count == 0
    assert state == {name: getattr(bot, name) for name in state}
    assert state_path.read_bytes() == state_before
    asyncio.run(MaxwellBot.on_message_delete(bot, other))
    plugin.assert_called_once_with("on_message_delete", other)


def test_forward_serializes_history_selection_and_deletion(operator_case):
    bot, message, dm, store = operator_case
    bot._dispatch_plugin_event = Mock()
    deleted = []
    message.channel.messages = [own_message(bot, message.channel, index) for index in (10, 20, 30, 40)]
    first_message = message.channel.messages[-1]
    second_invocation = SimpleNamespace(**(vars(message) | {"id": 110}))

    async def run():
        started, release, second_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original_delete = first_message.delete

        async def slow_delete():
            started.set()
            await release.wait()
            await original_delete()

        first_message.delete = slow_delete
        for item in message.channel.messages:
            original = item.delete

            async def tracked_delete(original=original, item=item):
                deleted.append(item.id)
                await original()

            item.delete = tracked_delete
        first = asyncio.create_task(handle_forward_command(bot, message, "2"))
        await started.wait()

        async def second():
            second_started.set()
            await handle_forward_command(bot, second_invocation, "2")

        second_task = asyncio.create_task(second())
        await second_started.wait()
        assert message.channel.history_calls == [(None, 100)]
        release.set()
        await asyncio.gather(first, second_task)

    asyncio.run(run())
    assert deleted == [40, 30, 20, 10]
    assert message.channel.history_calls == [(None, 100), (None, 110)]
    assert not message.channel.messages and not message.channel.sent
    assert bot._forward_delete_ids == {10, 20, 30, 40}
    bot._dispatch_plugin_event.assert_not_called()


@pytest.mark.parametrize("argument", [None, "", "0", "-1", "+1", "1.0", "one", "１", "2 extra"])
def test_forward_requires_a_positive_explicit_integer(operator_case, argument):
    bot, message, dm, store = operator_case
    asyncio.run(handle_forward_command(bot, message, argument))
    assert "positive number" in message.channel.sent[0]["content"]
    assert not message.channel.history_calls and not bot._forward_delete_ids


def test_forward_not_found_is_already_gone_and_still_protected(operator_case):
    bot, message, dm, store = operator_case
    bot._dispatch_plugin_event = Mock()
    candidate = own_message(bot, message.channel, 90)
    candidate.delete.side_effect = discord.NotFound(
        SimpleNamespace(status=404, reason="Not Found"), "synthetic already deleted"
    )
    message.channel.messages = [candidate]
    asyncio.run(handle_forward_command(bot, message, "100000"))
    assert bot._forward_delete_ids == {90}
    assert not message.channel.sent
    assert store.get(0) is None


def test_forward_actual_delete_failure_is_private_and_public_reply_generic(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!forward 2"
    bot._dispatch_plugin_event = Mock()
    first, second = own_message(bot, message.channel, 90), own_message(bot, message.channel, 80)
    first.delete.side_effect = RuntimeError("synthetic detailed deletion failure")
    message.channel.messages = [first, second]
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert bot._forward_delete_ids == {90}
    second.delete.assert_not_awaited()
    assert [item["content"] for item in message.channel.sent] == [PUBLIC_ERROR_TEXT]
    assert "synthetic detailed deletion failure" in store.get(0).traceback
    assert store.get(1) is None


def test_forward_partial_failure_captures_batch_progress_without_message_bodies(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!forward 3"
    bot._dispatch_plugin_event = Mock()
    selected = [own_message(bot, message.channel, item, content="PRIVATE MESSAGE BODY") for item in (90, 80, 70)]
    selected[1].delete.side_effect = discord.NotFound(
        SimpleNamespace(status=404, reason="Not Found"), "synthetic already gone"
    )
    selected[2].delete.side_effect = RuntimeError("synthetic partial failure")
    message.channel.messages = list(selected)
    asyncio.run(MaxwellBot._handle_command(bot, message))
    incident = store.get(0)
    assert incident.source == "discord.forward"
    for field in (
        "requested_count: 3", "phase: delete", "failed_target: 70",
        "selected_ids: [90, 80, 70]", "completed_ids: [90]", "absent_ids: [80]",
    ):
        assert field in incident.details
    assert incident.context == {"channel": "23", "message": "100", "user": "7", "guild": "31"}
    assert "PRIVATE MESSAGE BODY" not in incident.format_report()
    assert store.get(1) is None
    assert [item["content"] for item in message.channel.sent] == [PUBLIC_ERROR_TEXT]


def test_forward_history_failure_captures_selection_phase_before_deletion(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!forward 3"
    candidate = own_message(bot, message.channel, 90)

    async def history(*, limit, before):
        yield candidate
        raise RuntimeError("synthetic history failure")

    message.channel.history = history
    asyncio.run(MaxwellBot._handle_command(bot, message))
    details = store.get(0).details
    assert "requested_count: 3" in details and "phase: history" in details
    assert "selected_ids: [90]" in details and "completed_ids: []" in details
    assert "failed_target: -" in details
    assert not bot._forward_delete_ids
    candidate.delete.assert_not_awaited()
    assert store.get(1) is None


def test_forward_cancellation_propagates_without_an_error_incident(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!forward 1"
    candidate = own_message(bot, message.channel, 90)
    candidate.delete.side_effect = asyncio.CancelledError()
    message.channel.messages = [candidate]
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(MaxwellBot._handle_command(bot, message))
    assert not message.channel.sent
    assert store.get(0) is None
    assert bot._forward_delete_ids == {90}


@pytest.mark.parametrize("error_replies", [False, True])
def test_public_projection_respects_switch_and_never_adds_footer(operator_case, error_replies):
    bot, message, dm, store = operator_case
    bot._control["error_replies"] = error_replies
    bot._control["error_details"] = True
    asyncio.run(send_public_error(bot, message.channel))
    assert [item["content"] for item in message.channel.sent] == ([PUBLIC_ERROR_TEXT] if error_replies else [])


@pytest.mark.parametrize("structured", [False, True])
def test_guide_projects_only_structured_failures_not_arbitrary_text(operator_case, structured):
    bot, message, dm, store = operator_case
    message.content = "!guide a synthetic goal"
    text = "Error: this is intentional quoted model/log prose"
    result = ToolFailure(text, None) if structured else text
    bot.tools["guide"] = SimpleNamespace(execute=AsyncMock(return_value=result))
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert message.channel.sent[0]["content"] == (PUBLIC_ERROR_TEXT if structured else text)
    assert str(result) == text


def test_plugin_failure_projects_only_typed_result(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!plugin reload"
    bot.plugin_manager = SimpleNamespace(reload_plugins=Mock(return_value=PluginReloadFailure("private reload failure")))
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert message.channel.sent[0]["content"] == PUBLIC_ERROR_TEXT


def test_help_is_bounded_and_lists_operator_commands(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!help"
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert all(len(item["content"]) <= 2000 for item in message.channel.sent)
    combined = "".join(item["content"] for item in message.channel.sent)
    assert "!error 0..9" in combined and "!forward N" in combined
    assert FOOTER_MARKER not in combined


def test_job_status_does_not_echo_stored_failure_progress(operator_case):
    bot, message, dm, store = operator_case
    message.content = "!job synthetic-job"
    job = SimpleNamespace(id="synthetic-job", status="error", goal="safe goal", progress="PRIVATE JOB PROGRESS")
    bot.bg_jobs = SimpleNamespace(get=lambda job_id: job)
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert "PRIVATE JOB PROGRESS" not in message.channel.sent[0]["content"]


@pytest.mark.parametrize("error_replies", [False, True])
def test_rem_runtime_failure_is_generic_but_already_running_remains_validation(operator_case, error_replies):
    bot, message, dm, store = operator_case
    bot._control["error_replies"] = error_replies
    bot._run_rem_once_guarded = AsyncMock(return_value=(False, "PRIVATE REM FAILURE", None))
    asyncio.run(MaxwellBot._handle_rem_command(bot, message, "now"))
    assert [item["content"] for item in message.channel.sent] == ([PUBLIC_ERROR_TEXT] if error_replies else [])
    message.channel.sent.clear()
    bot._run_rem_once_guarded.return_value = (False, "REM is already running", None)
    asyncio.run(MaxwellBot._handle_rem_command(bot, message, "now"))
    assert [item["content"] for item in message.channel.sent] == ["REM not started: REM is already running"]


def test_x_and_vc_real_failures_use_generic_public_projection(operator_case, monkeypatch):
    bot, message, dm, store = operator_case
    bot.x_client = SimpleNamespace(read=AsyncMock(side_effect=RuntimeError("private X error")))
    asyncio.run(MaxwellBot._handle_x_command(bot, message, "read"))
    assert message.channel.sent[-1]["content"] == PUBLIC_ERROR_TEXT
    assert "private X error" in store.get(0).traceback
    bot.config = SimpleNamespace(ENABLE_VC=True)
    monkeypatch.setattr(bot_module, "voice_recv", None)
    monkeypatch.setattr(bot_module, "_voice_recv_import_error", ImportError("private VC import error"))
    asyncio.run(MaxwellBot._handle_vc_command(bot, message, "join"))
    assert message.channel.sent[-1]["content"] == PUBLIC_ERROR_TEXT
    assert "private VC import error" in store.get(0).traceback


def test_telegram_boundary_uses_generic_projection_and_preserves_context(operator_case, monkeypatch):
    bot, message, dm, store = operator_case
    bot._process_telegram_message_inner = AsyncMock(side_effect=RuntimeError("private Telegram error"))
    reply = AsyncMock()
    monkeypatch.setattr(bot_module, "TelegramMessageAdapter", lambda *args: SimpleNamespace(reply=reply))
    asyncio.run(MaxwellBot._process_telegram_message(bot, {"message_id": 9}, 71, "synthetic", "root", 7, None, "synthetic"))
    reply.assert_awaited_once_with(PUBLIC_ERROR_TEXT)
    assert "private Telegram error" in store.get(0).traceback
    assert store.get(0).context["channel"] == "71"
    assert store.get(0).context["message"] == "9"
