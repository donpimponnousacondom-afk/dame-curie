"""The Dirac smoke protocol against fakes that keep the real shapes.

No Discord, no bot process, no provider and no network: the fake client's
``send_message`` returns the raw payload dict the SDK's own HTTP client returns,
the fake channel routes its sends through that method, the fake bot's
``_generate_response`` stands in for the provider the runtime observes, and the
reply queue and ``MaxwellBot._run_queued_reply`` are the real ones. What is faked
is the transport, not the path — the notice, its injection, the correlation
ContextVar and the single record all run the code that runs against the live bot.

Not covered here: real Discord behaviour, the bot's real gates (allowlist,
blacklist, ``bot_enabled``), the live HTTP client, memory/REM persistence,
and the container mounts.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import discord
import pytest

import dirac_runtime
from bot import MaxwellBot
from providers import ProviderResult
from tool_progress import ToolProgress
from dirac_runtime import DiracSmokeRuntime, _TurnObserver, sent_message_id
from message_pipeline import ReplyQueue
from rag_memory import _detect_source
from response_observability import TURN_INPUT, notice_send, record_delivery
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
    runtime_state_path,
    status_path,
)


# --------------------------------------------------------------------------
# fakes: the shape of the real path, without the real world
# --------------------------------------------------------------------------


class _FakeHTTP:
    """``HTTPClient`` as far as this protocol is concerned.

    ``send_message`` is awaited and answers with the message payload itself, which
    is what ``HTTPClient.request`` returns and what ``Messageable`` builds the
    message from. With ``lose_response``, the fake accepts and assigns an ID before
    losing the response; the caller cannot observe that ID.
    """

    def __init__(self) -> None:
        self.calls = []
        self.next_id = 700
        self.lose_response = False

    async def send_message(self, channel_id, *, params=None):
        self.next_id += 1
        self.calls.append((str(channel_id), params))
        if self.lose_response:
            raise TimeoutError("send accepted, response lost")
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

    # The real classmethod, so a turn can drive the real late-embed refresh.
    _media_link_refs = MaxwellBot._media_link_refs

    def __init__(self, settings) -> None:
        self.user = SimpleNamespace(id=555000111)
        self.http = _FakeHTTP()
        self._reply_queue = ReplyQueue()
        self._reply_queue.bind(self._run_queued_reply)
        self._turn_observer = None
        self.dispatch = True
        self.dispatch_failure = ""
        self.injected = []
        self.turn = self._default_turn
        self.generate = self._default_generate
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
            if self.dispatch_failure in {"registered", "upstream_timeout"}:
                await asyncio.sleep(0)  # pump registers a task before its first turn step
                assert self._reply_queue.active(message.channel.id)
                assert self._turn_observer._turns[str(message.id)].task is None
            elif self.dispatch_failure == "after_partial":
                while len(message.channel.sent) < 2:
                    await asyncio.sleep(0)
            if self.dispatch_failure == "upstream_timeout":
                raise TimeoutError("synthetic private request and config contents")
            if self.dispatch_failure:
                raise RuntimeError("synthetic failure after smoke dispatch")

    async def _handle_message(self, message, content):
        await self.turn(message, content)

    async def _run_queued_reply(self, message, content=None):
        """The bot's own wrapper, so the observer bracketing under test is real."""
        return await MaxwellBot._run_queued_reply(self, message, content)

    async def _default_generate(self):
        """One model completion, in the shape the provider really returns."""
        return ProviderResult("pong")

    async def _generate_response(self, messages, **kwargs):
        """The bot's own generation entry point, which the runtime observes."""
        return await self.generate()

    async def _default_turn(self, message, content):
        await self._generate_response([{"role": "user", "content": content}])
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
    """Run one request to its finished record and hand back everything.

    Any record that delivered something gets its readback too, which the runtime
    writes after the terminal state: a failure that delivered a notice still has
    the notice text in it.
    """
    settings, bot, runtime = await _ready(tmp_path)
    if body is not None:
        bot.turn = body
    request = _submit(settings, task=task, **request_kwargs)
    record = await _wait_for_record(settings, request.request_id)
    if record.delivered_ids:
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


