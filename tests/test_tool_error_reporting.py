import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import bot_tools
import error_reporting
from bot_tools import ToolFailure
from error_reporting import PUBLIC_ERROR_TEXT, IncidentLoggingHandler, configure_incident_store, register_secrets
from operator_commands import PRIVATE_ERROR_REPORT_MARKER


@pytest.fixture
def incidents(tmp_path, monkeypatch):
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    monkeypatch.setattr(bot_tools, "_get_shared_session", AsyncMock(side_effect=AssertionError("unmocked HTTP")))
    monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(side_effect=AssertionError("unmocked subprocess")))
    return configure_incident_store(tmp_path / "incidents.json")


@pytest.fixture
def root_incidents(incidents):
    handler = IncidentLoggingHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    yield incidents
    root.removeHandler(handler)


class Posted:
    def __init__(self, content):
        self.content = content
        self.edits = []
        self.id = 501

    async def edit(self, *, content):
        self.content = content
        self.edits.append(content)
        return self


class Channel:
    def __init__(self, channel_id=10):
        self.id = channel_id
        self.sent = []
        self.options = []

    async def send(self, content=None, **kwargs):
        posted = Posted(content)
        self.sent.append(posted)
        self.options.append(kwargs)
        return posted


def message_in(channel=None):
    return SimpleNamespace(
        id=91, channel=channel or Channel(), guild=SimpleNamespace(id=20),
        author=SimpleNamespace(id=42), content="synthetic request",
    )


def tool_bot():
    return SimpleNamespace(
        user=SimpleNamespace(id=99), _control={"footer_enabled": True},
        _current_progress_by_channel={},
    )


