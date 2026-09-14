import asyncio
import copy
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

import error_reporting
import jobs
from autonomy import AutonomyEngine, GateVerdict, TOOL_OUTPUT_FEEDBACK_CHARS
from error_reporting import PUBLIC_ERROR_TEXT
from jobs import BackgroundJobManager, run_background_job
from provider_telemetry import CallMetrics
from providers import ProviderResult
from response_observability import FOOTER_MARKER


class Channel:
    def __init__(self, channel_id=222, error=None):
        self.id = channel_id
        self.guild = SimpleNamespace(id=333)
        self.jump_url = "https://discord.example.test/thread"
        self.sent = []
        self.attempted = []
        self.error = error

    async def send(self, text):
        self.attempted.append(text)
        if self.error is not None:
            raise self.error
        self.sent.append(text)
        return SimpleNamespace(id=1000 + len(self.sent), channel=self)


class JobBot:
    def __init__(self, manager, responses, dispatches=()):
        self.bg_jobs = manager
        self._control = {"footer_enabled": True, "footer_format": "MEASURED_FOOTER"}
        self.config = SimpleNamespace(OLLAMA_MAX_TOKENS=8192)
        self.responses = list(responses)
        self.dispatches = list(dispatches)
        self.model_messages = []
        self._last_native_followup_messages = []
        self._acquire_ai_slot = AsyncMock()
        self._release_ai_slot = AsyncMock()

    def _message_tool_platform(self, message):
        return "discord"

    def _tool_system_prompt(self, *args, **kwargs):
        return ""

    def _build_openai_tools(self, *args, **kwargs):
        return [{"type": "function", "function": {"name": name}} for name in ("shell", "send_message")]

    def _select_tool_protocol(self, tools):
        return False, tools

    async def _generate_response(self, messages, **kwargs):
        self.model_messages.append(copy.deepcopy(messages))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def _native_calls_from(self, response):
        return response.tool_calls

    def _recover_text_tool_calls(self, response):
        return [], response

    async def _dispatch_tool_calls(self, message, response, **kwargs):
        result = self.dispatches.pop(0) if self.dispatches else (str(response), [])
        if isinstance(result, BaseException):
            raise result
        return result


@pytest.fixture
def metrics():
    return CallMetrics(
        call_id="synthetic-call", provider="synthetic", endpoint="primary", model="synthetic-model",
        input_tokens=10, output_tokens=20, reasoning_tokens=0, input_source="provider", output_source="provider",
        elapsed_ms=1000, ttft_ms=100, ttft_estimated=False, stream=True, attempt=1, output_bytes=80,
    )


@pytest.fixture(autouse=True)
def private_store(tmp_path, monkeypatch):
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    store = error_reporting.configure_incident_store(tmp_path / "incidents.json")
    handler = error_reporting.IncidentLoggingHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        yield store
    finally:
        root_logger.removeHandler(handler)
        handler.close()


def background(tmp_path, responses, dispatches=(), *, channel_error=None):
    manager = BackgroundJobManager(str(tmp_path / "jobs.json"))
    channel = Channel(error=channel_error)
    thread = Channel(444)
    message = SimpleNamespace(
        channel=channel, guild=channel.guild, author=SimpleNamespace(id=111), content="synthetic goal",
        create_thread=AsyncMock(return_value=thread),
    )
    job = manager.create(guild_id=333, channel_id=222, user_id=111, goal="synthetic goal")
    manager.attach_runtime(job.id, message=message, channel=channel)
    return JobBot(manager, responses, dispatches), job, message, thread


def tool_response(metrics=None, name="shell"):
    return ProviderResult("", tool_calls=[{"id": "synthetic-tool", "function": {"name": name, "arguments": "{}"}}], metrics=metrics)


def autonomous(tmp_path, channel=None, tools=None):
    channel = channel or Channel()
    bot = SimpleNamespace(
        config=SimpleNamespace(DATA_DIR=str(tmp_path)), _auto_channels={"222"}, _control={},
        tools=tools or {}, user=SimpleNamespace(id=999, name="Synthetic"), bot_name="Synthetic",
        get_channel=lambda channel_id: channel, fetch_channel=AsyncMock(return_value=channel),
        get_user=lambda user_id: None, fetch_user=AsyncMock(), private_channels=[],
        is_closed=lambda: False, rem_log=None, memory=None,
    )
    engine = AutonomyEngine(bot)
    engine._channel_allowed = lambda channel_id: True
    engine._guild_allowed = lambda guild_id: True
    engine._note_autonomy_post = lambda *args: None
    engine._remember_visible_self_message = AsyncMock()
    return engine, channel


