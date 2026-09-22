"""The Dirac smoke protocol against fakes that keep the real shapes.

No Discord, no bot process, no provider and no network: the fake client's
``send_message`` returns the raw payload dict the SDK's own HTTP client returns,
the fake channel routes its sends through that method, and the reply queue and
``MaxwellBot._run_queued_reply`` are the real ones. What is faked is the
transport, not the path — the notice, its injection, the correlation ContextVar
and the single record all run the code that runs against the live bot.

Not covered here: real Discord behaviour, the bot's real gates (allowlist,
blacklist, ``bot_enabled``), the live HTTP client, and the container mounts.
"""

import asyncio
import json
import os
import time
from types import SimpleNamespace
from uuid import uuid4

import discord
import pytest

import dirac_runtime
from bot import MaxwellBot
from dirac_runtime import DiracSmokeRuntime, _TurnObserver, sent_message_id
from message_pipeline import ReplyQueue
from response_observability import TURN_INPUT
from smoke_protocol import (
    NOTICE_HEADER_LIMIT,
    NOTICE_LIMIT,
    TERMINAL_STATUSES,
    SmokeProtocolError,
    SmokeRecord,
    SmokeSettings,
    build_request,
    compose_notice,
    create_json_exclusive,
    iso_now,
    read_json_object,
    request_files,
    request_path,
    status_path,
)


# --------------------------------------------------------------------------
# fakes: the shape of the real path, without the real world
# --------------------------------------------------------------------------


class _FakeHTTP:
    """``HTTPClient`` as far as this protocol is concerned.

    ``send_message`` is awaited and answers with the message payload itself, which
    is what ``HTTPClient.request`` returns and what ``Messageable`` builds the
    message from.
    """

    def __init__(self) -> None:
        self.calls = []
        self.next_id = 700

    async def send_message(self, channel_id, *, params=None):
        self.next_id += 1
        self.calls.append((str(channel_id), params))
        return {"id": str(self.next_id), "channel_id": str(channel_id)}


class _FakeMessage:
    """A delivered message, and only the parts this protocol reads."""

    def __init__(self, payload, channel, author=None) -> None:
        self.id = int(payload["id"])
        self.content = payload.get("content", "")
        self.channel = channel
        self.author = author


class _ReadbackNotFound(discord.NotFound):
    """The readback's own 404: a real SDK exception type with no HTTP response."""

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return "404 Not Found (Unknown Message)"


class _FakeChannel:
    """A channel whose ``send`` goes through ``http.send_message``, as the SDK does."""

    def __init__(self, bot, channel_id, *, guild=True, parent_id=None) -> None:
        self._bot = bot
        self.id = channel_id
        self.guild = object() if guild else None
        self.parent_id = parent_id
        self._state = SimpleNamespace(http=bot.http)
        self.messages = {}
        self.sent = []

    async def send(self, content, **kwargs):
        payload = await self._state.http.send_message(
            self.id, params={"content": content}
        )
        payload["content"] = content
        message = _FakeMessage(payload, self, author=self._bot.user)
        self.messages[message.id] = message
        self.sent.append(message)
        return message

    async def fetch_message(self, message_id):
        message = self.messages.get(message_id)
        if message is None:
            raise _ReadbackNotFound()
        return message


class _FakeThread(_FakeChannel):
    """``discord.Thread`` as much as the scope checks need, monkeypatched in."""

    def __init__(self, bot, thread_id, *, parent_id, owner_id) -> None:
        super().__init__(bot, thread_id, parent_id=parent_id)
        self.owner_id = owner_id


class _Input:
    """A queued input for the reply queue: an id and a channel id."""

    def __init__(self, message_id, channel_id) -> None:
        self.id = message_id
        self.channel = SimpleNamespace(id=channel_id)