class Response:
    def __init__(self, status=200, body="", content_type="application/json"):
        self.status = status
        self.body = body
        self.headers = {"Content-Type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self.body

    async def read(self):
        return self.body.encode()


def image_session(monkeypatch, response):
    session = SimpleNamespace(post=Mock(return_value=response), get=Mock(return_value=response))
    monkeypatch.setattr(bot_tools, "_get_shared_session", AsyncMock(return_value=session))
    return session


def test_tool_failure_retains_text_and_redacts_private_record(incidents):
    secret = "synthetic-tool-secret"
    register_secrets([secret])
    exception = RuntimeError("failed " + secret)
    result = bot_tools.tool_failure("tool.synthetic", "Error: " + secret, exception=exception, details="BODY-END " + secret)
    assert isinstance(result, str)
    assert result == "Error: " + secret
    assert result.incident_id == incidents.get(0).incident_id
    assert secret not in incidents.get(0).format_report()
    assert "BODY-END [REDACTED]" in incidents.get(0).details
    assert "RuntimeError" in incidents.get(0).traceback


@pytest.mark.parametrize("status,body,decode_failure", [
    (503, "upstream diagnostic\n" * 1000 + "BODY-END", False),
    (200, "not JSON\n" * 1000 + "BODY-END", False),
    (200, json.dumps({"diagnostic": "decode detail\n" * 1000 + "BODY-END"}), True),
])
def test_image_failures_capture_full_response_body(incidents, monkeypatch, status, body, decode_failure):
    image_session(monkeypatch, Response(status, body))
    if decode_failure:
        monkeypatch.setattr(bot_tools, "_decode_image_response", Mock(side_effect=ValueError("bad image bytes")))
    blob, ext, result = asyncio.run(bot_tools._image_generation_request(
        "https://images.invalid/generate", "synthetic-image-key", {"model": "synthetic"}, timeout_s=1, native=True,
    ))
    assert (blob, ext) == (b"", "png")
    assert isinstance(result, ToolFailure)
    assert "may have been billed" not in result
    assert "not retried" in result
    if status != 200:
        assert body in result
    incident = incidents.get(0)
    assert body in incident.details
    assert incident.context["status"] == str(status)
    assert incidents.get(1) is None
    if status == 200:
        assert "_image_generation_request" in incident.traceback


def test_image_credentials_redacted_in_result_and_private_record(incidents, monkeypatch):
    secret = "synthetic-image-key"
    image_session(monkeypatch, Response(503, "raw key " + secret + " BODY-END"))
    _, _, result = asyncio.run(bot_tools._image_generation_request(
        "https://images.invalid/generate", secret, {"model": "synthetic"}, timeout_s=1, native=True,
    ))
    assert result.startswith("Error: image API returned status 503")
    assert secret not in result
    assert "raw key [REDACTED] BODY-END" in result
    assert secret not in incidents.get(0).format_report()
    assert "raw key [REDACTED] BODY-END" in incidents.get(0).details


def test_pollinations_error_logging_does_not_duplicate_capture(incidents, monkeypatch):
    body = "private HTTP body\n" * 1000 + "BODY-END"
    image_session(monkeypatch, Response(502, body))
    tool = bot_tools.ImageGeneratorTool(SimpleNamespace(config=SimpleNamespace(POLLINATIONS_MODEL="synthetic")))
    handler = IncidentLoggingHandler()
    bot_tools.logger.addHandler(handler)
    try:
        result = asyncio.run(tool._pollinations_generate(message_in(), "synthetic image"))
    finally:
        bot_tools.logger.removeHandler(handler)
    assert result == "Error generating image: Pollinations returned 502."
    assert isinstance(result, ToolFailure)
    assert body in incidents.get(0).details
    assert incidents.get(1) is None


@pytest.mark.parametrize("failure", [TimeoutError("synthetic timeout"), RuntimeError("private transport detail")])
def test_shell_failures_only_edit_exact_public_constant(incidents, failure):
    tool = bot_tools.ShellTool(tool_bot())
    message = message_in()
    tool._run_shell_command = AsyncMock(side_effect=failure)
    result = asyncio.run(tool.execute(message, command="printf synthetic"))
    assert isinstance(result, ToolFailure)
    assert result.startswith("Error")
    assert message.channel.sent[0].content == PUBLIC_ERROR_TEXT
    assert set(message.channel.sent[0].edits) == {PUBLIC_ERROR_TEXT}
    assert incidents.get(1) is None
    assert "Traceback" in incidents.get(0).traceback


@pytest.mark.parametrize("failure", [None, TimeoutError("synthetic timeout"), RuntimeError("synthetic failure")])
def test_shell_error_replies_switch_keeps_incident_private(incidents, failure):
    tool = bot_tools.ShellTool(tool_bot())
    tool.bot._control["error_replies"] = False
    message = message_in()
    tool._run_shell_command = AsyncMock(return_value=(b"private output", b"", 2), side_effect=failure)
    result = asyncio.run(tool.execute(message, command="printf synthetic"))
    assert isinstance(result, ToolFailure)
    assert incidents.get(0) is not None
    assert message.channel.sent[0].content == "working on it…"
    assert PUBLIC_ERROR_TEXT not in message.channel.sent[0].edits


def test_nonzero_shell_keeps_model_output_and_hides_live_output(incidents):
    tool = bot_tools.ShellTool(tool_bot())
    message = message_in()

    async def execute(command, on_progress=None):
        await on_progress(b"PRIVATE-STDOUT", b"PRIVATE-STDERR", 1)
        return b"PRIVATE-STDOUT", b"PRIVATE-STDERR", 2

    tool._run_shell_command = execute
    result = asyncio.run(tool.execute(message, command="false"))
    assert result == "PRIVATE-STDOUT\n[stderr] PRIVATE-STDERR\n[exit code: 2]"
    assert isinstance(result, ToolFailure)
    assert message.channel.sent[0].content == PUBLIC_ERROR_TEXT
    assert all(text in {"working on it…", PUBLIC_ERROR_TEXT} for text in message.channel.sent[0].edits)
    assert "PRIVATE-STDOUT" in incidents.get(0).details
    assert "PRIVATE-STDERR" in incidents.get(0).details
    assert incidents.get(1) is None


def test_successful_shell_diagnostic_quotes_are_not_failures(incidents):
    tool = bot_tools.ShellTool(tool_bot())
    message = message_in()
    output = b"Error: an intentional log quote\nTraceback (most recent call last):"
    tool._run_shell_command = AsyncMock(return_value=(output, b"diagnostic stderr", 0))
    result = asyncio.run(tool.execute(message, command="printf synthetic"))
    assert result == output.decode() + "\n[stderr] diagnostic stderr"
    assert not isinstance(result, ToolFailure)
    assert incidents.get(0) is None
    assert message.channel.sent[0].content == "working on it…"


def test_shell_private_spool_retains_output_beyond_model_cap(incidents, monkeypatch):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._max_output = lambda: 32
    stdout_body = b"stdout " * 3000 + b"STDOUT-END"
    stderr_body = b"stderr " * 3000 + b"STDERR-END"

    async def run():
        stdout = asyncio.StreamReader()
        stdout.feed_data(stdout_body)
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_data(stderr_body)
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=7, wait=AsyncMock(return_value=7))
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        return await tool.execute(message_in(), command="printf synthetic")

    result = asyncio.run(run())
    assert isinstance(result, ToolFailure)
    assert "... (truncated)" in result
    assert "STDOUT-END" not in result
    incident = incidents.get(0)
    assert stdout_body.decode() in incident.details
    assert stderr_body.decode() in incident.details
    assert "[exit code: 7]" in incident.details
    assert result.incident_id == incident.incident_id
    assert incidents.get(1) is None


