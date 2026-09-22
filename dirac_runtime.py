"""Live Dirac smoke runtime: one authorized operator input per poll.

Installed by ``bot.setup_hook`` only when ``DAME_CURIE_DIRAC_SMOKE_CONFIG`` is set
and inert when that config says ``enabled: false``. It invents no bot policy: the
injected input goes through ``bot._on_message_impl``, so the allowlist, blacklist,
``bot_enabled`` and sleep windows stay where they already live. An input those
gates drop is recorded as a request that never became a turn, never retried.

Correlation is the notice's own message id, carried by
``response_observability.TURN_INPUT`` into everything the turn spawns. Deliveries
come from ``record_delivery`` and from a wrapper around the client's
``send_message``, which is what catches file and plugin posts; only deliveries in
the target channel count for the receipt. The runtime sets ``bot._turn_observer``
itself; ``bot.py`` never does.

Eligibility to run is the absence of a record, so the record directory *is* the
ledger: a request that has one never runs again, and wiping that directory makes
the requests still in the request directory runnable again. Nothing here promises
otherwise.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from response_observability import TURN_INPUT
from smoke_protocol import (
    REPLY_FETCH_LIMIT,
    TERMINAL_STATUSES,
    SmokeProtocolError,
    SmokeRecord,
    SmokeRequest,
    SmokeSettings,
    compose_notice,
    iso_now,
    parse_request,
    read_json_object,
    request_files,
    status_path,
    write_json_atomic,
)

if TYPE_CHECKING:
    from bot import MaxwellBot

logger = logging.getLogger(__name__)

# How long a cancelled turn is given to actually stop before the runtime says so.
CLEANUP_SECONDS = 5.0

# The whole optional reply readback, not each fetch: it only enriches a record
# that is already terminal.
READBACK_SECONDS = 5.0


def sent_message_id(payload: object) -> str:
    """The created message id from a raw HTTP send result.

    ``HTTPClient.request`` returns the message payload itself and ``Messageable``
    builds the message from it (abc.py:2038 ``data = await
    state.http.send_message(...)``, 2040 ``state.create_message(data=data)``,
    http.py:1197 ``int(data['id'])``). The id is a dict item: reading it as an
    attribute records nothing at all, for every send, text or multipart.
    """
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("id") or "")


@dataclass
class _Turn:
    """One injected input as the observer sees it."""

    input_id: str
    channel_id: str
    task: asyncio.Task | None = None
    returned: bool = False
    delivered: list[str] = field(default_factory=list)
    done: asyncio.Event = field(default_factory=asyncio.Event)


class _TurnObserver:
    """The synchronous observer ``bot.py`` duck-types on ``bot._turn_observer``.

    ``bot._run_queued_reply`` calls ``start`` and ``finish`` on the turn's own
    task, and ``record_delivery`` calls ``delivered`` from wherever a message was
    created. Every method here is synchronous and non-blocking by contract: an
    await or a raise in any of them would land in the middle of a real reply.
    """

    def __init__(self) -> None:
        self._turns: dict[str, _Turn] = {}

    def open(self, input_id: str, channel_id: str) -> _Turn:
        """Register an input before it is injected, so no turn can outrun it."""
        turn = _Turn(input_id=input_id, channel_id=channel_id)
        self._turns[input_id] = turn
        return turn

    def start(self, input_id: str, channel_id: str, task: object) -> object:
        """Mark the input this turn belongs to, inside the turn's own task."""
        token = TURN_INPUT.set(input_id)
        turn = self._turns.get(input_id)
        if turn is not None:
            turn.task = task
        return token

    def delivered(self, input_id: str, channel_id: str, message_id: str) -> None:
        """Record one real delivery into this input's own room, once.

        A message the turn posted somewhere else is not part of this receipt: the
        record is evidence for the target channel, and implying more than that
        would overstate what was verified. Cross-channel behaviour is a separate
        scenario with its own checks.
        """
        turn = self._turns.get(input_id)
        if turn is None or turn.done.is_set():
            return
        if str(channel_id) != turn.channel_id:
            return
        message_key = str(message_id or "")
        if message_key and message_key not in turn.delivered:
            turn.delivered.append(message_key)

    def finish(self, input_id: str, channel_id: str, returned: bool, token) -> None:
        """Close the input: late deliveries can no longer join its result."""
        turn = self._turns.get(input_id)
        TURN_INPUT.reset(token)
        if turn is not None:
            turn.returned = bool(returned)
            turn.done.set()

    def discard(self, input_id: str) -> None:
        self._turns.pop(input_id, None)

    def outstanding(self) -> list[_Turn]:
        return list(self._turns.values())