class _FakeBot:
    """The parts of ``MaxwellBot`` the smoke runtime touches, and no more."""

    def __init__(self, settings) -> None:
        self.user = SimpleNamespace(id=555000111)
        self.http = _FakeHTTP()
        self._reply_queue = ReplyQueue()
        self._reply_queue.bind(self._run_queued_reply)
        self._turn_observer = None
        self.dispatch = True
        self.injected = []
        self.turn = self._default_turn
        self.release = asyncio.Event()
        self.channels = {}
        self.users = {
            settings.operator_id: SimpleNamespace(
                id=settings.operator_id, display_name="root"
            )
        }
        self.use_channel(_FakeChannel(self, str(settings.channel_id)))

    def use_channel(self, channel):
        self.channels[int(channel.id)] = channel
        return channel

    async def wait_until_ready(self):
        return True

    def get_channel(self, channel_id):
        return self.channels.get(int(channel_id))

    async def fetch_channel(self, channel_id):
        return self.get_channel(channel_id)

    def get_user(self, user_id):
        return self.users.get(int(user_id))

    async def fetch_user(self, user_id):
        return self.get_user(user_id)

    async def _on_message_impl(self, message):
        """Mirrors the bot's dispatch: a hard ping becomes one queued turn."""
        self.injected.append(message)
        if self.dispatch:
            self._reply_queue.submit(
                str(message.channel.id), message, message.content, directed=True
            )

    async def _handle_message(self, message, content):
        await self.turn(message, content)

    async def _run_queued_reply(self, message, content=None):
        """The bot's own wrapper, so the observer bracketing under test is real."""
        return await MaxwellBot._run_queued_reply(self, message, content)

    async def _default_turn(self, message, content):
        await message.channel.send("smoke reply")


# --------------------------------------------------------------------------
# scaffolding
# --------------------------------------------------------------------------


def _settings(tmp_path, *, enabled=True, make_requests=True, make_status=True):
    """A real config file, loaded by the real loader.

    ``status_dir`` is the ``../smoke-status`` form: the same config resolves to
    the host mount and to ``/smoke-status`` next to the ``/smoke`` mount. Both
    directories are prepared here the way the operator prepares the real mounts:
    the runtime requires them and never creates them.
    """
    root = tmp_path / "smoke"
    root.mkdir(parents=True, exist_ok=True)
    if make_requests:
        (root / "requests").mkdir(exist_ok=True)
    if make_status:
        (tmp_path / "smoke-status").mkdir(exist_ok=True)
    config = {
        "enabled": enabled,
        "channel_id": 4242,
        "operator_id": 1482143139828596916,
        "operator_name": "root",
        "requests_dir": "requests",
        "status_dir": "../smoke-status",
        "poll_seconds": 0.25,
    }
    path = root / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return SmokeSettings.load(path)


async def _ready(tmp_path, *, enabled=True, make_requests=True, make_status=True):
    """A started runtime over a fake bot, driven by a config file on disk."""
    settings = _settings(
        tmp_path,
        enabled=enabled,
        make_requests=make_requests,
        make_status=make_status,
    )
    bot = _FakeBot(settings)
    runtime = DiracSmokeRuntime(bot, settings)
    await runtime.start()
    return settings, bot, runtime


def _submit(settings, task="say pong", **kwargs):
    request = build_request(request_id=uuid4().hex, task=task, **kwargs)
    create_json_exclusive(request_path(settings, request.request_id), request.as_json())
    return request


def _record_of(settings, request_id):
    return SmokeRecord.from_json(
        read_json_object(status_path(settings, request_id), "record")
    )


async def _wait_for_record(settings, request_id, tries=600):
    """Wait for the runtime to terminate this request's record."""
    record = None
    for _ in range(tries):
        path = status_path(settings, request_id)
        if path.exists():
            record = _record_of(settings, request_id)
            if record.status in TERMINAL_STATUSES:
                return record
        await asyncio.sleep(0.05)
    raise AssertionError(f"{request_id} never terminated: {record}")


async def _wait_for_reply(settings, request_id, tries=100):
    """Wait for the optional readback to enrich an already terminal record.

    The record is written before that readback, so a caller that asserts on
    ``reply_text`` or ``reply_readback`` has to wait for the second write.
    """
    record = _record_of(settings, request_id)
    for _ in range(tries):
        if record.reply_text or record.reply_readback:
            return record
        await asyncio.sleep(0.05)
        record = _record_of(settings, request_id)
    return record


async def _one(tmp_path, *, body=None, task="say pong", **request_kwargs):
    """Run one request to its finished record and hand back everything."""
    settings, bot, runtime = await _ready(tmp_path)
    if body is not None:
        bot.turn = body
    request = _submit(settings, task=task, **request_kwargs)
    record = await _wait_for_record(settings, request.request_id)
    if record.status == "completed":
        record = await _wait_for_reply(settings, request.request_id)
    return settings, bot, runtime, request, record


# --------------------------------------------------------------------------
# the config is one file for two mounts
# --------------------------------------------------------------------------


def test_settings_resolve_both_directories_against_the_config_file(tmp_path):
    settings = _settings(tmp_path)
    assert settings.requests_dir == (tmp_path / "smoke" / "requests").resolve()
    assert settings.status_dir == (tmp_path / "smoke-status").resolve()
    assert settings.enabled is True