def test_successful_shell_does_not_capture_callers_handled_exception(incidents, monkeypatch):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")

    async def run():
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"ok")
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0, wait=AsyncMock(return_value=0))
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        try:
            raise RuntimeError("handled by the caller")
        except RuntimeError:
            return await tool._run_shell_command("printf synthetic")

    assert asyncio.run(run()) == (b"ok", b"", 0)
    assert incidents.get(0) is None


def test_multiple_shell_progress_slots_do_not_decorate_error(incidents):
    tool = bot_tools.ShellTool(tool_bot())
    message = message_in()
    tool._run_shell_command = AsyncMock(side_effect=[(b"ok", b"", 0), (b"private", b"", 1)])

    async def run():
        await tool.execute(message, command="true")
        await tool.execute(message, command="false")

    asyncio.run(run())
    assert len(message.channel.sent) == 1
    assert message.channel.sent[0].content == PUBLIC_ERROR_TEXT


def test_validation_and_refusals_do_not_create_incidents(incidents):
    message = message_in()
    shell = bot_tools.ShellTool(tool_bot())
    shell._run_shell_command = AsyncMock(side_effect=AssertionError("invalid shell executed"))
    shell._validate_command = lambda command: "blocked dangerous shell pattern"
    result = asyncio.run(shell.execute(message, command="synthetic blocked command"))
    assert result == "Error executing command: blocked dangerous shell pattern"
    assert not isinstance(result, ToolFailure)
    shell._run_shell_command.assert_not_called()
    file_result = asyncio.run(bot_tools.SendFileTool(tool_bot()).execute(
        message, filename="synthetic.txt", content="%not-base64%", encoding="base64",
    ))
    assert file_result.startswith("Error: could not decode file content:")
    assert not isinstance(file_result, ToolFailure)
    assert incidents.get(0) is None
    assert message.channel.sent == []


def test_shell_cancellation_propagates_without_incident(incidents):
    tool = bot_tools.ShellTool(tool_bot())
    tool._run_shell_command = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(tool.execute(message_in(), command="sleep 1"))
    assert incidents.get(0) is None


@pytest.mark.parametrize("tool_class,params,expected", [
    (bot_tools.EditMessageTool, {"message_id": "123", "content": "new"}, "Error editing message: private diagnostic"),
    (bot_tools.DeleteMessageTool, {"message_id": "123"}, "Error deleting message: private diagnostic"),
])
def test_internally_caught_tool_failures_preserve_text(incidents, tool_class, params, expected):
    message = message_in()
    message.channel.fetch_message = AsyncMock(side_effect=RuntimeError("private diagnostic"))
    result = asyncio.run(tool_class(tool_bot()).execute(message, **params))
    assert result == expected
    assert "RuntimeError: private diagnostic" in incidents.get(0).traceback
    assert incidents.get(1) is None


def test_guide_partial_failure_preserves_original_result_and_full_trace(incidents):
    message = message_in()
    detail = "private thread error " * 100 + "TRACE-END"
    message.create_thread = AsyncMock(side_effect=RuntimeError(detail))
    result = asyncio.run(bot_tools.GuideTool(tool_bot()).execute(message, goal="synthetic goal"))
    assert result == f"Guide posted in channel (no thread: {detail[:200]}) — waiting for replies."
    assert isinstance(result, ToolFailure)
    assert result.incident_id == incidents.get(0).incident_id
    assert "TRACE-END" in incidents.get(0).format_report()
    assert len(message.channel.sent) == 1


def test_guide_ordinary_dm_no_thread_is_not_an_incident(incidents):
    message = message_in()
    message.guild = None
    result = asyncio.run(bot_tools.GuideTool(tool_bot()).execute(message, goal="synthetic goal"))
    assert result == "Guide posted in channel (no thread: DMs have no threads) — waiting for replies."
    assert not isinstance(result, ToolFailure)
    assert incidents.get(0) is None


class SyntheticCaptcha(RuntimeError):
    service = "synthetic"
    sitekey = "synthetic-site-key"
    session_id = "synthetic-session"
    rqdata = "private challenge data " * 100 + "CHALLENGE-END"
    rqtoken = "synthetic-rqtoken"
    should_serve_invisible = False
    errors = ["synthetic challenge"]


