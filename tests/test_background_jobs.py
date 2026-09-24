"""Background sub-agent jobs (jobs.py): caps, budgets, ack-then-deliver.

Style follows the repo: sync test functions, asyncio.run() for async paths,
fake Discord objects instead of a connection.
"""

import asyncio
import json
from types import SimpleNamespace

import discord
import pytest

from bot import MaxwellBot
from error_reporting import PUBLIC_ERROR_TEXT
from jobs import (
    JOB_TURN,
    BackgroundJobManager,
    SpawnBackgroundTool,
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

    async def send(self, text):
        self.sent.append(text)
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

    _channel_allowed = MaxwellBot._channel_allowed
    _solo_blocks = MaxwellBot._solo_blocks
    _solo_channel_for = MaxwellBot._solo_channel_for
    _message_update_allowed = MaxwellBot._message_update_allowed

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
    assert budgets["max_tokens"] == 32768  # max(16384*2, 32768)
    assert budgets["timeout_seconds"] == 7200
    assert budgets["max_iters"] == 100


def test_budgets_clamp_to_hard_caps():
    budgets = resolve_job_budgets(
        {"bg_max_tokens": 999999, "bg_timeout_seconds": 99999, "bg_max_iters": 9999},
        FakeConfig(),
    )
    assert budgets == {"max_tokens": 131072, "timeout_seconds": 14400, "max_iters": 200}


def test_budgets_zero_means_default(monkeypatch):
    monkeypatch.delenv("BG_MAX_TOKENS", raising=False)
    budgets = resolve_job_budgets({"bg_max_tokens": 0}, FakeConfig())
    assert budgets["max_tokens"] == 32768


def test_budgets_env_override(monkeypatch):
    monkeypatch.setenv("BG_MAX_ITERS", "42")
    budgets = resolve_job_budgets({}, FakeConfig())
    assert budgets["max_iters"] == 42


# manager


def test_manager_caps_per_user_then_global(tmp_path):
    manager = BackgroundJobManager(
        data_path=str(tmp_path / "jobs.json"), max_jobs=2, max_per_user=1
    )
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


def test_spawn_tool_acks_and_tracks_job(tmp_path):
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
            result = await tool.execute(message, goal="a portfolio site")
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            jobs_mod.run_background_job = real
        assert "Background job `" in result
        assert manager.active_count() == 1
        assert launched["jid"] is not None
        return result

    result = asyncio.run(scenario())
    assert "send_message" in result  # ack instruction for the live turn


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

    _channel_allowed = MaxwellBot._channel_allowed

    def __init__(self, manager):
        super().__init__(manager)
        self.slot_priority = None
        self.generated_with = {}

    def _message_tool_platform(self, message):
        return "discord"

    def _tool_system_prompt(self, platform, message=None, content=None):
        return ""

    def _build_openai_tools(self, platform, message=None, content=None):
        return []

    def _select_tool_protocol(self, openai_tools):
        return False, []

    async def _acquire_ai_slot(self, timeout, *, priority="background", key=""):
        self.slot_priority = priority

    async def _release_ai_slot(self):
        return None

    async def _generate_response(self, messages, **kwargs):
        self.generated_with = dict(kwargs)
        return "built it: http://example.local/site"

    def _native_calls_from(self, response):
        return []

    def _recover_text_tool_calls(self, response):
        return [], response

    async def _dispatch_tool_calls(self, message, response, **kwargs):
        return str(response), []


def test_runner_delivers_final_reply_with_mention(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = RunnerStubBot(manager)
        message = FakeMessage()
        job = manager.create(
            guild_id="g", channel_id="222", user_id="111", goal="a portfolio site"
        )
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel, bot

    job, channel, bot = asyncio.run(scenario())
    assert job.status == "done"
    assert bot.slot_priority == "background"  # user turns outrank it
    assert bot.generated_with.get("disable_reasoning") is False  # full thinking
    assert bot.generated_with.get("max_tokens", 0) >= 32768  # extended output
    assert any("<@111>" in text and job.id in text for text in channel.sent)
    assert any("http://example.local/site" in text for text in channel.sent)


def test_runner_marks_error_and_notifies(tmp_path):
    class BrokenBot(RunnerStubBot):
        async def _generate_response(self, messages, **kwargs):
            raise RuntimeError("provider down")

    async def scenario():
        manager = BackgroundJobManager(data_path=str(tmp_path / "jobs.json"))
        bot = BrokenBot(manager)
        message = FakeMessage()
        job = manager.create(guild_id="g", channel_id="222", user_id="111", goal="x")
        manager.attach_runtime(job.id, message=message, channel=message.channel)
        await run_background_job(bot, job.id)
        return manager.get(job.id), message.channel

    job, channel = asyncio.run(scenario())
    assert job.status == "error"
    assert channel.sent == [PUBLIC_ERROR_TEXT]


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
        await MaxwellBot._handle_command(bot, message)
        message.content = f"!job {threadless.id}"
        await MaxwellBot._handle_command(bot, message)
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
    assert MaxwellBot._message_update_allowed(bot, GateMessage(FakeChannel("100"))) is True
    assert MaxwellBot._message_update_allowed(bot, GateMessage(FakeChannel("999"))) is False
    assert (
        MaxwellBot._message_update_allowed(
            bot, GateMessage(FakeThreadChannel(SimpleNamespace(id="100")))
        )
        is True
    )
    assert (
        MaxwellBot._message_update_allowed(
            bot, GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
        )
        is False
    )
    # Same explicit-choice rule through the edit gate.
    explicit = AllowlistBot(allowed=["100", "555"], blocked=["200"])
    assert (
        MaxwellBot._message_update_allowed(
            explicit, GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
        )
        is True
    )


def test_on_message_gate_denies_a_thread_of_a_blocked_parent(monkeypatch):
    monkeypatch.setattr(discord, "Thread", FakeThreadChannel)
    bot = AllowlistBot(allowed=["100"], blocked=["200"])
    message = GateMessage(FakeThreadChannel(SimpleNamespace(id="200")))
    asyncio.run(MaxwellBot._on_message_impl(bot, message))
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
