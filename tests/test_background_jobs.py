"""Background sub-agent jobs (jobs.py): caps, budgets, ack-then-deliver.

Style follows the repo: sync test functions, asyncio.run() for async paths,
fake Discord objects instead of a connection.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from control_defaults import SERVER_PROMPT_MAX_BYTES
from bot import DameCurieBot
from error_reporting import PUBLIC_ERROR_TEXT
from job_routing import JobProvider, parse_background_request
from tool_schemas import TOOL_PARAMETERS
from turn_budget import (
    TOOL_GROUPS_CONTEXT,
    ForegroundTurn,
    current_foreground_turn,
    current_tool_groups,
    reset_foreground_turn,
    set_foreground_turn,
)
import jobs as jobs_module
from jobs import (
    JOB_COMPACT_PROMPT,
    JOB_SUMMARY_HEADER,
    JOB_TURN,
    BackgroundJobManager,
    SpawnBackgroundTool,
    background_messages,
    estimate_job_tokens,
    resolve_job_budgets,
    run_background_job,
)


class FakeConfig:
    OPENAI_MAX_TOKENS = 16384


class FakeAuthor:
    def __init__(self, uid="111"):
        self.id = uid


class FakeThread:
    def __init__(self):
        self.id = "thread-1"
        self.sent = []
        self.jump_url = "http://thread.local/t1"
        self.native_result_owner = None
        self.foreign_overwrites = 0

    async def send(self, text):
        self.sent.append(text)
        if self.native_result_owner is not None and text.startswith("step "):
            self.foreign_overwrites += 1
            self.native_result_owner._last_native_followup_messages = [
                {"role": "assistant", "content": "FOREIGN_ROUND"},
                {"role": "user", "content": "FOREIGN_TOOL_RESULT"},
            ]
        return None


class FakeChannel:
    def __init__(self, cid="222", parent_id=""):
        self.id = cid
        self.parent_id = parent_id
        self.sent = []
        self.thread = FakeThread()

    async def send(self, text):
        self.sent.append(text)
        return None


class FakeGuild:
    def __init__(self, gid="333"):
        self.id = gid


class FakeMessage:
    def __init__(self, channel=None, content=",bg a portfolio site"):
        self.id = "900"
        self.channel = channel or FakeChannel()
        self.content = content
        self.author = FakeAuthor()
        self.guild = FakeGuild()

    async def create_thread(self, name=None, auto_archive_duration=None):
        return self.channel.thread


class StubBot:
    def __init__(self, manager):
        self.bg_jobs = manager
        self._control = {}
        self.config = FakeConfig()
        self.memory = SimpleNamespace(get_server_prompt=lambda server_id: None)
        self._get_personality = lambda: "Synthetic personality"


class FakeParentChannel(FakeChannel):
    """The channel that owns a thread; a job started in the thread lands here."""

    def __init__(self, cid="666"):
        super().__init__(cid)
        self.created_threads = []

    async def create_thread(self, **kwargs):
        self.created_threads.append(kwargs)
        self.thread = FakeThread()
        return self.thread


class FakeThreadChannel:
    """A live Discord thread: sendable, and it names its parent channel."""

    def __init__(self, parent):
        self.id = "555"
        self.parent = parent
        self.parent_id = str(getattr(parent, "id", "") or "")
        self.sent = []

    async def send(self, text):
        self.sent.append(text)
        return None


class GateMessage:
    """The message surface the allowlist gates read."""

    def __init__(self, channel):
        self.id = "900"
        self.channel = channel
        self.content = "hello there"
        self.author = SimpleNamespace(id=111, bot=False, display_name="root")
        self.guild = SimpleNamespace(id=333)


class AllowlistBot:
    """Only the bot surface the allowed_channels gates actually touch."""

    _blacklist = set()
    _stop_until = {}
    command_prefix = "!"
    user = SimpleNamespace(id=42)

    _channel_allowed = DameCurieBot._channel_allowed
    _solo_blocks = DameCurieBot._solo_blocks
    _solo_channel_for = DameCurieBot._solo_channel_for
    _message_update_allowed = DameCurieBot._message_update_allowed

    def __init__(self, allowed=(), blocked=()):
        self._control = {
            "bot_enabled": True,
            "allowed_channels": list(allowed),
            "blocked_channels": list(blocked),
        }
        self.dispatched = []

    def _is_admin(self, user_id):
        return False

    def _load_control(self):
        return None

    def _dispatch_reply(self, message, content, *, directed):
        self.dispatched.append((str(getattr(message, "id", "")), bool(directed)))
        return "started"


class FakeRefusingMessage(FakeMessage):
    """A thread origin, where Discord refuses a thread of a thread."""

    async def create_thread(self, name=None, auto_archive_duration=None):
        raise RuntimeError("no nested threads")


class FakeDMMessage(FakeMessage):
    """A DM: discord.py refuses to create a thread without guild info."""

    def __init__(self, channel=None):
        super().__init__(channel=channel)
        self.guild = None

    async def create_thread(self, name=None, auto_archive_duration=None):
        raise ValueError("This message does not have guild info attached")


# budgets


def test_budgets_default_to_extended_headroom():
    budgets = resolve_job_budgets({}, FakeConfig())
    assert "max_tokens" not in budgets
    assert budgets["timeout_seconds"] == 7200
    assert budgets["max_iters"] == 100
    assert budgets["compact_at_tokens"] == 180_000
    turn = ForegroundTurn.from_controls({"turn_output_token_budget": 1})
    # The unconfigured attempt ceiling was removed on 2026-10-03; only an
    # explicit control sets one.
    assert turn.attempt_limit is None
    assert ForegroundTurn.from_controls({"turn_generation_attempt_budget": 12}).attempt_limit == 12
    assert 590 < turn.remaining_seconds <= 600
    assert turn.reserve_attempt(45) == 45
    assert turn.attempts == 1
    assert not hasattr(turn, "output_remaining")


def test_budgets_clamp_to_hard_caps():
    budgets = resolve_job_budgets(
        {"bg_max_tokens": 999999, "bg_timeout_seconds": 99999, "bg_max_iters": 9999,
         "bg_compact_at_tokens": 9_999_999},
        FakeConfig(),
    )
    assert budgets == {"timeout_seconds": 14400, "max_iters": 200, "compact_at_tokens": 900_000}


def test_budgets_zero_means_default(monkeypatch):
    monkeypatch.setenv("BG_MAX_TOKENS", "131072")
    budgets = resolve_job_budgets({"bg_max_tokens": 0}, FakeConfig())
    assert "max_tokens" not in budgets


def test_budgets_env_override(monkeypatch):
    monkeypatch.setenv("BG_MAX_ITERS", "42")
    budgets = resolve_job_budgets({}, FakeConfig())
    assert budgets["max_iters"] == 42


# manager


def test_manager_caps_per_user_then_global(tmp_path):
    manager = BackgroundJobManager(
        data_path=str(tmp_path / "jobs.json"), max_jobs=2, max_per_user=1
    )
    assert parse_background_request("build a page") == ("build a page", JobProvider.MAIN, None)
    assert parse_background_request("-- build a page") == ("build a page", JobProvider.MAIN, None)
    for selector in ("--provider main -- goal", "--provider aux -- goal", "--model other -- goal"):
        with pytest.raises(ValueError, match="active provider configuration"):
            parse_background_request(selector)
    for selectors in ({"provider": "aux"}, {"model": "other"}):
        with pytest.raises(ValueError, match="active provider configuration"):
            manager.create(guild_id="g", channel_id="c", user_id="u1", goal="one", **selectors)
    assert not {"provider", "model"} & TOOL_PARAMETERS["spawn_background"]["properties"].keys()
    manager.create(guild_id="g", channel_id="c", user_id="u1", goal="one")
    with pytest.raises(RuntimeError, match="ALREADY_RUNNING"):
        manager.create(guild_id="g", channel_id="c", user_id="u1", goal="two")
    manager.create(guild_id="g", channel_id="c", user_id="u2", goal="three")
    with pytest.raises(RuntimeError, match="ALL_BUSY"):
        manager.create(guild_id="g", channel_id="c", user_id="u3", goal="four")


def test_manager_cancel_owner_vs_stranger(tmp_path):
    manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
    job = manager.create(guild_id="g", channel_id="c", user_id="owner", goal="x")
    ok, _ = manager.cancel(job.id, requester_id="stranger", is_admin=False)
    assert ok is False
    ok, _ = manager.cancel(job.id, requester_id="", is_admin=False)
    assert ok is False
    ok, msg = manager.cancel(job.id, requester_id="owner", is_admin=False)
    assert ok is True and job.id in msg
    assert manager.get(job.id).status == "cancelled"


def test_manager_persistence_round_trip(tmp_path):
    path = str(tmp_path / "jobs.json")
    manager = BackgroundJobManager(data_path=path)
    job = manager.create(guild_id="g", channel_id="c", user_id="u", goal="remember me")
    manager.mark(job.id, status="done", result="did it")
    raw = json.load(open(path, encoding="utf-8"))
    assert raw["jobs"][job.id]["status"] == "done"
    again = BackgroundJobManager(data_path=path)
    assert again.get(job.id).result == "did it"


def test_manager_restart_cancels_inflight(tmp_path):
    path = str(tmp_path / "jobs.json")
    manager = BackgroundJobManager(data_path=path)
    job = manager.create(guild_id="g", channel_id="c", user_id="u", goal="x")
    manager.mark(job.id, status="running")
    manager._save()
    again = BackgroundJobManager(data_path=path)
    assert again.get(job.id).status == "cancelled"


# spawn tool


@pytest.mark.parametrize("selectors", [{}, {"provider": "main"}, {"provider": "aux"}, {"model": "other"}])
def test_spawn_tool_acks_and_tracks_job(tmp_path, selectors):
    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        tool = SpawnBackgroundTool(StubBot(manager))
        message = FakeMessage()
        launched = {}

        async def fake_runner(bot, jid):
            launched["jid"] = jid

        import jobs as jobs_mod

        real = jobs_mod.run_background_job
        jobs_mod.run_background_job = fake_runner
        try:
            result = await tool.execute(message, goal="a portfolio site", **selectors)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            jobs_mod.run_background_job = real
        if selectors:
            assert "provider/model selection is not available to tools" in result
            assert manager.active_count() == 0
            assert launched == {}
        else:
            assert "Background job `" in result
            assert manager.active_count() == 1
            assert launched["jid"] is not None
        return result

    result = asyncio.run(scenario())
    if not selectors:
        assert "send_message" in result


def test_spawn_tool_refuses_recursion(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        tool = SpawnBackgroundTool(StubBot(manager))
        token = JOB_TURN.set(True)
        try:
            return await tool.execute(FakeMessage(), goal="nested")
        finally:
            JOB_TURN.reset(token)

    assert "ALREADY INSIDE" in asyncio.run(scenario())


def test_spawn_tool_second_spawn_tells_model_to_ack(tmp_path):
    """The live turn's own second attempt is a limit, not "you are inside a job"."""

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        tool = SpawnBackgroundTool(StubBot(manager))
        message = FakeMessage()
        first = await tool.execute(message, goal="first")
        assert "Background job `" in first
        return await tool.execute(message, goal="second")

    result = asyncio.run(scenario())
    assert "ALREADY RUNNING" in result
    assert "ALREADY INSIDE" not in result
    assert "send_message" in result