def captcha_call(monkeypatch, *, denied_dm=False):
    monkeypatch.setattr(bot_tools.discord, "CaptchaRequired", SyntheticCaptcha, raising=False)
    message = message_in()
    dm = Channel(55)
    message.author.create_dm = AsyncMock(side_effect=RuntimeError("DM delivery blocked")) if denied_dm else AsyncMock(return_value=dm)
    guild = SimpleNamespace(id=77, name="Synthetic Guild", features=[], verification_level=None, member_count=2)
    invite = SimpleNamespace(guild=guild, approximate_member_count=2, accept=AsyncMock(side_effect=SyntheticCaptcha("challenge")))
    bot = tool_bot()
    bot.config = SimpleNamespace(CAPTCHA_HUMAN_SOLVE=True)
    bot._is_admin = Mock(return_value=True)
    bot.fetch_invite = AsyncMock(return_value=invite)
    bot.get_guild = Mock(side_effect=[None, guild])
    bot._retry_invite_with_captcha = AsyncMock(return_value={"guild": {"id": 77}})
    bot._auto_onboard = AsyncMock(return_value={"ok": False})

    async def solve(exception, notify):
        await notify("https://solve.invalid/synthetic-private-challenge")
        return "synthetic-solved-token"

    bot._solve_captcha_with_notify = solve
    return bot_tools.JoinServerTool(bot), message, dm


@pytest.mark.parametrize("denied_dm", [False, True])
def test_captcha_notification_is_private_and_solver_still_runs(incidents, monkeypatch, denied_dm):
    tool, message, dm = captcha_call(monkeypatch, denied_dm=denied_dm)
    result = asyncio.run(tool.execute(message, invite="synthetic-code"))
    assert "JOINED Synthetic Guild" in result
    assert message.channel.sent == []
    message.author.create_dm.assert_awaited_once()
    tool.bot._retry_invite_with_captcha.assert_awaited_once()
    if denied_dm:
        assert dm.sent == []
    else:
        assert "https://solve.invalid/synthetic-private-challenge" in dm.sent[0].content
        assert PRIVATE_ERROR_REPORT_MARKER in dm.sent[0].content
        assert dm.options[0]["allowed_mentions"].everyone is False
    assert "CHALLENGE-END" in incidents.get(0).format_report()


def test_captcha_rechecks_admin_before_private_notification(incidents, monkeypatch):
    tool, message, dm = captcha_call(monkeypatch)
    tool.bot._is_admin = Mock(side_effect=[True, False])
    asyncio.run(tool.execute(message, invite="synthetic-code"))
    message.author.create_dm.assert_not_called()
    assert dm.sent == message.channel.sent == []


def test_private_url_refusal_is_not_an_incident(incidents, monkeypatch):
    session = image_session(monkeypatch, Response())
    with pytest.raises(ValueError, match="private/internal"):
        asyncio.run(bot_tools._fetch_public_url("http://127.0.0.1/private", max_bytes=100))
    session.get.assert_not_called()
    assert incidents.get(0) is None


def test_http_fetch_failure_keeps_full_body_and_original_error(incidents, monkeypatch):
    body = "server failure\n" * 1000 + "BODY-END"
    image_session(monkeypatch, Response(502, body))
    with pytest.raises(ValueError, match="HTTP 502"):
        asyncio.run(bot_tools._fetch_public_url("https://public.invalid/page", max_bytes=100))
    assert body in incidents.get(0).details
    assert "ValueError: HTTP 502" in incidents.get(0).traceback
    assert incidents.get(1) is None


def server_tool(tmp_path):
    bot = tool_bot()
    bot.config = SimpleNamespace(DATA_DIR=tmp_path, MAXWELL_SITE_DIR=tmp_path / "sites")
    tool = bot_tools.SiteServerTool(bot)
    tool._resolve = Mock(return_value=("synthetic", {"server": True}, tmp_path, None))
    tool._mark_server = AsyncMock()
    return tool


def test_site_execution_marker_is_preserved_and_deduplicated(incidents, monkeypatch, tmp_path):
    tool = server_tool(tmp_path)
    failure = bot_tools.site_server.SiteServerExecutionError(
        "could not start backend", operation="start", details="full backend log\n" * 1000 + "BACKEND-END",
    )
    monkeypatch.setattr(bot_tools.site_server, "start", AsyncMock(side_effect=failure))
    result = asyncio.run(tool.execute(message_in(), name="synthetic", action="start"))
    assert result == "Error: could not start backend"
    assert isinstance(result, ToolFailure)
    assert result.incident_id == failure.incident_id
    assert "BACKEND-END" in incidents.get(0).details
    assert incidents.get(1) is None
    tool._mark_server.assert_awaited_once_with("synthetic", {"server": True}, False)