def test_the_observer_counts_output_apart_from_deliveries():
    """Every real send is evidence; only unmarked model output makes a turn pass."""

    async def scenario():
        observer = _TurnObserver()
        turn = observer.open("1", "4242")
        token = observer.start("1", "4242", asyncio.current_task())
        observer.delivered("1", "4242", "notice", True)  # a bot notice
        observer.delivered("1", "4242", "progress", True)  # the placeholder
        observer.model_result("1", True)
        assert turn.model_answered is True
        observer.delivered("1", "4242", "answer")
        observer.delivered("1", "4242", "progress")  # the same placeholder, now reply
        observer.delivered("1", "4242", "answer")  # the same message twice
        assert turn.delivered == ["notice", "progress", "answer"]
        assert turn.output == ["answer", "progress"]

        observer.model_result("1", False)  # the call after it failed
        observer.delivered("1", "4242", "error notice")
        assert turn.output == ["answer", "progress"]
        assert turn.delivered == ["notice", "progress", "answer", "error notice"]
        # Another task's model call is not this turn's answer.
        turn.model_ok = False

        async def other_task_call():
            observer.model_result("1", True)

        other = asyncio.create_task(other_task_call())
        await other
        assert turn.model_ok is False
        observer.finish("1", "4242", True, token)
        assert TURN_INPUT.get() == ""

    asyncio.run(scenario())


def test_a_refreshed_notice_keeps_the_granted_actor(tmp_path):
    """A late-embed refresh must not hand the turn the bot's own message."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        seen = {}

        async def refreshing(message, content):
            refreshed = await MaxwellBot._wait_for_late_embeds(bot, message, content)
            # The refresh is a fresh fetch of the notice, posted by the bot.
            assert refreshed is not message
            assert refreshed.author.id == bot.user.id
            message = MaxwellBot._preserve_input_actor(message, refreshed)
            seen["actor"] = message.author.id
            seen["author"] = message.notice_author.id
            await bot._generate_response([{"role": "user", "content": content}])
            await message.channel.send("answered after the refresh")

        bot.turn = refreshing
        request = _submit(settings, task="describe https://example.test/a.png")
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "completed"
        # The permission actor survives the swap; the author does not change.
        assert seen == {"actor": settings.operator_id, "author": bot.user.id}
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_refreshed_snapshot_cannot_change_the_notice_provenance(tmp_path):
    """A snapshot rebuilt from the proxy says the actor, not who posted the text."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        seen = {}

        async def rebuilt_from_the_actor(message, content):
            # What a snapshot rebuilt from this input looks like: the message id is
            # the notice's, the author is the permission actor the proxy exposes.
            snapshot = _FakeMessage(
                {"id": str(message.id)}, message.channel, author=message.author
            )
            assert snapshot.author.id == settings.operator_id
            rebound = MaxwellBot._preserve_input_actor(message, snapshot)
            author = MaxwellBot._memory_author(rebound)
            seen["actor"] = rebound.author.id
            seen["author"] = rebound.notice_author.id
            seen["row_author"] = author.id
            seen["row_is_bot"] = MaxwellBot._memory_author_is_bot(bot, author)
            await bot._generate_response([{"role": "user", "content": content}])
            await message.channel.send("answered")

        bot.turn = rebuilt_from_the_actor
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "completed"
        # Pinned provenance: the snapshot's author cannot overwrite the poster.
        assert seen == {
            "actor": settings.operator_id,
            "author": bot.user.id,
            "row_author": bot.user.id,
            "row_is_bot": True,
        }
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_delivery_is_read_from_the_payload_dict_only():
    """The SDK returns the raw payload; an attribute read sees nothing at all."""
    assert sent_message_id({"id": "42"}) == "42"
    assert sent_message_id({"no_id": True}) == ""
    assert sent_message_id(None) == ""
    assert sent_message_id(SimpleNamespace(id="42")) == ""


# --------------------------------------------------------------------------
# one request, end to end
# --------------------------------------------------------------------------