def test_a_config_must_state_enabled_explicitly(tmp_path):
    root = tmp_path / "smoke"
    root.mkdir()
    path = root / "config.json"
    base = {"channel_id": 1, "operator_id": 2, "requests_dir": "r", "status_dir": "s"}
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(SmokeProtocolError):
        SmokeSettings.load(path)
    path.write_text(json.dumps({**base, "enabled": "yes"}), encoding="utf-8")
    with pytest.raises(SmokeProtocolError):
        SmokeSettings.load(path)
    bad_id = {**base, "enabled": True, "channel_id": "not-an-id"}
    path.write_text(json.dumps(bad_id), encoding="utf-8")
    with pytest.raises(SmokeProtocolError):
        SmokeSettings.load(path)


# --------------------------------------------------------------------------
# requests and the notice
# --------------------------------------------------------------------------


def test_a_request_is_published_exclusively_and_never_overwritten(tmp_path):
    settings = _settings(tmp_path)
    request = build_request(request_id="a" * 32, task="first")
    path = request_path(settings, request.request_id)
    create_json_exclusive(path, request.as_json())
    rival = build_request(request_id="a" * 32, task="second")
    with pytest.raises(FileExistsError):
        create_json_exclusive(path, rival.as_json())
    assert read_json_object(path, "request")["task"] == "first"
    # The temporary that lost the race is invisible to every scanner.
    assert request_files(settings) == [path]


def test_the_notice_states_the_grant_and_fits_one_message(tmp_path):
    settings = _settings(tmp_path)
    request = build_request(request_id="b" * 32, task="say pong")
    notice = compose_notice(
        request, operator_name="root", operator_id=settings.operator_id, bot_id=777
    )
    assert notice.endswith("say pong")
    assert "<@777>" in notice  # the hard ping that reaches the reply path
    assert "HARNESS SMOKE TEST" in notice
    assert "No human typed this" in notice
    assert "Root authorized it while AFK" in notice
    assert "Permission actor: root (" in notice
    assert len(notice) <= NOTICE_LIMIT
    assert len(notice) - len(request.task) <= NOTICE_HEADER_LIMIT
    with pytest.raises(SmokeProtocolError):
        build_request(
            request_id="c" * 32,
            task="x" * (NOTICE_LIMIT - NOTICE_HEADER_LIMIT + 1),
        )


def test_a_delivery_is_read_from_the_payload_dict_only():
    """The SDK returns the raw payload; an attribute read sees nothing at all."""
    assert sent_message_id({"id": "42"}) == "42"
    assert sent_message_id({"no_id": True}) == ""
    assert sent_message_id(None) == ""
    assert sent_message_id(SimpleNamespace(id="42")) == ""


# --------------------------------------------------------------------------
# one request, end to end
# --------------------------------------------------------------------------