def test_site_validation_is_not_an_execution_incident(incidents, monkeypatch, tmp_path):
    tool = server_tool(tmp_path)
    monkeypatch.setattr(bot_tools.site_server, "start", AsyncMock(side_effect=bot_tools.site_server.SiteServerError("no app.py")))
    result = asyncio.run(tool.execute(message_in(), name="synthetic", action="start"))
    assert result == "Error: no app.py"
    assert not isinstance(result, ToolFailure)
    assert incidents.get(0) is None


def test_existing_backend_log_access_is_unchanged(incidents, monkeypatch, tmp_path):
    tool = server_tool(tmp_path)
    diagnostic = "Error: intentional log read\nTraceback (most recent call last):\nLOG-END"
    monkeypatch.setattr(bot_tools.site_server, "logs", AsyncMock(return_value=diagnostic))
    result = asyncio.run(tool.execute(message_in(), name="synthetic", action="logs"))
    assert result == "synthetic backend logs:\n" + diagnostic
    assert not isinstance(result, ToolFailure)
    assert incidents.get(0) is None


def test_partial_send_failure_retains_original_sent_result(incidents):
    tool = bot_tools.SendMessageTool(tool_bot())
    message = message_in()
    message.channel.send = AsyncMock(side_effect=[Posted("sent"), RuntimeError("private second chunk failure")])
    result = asyncio.run(tool.execute(message, content="a" * 2500, reply=False))
    first_chunk = message.channel.send.await_args_list[0].args[0]
    assert result == "__MESSAGE_SENT__\n" + first_chunk
    assert "private second chunk failure" not in result
    assert "private second chunk failure" in incidents.get(0).traceback
    assert incidents.get(1) is None


def test_shell_timeout_keeps_full_spooled_diagnostics(incidents, monkeypatch):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._kill_container_exec = AsyncMock()
    tool._max_output = lambda: 32
    body = b"timeout stdout " * 3000 + b"TIMEOUT-END"
    message = message_in()

    async def run():
        stdout = asyncio.StreamReader()
        stdout.feed_data(body)
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=None, wait=AsyncMock(side_effect=[TimeoutError("synthetic timeout"), 0]))
        process.kill = Mock(side_effect=lambda: setattr(process, "returncode", -9))
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        return await tool.execute(message, command="printf synthetic")

    result = asyncio.run(run())
    assert result.startswith("Error: Command timed out after")
    assert message.channel.sent[0].content == PUBLIC_ERROR_TEXT
    assert body.decode() in incidents.get(0).details
    assert incidents.get(1) is None


class FaultySpool:
    def __init__(self, raw, fault, state):
        self.raw = raw
        self.fault = fault
        self.state = state

    def write(self, data):
        if self.fault == "write":
            raise OSError("synthetic spool write ENOSPC")
        if self.fault == "short_write":
            data = data[:2]
        return self.raw.write(data)

    def seek(self, offset):
        if self.state.before_read is not None:
            self.state.before_read()
        if self.fault in {"seek", "flush"}:
            raise OSError(f"synthetic spool {self.fault} failed")
        return self.raw.seek(offset)

    def read(self):
        if self.state.before_read is not None:
            self.state.before_read()
        if self.fault == "read":
            raise OSError("synthetic spool read failed")
        return self.raw.read()

    def close(self):
        self.raw.close()
        if self.fault == "close":
            raise OSError("synthetic spool close failed")


@pytest.fixture
def spool_state(monkeypatch):
    real_temporary_file = bot_tools.tempfile.TemporaryFile
    state = SimpleNamespace(fault=None, created=[], before_read=None)

    def allocate(*args, **kwargs):
        assert kwargs["buffering"] == 0
        if state.fault == "allocation":
            raise OSError("synthetic spool allocation ENOSPC")
        spool = FaultySpool(real_temporary_file(*args, **kwargs), state.fault, state)
        state.created.append(spool)
        return spool

    monkeypatch.setattr(bot_tools.tempfile, "TemporaryFile", allocate)
    return state


async def completed_shell(monkeypatch, tool, stdout_body, stderr_body, code=0):
    stdout = asyncio.StreamReader()
    stdout.feed_data(stdout_body)
    stdout.feed_eof()
    stderr = asyncio.StreamReader()
    stderr.feed_data(stderr_body)
    stderr.feed_eof()
    process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code, wait=AsyncMock(return_value=code), kill=Mock())
    monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    result = await tool.execute(message_in(), command="printf synthetic")
    assert asyncio.all_tasks() == {asyncio.current_task()}
    process.kill.assert_not_called()
    return result