@pytest.mark.parametrize("instance_override", [False, True])
def test_stop_restores_the_original_generation_method(tmp_path, instance_override):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        original = bot._generate_response
        if instance_override:
            bot._generate_response = original
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        assert bot._generate_response is not original
        await runtime.stop()
        await runtime.stop()
        assert bot._generate_response == original
        assert ("_generate_response" in bot.__dict__) is instance_override
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("response", [None, ProviderResult("")])
def test_an_empty_model_result_does_not_make_a_send_a_completion(tmp_path, response):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def generate():
            return response

        bot.generate = generate
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "failed"
        assert record.delivered_ids
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


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
        # authored by the configured operator actor instead, and names the bot as
        # the account that really posted the text.
        posted = bot.channels[int(settings.channel_id)].sent[0]
        assert posted.author.id == bot.user.id
        assert notice.author.id == settings.operator_id
        assert notice.notice_author.id == bot.user.id
        assert isinstance(notice.author.id, int)
        assert f"<@{bot.user.id}>" in notice.content
        assert request.task in notice.content
        # The notice was posted by the poll task, which is nobody's turn: it is
        # never mistaken for something this request delivered.
        assert record.notice_id not in record.delivered_ids
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_the_notice_row_is_the_self_accounts_own_not_human_traffic(tmp_path):
    """A self client signs in as a user account, so ``.bot`` proves nothing."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        request = _submit(settings)
        await _wait_for_record(settings, request.request_id)
        notice = bot.injected[0]
        posted = bot.channels[int(settings.channel_id)].sent[0]
        # The real self account: a user account, whose own messages say bot=False.
        assert getattr(bot.user, "bot", False) is False
        assert getattr(posted.author, "bot", False) is False
        for message in (notice, posted):
            author = MaxwellBot._memory_author(message)
            assert author.id == bot.user.id
            assert MaxwellBot._memory_author_is_bot(bot, author) is True
        writer = object.__new__(MaxwellBot)
        writer._connection = SimpleNamespace(user=bot.user)
        writer._message_memory_content = lambda message: message.content
        writer._reply_meta_from_message = lambda message: {}
        for message in (notice, posted):
            row = writer._message_memory_item(message)
            assert row["author_id"] == str(bot.user.id)
            assert row["author_is_bot"] is True
            assert _detect_source(row) == "bot"
        # A raw payload carries the id as text while the client holds an int.
        assert (
            MaxwellBot._memory_author_is_bot(
                bot, SimpleNamespace(id=str(bot.user.id), display_name="dame", bot=False)
            )
            is True
        )
        assert (
            MaxwellBot._memory_author_is_bot(
                bot,
                SimpleNamespace(id=str(settings.operator_id), display_name="root", bot=False),
            )
            is False
        )
        # The operator is still a person, and still the permission actor.
        assert MaxwellBot._memory_author_is_bot(bot, notice.author) is False
        assert notice.author.id == settings.operator_id
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_marked_notice_after_a_good_call_does_not_pass_the_turn(tmp_path):
    """A public error posted after the model answered is still not the answer."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def good():
            return ProviderResult("the answer")

        async def render_fails(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
            with notice_send():
                sent = await message.channel.send("something went wrong on my end")
                record_delivery(bot, message.channel, sent, None)

        bot.generate = good
        bot.turn = render_fails
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "failed"
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert "published no reply" in record.failure
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_notice_with_no_model_call_is_a_failed_turn(tmp_path):
    """A gate notice is a delivery, but a turn no model completed is not a pass."""

    async def notice_only(message, content):
        # What a sleep gate and a public error both do: post and return.
        await message.channel.send("the dame is sleeping rn, back in ~3m.")

    async def scenario():
        settings, bot, runtime, request, record = await _one(tmp_path, body=notice_only)
        assert record.status == "failed"
        assert record.returned is True
        # The notice stays in the receipt: it is what the operator reads to see
        # why this request did not pass.
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert "model call did not complete" in record.failure
        assert record.reply_text.startswith("the dame is sleeping")
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_progress_post_after_the_model_returns_is_not_output(tmp_path):
    """The real placeholder is marked where it is posted, not timed by the harness."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        seen = {}

        async def progress_after_the_call(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
            # A real ToolProgress, posted after the model call has already
            # returned: nothing about the timing says progress, the mark does.
            progress = ToolProgress(message)
            await progress.start()
            seen["posted"] = getattr(progress.posted, "id", None)

        bot.turn = progress_after_the_call
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert seen["posted"] == int(str(bot.http.next_id))
        assert record.status == "failed"
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert "published no reply" in record.failure
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_an_error_notice_after_a_failed_call_is_not_output(tmp_path):
    """A public error is posted after the model call failed, not as an answer."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def failing():
            raise RuntimeError("provider down")

        async def error_turn(message, content):
            try:
                await bot._generate_response([{"role": "user", "content": content}])
            except RuntimeError:
                await message.channel.send("something went wrong on my end")

        bot.generate = failing
        bot.turn = error_turn
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "failed"
        assert record.returned is True
        assert record.delivered_ids == [str(bot.http.next_id)]
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_an_error_notice_after_a_good_call_is_not_output_either(tmp_path):
    """The last call decides, so a later failure cannot pass on its own notice."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError("follow-up down")
            return ProviderResult("working on it", tool_calls=[{"id": "1"}])

        async def partial(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
            try:
                await bot._generate_response([{"role": "user", "content": content}])
            except RuntimeError:
                await message.channel.send("something went wrong on my end")

        bot.generate = flaky
        bot.turn = partial
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "failed"
        assert record.delivered_ids == [str(bot.http.next_id)]
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_an_answer_delivered_before_a_later_failure_still_counts(tmp_path):
    """The record is about delivery: what the model published is still evidence."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError("follow-up down")
            return ProviderResult("here it is")

        async def partial(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
            await message.channel.send("here it is")
            try:
                await bot._generate_response([{"role": "user", "content": content}])
            except RuntimeError:
                await message.channel.send("something went wrong on my end")

        bot.generate = flaky
        bot.turn = partial
        request = _submit(settings)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "completed"
        # The answer and the notice are both deliveries; only the answer counts.
        assert len(record.delivered_ids) == 2
        assert record.delivered_ids[0] == str(bot.http.next_id - 1)
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["silent", "lost_response_caught", "lost_response_raised"])
def test_a_silent_turn_is_a_failure_not_a_pass(tmp_path, case):
    """Missing acknowledged IDs cannot prove Discord received no message."""

    async def silent(message, content):
        if case != "silent":
            message.channel._bot.http.lose_response = True
            if case == "lost_response_caught":
                try:
                    await message.channel.send("uncertain reply")
                except TimeoutError:
                    pass
            else:
                await message.channel.send("uncertain reply")
        return None

    async def scenario():
        settings, bot, runtime, request, record = await _one(tmp_path, body=silent)
        assert record.status == "failed"
        assert record.returned is (case != "lost_response_raised")
        assert record.delivered_ids == []
        assert "no_response" not in record.failure
        assert "unacknowledged sends, if any, may still have reached Discord" in record.failure
        if case != "silent":
            assert bot.http.calls[-1] == (str(settings.channel_id), {"content": "uncertain reply"})
            assert bot.http.next_id == int(record.notice_id) + 1
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_reply_the_harness_cannot_read_back_is_still_a_delivery(tmp_path):
    """A readback 404 is recorded as a readback failure, never as a failed turn."""

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)

        async def direct_post(message, content):
            """Post the way a plugin does: through HTTP, with no channel object.

            The model call is the turn's own, as it is for a real plugin post; the
            delivery then happens outside it, so the record counts it.
            """
            await bot._generate_response([{"role": "user", "content": content}])
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