@pytest.mark.parametrize("prior_success", [False, True])
def test_job_generation_failure_never_borrows_previous_success(tmp_path, metrics, private_store, prior_success):
    error = RuntimeError("private generation detail " + "x" * 3000 + " FULL GENERATION TAIL")
    error.incident_details = "upstream body " + "y" * 405 + " UPSTREAM TAIL"
    first_id = error_reporting.capture_incident("provider", "underlying generation failure", exception=error)
    responses = [tool_response(metrics), error] if prior_success else [error]
    dispatches = [("partial private work", ["private log contents"])] if prior_success else []
    bot, job, message, thread = background(tmp_path, responses, dispatches)
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert message.channel.sent == [PUBLIC_ERROR_TEXT]
    assert thread.sent[-1] == PUBLIC_ERROR_TEXT
    assert all("MEASURED_FOOTER" not in text and "Finished." not in text for text in thread.sent)
    assert all("partial private work" not in text and "private log" not in text for text in message.channel.sent + thread.sent)
    assert job.result == ("partial private work" if prior_success else "")
    incident = private_store.get(0)
    assert incident.incident_id == first_id == error.incident_id
    assert private_store.get(1) is None
    assert "FULL GENERATION TAIL" in incident.format_report()
    assert "UPSTREAM TAIL" in incident.format_report()
    assert "_generate_response" in incident.traceback
    assert dict(incident.context) == {"job_id": job.id, "guild_id": "333", "channel_id": "222", "user_id": "111", "step": "2" if prior_success else "1"}
    assert bot._release_ai_slot.await_count == (2 if prior_success else 1)
    assert not hasattr(bot, "_delivery_measurements")


@pytest.mark.parametrize("native_followups", [False, True])
def test_job_public_progress_never_echoes_log_results_but_model_gets_full_text(tmp_path, private_store, native_followups):
    raw = "ERROR historical private log with synthetic key " + "x" * 5000 + " FULL LOG TAIL"
    bot, job, message, thread = background(tmp_path, [tool_response(), ProviderResult("safe final answer")], [("", [raw])])
    if native_followups:
        bot._last_native_followup_messages = [{"role": "tool", "content": raw, "tool_call_id": "synthetic-tool"}]
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "done"
    assert raw in str(bot.model_messages[1])
    progress = next(text for text in thread.sent if text.startswith("step "))
    assert progress == "step 1 `shell` — 1 tool call(s), 1 result(s) received"
    assert "historical private log" not in "\n".join(message.channel.sent + thread.sent)
    assert private_store.get(0) is None


def test_job_tool_only_partial_work_survives_later_failure_privately(tmp_path, private_store):
    raw = "completed private tool output " + "x" * 5000 + " PARTIAL TOOL TAIL"
    bot, job, message, thread = background(tmp_path, [tool_response(), RuntimeError("followup failed")], [("", [raw])])
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert raw in private_store.get(0).details
    assert private_store.get(1) is None
    assert message.channel.sent == [PUBLIC_ERROR_TEXT]
    assert "PARTIAL TOOL TAIL" not in "\n".join(thread.sent)
    assert raw in str(bot.model_messages[1])


def test_job_unrecognized_tool_names_are_not_public_progress(tmp_path):
    name = "unrecognized private payload`\n" + "x" * 500
    bot, job, message, thread = background(tmp_path, [tool_response(name=name), ProviderResult("safe final answer")], [("", ["private body"])])
    asyncio.run(run_background_job(bot, job.id))
    assert any("step 1 `tools`" in text for text in thread.sent)
    assert name not in "\n".join(message.channel.sent + thread.sent)


@pytest.mark.parametrize("prior_success", [False, True])
def test_job_slot_failure_is_generic_even_after_output(tmp_path, metrics, private_store, prior_success):
    error = TimeoutError("private slot wait detail " + "x" * 3000 + " SLOT TAIL")
    bot, job, message, thread = background(tmp_path, [tool_response(metrics)], [("partial work", ["result"])])
    bot._acquire_ai_slot.side_effect = [None, error] if prior_success else [error]
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert message.channel.sent == [PUBLIC_ERROR_TEXT]
    assert job.result == ("partial work" if prior_success else "")
    assert bot._release_ai_slot.await_count == int(prior_success)
    assert private_store.get(1) is None
    assert "SLOT TAIL" in private_store.get(0).format_report()
    assert not any("MEASURED_FOOTER" in text or "Finished." in text for text in thread.sent)