@pytest.mark.parametrize("fault", ["allocation", "write", "close"])
def test_capture_io_failure_does_not_change_successful_shell_output(root_incidents, monkeypatch, spool_state, fault):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._max_output = lambda: 100_000
    stdout = b"original stdout\n" * 1000 + b"STDOUT-END"
    stderr = b"original stderr\n" * 1000 + b"STDERR-END"
    expected = asyncio.run(completed_shell(monkeypatch, tool, stdout, stderr))
    spool_state.fault = fault
    actual = asyncio.run(completed_shell(monkeypatch, tool, stdout, stderr))
    assert actual == expected
    assert "STDOUT-END" in actual and "STDERR-END" in actual
    assert not isinstance(actual, ToolFailure)
    assert root_incidents.get(0).source == "tool.shell.capture"
    assert "command result is unchanged" in root_incidents.get(0).summary
    assert f"synthetic spool {fault}" in root_incidents.get(0).format_report()
    assert root_incidents.get(1) is None
    assert all(spool.raw.closed for spool in spool_state.created)


@pytest.mark.parametrize("fault", ["allocation", "write", "seek", "read", "flush", "close", "short_write"])
def test_capture_io_failure_keeps_nonzero_shell_feedback(root_incidents, monkeypatch, spool_state, fault):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    spool_state.fault = fault
    actual = asyncio.run(completed_shell(monkeypatch, tool, b"stdout tail", b"stderr tail", 7))
    assert actual == "stdout tail\n[stderr] stderr tail\n[exit code: 7]"
    assert isinstance(actual, ToolFailure)
    incident = root_incidents.get(0)
    assert "stdout tail" in incident.details and "stderr tail" in incident.details
    assert "[exit code: 7]" in incident.details
    assert actual.incident_id == incident.incident_id
    assert root_incidents.get(1) is None
    assert all(spool.raw.closed for spool in spool_state.created)
    if fault not in {"short_write", "close"}:
        assert "Full diagnostic capture unavailable" in incident.details
    if fault != "short_write":
        assert f"synthetic spool {fault}" in incident.format_report()


class StalledPipe:
    def __init__(self, failure=None):
        self.failure = failure
        self.sent_prefix = False
        self.started = asyncio.Event()
        self.settled = asyncio.Event()
        self.peer_started = None
        self.release = asyncio.Event()

    async def read(self, size):
        if not self.sent_prefix:
            self.sent_prefix = True
            return b"original pipe log\n"
        self.started.set()
        try:
            await self.peer_started.wait()
            if self.failure is not None:
                raise self.failure
            await self.release.wait()
            return b""
        finally:
            self.settled.set()


class RunningProcess:
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = None
        self.killed = asyncio.Event()
        self.reaped = False

    def kill(self):
        self.returncode = -9
        self.killed.set()

    async def wait(self):
        await self.killed.wait()
        self.reaped = True
        return self.returncode


@pytest.mark.parametrize("mode", ["pipe", "timeout", "cancel", "double_cancel"])
@pytest.mark.parametrize("fault", [None, "seek", "read", "flush"])
def test_shell_settles_process_and_sibling_before_capture(root_incidents, monkeypatch, spool_state, mode, fault):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._timeout_seconds = lambda: 0.01 if mode == "timeout" else 10
    spool_state.fault = fault

    async def run():
        stdout = StalledPipe(OSError("synthetic pipe transport failure") if mode == "pipe" else None)
        stderr = StalledPipe()
        stdout.peer_started, stderr.peer_started = stderr.started, stdout.started
        process = RunningProcess(stdout, stderr)
        group_started, group_release = asyncio.Event(), asyncio.Event()
        if mode != "double_cancel":
            group_release.set()

        async def kill_group(*args):
            group_started.set()
            await group_release.wait()

        read_states = []

        def check_settled():
            settled = process.reaped and process.returncode == -9 and stdout.settled.is_set() and stderr.settled.is_set()
            read_states.append(settled)
            assert settled

        spool_state.before_read = check_settled
        tool._kill_container_exec = AsyncMock(side_effect=kill_group)
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        call = asyncio.create_task(tool.execute(message_in(), command="printf synthetic"))
        await asyncio.wait_for(asyncio.gather(stdout.started.wait(), stderr.started.wait()), timeout=1)
        if mode in {"cancel", "double_cancel"}:
            call.cancel()
            await asyncio.wait_for(group_started.wait(), timeout=1)
            if mode == "double_cancel":
                call.cancel()
                group_release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(call, timeout=1)
        else:
            result = await asyncio.wait_for(call, timeout=1)
            assert isinstance(result, ToolFailure)
            assert "synthetic pipe transport failure" in result if mode == "pipe" else "Command timed out" in result
        check_settled()
        assert all(read_states)
        tool._kill_container_exec.assert_awaited_once()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert all(spool.raw.closed for spool in spool_state.created)
    if mode in {"cancel", "double_cancel"}:
        assert root_incidents.get(0) is None
    else:
        assert "original pipe log" in root_incidents.get(0).details
        assert root_incidents.get(1) is None