def test_start_unhooks_http_after_generation_observation_fails(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        original_send = bot.http.send_message
        bot._generate_response = None
        runtime = DiracSmokeRuntime(bot, settings)

        with pytest.raises(SmokeProtocolError):
            await runtime.start()

        assert bot.http.send_message.__self__ is original_send.__self__
        assert bot.http.send_message.__func__ is original_send.__func__
        assert bot._turn_observer is None
        assert runtime._poll is None
        assert runtime._started is False
        await bot._reply_queue.close()

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
# a request the operator deletes
# --------------------------------------------------------------------------


def test_a_request_deleted_before_it_is_read_is_withdrawn_without_a_record(tmp_path):
    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        request = _submit(settings)
        path = request_path(settings, request.request_id)
        path.unlink()  # the operator deletes it between discovery and the read
        await runtime._handle(path)
        assert not status_path(settings, request.request_id).exists()
        assert bot.injected == []
        assert bot.http.calls == []
        await runtime.stop()

    asyncio.run(scenario())


def test_a_vanished_request_does_not_stop_the_poll_loop(tmp_path, monkeypatch):
    """The next request still runs, before and after the withdrawn one."""
    real_listing = dirac_runtime.request_files

    async def scenario():
        settings, bot, runtime = await _ready(tmp_path)
        phantom = request_path(settings, "f" * 32)
        real = _submit(settings, task="say pong")
        listings = []

        def with_phantom_once(settings_):
            listings.append(1)
            if len(listings) == 1:
                return [phantom]
            return real_listing(settings_)

        monkeypatch.setattr(dirac_runtime, "request_files", with_phantom_once)
        record = await _wait_for_record(settings, real.request_id)
        assert len(listings) > 1  # the loop polled again after the phantom
        assert record.status == "completed"
        assert not status_path(settings, phantom.stem).exists()
        assert runtime._poll is not None
        assert runtime._poll.done() is False
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_malformed_request_is_recorded_and_does_not_stop_polling(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        malformed_id = "e" * 32
        malformed_path = request_path(settings, malformed_id)
        malformed_path.write_text("{not json", encoding="utf-8")
        valid = _submit(settings, task="still process the next request")
        stamp = time.time()
        os.utime(malformed_path, (stamp - 10, stamp - 10))
        os.utime(request_path(settings, valid.request_id), (stamp, stamp))
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()

        malformed = await _wait_for_record(settings, malformed_id)
        completed = await _wait_for_record(settings, valid.request_id)
        assert malformed.status == "failed"
        assert completed.status == "completed"
        assert runtime._poll is not None and not runtime._poll.done()
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_request_deleted_between_the_scan_and_the_stamp_is_skipped(
    tmp_path, monkeypatch
):
    settings = _settings(tmp_path)
    request = build_request(request_id="d" * 32, task="withdrawn")
    path = request_path(settings, request.request_id)
    create_json_exclusive(path, request.as_json())
    real_glob = Path.glob

    def vanishing_glob(self, pattern):
        """Yield what the scan saw, after the operator deleted it."""
        for found in real_glob(self, pattern):
            found.unlink()
            yield found

    monkeypatch.setattr(Path, "glob", vanishing_glob)
    assert request_files(settings) == []


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


@pytest.mark.parametrize("settlement", ["registered", "taskless"])
def test_an_input_that_expires_while_queued_never_runs(
    tmp_path, monkeypatch, caplog, settlement
):
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
        for _ in range(50):
            await asyncio.sleep(0)
            if not bot._reply_queue.active(channel):
                break
        if settlement == "registered":
            bot.dispatch_failure = "registered"
        else:
            # The queue must register a task for the confirmed case; an ordinary
            # dispatch_failure always queues, so raise before the queue is reached.
            monkeypatch.setattr(
                bot,
                "_on_message_impl",
                AsyncMock(
                    side_effect=RuntimeError("synthetic failure before any queue registration")
                ),
            )
        failed = _submit(settings, task="fail after the queue registers a task")
        failed_record = await _wait_for_record(settings, failed.request_id)
        for _ in range(100):
            if "settlement is unconfirmed" not in failed_record.failure:
                break
            await asyncio.sleep(0.01)
            failed_record = _record_of(settings, failed.request_id)
        assert failed_record.status == "failed"
        assert "RuntimeError" in failed_record.failure
        if settlement == "registered":
            # A registered task settles confirmed: not an unconfirmed stop, and
            # the runtime keeps processing the next request.
            assert "unconfirmed" not in failed_record.failure
            assert failed_record.returned is False
            assert failed_record.delivered_ids == []
            assert not any("fail after the queue" in item for item in ran)
            bot.dispatch_failure = ""
            bot.turn = bot._default_turn
            next_request = _submit(settings, task="run after pre-start cancellation")
            assert (await _wait_for_record(settings, next_request.request_id)).status == "completed"
            assert ran == ["blocker"]
        else:
            # Nothing was ever registered, so settlement cannot be confirmed: the
            # poller stops fail-closed, says so, and processes nothing further.
            assert "owned input settlement is unconfirmed" in failed_record.failure
            assert "no registered task to settle" in caplog.text
            state = read_json_object(runtime_state_path(settings), "runtime state")
            assert state["status"] == "stop_unconfirmed"
            assert state["observed_at"]
            poll = runtime._poll
            assert poll is not None
            await poll
            assert runtime._stop_requested is True
            later = _submit(settings, task="not processed after the fail-closed stop")
            for _ in range(50):
                await asyncio.sleep(0)
            assert not status_path(settings, later.request_id).exists()
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
        assert "unconfirmed" not in record.failure
        bot.dispatch = True
        following = _submit(settings, task="admit after an ordinary gate")
        assert (await _wait_for_record(settings, following.request_id)).status == "completed"
        await runtime.stop()

    asyncio.run(scenario())


def test_concurrent_stops_wait_for_the_same_poll_without_recancelling(tmp_path):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        poll_started = asyncio.Event()
        cancellation_seen = asyncio.Event()
        release = asyncio.Event()
        cancellations = 0

        async def slow_poll():
            nonlocal cancellations
            poll_started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancellations += 1
                cancellation_seen.set()
                await release.wait()

        runtime = DiracSmokeRuntime(bot, settings)
        runtime._poll_loop = slow_poll
        await runtime.start()
        await poll_started.wait()
        first_stop = asyncio.create_task(runtime.stop())
        await cancellation_seen.wait()
        second_stop = asyncio.create_task(runtime.stop())
        await asyncio.sleep(0)
        assert not first_stop.done()
        assert not second_stop.done()

        release.set()
        await asyncio.gather(first_stop, second_stop)
        assert cancellations == 1
        assert runtime._poll is None
        assert bot._turn_observer is None
        assert read_json_object(runtime_state_path(settings), "runtime state")["status"] == "stopped"
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_unconfirmed_poll_stop_is_not_reported_as_stopped(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr(dirac_runtime, "CLEANUP_SECONDS", 0.01)
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        cancellation_seen = asyncio.Event()
        poll_started = asyncio.Event()
        release = asyncio.Event()
        cancellations = 0

        async def slow_poll():
            nonlocal cancellations
            poll_started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancellations += 1
                cancellation_seen.set()
                await release.wait()

        runtime = DiracSmokeRuntime(bot, settings)
        runtime._poll_loop = slow_poll
        await runtime.start()
        poll = runtime._poll
        assert poll is not None
        await poll_started.wait()
        await runtime.stop()
        await cancellation_seen.wait()
        assert runtime._poll is poll
        assert not poll.done()
        state = read_json_object(runtime_state_path(settings), "runtime state")
        assert state["status"] == "stop_unconfirmed"
        assert bot._turn_observer is None

        await runtime.stop()
        assert cancellations == 1
        assert read_json_object(runtime_state_path(settings), "runtime state")["status"] == "stop_unconfirmed"
        release.set()
        await poll
        await runtime.stop()
        assert runtime._poll is None
        assert read_json_object(runtime_state_path(settings), "runtime state")["status"] == "stopped"
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["target", "operator", "notice", "injection"])
def test_unconfirmed_stop_cannot_resume_into_notice_or_injection(
    tmp_path, monkeypatch, stage
):
    async def scenario():
        monkeypatch.setattr(dirac_runtime, "CLEANUP_SECONDS", 0.01)
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        entered, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        owner = bot.channels[int(settings.channel_id)] if stage == "notice" else bot if stage == "injection" else runtime
        method = {"target": "_target_channel", "operator": "_operator", "notice": "send", "injection": "_on_message_impl"}[stage]
        original = getattr(owner, method)

        async def delayed_operation(*args, **kwargs):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
            return await original(*args, **kwargs)

        monkeypatch.setattr(owner, method, delayed_operation)
        await runtime.start()
        poll = runtime._poll
        request = _submit(settings, deadline_seconds=30.0)
        await asyncio.wait_for(entered.wait(), timeout=1)
        await runtime.stop()
        assert cancelled.is_set()
        assert not poll.done()
        assert bot._turn_observer is (runtime._observer if stage == "injection" else None)
        state = read_json_object(runtime_state_path(settings), "runtime state")
        assert state["status"] == "stop_unconfirmed"

        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(poll, timeout=1)
        record = _record_of(settings, request.request_id)
        assert record.status == "interrupted"
        assert bool(record.notice_id) == (stage in {"notice", "injection"})
        assert len(bot.injected) == (1 if stage == "injection" else 0)
        if stage == "injection":
            assert bot._reply_queue.depth(str(settings.channel_id)) == 0
            assert len(bot.channels[int(settings.channel_id)].sent) == 1
        assert runtime._observer.outstanding() == []
        await runtime.stop()
        assert bot._turn_observer is None
        assert runtime._poll is None
        assert read_json_object(runtime_state_path(settings), "runtime state")["status"] == "stopped"
        await bot._reply_queue.close()

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
            await bot._generate_response([{"role": "user", "content": content}])
            await message.channel.send("partial before stop")
            await bot.release.wait()

        bot.turn = blocking
        request = _submit(settings)
        channel = bot.channels[int(settings.channel_id)]
        for _ in range(200):
            await asyncio.sleep(0.05)
            path = status_path(settings, request.request_id)
            if path.exists() and _record_of(settings, request.request_id).status == "running" and len(channel.sent) == 2:
                break
        assert len(channel.sent) == 2
        await runtime.stop()
        record = _record_of(settings, request.request_id)
        assert record.status == "interrupted"
        assert record.status in TERMINAL_STATUSES
        assert record.delivered_ids == [str(channel.sent[1].id)]
        assert record.returned is False
        assert bot._turn_observer is None
        assert bot.http.send_message.__self__ is unwrapped.__self__
        assert bot.http.send_message.__func__ is unwrapped.__func__
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["target_fetch", "notice_send"])
def test_the_deadline_covers_the_notice_not_only_the_turn(tmp_path, stage):
    """A started send is not proof of a confirmed notice or an injected turn."""

    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        channel = bot.channels[int(settings.channel_id)]
        release = asyncio.Event()  # never set

        async def stalled_fetch(*args, **kwargs):
            if stage == "notice_send":
                await bot.http.send_message(channel.id, params={"content": args[0]})
            await release.wait()

        if stage == "target_fetch":
            bot.channels.clear()  # nothing cached: the fetch is on the path
            bot.fetch_channel = stalled_fetch
        else:
            channel.send = stalled_fetch
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        request = _submit(settings, deadline_seconds=1.0)
        record = await _wait_for_record(settings, request.request_id)
        assert record.status == "timeout"
        assert "before the bot's message handler was invoked" in record.failure
        assert ("notice send started but delivery is unconfirmed" in record.failure) == (stage == "notice_send")
        assert record.notice_id == ""
        assert len(bot.http.calls) == (1 if stage == "notice_send" else 0)
        assert bot.injected == []
        await runtime.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["target_fetch", "operator_fetch", "notice_send", "post_dispatch"])