# runner (ack-then-deliver with stubbed LLM seams)


class RunnerStubBot(StubBot):
    """Runner seams plus the allowlist gate the real bot always has."""

    _channel_allowed = DameCurieBot._channel_allowed

    def __init__(self, manager):
        super().__init__(manager)
        self.slot_priority = None
        self.generated_with = {}
        self.generated_messages = []
        self.generated_prompts = []
        self.generated_turns = []
        self.catalog_groups = []
        self.discover = False
        self.refuse_ending = False
        self.long_steps = 0
        self.compact_requests = []
        self.compact_kwargs = []
        self.summary_text = ""
        self.dispatch_delay = 0.0
        self.dispatch_events = []

    def _message_tool_platform(self, message):
        return "discord"

    def _tool_system_prompt(self, platform, message=None, content=None):
        return "catalog: " + (", ".join(sorted(current_tool_groups() or [])) or "core")

    def _build_openai_tools(self, platform, message=None, content=None):
        groups = current_tool_groups()
        assert groups is not None
        self.catalog_groups.append(set(groups))
        names = ["more_tools", "extra_tool"] if "identity" in groups else ["more_tools"]
        return [{"type": "function", "function": {"name": name}} for name in names] if self.discover else []

    def _select_tool_protocol(self, openai_tools):
        return False, openai_tools

    async def _acquire_ai_slot(self, timeout, *, priority="background", key=""):
        self.slot_priority = priority

    async def _release_ai_slot(self):
        return None

    async def _generate_response(self, messages, **kwargs):
        if messages[0]["content"] == JOB_COMPACT_PROMPT:
            self.compact_requests.append(messages[1]["content"])
            self.compact_kwargs.append(dict(kwargs))
            return self.summary_text or f"summary {len(self.compact_requests)} of the older steps"
        self.generated_with = dict(kwargs)
        self.generated_messages = messages
        self.generated_prompts.append(messages[0]["content"])
        self.generated_turns.append(current_foreground_turn())
        if self.discover and len(self.generated_prompts) == 1:
            return "discover"
        if self.refuse_ending and len(self.generated_prompts) == 1 + self.discover:
            return "refused"
        if len(self.generated_prompts) <= self.discover + self.refuse_ending + self.long_steps:
            return f"step {len(self.generated_prompts)}"
        return "built it: http://example.local/site"

    def _native_calls_from(self, response):
        if response.startswith("step "):
            return [{"id": "call_" + response.split()[1], "type": "function", "function": {
                "name": "shell", "arguments": '{"command":"true"}',
            }}]
        if response == "refused":
            return [{"id": "send_1", "type": "function", "function": {
                "name": "send_message", "arguments": '{"content":"page"}',
            }}]
        return [{"id": "discover_1", "type": "function", "function": {
            "name": "more_tools", "arguments": '{"group":"identity"}',
        }}] if response == "discover" else []

    async def _dispatch_tool_calls(self, message, response, **kwargs):
        self.dispatch_events.append("started")
        try:
            await asyncio.sleep(self.dispatch_delay)
        finally:
            await asyncio.sleep(0)
            self.dispatch_events.append("settled")
        self.dispatch_events.append("completed")
        self._last_native_followup_messages = []
        if response == "discover":
            current_tool_groups().add("identity")
            call = kwargs["native_tool_calls"][0]
            self._last_native_followup_messages = [
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": call["id"], "content": "Expanded identity tools."},
            ]
            return "", ["Expanded identity tools."]
        if response == "refused":
            refusal = (
                "Tool send_message: Error - batch refused because the batch carries "
                "40,000 bytes of arguments; the limit is 32,000; no calls in this batch were executed."
            )
            call = kwargs["native_tool_calls"][0]
            self._last_native_followup_messages = [
                {"role": "assistant", "content": "refused", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": call["id"], "content": refusal},
            ]
            return "refused", [refusal]
        if str(response).startswith("step "):
            call = kwargs["native_tool_calls"][0]
            result = f"Tool shell: ok {call['id']} " + "x" * 3000
            self._last_native_followup_messages = [
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": call["id"], "content": result},
            ]
            return "", [result]
        return str(response), []


@pytest.mark.parametrize("long_steps", [0, 10])
@pytest.mark.parametrize("refuse_ending", [False, True])
@pytest.mark.parametrize("discover", [False, True])
@pytest.mark.parametrize("descendant", [False, True])
@pytest.mark.parametrize("dispatch_delay", [0.0, 0.2])
def test_runner_delivers_final_reply_with_mention(
    tmp_path, monkeypatch, discover, descendant, dispatch_delay, refuse_ending, long_steps,
):
    # This test covers the model summary; masking would keep these prompts
    # under the limit, so it is off here. Masking has its own test.
    monkeypatch.setattr(jobs_module, "BG_MASK_KEEP_ROUNDS", 10_000)
    oversized_prompt = "x" * (SERVER_PROMPT_MAX_BYTES + 1)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        bot.discover = discover
        bot.refuse_ending = refuse_ending
        bot.long_steps = long_steps
        bot.dispatch_delay = dispatch_delay
        bot.command_prefix = "?"
        bot.memory.get_server_prompt = lambda server_id: oversized_prompt
        message = FakeMessage()
        message.channel.thread.native_result_owner = bot
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        if long_steps:
            head = estimate_job_tokens(background_messages(bot, job, message, "discord"))
            call = {"id": "call_9", "type": "function", "function": {"name": "shell", "arguments": '{"command":"true"}'}}
            step_tokens = estimate_job_tokens([
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": "call_9", "content": "Tool shell: ok call_9 " + "x" * 3000},
            ])
            # Compaction fires at the 7th and the 10th long step. 4 kept
            # steps fit under the limit minus the summary reserve.
            limit = head + int(6.5 * step_tokens)
            assert head + 4 * step_tokens < limit - min(limit // 5, 16_000)
            bot._control["bg_compact_at_tokens"] = limit
        turn = ForegroundTurn(12, asyncio.get_running_loop().time() + 600) if descendant else None
        turn_token = set_foreground_turn(turn) if descendant else None
        parent_groups = {"games"}
        groups_token = TOOL_GROUPS_CONTEXT.set(parent_groups)
        try:
            await run_background_job(bot, job.id)
            assert current_tool_groups() is parent_groups and parent_groups == {"games"}
            assert current_foreground_turn() is turn
            assert all(observed is turn for observed in bot.generated_turns)
        finally:
            TOOL_GROUPS_CONTEXT.reset(groups_token)
            if turn_token is not None:
                reset_foreground_turn(turn_token)
        return manager.get(job.id), message.channel, bot

    job, channel, bot = asyncio.run(scenario())
    assert job.status == "done"
    assert bot.slot_priority == "background"  # user turns outrank it
    assert not {"disable_reasoning", "max_tokens", "temperature", "model", "prefer_fallback"} & bot.generated_with.keys()
    assert bot.dispatch_events == ["started", "settled", "completed"] * (1 + discover + refuse_ending + long_steps)
    if not descendant:
        assert 600 < bot.generated_with["timeout"] <= 7200
    system_prompt = bot.generated_messages[0]["content"]
    assert "Stored server prompt omitted" in system_prompt
    assert "?longprompt" in system_prompt
    assert oversized_prompt not in system_prompt
    assert bot.memory.get_server_prompt("333") == oversized_prompt
    expected_groups = [set(), {"identity"}] if discover else [set()]
    assert bot.catalog_groups == expected_groups + expected_groups[-1:] * (refuse_ending + long_steps)
    assert channel.thread.foreign_overwrites == int(discover) + refuse_ending + long_steps
    assert "catalog: core" in bot.generated_prompts[0]
    if discover and not long_steps:
        assert "catalog: identity" in bot.generated_prompts[1]
        assert len(bot.generated_messages) == 4 + 2 * refuse_ending
        assert bot.generated_messages[2]["tool_calls"][0]["id"] == "discover_1"
        assert bot.generated_messages[3]["tool_call_id"] == "discover_1"
    if discover:
        assert "FOREIGN_" not in json.dumps(bot.generated_messages)
        assert [tool["function"]["name"] for tool in bot.generated_with["tools"]] == ["more_tools", "extra_tool"]
    assert any("<@111>" in text and job.id in text for text in channel.sent)
    assert any("http://example.local/site" in text for text in channel.sent)
    if long_steps:
        # Older steps are replaced by a model-written summary; the newest four
        # rounds stay verbatim and keep their call/result pairing.
        compactions = 2
        assert len(bot.compact_requests) == compactions
        assert all(set(kwargs) == {"timeout"} for kwargs in bot.compact_kwargs)
        assert "Steps to summarize:" in bot.compact_requests[0]
        assert "Previous summary:" not in bot.compact_requests[0]
        assert "null" not in bot.compact_requests[0]
        assert all("Previous summary:\n" + JOB_SUMMARY_HEADER in r for r in bot.compact_requests[1:])
        final = bot.generated_messages
        assert final[2]["content"].startswith(JOB_SUMMARY_HEADER)
        assert final[2]["role"] == "assistant"
        assert any(f"summary {compactions} of the older steps" == text for text in channel.thread.sent)
        assert f"summary {compactions} of the older steps" in final[2]["content"]
        assert len(final) == 3 + 2 * 4
        assert [m["tool_calls"][0]["id"] for m in final[3::2]] == [m["tool_call_id"] for m in final[4::2]]
        assert sum("Context compacted" in text for text in channel.thread.sent) == compactions
    else:
        assert bot.compact_requests == []


@pytest.mark.parametrize(
    ("failure", "discover"),
    [
        ("generation", False), ("catalog", False),
        ("deadline", False), ("deadline", True), ("expired", True),
        ("unresolved", False),
        ("compaction", False),
        ("summary_too_big", False),
    ],
)
def test_runner_marks_error_and_notifies(tmp_path, monkeypatch, failure, discover):
    class BrokenBot(RunnerStubBot):
        async def _generate_response(self, messages, **kwargs):
            if failure in {"generation", "catalog"}:
                raise RuntimeError("provider down")
            return await super()._generate_response(messages, **kwargs)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = BrokenBot(manager)
        bot.discover = discover
        bot.dispatch_delay = 0.2
        if failure == "unresolved":
            bot.refuse_ending = True
            bot._control["bg_max_iters"] = 1
        if failure == "compaction":
            bot.long_steps = 6
            bot._control["bg_compact_at_tokens"] = 1
        if failure == "summary_too_big":
            bot.long_steps = 6
            bot.summary_text = "s" * 300_000
            step_tokens = estimate_job_tokens([
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "call_9", "type": "function", "function": {"name": "shell", "arguments": '{"command":"true"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_9", "content": "Tool shell: ok call_9 " + "x" * 3000},
            ])
            bot._control["bg_compact_at_tokens"] = 400 + int(2.5 * step_tokens)
        provider = SimpleNamespace(
            generate_response=bot._generate_response, close=AsyncMock(),
        )
        bot._create_background_provider = Mock(return_value=provider)
        if failure == "catalog":
            monkeypatch.setattr(bot, "_build_openai_tools", Mock(side_effect=RuntimeError("catalog unavailable")))
        message = FakeMessage()
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="x",
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        parent_groups = {"games"}
        token = TOOL_GROUPS_CONTEXT.set(parent_groups)
        turn = ForegroundTurn(
            12, asyncio.get_running_loop().time() + (0.05 if failure == "deadline" else -1),
        )
        turn_token = set_foreground_turn(turn) if failure in {"deadline", "expired"} else None
        try:
            task = asyncio.create_task(run_background_job(bot, job.id))
            manager.track_task(job.id, task)
            await task
            assert current_tool_groups() is parent_groups and parent_groups == {"games"}
            assert not JOB_TURN.get()
            assert not manager._tasks and not manager.runtime(job.id)
            if turn_token is not None:
                assert current_foreground_turn() is turn
                assert all(observed is turn for observed in bot.generated_turns)
                assert turn.attempts == 0
        finally:
            TOOL_GROUPS_CONTEXT.reset(token)
            if turn_token is not None:
                reset_foreground_turn(turn_token)
        provider.close.assert_not_awaited()
        bot._create_background_provider.assert_not_called()
        return manager.get(job.id), message.channel, bot

    job, channel, bot = asyncio.run(scenario())
    assert job.status == "error"
    assert job.finished_at > 0
    assert channel.sent == [PUBLIC_ERROR_TEXT]
    if failure in {"deadline", "expired"}:
        assert job.progress == "Foreground turn deadline expired"
        assert job.result == ""
        assert bot.dispatch_events == (["started", "settled"] if failure == "deadline" else [])
        assert len(bot.generated_turns) == int(failure == "deadline")
        assert channel.thread.sent[-1] == PUBLIC_ERROR_TEXT
    if failure == "expired":
        assert bot.slot_priority is None and bot.catalog_groups == []
    if failure == "summary_too_big":
        assert job.progress.startswith(
            "context compaction failed at step 3: after compaction the prompt is still about "
        )
        assert len(bot.compact_requests) == 1
    if failure == "compaction":
        assert job.progress == (
            "context compaction failed at step 1: the history has one step and the prompt "
            "reaches the 1-token compaction limit, so nothing can be compacted"
        )
        assert bot.compact_requests == []
    if failure == "unresolved":
        assert job.progress.startswith(
            "the job reached its step limit with an unresolved tool error: "
            "Tool send_message: Error - batch refused"
        )
        assert job.result == "refused"


def test_manager_list_text_guild_filtering(tmp_path):
    manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
    j1 = manager.create(guild_id="g1", channel_id="c1", user_id="u1", goal="goal 1")
    j2 = manager.create(guild_id="g2", channel_id="c2", user_id="u2", goal="goal 2")

    lines_g1 = manager.list_text(guild_id="g1")
    assert j1.id in lines_g1
    assert j2.id not in lines_g1

    lines_all = manager.list_text()
    assert j1.id in lines_all
    assert j2.id in lines_all


def test_runner_splits_long_delivery_messages(tmp_path):
    class LongOutputBot(RunnerStubBot):
        async def _generate_response(self, messages, **kwargs):
            return "A" * 3500

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = LongOutputBot(manager)
        message = FakeMessage()
        job = manager.create(guild_id="g", channel_id="222", user_id="111", goal="long")
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return message.channel

    channel = asyncio.run(scenario())
    assert len(channel.sent) >= 2
    for msg in channel.sent:
        assert len(msg) <= 1900


# progress thread targeting and honest thread failure


@pytest.mark.parametrize("configured_ids", [[], ["666"], [666]])
def test_runner_puts_progress_thread_in_parent_channel_for_thread_origin(tmp_path, monkeypatch, configured_ids):
    """A job started inside a thread cannot nest: progress goes to its parent."""
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        bot._control["allowed_channels"] = configured_ids
        parent = FakeParentChannel()
        channel = FakeThreadChannel(parent)
        message = FakeRefusingMessage(channel=channel)
        job = manager.create(
            guild_id="g", channel_id="555", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), parent, channel

    job, parent, channel = asyncio.run(scenario())
    assert job.status == "done"
    assert [entry["name"] for entry in parent.created_threads] == ["build: a portfolio site"]
    assert job.thread_id == "thread-1"
    assert job.thread_error == ""
    assert parent.thread.sent[0].startswith(f"Job `{job.id}` running")
    assert not any("no progress thread" in text for text in channel.sent)


def test_runner_reports_missing_progress_thread_instead_of_silent_success(tmp_path):
    """The work still finishes; the missing thread is stated, not implied."""

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        message = FakeRefusingMessage()
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel

    job, channel = asyncio.run(scenario())
    assert job.status == "done"
    assert job.thread_id == ""
    assert job.thread_error == "RuntimeError"
    notices = [text for text in channel.sent if "no progress thread" in text]
    assert len(notices) == 1
    assert "The job continues; its result lands here." in notices[0]
    assert PUBLIC_ERROR_TEXT not in channel.sent
    assert any("<@111>" in text and job.id in text for text in channel.sent)


def test_runner_keeps_thread_failure_quiet_when_error_replies_are_off(tmp_path):
    """The record is still honest even when the notice is configured away."""

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        bot._control = {"error_replies": False}
        message = FakeRefusingMessage()
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel

    job, channel = asyncio.run(scenario())
    assert job.status == "done"
    assert job.thread_error == "RuntimeError"
    assert not any("no progress thread" in text for text in channel.sent)


def test_runner_dm_job_reports_no_thread_without_claiming_one(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        message = FakeDMMessage()
        job = manager.create(
            guild_id="DM", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel

    job, channel = asyncio.run(scenario())
    assert job.status == "done"
    assert job.thread_id == ""
    assert job.thread_error == ""
    assert not any("progress thread" in text for text in channel.sent)


def test_job_command_shows_thread_link_or_honest_thread_failure(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(
            data_path=str(tmp_path / "jobs.json"), max_jobs=2, max_per_user=1
        )
        channel = FakeChannel("222")
        bot = SimpleNamespace(
            command_prefix="!",
            _control={},
            _is_admin=lambda _uid: False,
            bg_jobs=manager,
        )
        message = SimpleNamespace(
            content="",
            channel=channel,
            author=SimpleNamespace(id=111),
            guild=SimpleNamespace(id="333"),
        )
        linked = manager.create(
            guild_id="333", channel_id="222", user_id="111", goal="linked job"
        )
        manager.mark(linked.id, thread_id="thread-1")
        threadless = manager.create(
            guild_id="333", channel_id="222", user_id=222, goal="threadless job"
        )
        manager.mark(threadless.id, thread_error="Forbidden")
        message.content = f"!job {linked.id}"
        await DameCurieBot._handle_command(bot, message)
        message.content = f"!job {threadless.id}"
        await DameCurieBot._handle_command(bot, message)
        return channel

    channel = asyncio.run(scenario())
    assert "https://discord.com/channels/333/thread-1" in channel.sent[0]
    assert "no progress thread: Forbidden" in channel.sent[1]


# allowed_channels: a thread inherits an allowed parent, never a blocked one


def test_channel_allowed_inherits_an_allowed_parent_but_not_a_blocked_one(monkeypatch):
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)
    bot = AllowlistBot(allowed=["100"], blocked=["200"])
    allowed_ids = {"100"}
    assert bot._channel_allowed(FakeChannel("100"), allowed_ids) is True
    assert bot._channel_allowed(FakeChannel("999"), allowed_ids) is False
    assert (
        bot._channel_allowed(FakeThreadChannel(SimpleNamespace(id="100")), allowed_ids)
        is True
    )
    assert (
        bot._channel_allowed(FakeThreadChannel(SimpleNamespace(id="999")), allowed_ids)
        is False
    )
    # The regression: a thread of a blocked parent was denied before the
    # inheritance existed, so it must stay denied.
    assert (
        bot._channel_allowed(FakeThreadChannel(SimpleNamespace(id="200")), allowed_ids)
        is False
    )
    # An explicit thread allowance is the operator's own choice and survives a
    # blocked parent; only the inherited allowance is withheld.
    assert (
        bot._channel_allowed(
            FakeThreadChannel(SimpleNamespace(id="200")), {"100", "555"}
        )
        is True
    )
    # A plain channel is never judged by its category id.
    assert bot._channel_allowed(FakeChannel("100", parent_id="200"), allowed_ids) is True


def test_edit_gate_applies_the_same_parent_rule(monkeypatch):
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)
    bot = AllowlistBot(allowed=["100"], blocked=["200"])
    assert DameCurieBot._message_update_allowed(bot, GateMessage(FakeChannel("100"))) is True
    assert DameCurieBot._message_update_allowed(bot, GateMessage(FakeChannel("999"))) is False
    assert (
        DameCurieBot._message_update_allowed(
            bot, GateMessage(FakeThreadChannel(SimpleNamespace(id="100")))
        )
        is True
    )
    assert (
        DameCurieBot._message_update_allowed(
            bot, GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
        )
        is False
    )
    # Same explicit-choice rule through the edit gate.
    explicit = AllowlistBot(allowed=["100", "555"], blocked=["200"])
    assert (
        DameCurieBot._message_update_allowed(
            explicit, GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
        )
        is True
    )


def test_on_message_gate_denies_a_thread_of_a_blocked_parent(monkeypatch):
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)
    bot = AllowlistBot(allowed=["100"], blocked=["200"])
    message = GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
    asyncio.run(DameCurieBot._on_message_impl(bot, message))
    assert bot.dispatched == []


# a job inside an explicitly allowed thread must not touch its refused parent


class ThreadScopedJobBot(RunnerStubBot):
    """A bot whose allowlist names one thread inside a refused parent."""

    def __init__(self, manager, allowed, blocked):
        super().__init__(manager)
        self._control = {
            "allowed_channels": list(allowed),
            "blocked_channels": list(blocked),
            "error_replies": True,
        }


@pytest.mark.parametrize("allowed", [[], ["555"], ["555", "666"], ["555", 666]])
@pytest.mark.parametrize("blocked", [["666"], [666]])
def test_runner_never_creates_a_progress_thread_in_a_blocked_parent(tmp_path, monkeypatch, allowed, blocked):
    """The allowed thread is usable; the refused parent gets nothing at all."""
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = ThreadScopedJobBot(manager, allowed=allowed, blocked=blocked)
        parent = FakeParentChannel("666")
        channel = FakeThreadChannel(parent)
        message = FakeRefusingMessage(channel=channel)
        job = manager.create(
            guild_id="g", channel_id="555", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), parent, channel

    job, parent, channel = asyncio.run(scenario())
    # The refused parent is untouched: no thread, and not one single message.
    assert parent.created_threads == []
    assert parent.sent == []
    # The job itself still runs to completion where the requester is.
    assert job.status == "done"
    assert job.thread_id == ""
    assert job.thread_error == "the origin thread's parent channel is not allowed for this bot"
    assert any("no progress thread" in text for text in channel.sent)
    assert any("<@111>" in text and job.id in text for text in channel.sent)


def test_runner_still_places_progress_in_a_refused_parent_for_a_plain_channel(tmp_path, monkeypatch):
    """A plain-channel !bg keeps its existing placement, refused parent or not."""
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = ThreadScopedJobBot(manager, allowed=["555"], blocked=["222"])
        message = FakeMessage()
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel

    job, channel = asyncio.run(scenario())
    assert job.status == "done"
    assert job.thread_id == "thread-1"
    assert job.thread_error == ""
    assert channel.thread.sent[0].startswith(f"Job `{job.id}` running")


def test_placement_gate_refuses_a_blocked_parent_and_keeps_an_allowed_one(monkeypatch):
    """The gate scope the job runner uses, on a bot shaped like the real one."""
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)
    gate_bot = AllowlistBot(allowed=["100", "555", "777"], blocked=["200", "666"])
    allowed = set(gate_bot._control["allowed_channels"])
    assert gate_bot._channel_allowed(FakeChannel("100"), allowed) is True
    # A parent that is not the allowlist's: refused as a job target.
    assert gate_bot._channel_allowed(FakeChannel("999"), allowed) is False
    # A parent explicitly blocked: refused as a job target.
    assert gate_bot._channel_allowed(FakeChannel("666"), allowed) is False
    # An allowed, unblocked parent still hosts the progress thread.
    assert gate_bot._channel_allowed(FakeChannel("777"), allowed) is True
    # An explicitly allowed thread under a blocked parent keeps its own
    # allowance; the job simply never creates anything in that parent.
    assert (
        gate_bot._channel_allowed(FakeThreadChannel(SimpleNamespace(id="666")), allowed)
        is True
    )


@pytest.mark.parametrize("masking", [True, False])
def test_job_masks_old_tool_results_and_keeps_the_newest_rounds(tmp_path, monkeypatch, masking):
    # Root, 1 November 2026 (Fable's research, arXiv 2508.21433): results of
    # rounds older than the newest BG_MASK_KEEP_ROUNDS become one line, so a
    # long job stays under the compaction limit without a model summary.
    from jobs import BG_MASK_KEEP_ROUNDS, BG_MASK_PREFIX

    if not masking:
        monkeypatch.setattr(jobs_module, "BG_MASK_KEEP_ROUNDS", 10_000)

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        bot.long_steps = 10
        message = FakeMessage()
        message.channel.thread.native_result_owner = bot
        job = manager.create(guild_id="g", channel_id="222", user_id="111", goal="a portfolio site")
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        head = estimate_job_tokens(background_messages(bot, job, message, "discord"))
        call = {"id": "call_9", "type": "function", "function": {"name": "shell", "arguments": '{"command":"true"}'}}
        step_tokens = estimate_job_tokens([
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": "call_9", "content": "Tool shell: ok call_9 " + "x" * 3000},
        ])
        # 10 long steps exceed 9.5 steps of results, so without masking the
        # job compacts. Batched masking keeps at most 8 steps unmasked.
        bot._control["bg_compact_at_tokens"] = head + int(9.5 * step_tokens)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel, bot

    job, channel, bot = asyncio.run(scenario())
    assert job.status == "done"
    if not masking:
        # The same job without masking needs a model summary.
        assert len(bot.compact_requests) >= 1
        return
    assert bot.compact_requests == []
    final = bot.generated_messages
    results = [m for m in final if m.get("role") == "tool"]
    masked = [m for m in results if m["content"].startswith(BG_MASK_PREFIX)]
    kept = [m for m in results if not m["content"].startswith(BG_MASK_PREFIX)]
    # Batches: masking waits for 2 * BG_MASK_KEEP_ROUNDS open rounds, then
    # keeps the newest BG_MASK_KEEP_ROUNDS.
    assert BG_MASK_KEEP_ROUNDS <= len(kept) < 2 * BG_MASK_KEEP_ROUNDS
    assert len(masked) == len(results) - len(kept) > 0
    assert masked[0]["content"].startswith(
        f"{BG_MASK_PREFIX} the shell result of an older step ("
    )
    assert "is masked to keep the job prompt small. It began: Tool shell: ok call_" in masked[0]["content"]
    assert masked[0]["content"].endswith("Call it again only if repeating it is safe.")
    # A masked row keeps its call pairing.
    pairs = [(a["tool_calls"][0]["id"], t["tool_call_id"]) for a, t in zip(final[2::2], final[3::2]) if a.get("tool_calls")]
    assert all(left == right for left, right in pairs)


@pytest.mark.parametrize("keep", [0, 1, 4])
def test_mask_old_tool_results_is_deterministic_and_skips_short_results(keep):
    from jobs import BG_MASK_PREFIX, mask_old_tool_results

    def round_(index, size):
        call = {"id": f"c{index}", "type": "function", "function": {"name": "fetch_url", "arguments": "{}"}}
        return [
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": f"c{index}", "content": "r" * size},
        ]

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "goal"}]
    for index in range(6):
        messages += round_(index, 50 if index == 0 else 1000)
    count, removed = mask_old_tool_results(messages, keep_rounds=keep)
    results = [m["content"] for m in messages if m.get("role") == "tool"]
    if keep == 4:
        # 5 open rounds are fewer than 2 * 4: the batch waits.
        assert (count, removed) == (0, 0)
        assert results == ["r" * 50] + ["r" * 1000] * 5
        return
    old = results[: max(0, 6 - keep)]
    # The short result of round 0 stays; long old results are masked.
    assert old[0] == "r" * 50
    assert all(text.startswith(BG_MASK_PREFIX) for text in old[1:])
    assert results[max(0, 6 - keep):] == ["r" * 1000] * min(keep, 6)
    assert count == max(0, len(old) - 1)
    assert removed > 0
    snapshot = [dict(m) for m in messages]
    # A second pass changes nothing: a masked row is never rewritten.
    assert mask_old_tool_results(messages, keep_rounds=keep) == (0, 0)
    assert messages == snapshot