@pytest.mark.parametrize("mode", ["pipe", "timeout"])
def test_execution_failure_survives_cancellation_during_cleanup(root_incidents, monkeypatch, spool_state, mode):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._timeout_seconds = lambda: 0.01 if mode == "timeout" else 10
    tool._max_output = lambda: 4

    async def run():
        stdout = StalledPipe(OSError("synthetic pipe transport failure") if mode == "pipe" else None)
        stderr = StalledPipe()
        stdout.peer_started, stderr.peer_started = stderr.started, stdout.started
        process = RunningProcess(stdout, stderr)
        group_started, group_release = asyncio.Event(), asyncio.Event()
        read_states = []

        async def kill_group(*args):
            group_started.set()
            await group_release.wait()

        def observe_read():
            read_states.append(process.reaped and stdout.settled.is_set() and stderr.settled.is_set())

        spool_state.before_read = observe_read
        tool._kill_container_exec = AsyncMock(side_effect=kill_group)
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        call = asyncio.create_task(tool.execute(message_in(), command="printf synthetic"))
        await asyncio.wait_for(asyncio.gather(stdout.started.wait(), stderr.started.wait()), timeout=1)
        await asyncio.wait_for(group_started.wait(), timeout=1)
        call.cancel()
        group_release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(call, timeout=1)
        assert process.killed.is_set() and process.reaped and process.returncode == -9
        assert stdout.settled.is_set() and stderr.settled.is_set()
        assert read_states and all(read_states)
        tool._kill_container_exec.assert_awaited_once()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert all(spool.raw.closed for spool in spool_state.created)
    incident = root_incidents.get(0)
    assert "Traceback (most recent call last):" in incident.traceback
    assert "_run_shell_command" in incident.traceback
    assert ("OSError: synthetic pipe transport failure" if mode == "pipe" else "TimeoutError") in incident.traceback
    assert "[stdout]\noriginal pipe log\n" in incident.details
    assert "[stderr]\noriginal pipe log\n" in incident.details
    assert root_incidents.get(1) is None


@pytest.mark.parametrize("exit_code", [0, 7])
def test_completed_exit_status_survives_cleanup_cancellation(root_incidents, monkeypatch, spool_state, exit_code):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._kill_container_exec = AsyncMock()
    tool._max_output = lambda: 4

    async def run():
        stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
        stdout.feed_data(b"complete stdout prefix STDOUT-END\n")
        stderr.feed_data(b"complete stderr prefix STDERR-END\n")
        stdout.feed_eof()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=exit_code, wait=AsyncMock(return_value=exit_code), kill=Mock())
        cleanup_started, cleanup_release, cleanup_finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        settle = tool._settle_shell_execution
        read_states = []

        async def pause_cleanup(*args):
            assert args[-1] is True
            cleanup_started.set()
            await cleanup_release.wait()
            await settle(*args)
            cleanup_finished.set()

        spool_state.before_read = lambda: read_states.append(cleanup_finished.is_set())
        tool._settle_shell_execution = pause_cleanup
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        call = asyncio.create_task(tool._run_shell_command("printf synthetic"))
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        call.cancel()
        cleanup_release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(call, timeout=1)
        assert cleanup_finished.is_set()
        assert stdout.at_eof() and stderr.at_eof()
        assert all(read_states)
        process.wait.assert_awaited_once()
        process.kill.assert_not_called()
        tool._kill_container_exec.assert_not_called()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert all(spool.raw.closed for spool in spool_state.created)
    incident = root_incidents.get(0)
    if exit_code == 0:
        assert incident is None
    else:
        assert incident is not None
        assert incident.summary == "Command exited with status 7"
        assert "[stdout]\ncomplete stdout prefix STDOUT-END\n" in incident.details
        assert "[stderr]\ncomplete stderr prefix STDERR-END\n" in incident.details
        assert "[exit code: 7]" in incident.details
        assert root_incidents.get(1) is None