def test_an_upstream_timeout_is_not_the_request_deadline(tmp_path, stage):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        failure_text = "synthetic private request and config contents"
        if stage == "target_fetch":
            bot.channels.clear()

            async def fail_fetch(_channel_id):
                raise TimeoutError(failure_text)

            bot.fetch_channel = fail_fetch
        elif stage == "operator_fetch":
            bot.users.clear()

            async def fail_fetch(_user_id):
                raise TimeoutError(failure_text)

            bot.fetch_user = fail_fetch
        elif stage == "notice_send":
            channel = bot.channels[int(settings.channel_id)]

            async def fail_send(_content, **_kwargs):
                raise TimeoutError(failure_text)

            channel.send = fail_send
        else:
            bot.dispatch_failure = "upstream_timeout"

        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        request = _submit(settings, deadline_seconds=30.0)
        record = await _wait_for_record(settings, request.request_id)
        if stage == "post_dispatch":
            for _ in range(100):
                if "settlement is unconfirmed" not in record.failure:
                    break
                await asyncio.sleep(0.01)
                record = _record_of(settings, request.request_id)

        assert record.status == "failed"
        assert record.failure.startswith("an upstream operation timed out")
        assert ("notice send started but delivery is unconfirmed" in record.failure) == (stage == "notice_send")
        assert failure_text not in record.failure
        assert bool(record.notice_id) == (stage == "post_dispatch")
        assert len(bot.injected) == (1 if stage == "post_dispatch" else 0)
        if stage == "post_dispatch":
            assert record.delivered_ids == []
            assert record.returned is False
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure_site", ["discovery", "record_write"])
def test_fatal_poll_io_cleans_only_owned_inputs_and_restores_hooks(
    tmp_path, monkeypatch, caplog, failure_site
):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        original_send = bot.http.send_message
        original_generate = bot._generate_response

        async def blocking_turn(_message, _content):
            await bot.release.wait()

        bot.turn = blocking_turn
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        channel_id = str(settings.channel_id)
        turn = runtime._observer.open("777", channel_id)
        message = _FakeMessage(
            {"id": "777", "content": "synthetic request payload"},
            bot.channels[int(channel_id)],
            author=bot.user,
        )
        token = TURN_INPUT.set("777")
        await bot._on_message_impl(message)
        TURN_INPUT.reset(token)
        for _ in range(50):
            await asyncio.sleep(0)
            if turn.task is not None and bot._reply_queue.active(channel_id):
                break
        assert turn.task is not None

        unrelated = asyncio.create_task(bot.release.wait())

        def fail_storage(*_args):
            raise OSError("synthetic private path and request payload")

        if failure_site == "discovery":
            monkeypatch.setattr(runtime, "_next_request", fail_storage)
        else:
            monkeypatch.setattr(SmokeRecord, "write", fail_storage)
            _submit(settings)
        poll = runtime._poll
        assert poll is not None
        await poll

        assert turn.task.cancelled()
        assert not unrelated.done()
        assert runtime._poll is None
        assert bot._turn_observer is None
        assert bot.http.send_message.__self__ is original_send.__self__
        assert bot.http.send_message.__func__ is original_send.__func__
        assert bot._generate_response == original_generate
        state = read_json_object(runtime_state_path(settings), "runtime state")
        assert state["status"] == "failed"
        assert state["failure_type"] == "OSError"
        assert "synthetic private" not in caplog.text

        await runtime.stop()
        await runtime.stop()
        assert read_json_object(runtime_state_path(settings), "runtime state")["status"] == "failed"
        unrelated.cancel()
        with pytest.raises(asyncio.CancelledError):
            await unrelated
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_fatal_poll_with_missing_status_storage_reports_unavailable(
    tmp_path, caplog
):
    async def scenario():
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        runtime_state_path(settings).unlink()
        settings.status_dir.rmdir()
        request = _submit(settings, task="synthetic unaccepted request")
        poll = runtime._poll
        assert poll is not None
        await poll

        assert runtime._poll is None
        assert bot._turn_observer is None
        assert bot.http.send_message.__func__ is _FakeHTTP.send_message
        assert not status_path(settings, request.request_id).exists()
        assert "runtime health unavailable (FileNotFoundError)" in caplog.text
        assert "synthetic unaccepted request" not in caplog.text
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["deadline", "after_partial", "stop_during_cleanup"])
def test_a_stuck_owned_task_holds_back_the_next_request(tmp_path, monkeypatch, failure):
    """An unsettled turn cannot overlap a later smoke, even after partial delivery."""

    async def scenario():
        monkeypatch.setattr(dirac_runtime, "CLEANUP_SECONDS", 0.5 if failure == "stop_during_cleanup" else 0.05)
        settings = _settings(tmp_path)
        bot = _FakeBot(settings)

        async def stubborn(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
            await message.channel.send("partial before cancellation")
            try:
                await bot.release.wait()
            except asyncio.CancelledError:
                await asyncio.sleep(1.0)  # swallows the cancel, for now

        bot.turn = stubborn
        bot.dispatch_failure = "after_partial" if failure != "deadline" else ""
        runtime = DiracSmokeRuntime(bot, settings)
        await runtime.start()
        first = _submit(settings, deadline_seconds=30.0 if failure != "deadline" else 1.0)
        record = await _wait_for_record(settings, first.request_id)
        assert record.status == ("timeout" if failure == "deadline" else "failed")
        assert "settlement is unconfirmed" in record.failure
        assert record.delivered_ids == [str(bot.http.next_id)]
        assert record.returned is False
        assert "unacknowledged sends, if any, may still have reached Discord" in record.failure
        if failure == "stop_during_cleanup":
            assert runtime._poll is not None and not runtime._poll.done()
            await runtime.stop()
            interrupted_cleanup = _record_of(settings, first.request_id)
            assert interrupted_cleanup.status == "failed"
            assert "settlement is unconfirmed" not in interrupted_cleanup.failure
            assert interrupted_cleanup.delivered_ids == record.delivered_ids
            assert interrupted_cleanup.returned is False
            assert runtime._observer.outstanding() == []
            assert bot._turn_observer is None
            await bot._reply_queue.close()
            return
        # The stuck coroutine is already running and keeps its own code; the room
        # gets an ordinary turn again for whatever comes next.
        bot.dispatch_failure = ""
        bot.turn = bot._default_turn
        second = _submit(settings, task="second")
        await asyncio.sleep(0.5)
        assert not status_path(settings, second.request_id).exists()
        # Once the stuck task is really gone, the queue moves again.
        held = await _wait_for_record(settings, second.request_id)
        assert held.status == "completed"
        settled_first = _record_of(settings, first.request_id)
        assert settled_first.status == record.status
        assert "settlement is unconfirmed" not in settled_first.failure
        assert "unacknowledged sends, if any, may still have reached Discord" in settled_first.failure
        assert settled_first.delivered_ids == record.delivered_ids
        assert settled_first.returned is True
        assert runtime._observer.outstanding() == []
        await runtime.stop()
        await bot._reply_queue.close()

    asyncio.run(scenario())


def test_a_stalled_readback_cannot_downgrade_a_completed_turn(tmp_path, monkeypatch):
    """The outcome is written first; the readback is optional and bounded."""

    async def scenario():
        monkeypatch.setattr(dirac_runtime, "READBACK_SECONDS", 0.05)
        settings, bot, runtime = await _ready(tmp_path)

        async def direct_post(message, content):
            await bot._generate_response([{"role": "user", "content": content}])
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
            await bot._generate_response([{"role": "user", "content": content}])
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