def test_a_visible_turn_is_completed_with_its_exact_delivery(tmp_path):
    async def scenario():
        settings, bot, runtime, request, record = await _one(tmp_path)
        assert record.status == "completed"
        assert record.returned is True
        # The id is the one the payload carried, read as a dict item.
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert bot.http.calls[-1] == (
            str(settings.channel_id),
            {"content": "smoke reply"},
        )
        assert record.reply_text == "smoke reply"
        assert record.reply_readback == []
        assert record.reply_verified is False
        assert record.channel_id == str(settings.channel_id)
        notice = bot.injected[0]
        assert record.notice_id == str(notice.id)
        # The real notice was posted by the bot; the input the turn sees is
        # authored by the configured operator actor instead.
        posted = bot.channels[int(settings.channel_id)].sent[0]
        assert posted.author.id == bot.user.id
        assert notice.author.id == settings.operator_id
        assert isinstance(notice.author.id, int)
        assert f"<@{bot.user.id}>" in notice.content
        assert request.task in notice.content
        # The notice was posted by the poll task, which is nobody's turn: it is
        # never mistaken for something this request delivered.
        assert record.notice_id not in record.delivered_ids
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_silent_turn_is_a_failure_not_a_pass(tmp_path):
    """`completed` requires a visible delivery, whatever the turn intended."""

    async def silent(message, content):
        return None

    async def scenario():
        settings, bot, runtime, request, record = await _one(tmp_path, body=silent)
        assert record.status == "failed"
        assert record.returned is True
        assert record.delivered_ids == []
        assert "no_response" in record.failure
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_reply_the_harness_cannot_read_back_is_still_a_delivery(tmp_path):
    """A readback 404 is recorded as a readback failure, never as a failed turn."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def direct_post(message, content):
            """Post the way a plugin does: through HTTP, with no channel object."""
            await bot.http.send_message(
                str(message.channel.id), params={"content": "posted"}
            )

        bot.turn = direct_post
        request = _submit(settings)
        await _wait_for_record(settings, request.request_id)
        record = await _wait_for_reply(settings, request.request_id)
        assert record.status == "completed"
        assert record.returned is True
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert record.reply_text == ""
        assert record.reply_readback == [f"{bot.http.next_id} (_ReadbackNotFound)"]
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_the_observer_ignores_unrelated_and_late_deliveries():
    observer = _TurnObserver()
    turn = observer.open("1", "4242")
    observer.delivered("", "4242", "x")  # a task that is nobody's turn
    observer.delivered("99", "4242", "x")  # an input nobody opened
    observer.delivered("1", "7777", "x")  # another room's output
    observer.delivered("1", "4242", "a")
    observer.delivered("1", "4242", "a")  # the same message twice
    observer.delivered("1", "4242", "")
    assert turn.delivered == ["a"]
    token = observer.start("1", "4242", None)
    assert TURN_INPUT.get() == "1"
    observer.finish("1", "4242", True, token)
    assert TURN_INPUT.get() == ""
    observer.delivered("1", "4242", "late")
    assert turn.delivered == ["a"]  # a closed input stays closed
    assert turn.returned is True


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------


def test_a_direct_message_channel_is_rejected_and_nothing_is_injected(tmp_path):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        bot.use_channel(_FakeChannel(bot, str(settings.channel_id), guild=False))
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "rejected"
        assert record.status in TERMINAL_STATUSES
        assert "direct message" in record.failure
        assert bot.injected == []
        assert bot.http.calls == []
        await runtime.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["not_a_thread", "foreign_parent", "foreign_owner"])
def test_thread_scope_is_enforced(tmp_path, monkeypatch, case):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        monkeypatch.setattr(dirac_runtime.discord, "Thread", _FakeThread)
        parent = str(settings.channel_id)
        if case == "not_a_thread":
            bot.use_channel(_FakeChannel(bot, "9001"))
        elif case == "foreign_parent":
            thread = _FakeThread(bot, "9001", parent_id="1", owner_id=bot.user.id)
            bot.use_channel(thread)
        else:
            thread = _FakeThread(bot, "9001", parent_id=parent, owner_id=1234)
            bot.use_channel(thread)
        request = _submit(settings, thread_id="9001")
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "rejected"
        assert bot.injected == []
        await runtime.stop()

    asyncio.run(scenario())


def test_a_bot_owned_thread_in_the_approved_channel_runs(tmp_path, monkeypatch):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        monkeypatch.setattr(dirac_runtime.discord, "Thread", _FakeThread)
        thread = bot.use_channel(
            _FakeThread(
                bot, "9001", parent_id=str(settings.channel_id), owner_id=bot.user.id
            )
        )
        request = _submit(settings, thread_id="9001")
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "completed"
        assert record.thread_id == "9001"
        assert record.channel_id == "9001"
        assert bot.injected[0].channel.id == "9001"
        assert thread.sent[0].id == int(record.notice_id)
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


# --------------------------------------------------------------------------
# startup
# --------------------------------------------------------------------------


def test_start_fails_when_the_request_mount_is_missing(tmp_path):
    async def scenario():
        settings = _settings(tmp_path, make_requests=False)
        runtime = DiracSmokeRuntime(_FakeBot(settings), settings)
        with pytest.raises(SmokeProtocolError):
            await runtime.start()

    asyncio.run(scenario())


def test_start_fails_when_the_status_mount_is_missing(tmp_path):
    """An absent mount must fail, not be manufactured as an ephemeral ledger."""

    async def scenario():
        settings = _settings(tmp_path, make_status=False)
        runtime = DiracSmokeRuntime(_FakeBot(settings), settings)
        with pytest.raises(SmokeProtocolError):
            await runtime.start()
        assert not settings.status_dir.exists()

    asyncio.run(scenario())


def test_start_fails_when_the_status_mount_cannot_be_a_directory(tmp_path):
    async def scenario():
        settings = _settings(tmp_path, make_status=False)
        settings.status_dir.write_text("a file, not a mount", encoding="utf-8")
        runtime = DiracSmokeRuntime(_FakeBot(settings), settings)
        with pytest.raises(SmokeProtocolError):
            await runtime.start()

    asyncio.run(scenario())


def test_a_disabled_config_does_nothing_at_all(tmp_path):
    async def scenario():
        settings = _settings(tmp_path, enabled=False)
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        assert bot._turn_observer is None
        assert runtime._poll is None
        assert bot.http.send_message.__func__ is _FakeHTTP.send_message
        await runtime.stop()

    asyncio.run(scenario())


def test_a_nonterminal_record_is_interrupted_and_never_rerun(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        request = _submit(settings)
        stale = SmokeRecord(
            request_id=request.request_id, status="running", created_at=iso_now()
        )
        stale.write(status_path(settings, request.request_id))
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        record = _record_of(settings, request.request_id)
        assert record.status == "interrupted"
        assert record.status in TERMINAL_STATUSES
        assert "never re-run" in record.failure
        assert runtime._next_request() is None
        await asyncio.sleep(settings.poll_seconds * 1.5)
        assert bot.injected == []
        assert bot.http.calls == []
        await runtime.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------
# the clock, and no replay
# --------------------------------------------------------------------------


def test_the_oldest_pending_request_is_chosen_by_clock_not_by_id(tmp_path):
    async def scenario():
        # Deliberately not started: this is the choice the poll makes, and a
        # running poll could pick a request before the clocks are set.
        settings = _settings(tmp_path)
        runtime = DiracSmokeRuntime(_FakeBot(settings), settings)
        older = build_request(request_id="ff" * 16, task="older")
        newer = build_request(request_id="00" * 16, task="newer")
        for request in (older, newer):
            create_json_exclusive(
                request_path(settings, request.request_id), request.as_json()
            )
        stamp = time.time()
        os.utime(request_path(settings, newer.request_id), (stamp, stamp))
        os.utime(request_path(settings, older.request_id), (stamp - 60, stamp - 60))
        # The lexicographically smaller id is the newer request, so a name sort
        # would pick the wrong one.
        assert newer.request_id < older.request_id
        assert runtime._next_request().stem == older.request_id

    asyncio.run(scenario())


def test_more_than_300_completed_requests_are_never_replayed(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        finished = []
        for index in range(301):
            request = build_request(request_id=f"{index:032x}", task=f"done {index}")
            create_json_exclusive(
                request_path(settings, request.request_id), request.as_json()
            )
            done = SmokeRecord(
                request_id=request.request_id, status="completed", created_at=iso_now()
            )
            done.write(status_path(settings, request.request_id))
            finished.append(request.request_id)
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        before = {rid: status_path(settings, rid).read_bytes() for rid in finished}
        fresh = _submit(settings)
        record = await _wait_for_record(settings, fresh.request_id)
        assert record.status == "completed"
        assert runtime._next_request() is None
        after = {rid: status_path(settings, rid).read_bytes() for rid in finished}
        assert before == after  # not one finished request was touched again
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


# --------------------------------------------------------------------------
# deadline, queue and shutdown
# --------------------------------------------------------------------------


def test_a_turn_past_its_deadline_is_cancelled_without_touching_other_turns(tmp_path):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        ran = []

        async def blocking(message, content):
            await bot.release.wait()
            ran.append(content)

        bot.turn = blocking
        other = bot.use_channel(_FakeChannel(bot, "7777"))
        blocker = _Input(1, "7777")
        bot._reply_queue.submit("7777", blocker, "real traffic", directed=True)
        for _ in range(50):
            await asyncio.sleep(0)
            if other.sent or bot._reply_queue.active("7777"):
                break
        request = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "timeout"
        assert "only this input was cancelled" in record.failure
        assert bot._reply_queue.active("7777") is True  # the other room is untouched
        bot.release.set()
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_an_input_that_expires_while_queued_never_runs(tmp_path):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        ran = []

        async def blocking(message, content):
            await bot.release.wait()
            ran.append(content)

        bot.turn = blocking
        channel = str(settings.channel_id)
        bot._reply_queue.submit(channel, _Input(1, channel), "blocker", directed=True)
        for _ in range(50):
            await asyncio.sleep(0)
            if bot._reply_queue.active(channel):
                break
        request = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "timeout"
        assert "removed unexecuted" in record.failure
        assert bot._reply_queue.depth(channel) == 0
        bot.release.set()
        for _ in range(200):
            await asyncio.sleep(0)
            if ran:
                break
        assert ran == ["blocker"]  # the expired input never became a turn
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_an_input_the_bot_never_dispatches_is_recorded_as_no_turn(tmp_path):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        bot.dispatch = False
        request = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "timeout"
        assert "no turn was dispatched" in record.failure
        assert record.notice_id  # the notice was really posted
        await runtime.stop()

    asyncio.run(scenario())


def test_stop_interrupts_the_request_in_flight(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        unwrapped = bot.http.send_message  # the baseline, before the wrapper
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        assert bot.http.send_message is not unwrapped  # the wrapper is installed

        async def blocking(message, content):
            await bot.release.wait()

        bot.turn = blocking
        request = _submit(settings)
        for _ in range(200):
            await asyncio.sleep(0.05)
            path = status_path(settings, request.request_id)
            if not path.exists():
                continue
            if _record_of(settings, request.request_id).status == "running":
                break
        await runtime.stop()
        record = _record_of(settings, request.request_id)
        assert record.status == "interrupted"
        assert record.status in TERMINAL_STATUSES
        assert bot._turn_observer is None
        assert bot.http.send_message.__self__ is unwrapped.__self__
        assert bot.http.send_message.__func__ is unwrapped.__func__
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_the_deadline_covers_the_notice_not_only_the_turn(tmp_path):
    """Resolving and posting the notice can stall too, and that is bounded."""

    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        bot.channels.clear()  # nothing cached: the fetch is on the path
        release = asyncio.Event()  # never set

        async def stalled_fetch(channel_id):
            await release.wait()

        bot.fetch_channel = stalled_fetch
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        request = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "timeout"
        assert "never injected" in record.failure
        assert record.notice_id == ""
        assert bot.injected == []
        await runtime.stop()

    asyncio.run(scenario())


def test_a_stuck_owned_task_holds_back_the_next_request(tmp_path, monkeypatch):
    """A turn that ignores its cancel is reported, and nothing new starts."""

    async def scenario():
        monkeypatch.setattr(dirac_runtime, "CLEANUP_SECONDS", 0.05)
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)

        async def stubborn(message, content):
            try:
                await bot.release.wait()
            except asyncio.CancelledError:
                await asyncio.sleep(1.0)  # swallows the cancel, for now

        bot.turn = stubborn
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        first = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, first.request_id)
        assert record.status == "timeout"
        assert "cleanup is unconfirmed" in record.failure
        # The stuck coroutine is already running and keeps its own code; the room
        # gets an ordinary turn again for whatever comes next.
        bot.turn = bot._default_turn
        second = _submit(settings, task="second")
        await asyncio.sleep(0.5)
        assert not status_path(settings, second.request_id).exists()
        # Once the stuck task is really gone, the queue moves again.
        held = await _wait_for_record(settings, second.request_id)
        assert held.status == "completed"
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_stalled_readback_cannot_downgrade_a_completed_turn(tmp_path, monkeypatch):
    """The outcome is written first; the readback is optional and bounded."""

    async def scenario():
        monkeypatch.setattr(dirac_runtime, "READBACK_SECONDS", 0.05)
        settings, bot, runtime = await _ready(tmp_path)

        async def direct_post(message, content):
            await bot.http.send_message(
                str(message.channel.id), params={"content": "posted"}
            )

        bot.turn = direct_post
        gate = asyncio.Event()  # never set: the readback cannot finish

        async def stalled_fetch(message_id):
            await gate.wait()

        bot.channels[int(settings.channel_id)].fetch_message = stalled_fetch
        request = _submit(settings)
        await _wait_for_record(settings, request.request_id)
        record = await _wait_for_reply(settings, request.request_id)
        assert record.status == "completed"
        assert record.returned is True
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert record.reply_text == ""
        assert record.reply_readback == [f"{bot.http.next_id} (TimeoutError)"]
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_stop_during_a_readback_keeps_the_completed_record(tmp_path):
    """A stop inside the optional readback never rewrites a terminal turn."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def direct_post(message, content):
            await bot.http.send_message(
                str(message.channel.id), params={"content": "posted"}
            )

        bot.turn = direct_post
        gate = asyncio.Event()  # never set: the readback is still in flight

        async def stalled_fetch(message_id):
            await gate.wait()

        bot.channels[int(settings.channel_id)].fetch_message = stalled_fetch
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "completed"
        await runtime.stop()
        record = _record_of(settings, request.request_id)
        assert record.status == "completed"  # not interrupted, not failed
        assert record.returned is True
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert record.reply_text == ""
        await bot._reply_queue.close()

    asyncio.run(scenario())