@pytest.mark.parametrize("fault", ["allocation", "write", "close"])
def test_healthy_shell_result_has_no_execution_incident_on_capture_failure(root_incidents, monkeypatch, spool_state, fault):
    tool = bot_tools.ShellTool(tool_bot())
    tool._ensure_container = AsyncMock(return_value="synthetic-container")
    tool._max_output = lambda: 100_000
    spool_state.fault = fault

    async def run():
        stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
        stdout.feed_data(b"usable log")
        stdout.feed_eof()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0, wait=AsyncMock(return_value=0), kill=Mock())
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        result = await tool._run_shell_command("printf synthetic")
        assert result == (b"usable log", b"", 0)
        assert isinstance(result, bot_tools.ShellResult)
        assert result.incident_id is None
        process.kill.assert_not_called()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert root_incidents.get(0).source == "tool.shell.capture"
    assert root_incidents.get(1) is None
    assert all(spool.raw.closed for spool in spool_state.created)


async def resolver_failure(kind, failure, *, logged=False):
    async def fetch(identifier):
        if logged:
            logging.getLogger("synthetic.transport").error("synthetic transport failed", extra={"incident_exception": failure})
        raise failure

    if kind == "member":
        guild = SimpleNamespace(name="Synthetic Guild", get_member=Mock(return_value=None), fetch_member=fetch)
        return await bot_tools._resolve_member(guild, "123456789012345678")
    bot = SimpleNamespace(get_channel=Mock(return_value=None), fetch_channel=fetch)
    return await bot_tools._get_guild_channel(bot, "123456789012345678")


@pytest.mark.parametrize("kind", ["member", "channel"])
@pytest.mark.parametrize("failure_kind", ["http", "connection", "timeout"])
def test_resolver_transport_failures_keep_full_body_and_one_incident(root_incidents, kind, failure_kind):
    body = "synthetic upstream detail\n" * 1000 + "TRANSPORT-TAIL"
    failure = {
        "http": bot_tools.discord.HTTPException(SimpleNamespace(status=503, reason="synthetic"), body),
        "connection": ConnectionResetError(body),
        "timeout": TimeoutError(body),
    }[failure_kind]
    value, result = asyncio.run(resolver_failure(kind, failure, logged=True))
    assert value is None
    prefix = "Error fetching member" if kind == "member" else "Error finding channel"
    assert result == f"{prefix}: {failure}"
    assert isinstance(result, ToolFailure)
    assert "TRANSPORT-TAIL" in root_incidents.get(0).format_report()
    assert result.incident_id == root_incidents.get(0).incident_id
    assert root_incidents.get(1) is None


@pytest.mark.parametrize("kind", ["member", "channel"])
@pytest.mark.parametrize("failure_kind", ["missing", "forbidden", "bad_request", "validation"])
def test_resolver_policy_and_validation_are_not_incidents(root_incidents, kind, failure_kind):
    failure = {
        "missing": bot_tools.discord.NotFound(SimpleNamespace(status=404, reason="synthetic"), "not found"),
        "forbidden": bot_tools.discord.Forbidden(SimpleNamespace(status=403, reason="synthetic"), "not allowed"),
        "bad_request": bot_tools.discord.HTTPException(SimpleNamespace(status=400, reason="synthetic"), "bad parameter"),
        "validation": ValueError("bad parameter"),
    }[failure_kind]
    value, result = asyncio.run(resolver_failure(kind, failure))
    assert value is None
    assert result.startswith("Error")
    assert not isinstance(result, ToolFailure)
    assert root_incidents.get(0) is None


@pytest.mark.parametrize("kind", ["member", "channel"])
def test_resolver_cancellation_is_not_a_tool_failure(root_incidents, kind):
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(resolver_failure(kind, asyncio.CancelledError()))
    assert root_incidents.get(0) is None


@pytest.mark.parametrize("status", [429, 503])
def test_ordinary_invite_accept_http_failure_keeps_full_body(root_incidents, monkeypatch, status):
    tool, message, dm = captcha_call(monkeypatch)
    body = "ordinary invite upstream detail\n" * 1000 + "INVITE-TAIL"
    failure = bot_tools.discord.HTTPException(SimpleNamespace(status=status, reason="synthetic"), body)

    async def accept():
        logging.getLogger("synthetic.discord").error("synthetic invite failure", extra={"incident_exception": failure})
        raise failure

    tool.bot.fetch_invite.return_value.accept = accept
    result = asyncio.run(tool.execute(message, invite="synthetic-code"))
    if status == 429:
        assert result == "Error joining Synthetic Guild: rate limited (429). Wait a bit and retry — Discord throttles rapid joins."
    else:
        assert result == f"Error joining Synthetic Guild: HTTP {status}: {body[:200]}"
    assert isinstance(result, ToolFailure)
    assert body in root_incidents.get(0).details
    assert result.incident_id == root_incidents.get(0).incident_id
    assert root_incidents.get(1) is None
    assert message.channel.sent == dm.sent == []