def test_job_lost_origin_has_private_context_and_generic_notice(tmp_path, private_store):
    bot, job, message, thread = background(tmp_path, [])
    bot.bg_jobs.attach_runtime(job.id, channel=message.channel)
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert message.channel.sent == [PUBLIC_ERROR_TEXT]
    incident = private_store.get(0)
    assert "lost the origin channel" in incident.details
    assert incident.context["job_id"] == job.id


def test_job_final_delivery_failure_is_not_followed_by_finished_or_body(tmp_path, metrics, private_store):
    error = RuntimeError("private Discord delivery explanation " + "e" * 3000 + " DELIVERY TAIL")
    final = "private undelivered final output " + "x" * 9000 + " FINAL OUTPUT TAIL"
    bot, job, message, thread = background(tmp_path, [ProviderResult(final, metrics=metrics)], channel_error=error)
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert job.result == final[:8000]
    assert message.channel.sent == []
    assert len(message.channel.attempted) == 1
    assert thread.sent[-1] == PUBLIC_ERROR_TEXT
    assert "private undelivered" not in "\n".join(thread.sent)
    assert "Finished." not in "\n".join(thread.sent)
    incident = private_store.get(0)
    assert private_store.get(1) is None
    assert "DELIVERY TAIL" in incident.format_report()
    assert "FINAL OUTPUT TAIL" in incident.details
    assert incident.context["channel_id"] == "222"


def test_job_thread_failure_is_private_without_additional_public_notice(private_store, caplog):
    error = RuntimeError("private thread failure " + "x" * 3000 + " THREAD TAIL")
    thread = Channel(error=error)
    caplog.set_level(logging.DEBUG, logger="jobs")
    asyncio.run(jobs._post_thread(thread, "unsent text", context={"job_id": "synthetic-job"}))
    assert len(thread.attempted) == 1
    assert thread.sent == []
    assert "THREAD TAIL" in private_store.get(0).format_report()
    assert "unsent text" in private_store.get(0).details
    assert "private thread failure" not in caplog.text


def test_job_thread_creation_failure_preserves_success_and_private_trace(tmp_path, private_store):
    bot, job, message, thread = background(tmp_path, [ProviderResult("safe result")])
    message.create_thread.side_effect = RuntimeError("private creation detail " + "x" * 3000 + " CREATION TAIL")
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "done"
    assert len(message.channel.sent) == 1
    assert PUBLIC_ERROR_TEXT not in message.channel.sent
    assert "CREATION TAIL" in private_store.get(0).format_report()


def test_job_dispatch_failure_can_recover_without_losing_model_feedback(tmp_path, private_store):
    error = RuntimeError("full model-facing tool exception " + "x" * 5000 + " DISPATCH TAIL")
    bot, job, message, thread = background(tmp_path, [tool_response(), ProviderResult("recovered")], [error])
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "done"
    assert str(error) in str(bot.model_messages[1])
    assert "DISPATCH TAIL" in private_store.get(0).format_report()
    assert "DISPATCH TAIL" not in "\n".join(message.channel.sent + thread.sent)
    assert PUBLIC_ERROR_TEXT not in message.channel.sent


def test_job_terminal_dispatch_exception_is_not_done(tmp_path, private_store):
    error = RuntimeError("terminal private dispatch error")
    bot, job, message, thread = background(tmp_path, [ProviderResult("private candidate answer")], [error])
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert job.result == "private candidate answer"
    assert message.channel.sent == [PUBLIC_ERROR_TEXT]
    assert private_store.get(1) is None


def test_successful_job_keeps_measured_delivery(tmp_path, metrics, private_store):
    bot, job, message, thread = background(tmp_path, [ProviderResult("safe answer", metrics=metrics)])
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "done"
    assert "MEASURED_FOOTER" in message.channel.sent[-1]
    assert message.channel.sent[-1].endswith(FOOTER_MARKER)
    assert bot._delivery_measurements.lookup("222")[1] is metrics
    assert "MEASURED_FOOTER" not in job.result
    assert private_store.get(0) is None


@pytest.mark.parametrize("delivery_failure", [False, True])
def test_job_error_replies_switch_suppresses_only_failure_notices(tmp_path, private_store, delivery_failure):
    error = RuntimeError("private failure while public notices disabled")
    bot, job, message, thread = background(
        tmp_path, [ProviderResult("intended answer")] if delivery_failure else [error],
        channel_error=error if delivery_failure else None,
    )
    bot._control["error_replies"] = False
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "error"
    assert message.channel.sent == []
    assert len(thread.sent) == 1
    assert thread.sent[0].startswith("Job ")
    assert PUBLIC_ERROR_TEXT not in thread.sent
    assert private_store.get(0) is not None
    assert private_store.get(1) is None