def test_masking_keeps_the_synthetic_results_line_and_the_round_count():
    from jobs import BG_MASK_PREFIX, mask_old_tool_results
    from tool_schemas import tool_tail_groups

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "goal"}]
    for index in range(6):
        messages += [
            {"role": "assistant", "content": f"step {index}"},
            {"role": "user", "content": "=== TOOL RESULTS ===\n" + "r" * 1000},
        ]
    before = len(tool_tail_groups(messages[2:]))
    count, _ = mask_old_tool_results(messages, keep_rounds=2)
    assert count == 4
    assert len(tool_tail_groups(messages[2:])) == before == 6
    masked = [m["content"] for m in messages[2:] if m["role"] == "user"][:4]
    assert all(text.startswith("=== TOOL RESULTS ===\n" + BG_MASK_PREFIX + " the tool results") for text in masked)
    assert mask_old_tool_results(messages, keep_rounds=2) == (0, 0)


@pytest.mark.parametrize("provider_tokens", [10_000, None])
def test_next_prompt_tokens_subtracts_masked_characters_from_a_provider_count(provider_tokens):
    from jobs import estimate_job_tokens, next_prompt_tokens

    earlier = [{"role": "user", "content": "e" * 3000}]
    new = [{"role": "user", "content": "n" * 300}]
    estimate, estimated = next_prompt_tokens(provider_tokens, earlier, new, 3000)
    if provider_tokens is None:
        # Without a provider count the earlier messages, already masked,
        # are estimated, and nothing is subtracted twice.
        assert estimated is True
        assert estimate == estimate_job_tokens(earlier) + estimate_job_tokens(new)
    else:
        assert estimated is False
        assert estimate == 10_000 - 1000 + estimate_job_tokens(new)