class _NoticeInput:
    """The notice message, standing in as the turn's own input.

    Everything is delegated to the real ``Message`` the bot posted, so the turn
    sees real ids, a real channel and a working ``reply``. Only the author is
    replaced: the permission actor is the configured root operator, which is the
    one substitution the grant calls for, because the actor is not the author of
    the text and must not be claimed to be. ``__dict__`` is kept in the slots so
    the bot can still stash its own per-message bookkeeping on the input.
    """

    __slots__ = ("_message", "_author", "__dict__")

    def __init__(self, message, author) -> None:
        self._message = message
        self._author = author

    @property
    def author(self):
        return self._author

    def __getattr__(self, name: str):
        return getattr(self._message, name)


class DiracSmokeRuntime:
    """One pending request per poll, delivered to the real bot, recorded once."""

    def __init__(self, bot: MaxwellBot, settings: SmokeSettings) -> None:
        self.bot = bot
        self.settings = settings
        self._observer = _TurnObserver()
        self._poll: asyncio.Task | None = None
        self._stuck: asyncio.Task | None = None
        self._http = None
        self._http_send = None

    async def start(self) -> None:
        """Validate the mounts, then arm observation. A bad setup raises here.

        The environment variable already opted in, so a missing request mount or
        an unwritable status mount fails the bot's own start: a poll loop that
        cannot record results would deliver real operator input and lose it. Both
        directories must already exist — the operator prepares the mounts, and a
        runtime that created its own status directory would be writing its ledger
        somewhere ephemeral that disappears with the container.
        """
        if not self.settings.enabled:
            logger.info("Dirac smoke runtime disabled in %s", self.settings.config_path)
            return
        for name, directory in (
            ("requests", self.settings.requests_dir),
            ("status", self.settings.status_dir),
        ):
            if not directory.is_dir():
                raise SmokeProtocolError(f"{name} directory is missing: {directory}")
        probe = self.settings.status_dir / f".write-probe-{id(self)}"
        write_json_atomic(probe, {"probe": iso_now()})
        probe.unlink()
        self._interrupt_stale()
        self._observe_sends()
        self.bot._turn_observer = self._observer
        self._poll = asyncio.create_task(self._poll_loop(), name="dirac-smoke-poll")
        self._poll.add_done_callback(self._poll_stopped)
        logger.info(
            "Dirac smoke runtime armed: requests %s, status %s, channel %s",
            self.settings.requests_dir,
            self.settings.status_dir,
            self.settings.channel_id,
        )

    async def stop(self) -> None:
        """Stop polling, cancel only what this runtime owns, then unhook.

        Inputs are cancelled before the observer is cleared, and each owned turn is
        awaited, briefly and boundedly, so its ``finally`` resets the ContextVar
        before the bot goes away. A turn that will not stop is reported as
        unconfirmed rather than claimed as stopped.
        """
        if not self.settings.enabled:
            return
        poll, self._poll = self._poll, None
        if poll is not None and not poll.done():
            poll.cancel()
            await self._wait_for_settle(poll)
        for turn in self._observer.outstanding():
            self._cancel_input(turn.channel_id, turn.input_id)
            await self._wait_for_settle(turn.task)
            self._observer.discard(turn.input_id)
        if self._http is not None and self._http_send is not None:
            self._http.send_message = self._http_send
        self._http = None
        self._http_send = None
        self.bot._turn_observer = None

    # ---- setup ------------------------------------------------------------

    def _interrupt_stale(self) -> None:
        """Close out requests a previous process left non-terminal.

        What such a request already did is unknown, so it is never run again: a
        record exists only after a process accepted it, and that absence is also
        what makes a request eligible, so a restart cannot replay one.
        """
        for path in sorted(self.settings.status_dir.glob("*.json")):
            record = SmokeRecord.from_json(read_json_object(path, "record"))
            if record.status in TERMINAL_STATUSES:
                continue
            record.status = "interrupted"
            record.failure = (
                "the previous process exited with this request non-terminal; "
                "it was never re-run"
            )
            record.write(path)
            logger.warning("Dirac smoke request %s interrupted", path.stem)

    def _observe_sends(self) -> None:
        """Report every real create, whatever path made it.

        ``record_delivery`` sees the main reply path, the message tool and edits;
        file uploads and plugin posts bypass it. ``send_message`` is wrapped in
        place and its result returned untouched, so what is reported is exactly
        what the SDK returned.
        """
        http = getattr(self.bot, "http", None)
        if http is None:
            raise SmokeProtocolError(
                "bot.http is unavailable; deliveries cannot be observed"
            )
        original = http.send_message
        observer = self._observer

        async def observed_send(channel_id, *args, **kwargs):
            payload = await original(channel_id, *args, **kwargs)
            input_id = TURN_INPUT.get()
            if input_id:
                observer.delivered(
                    input_id, str(channel_id), sent_message_id(payload)
                )
            return payload

        http.send_message = observed_send
        self._http = http
        self._http_send = original

    def _poll_stopped(self, task: asyncio.Task) -> None:
        """Report a stopped poll loop. Status IO never becomes a retry loop."""
        if not task.cancelled():
            logger.error("Dirac smoke poll loop stopped: %s", task.exception())

    # ---- polling ----------------------------------------------------------

    async def _poll_loop(self) -> None:
        """One request per interval, oldest clock first, until stopped."""
        TURN_INPUT.set("")  # this task is nobody's turn; its posts are not replies
        while True:
            await asyncio.sleep(self.settings.poll_seconds)
            if self._stuck is not None:
                if not self._stuck.done():
                    # An old turn that ignored its cancel is still running in a
                    # room. Starting another request now would overlap them.
                    continue
                self._stuck = None
            path = self._next_request()
            if path is None:
                continue
            await self.bot.wait_until_ready()
            await self._handle(path)

    def _next_request(self) -> Path | None:
        """The oldest request with no record yet, or None.

        Eligibility is the absence of a record, never a set of finished ids in
        memory: a completed request cannot run again, however many arrive behind
        it, and nothing has to be capped or evicted. A status mount that went away
        is refused rather than read as "nothing is done".
        """
        if not self.settings.status_dir.is_dir():
            raise SmokeProtocolError(
                f"status directory disappeared: {self.settings.status_dir}"
            )
        for path in request_files(self.settings):
            if not status_path(self.settings, path.stem).exists():
                return path
        return None

    async def _handle(self, path: Path) -> None:
        """One request, from accepted to a terminal record.

        Everything a real request can fail at is inside the single try below, so a
        failure always lands as a terminal record instead of an ``accepted``
        status that never moves again. Cancellation is the one outcome that must
        propagate, and it records the interruption first.
        """
        request_id = path.stem
        record_path = status_path(self.settings, request_id)
        record = SmokeRecord(
            request_id=request_id, status="accepted", created_at=iso_now()
        )
        turn: _Turn | None = None
        settled = False
        try:
            request = parse_request(read_json_object(path, "request"), request_id)
            record.created_at = request.created_at
            record.thread_id = request.thread_id
            record.channel_id = request.thread_id or str(self.settings.channel_id)
            record.write(record_path)
            # One deadline for the whole request. Resolving the target, fetching
            # the operator and posting the notice can stall too, and a deadline
            # that only started at the turn would leave those unbounded.
            async with asyncio.timeout(request.deadline_seconds):
                channel = await self._target_channel(request)
                operator = await self._operator()
                operator_name = self.settings.operator_name or str(
                    getattr(operator, "display_name", "") or ""
                )
                notice = await channel.send(
                    compose_notice(
                        request,
                        operator_name=operator_name,
                        operator_id=self.settings.operator_id,
                        bot_id=int(self.bot.user.id),
                    )
                )
                input_id = str(notice.id)
                record.notice_id = input_id
                record.status = "running"
                record.write(record_path)
                turn = self._observer.open(input_id, str(channel.id))
                await self.bot._on_message_impl(_NoticeInput(notice, operator))
                await turn.done.wait()
            # The block above only completes with the turn closed; the deadline is
            # the only way out of it without one.
            record.returned = turn.returned
            record.delivered_ids = list(turn.delivered)
            if not turn.returned:
                record.status = "failed"
                record.failure = "the turn did not return; it raised or was cancelled"
            elif not record.delivered_ids:
                record.status = "failed"
                record.failure = (
                    "the turn returned without delivering a visible message "
                    "(no_response)"
                )
            else:
                record.status = "completed"
            # The outcome reaches disk before the optional readback: a turn that
            # really delivered stays completed even if the readback stalls, fails,
            # or the process stops while it runs.
            record.write(record_path)
            settled = True
            self._observer.discard(turn.input_id)
            if record.status == "completed":
                record.reply_text, record.reply_readback = await self._reply_text(
                    channel, record.delivered_ids
                )
                record.reply_verified = False
                record.write(record_path)
        except TimeoutError:
            # The deadline is a recorded outcome, not an error: what is known is
            # persisted, including any delivery that did happen before it.
            if turn is not None:
                record.delivered_ids = list(turn.delivered)
            if turn is None:
                record.status = "timeout"
                record.failure = (
                    "the deadline expired before the notice was delivered; the "
                    "request was never injected"
                )
            else:
                queued = self._cancel_input(turn.channel_id, turn.input_id)
                settled = await self._wait_for_settle(turn.task)
                record.status = "timeout"
                if turn.task is not None:
                    record.failure = (
                        "the turn exceeded its deadline; only this input was "
                        "cancelled"
                    )
                elif queued:
                    record.failure = (
                        "the input was still waiting in the reply queue and was "
                        "removed unexecuted"
                    )
                else:
                    record.failure = (
                        "no turn was dispatched for the notice within the deadline; "
                        "the bot's own gates or the reply queue dropped it"
                    )
                if not settled:
                    record.failure += (
                        "; the cancelled turn had not stopped within "
                        f"{CLEANUP_SECONDS:g}s, so cleanup is unconfirmed"
                    )
            record.write(record_path)
            if turn is not None:
                self._observer.discard(turn.input_id)
        except SmokeProtocolError as refused:
            record.status = "rejected"
            record.failure = str(refused)
            record.write(record_path)
        except asyncio.CancelledError:
            if settled:
                # The request already has its terminal record; a stop during the
                # optional readback must not rewrite it as interrupted.
                raise
            if turn is not None:
                record.delivered_ids = list(turn.delivered)
            record.status = "interrupted"
            record.failure = (
                "the smoke runtime stopped while this request was in flight"
            )
            record.write(record_path)
            raise
        except Exception as exc:
            if settled:
                # Same reason as cancellation: the outcome is already on disk.
                logger.error(
                    "Dirac smoke request %s was recorded and then failed: %s",
                    request_id,
                    exc,
                )
                return
            # The type and its message, never a traceback: this record is read by
            # an operator and may be copied around.
            record.status = "failed"
            record.failure = f"{type(exc).__name__}: {exc}"[:300]
            record.write(record_path)
            logger.error(
                "Dirac smoke request %s failed: %s", request_id, record.failure
            )

    # ---- one request ------------------------------------------------------

    async def _operator(self):
        """The configured permission actor, as a real SDK user.

        The client's own object is preferred over anything invented here, because
        the turn attributes memory and permissions to a real account. The id must
        be an integer, and the actor must not be the bot itself: the bot never
        answers its own message.
        """
        user = self.bot.get_user(self.settings.operator_id)
        if user is None:
            user = await self.bot.fetch_user(self.settings.operator_id)
        if user is None or not isinstance(getattr(user, "id", None), int):
            raise SmokeProtocolError(
                f"operator {self.settings.operator_id} is not a real user id"
            )
        if int(user.id) == int(self.bot.user.id):
            raise SmokeProtocolError(
                "the configured operator is the bot itself; the bot never "
                "answers its own message"
            )
        return user

    async def _target_channel(self, request: SmokeRequest):
        """The approved channel, or a bot-owned thread inside it. Never a DM.

        These scope checks are the only ones here: allowlists, blacklists and the
        rest belong to the bot, which sees the injected input itself.
        """
        channel_id = int(request.thread_id) if request.thread_id else None
        if channel_id is None:
            channel_id = self.settings.channel_id
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if request.thread_id:
            if not isinstance(channel, discord.Thread):
                raise SmokeProtocolError(f"{request.thread_id} is not a thread")
            if str(channel.parent_id) != str(self.settings.channel_id):
                raise SmokeProtocolError(
                    "the thread is not inside the approved smoke channel"
                )
            # ``Thread.owner_id`` is the thread's creator (threads.py:141 slot,
            # 180 int from the payload), which is what "bot-owned" means and what
            # also covers a standalone thread. An owner that cannot be read is out
            # of scope: nothing here is assumed.
            owner_id = getattr(channel, "owner_id", None)
            if not isinstance(owner_id, int) or owner_id != int(self.bot.user.id):
                raise SmokeProtocolError("the thread was not started by the bot")
        if isinstance(channel, discord.DMChannel) or (
            getattr(channel, "guild", None) is None
        ):
            raise SmokeProtocolError(
                "refusing a direct message; the smoke channel must be a guild channel"
            )
        return channel

    async def _wait_for_settle(self, task: asyncio.Task | None) -> bool:
        """Wait up to ``CLEANUP_SECONDS`` for a cancelled task to actually stop.

        A cancellation is a request, not a result. When the task has not stopped,
        the runtime says so instead of claiming a stopped turn, and it starts no
        further request until that task is really gone.
        """
        if task is None or task.done():
            return True
        await asyncio.wait({task}, timeout=CLEANUP_SECONDS)
        if task.done():
            return True
        self._stuck = task
        logger.warning(
            "Dirac smoke: a cancelled task had not stopped after %gs: %r",
            CLEANUP_SECONDS,
            task,
        )
        return False

    async def _reply_text(
        self, channel, delivered: list[str]
    ) -> tuple[str, list[str]]:
        """What the delivered messages said, fetched by their exact ids.

        Capped in count and in time — the whole readback gets ``READBACK_SECONDS``,
        not each fetch — because it only enriches a record that is already
        terminal, and it must never hold a request open. Text the harness did not
        fetch itself is text it cannot stand behind, so an id it cannot read is
        recorded as exactly that and never turns a delivery into a failed turn.
        The catch is narrow on purpose: the SDK's own HTTP error and ``OSError``,
        which already covers a fetch that ran out of budget.
        """
        parts = []
        unreadable = []
        expires = asyncio.get_running_loop().time() + READBACK_SECONDS
        for message_id in delivered[:REPLY_FETCH_LIMIT]:
            remaining = expires - asyncio.get_running_loop().time()
            if remaining <= 0:
                unreadable.append(f"{message_id} (readback budget spent)")
                continue
            try:
                async with asyncio.timeout(remaining):
                    message = await channel.fetch_message(int(message_id))
            except (discord.HTTPException, OSError) as exc:
                unreadable.append(f"{message_id} ({type(exc).__name__})")
                continue
            parts.append(str(getattr(message, "content", "") or ""))
        return "\n---\n".join(parts), unreadable

    def _cancel_input(self, channel_id: str, input_id: str) -> bool:
        """Cancel exactly this input: not the channel, not the queue behind it."""
        queue = getattr(self.bot, "_reply_queue", None)
        if queue is None:
            return False
        return bool(queue.cancel_message(channel_id, input_id))