def test_job_listing_omits_private_failure_state(tmp_path):
    bot, job, message, thread = background(tmp_path, [])
    bot.bg_jobs.mark(job.id, status="error", progress="private failure diagnostics", result="private partial work")
    listing = bot.bg_jobs.list_text()
    assert "[error]" in listing and job.id in listing
    assert "private" not in listing
    assert job.progress == "private failure diagnostics"
    assert job.result == "private partial work"


def test_generated_error_looking_answer_is_not_manufactured_failure(tmp_path, private_store):
    text = "Error: a fictional line quoted in the requested answer"
    bot, job, message, thread = background(tmp_path, [ProviderResult(text)])
    asyncio.run(run_background_job(bot, job.id))
    assert job.status == "done"
    assert text in message.channel.sent[0]
    assert private_store.get(0) is None


def test_job_cancellation_keeps_existing_notice_and_propagation(tmp_path, private_store):
    bot, job, message, thread = background(tmp_path, [asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_background_job(bot, job.id))
    assert job.status == "cancelled"
    assert message.channel.sent == []
    assert thread.sent[-1] == f"Job `{job.id}` cancelled."
    assert private_store.get(0) is None


def test_autonomy_tick_captures_complete_exception_before_clipped_state(tmp_path, private_store):
    engine, channel = autonomous(tmp_path)
    error = RuntimeError("private tick detail " + "x" * 5000 + " TICK TAIL")
    engine.observe = AsyncMock(side_effect=error)
    engine.store.patch_state = AsyncMock()
    result = asyncio.run(engine.tick())
    assert result["error"] == str(error)
    assert engine.store.patch_state.call_args.args[0]["last_error"] == str(error)[:2000]
    assert "TICK TAIL" in private_store.get(0).format_report()
    assert private_store.get(1) is None
    assert private_store.get(0).context["user_id"] == "999"
    assert channel.sent == []
    assert engine._tick_in_flight is False


@pytest.mark.parametrize("error_type", [TimeoutError, RuntimeError])
def test_autonomy_action_failures_capture_trace_and_targets_without_public_posts(tmp_path, private_store, error_type):
    engine, channel = autonomous(tmp_path)
    error = error_type("private action explanation " + "x" * 3000 + " ACTION TAIL")
    engine._exec_create_goal = AsyncMock(side_effect=error)
    action = {"kind": "create_goal", "description": "synthetic goal", "target_channel_id": "222", "guild_id": "333", "target_user_id": "111"}
    results = asyncio.run(engine.run_allowed([GateVerdict(action, True)]))
    assert results[0]["result"] == "error"
    assert "ACTION TAIL" in private_store.get(0).format_report()
    assert dict(private_store.get(0).context) == {"action": "create_goal", "tool": "", "guild_id": "333", "channel_id": "222", "user_id": "111"}
    assert private_store.get(1) is None
    assert channel.sent == []


@pytest.mark.parametrize("forbidden", [False, True])
@pytest.mark.parametrize("mode", ["dm", "channel"])
def test_autonomy_discord_send_failures_are_private_and_keep_normal_feedback(tmp_path, private_store, forbidden, mode):
    error_type = discord.Forbidden if forbidden else discord.HTTPException
    error = error_type(SimpleNamespace(status=403 if forbidden else 500, reason="synthetic"), {"message": "private Discord body " + "x" * 3000 + " DISCORD TAIL", "code": 50013})
    channel = Channel(error=error)
    engine, _ = autonomous(tmp_path, channel)
    if mode == "dm":
        engine.bot.get_user = lambda user_id: SimpleNamespace(create_dm=AsyncMock(return_value=channel))
        action = {"kind": "send_dm", "target_user_id": "111", "content": "intended message"}
        result = {}
        asyncio.run(engine._exec_send_dm(action, result))
    else:
        action = {"kind": "post_channel", "target_channel_id": "222", "content": "intended message"}
        result = {}
        asyncio.run(engine._exec_post_channel(action, result))
    assert result["result"] == "error"
    assert channel.sent == []
    assert len(channel.attempted) == 1
    incident = private_store.get(0)
    assert "DISCORD TAIL" in incident.format_report()
    assert incident.context["channel_id"] == "222"
    assert private_store.get(1) is None
    if forbidden and mode == "dm":
        asyncio.run(engine._exec_send_dm(action, {}))
        assert len(channel.attempted) == 1
        assert private_store.get(1) is None


def test_autonomy_dm_creation_failure_is_captured_without_send(tmp_path, private_store):
    engine, channel = autonomous(tmp_path)
    error = discord.HTTPException(SimpleNamespace(status=500, reason="synthetic"), "private DM creation " + "x" * 3000 + " DM CREATE TAIL")
    engine.bot.get_user = lambda user_id: SimpleNamespace(create_dm=AsyncMock(side_effect=error))
    result = {}
    asyncio.run(engine._exec_send_dm({"kind": "send_dm", "target_user_id": "111", "content": "intended"}, result))
    assert result["result"] == "error"
    assert "DM CREATE TAIL" in private_store.get(0).format_report()
    assert private_store.get(0).context["user_id"] == "111"
    assert channel.attempted == []


def test_autonomy_direct_tool_exception_keeps_complete_private_details(tmp_path, private_store):
    error = RuntimeError("private direct tool failure " + "x" * 5000 + " TOOL TAIL")
    tool = SimpleNamespace(execute=AsyncMock(side_effect=error))
    engine, channel = autonomous(tmp_path, tools={"synthetic_tool": tool})
    action = {"kind": "run_tool", "tool_name": "synthetic_tool", "target_channel_id": "222", "tool_args": {"query": "synthetic query"}}
    result = {}
    asyncio.run(engine._exec_run_tool(action, result))
    assert result["error"] == str(error)[:1000]
    assert "TOOL TAIL" in private_store.get(0).format_report()
    assert private_store.get(0).context["guild_id"] == "333"
    assert private_store.get(0).context["channel_id"] == "222"
    assert private_store.get(0).context["tool"] == "synthetic_tool"
    assert tool.execute.call_args.kwargs == {"query": "synthetic query"}
    assert channel.sent == []


@pytest.mark.parametrize("already_captured", [False, True])
def test_autonomy_marked_tool_failure_keeps_model_feedback_and_no_duplicate(tmp_path, private_store, already_captured):
    class MarkedFailure(str):
        pass

    text = "exit status 1: private shell detail " + "x" * 5000 + " MARKED TAIL"
    failure = MarkedFailure(text)
    failure.incident_id = error_reporting.capture_incident("tool", "source-owned failure", details=text) if already_captured else None
    engine, channel = autonomous(tmp_path, tools={"synthetic_tool": SimpleNamespace(execute=AsyncMock(return_value=failure))})
    result = {}
    asyncio.run(engine._exec_run_tool({"kind": "run_tool", "tool_name": "synthetic_tool", "target_channel_id": "222"}, result))
    assert result["result"] == "error"
    assert result["tool_output"] == text[:TOOL_OUTPUT_FEEDBACK_CHARS]
    assert "MARKED TAIL" in private_store.get(0).format_report()
    assert private_store.get(1) is None
    assert channel.sent == []


def test_autonomy_plain_validation_error_string_is_not_new_incident(tmp_path, private_store):
    text = "Error: expected a required target argument"
    engine, channel = autonomous(tmp_path, tools={"synthetic_tool": SimpleNamespace(execute=AsyncMock(return_value=text))})
    result = {}
    asyncio.run(engine._exec_run_tool({"kind": "run_tool", "tool_name": "synthetic_tool", "target_channel_id": "222"}, result))
    assert result["error"] == text
    assert private_store.get(0) is None
    assert channel.sent == []


def test_autonomy_memory_failure_is_captured_before_feedback_truncation(tmp_path, private_store):
    engine, channel = autonomous(tmp_path)
    error = RuntimeError("private memory error " + "x" * 3000 + " MEMORY TAIL")
    engine.bot.memory = SimpleNamespace(add_long_term_memory=AsyncMock(side_effect=error))
    result = {}
    asyncio.run(engine._exec_update_memory({"kind": "update_memory", "content": "synthetic fact"}, result))
    assert result["error"] == str(error)[:1000]
    assert "MEMORY TAIL" in private_store.get(0).format_report()
    assert channel.sent == []


def test_autonomy_do_nothing_and_cancellation_are_unchanged(tmp_path, private_store):
    engine, channel = autonomous(tmp_path)
    result = asyncio.run(engine.run_allowed([GateVerdict({"kind": "do_nothing", "reason": "normal silence"}, True)]))
    assert result[0]["result"] == "skipped"
    engine._exec_create_goal = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(engine.run_allowed([GateVerdict({"kind": "create_goal", "description": "cancelled"}, True)]))
    assert private_store.get(0) is None
    assert channel.sent == []