def test_a_masked_error_result_keeps_its_first_line():
    # Failures stay visible: the outcome line of an old call survives masking.
    from jobs import mask_old_tool_results

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "goal"}]
    for index in range(8):
        call = {"id": f"c{index}", "type": "function", "function": {"name": "shell", "arguments": "{}"}}
        first = "Tool shell: Error - exit 1: permission denied" if index == 0 else "Tool shell: ok"
        messages += [
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": f"c{index}", "content": first + "\n" + "x" * 1000},
        ]
    count, _ = mask_old_tool_results(messages, keep_rounds=4)
    assert count == 4
    assert "It began: Tool shell: Error - exit 1: permission denied" in messages[3]["content"]


def test_a_result_is_not_masked_when_its_marker_is_not_shorter():
    # A 64-character tool name and a 200-character first line make a marker
    # of about 413 characters. A 410-character result then stays as it is.
    from jobs import BG_MASK_MIN_CHARS, mask_old_tool_results

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "goal"}]
    for index in range(8):
        call = {"id": f"c{index}", "type": "function", "function": {"name": "a" * 64, "arguments": "{}"}}
        content = "f" * 200 + "\n" + "t" * 209
        assert len(content) >= BG_MASK_MIN_CHARS
        messages += [
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": f"c{index}", "content": content},
        ]
    assert mask_old_tool_results(messages, keep_rounds=4) == (0, 0)
