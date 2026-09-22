"""Operator smoke protocol: settings, immutable requests, one result record.

A Dirac smoke run is one authorized operator instruction delivered to the live bot
as a real Discord message, plus a durable record of what the bot did with it. This
module owns what the host CLI and the bot container must agree on: where the files
live, what a request looks like, how the single record is written. It imports
nothing from the bot, from Discord, or from the network.

One config file, a read-only ``requests`` directory the operator writes, and a
writable status directory the bot owns. Both directories resolve against the
config file's own directory, so one config works at
``/srv/dame-curie/dirac/smoke/config.json`` on the host and ``/smoke/config.json``
in the container.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SMOKE_CONFIG_ENV = "DAME_CURIE_DIRAC_SMOKE_CONFIG"

# Discord's message limit, and the most the visible notice header may take.
NOTICE_LIMIT = 2000
NOTICE_HEADER_LIMIT = 250

# Replies the record self-reports, fetched by exact delivered id.
REPLY_FETCH_LIMIT = 5

DEFAULT_POLL_SECONDS = 5.0
DEFAULT_DEADLINE_SECONDS = 300.0

# A request is finished in any of these, and nothing may run it again after.
TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "rejected", "timeout", "interrupted"}
)


class SmokeProtocolError(RuntimeError):
    """A config, request or scope problem this protocol refuses to run."""


def iso_now() -> str:
    """Current UTC time in the one format every request and record uses."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def config_id(raw: object, field_name: str) -> int:
    """A Discord snowflake from config or request JSON, as a real int.

    ``isdigit`` is deliberate: a snowflake is always a positive run of digits, and
    this rejects the shapes ``int()`` would take differently (``'-5'``, ``'1_0'``)
    without needing exception handling.
    """
    text = str(raw).strip()
    if not text.isdigit():
        raise SmokeProtocolError(f"{field_name} must be a Discord id, got {raw!r}")
    return int(text)


def _number(raw: dict, key: str, default: float, low: float, high: float) -> float:
    """An optional numeric setting, bounded. Absent means the documented default."""
    if key not in raw:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SmokeProtocolError(f"config {key} must be a number")
    if not low <= value <= high:
        raise SmokeProtocolError(f"config {key} must be between {low} and {high}")
    return float(value)


def _directory(config_path: Path, raw: object, key: str) -> Path:
    """A directory setting, resolved against the config file's own directory."""
    if not isinstance(raw, str) or not raw.strip():
        raise SmokeProtocolError(f"config {key} must be a non-empty directory name")
    return (config_path.parent / raw.strip()).resolve()


@dataclass(frozen=True)
class SmokeSettings:
    """Resolved smoke configuration, identical for the CLI and the runtime."""

    config_path: Path
    requests_dir: Path
    status_dir: Path
    enabled: bool
    channel_id: int
    operator_id: int
    operator_name: str
    poll_seconds: float

    @classmethod
    def from_env(cls) -> SmokeSettings:
        """Load the config named by ``DAME_CURIE_DIRAC_SMOKE_CONFIG``."""
        raw = os.environ.get(SMOKE_CONFIG_ENV, "").strip()
        if not raw:
            raise SmokeProtocolError(f"{SMOKE_CONFIG_ENV} is not set")
        return cls.load(Path(raw))

    @classmethod
    def load(cls, path: Path) -> SmokeSettings:
        """Parse one config file.

        ``enabled`` must be stated explicitly. The operator opted in with the
        environment variable, so an unreadable, incomplete or mistyped config
        raises rather than starting a session that looks like it ran a smoke
        test, and ``enabled: false`` is the only quiet setting.
        """
        config_path = Path(path).expanduser()
        raw = read_json_object(config_path, "config")
        enabled = raw.get("enabled")
        if not isinstance(enabled, bool):
            raise SmokeProtocolError(
                f"config {config_path} must state 'enabled': true or false"
            )
        for key in ("channel_id", "operator_id"):
            if key not in raw:
                raise SmokeProtocolError(f"config {config_path} is missing {key!r}")
        operator_name = raw.get("operator_name", "")
        if not isinstance(operator_name, str):
            raise SmokeProtocolError("config operator_name must be text")
        return cls(
            config_path=config_path,
            requests_dir=_directory(
                config_path, raw.get("requests_dir"), "requests_dir"
            ),
            status_dir=_directory(config_path, raw.get("status_dir"), "status_dir"),
            enabled=enabled,
            channel_id=config_id(raw["channel_id"], "channel_id"),
            operator_id=config_id(raw["operator_id"], "operator_id"),
            operator_name=operator_name.strip(),
            poll_seconds=_number(
                raw, "poll_seconds", DEFAULT_POLL_SECONDS, 0.25, 300.0
            ),
        )


@dataclass(frozen=True)
class SmokeRequest:
    """One operator instruction. Written once by the CLI and never edited.

    The deadline is the request's own, not a config knob: it bounds the whole
    execution (resolve, notice, injection, the turn) and is recorded with the
    request that asked for it.
    """

    request_id: str
    created_at: str
    task: str
    thread_id: str
    deadline_seconds: float

    def as_json(self) -> dict:
        return asdict(self)


def build_request(
    *,
    request_id: str,
    task: str,
    thread_id: str = "",
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    created_at: str = "",
) -> SmokeRequest:
    """Validate one request and freeze it.

    The task is capped below Discord's limit minus the notice header, so the
    notice is never split into two messages and never silently truncated.
    """
    if not request_id or not request_id.isalnum():
        raise SmokeProtocolError("request_id must be a name, not a path")
    text = str(task)
    if not text.strip():
        raise SmokeProtocolError("request task must be non-empty text")
    limit = NOTICE_LIMIT - NOTICE_HEADER_LIMIT
    if len(text) > limit:
        raise SmokeProtocolError(
            f"request task is {len(text)} characters; the notice leaves {limit}"
        )
    thread = str(thread_id or "").strip()
    if thread and not thread.isdigit():
        raise SmokeProtocolError("thread_id must be a Discord id")
    if isinstance(deadline_seconds, bool) or not isinstance(
        deadline_seconds, (int, float)
    ):
        raise SmokeProtocolError("deadline_seconds must be a number")
    if not 1.0 <= float(deadline_seconds) <= 86400.0:
        raise SmokeProtocolError("deadline_seconds must be between 1 and 86400")
    return SmokeRequest(
        request_id=request_id,
        created_at=created_at or iso_now(),
        task=text,
        thread_id=thread,
        deadline_seconds=float(deadline_seconds),
    )


def parse_request(raw: dict, request_id: str) -> SmokeRequest:
    """Read one operator request file, refusing anything the runtime cannot run.

    A refusal is recorded as a rejection against the request, not raised at the
    poll loop: a malformed file must not stop the runtime or be retried forever.
    """
    task = raw.get("task")
    if not isinstance(task, str):
        raise SmokeProtocolError("request task must be text")
    thread = raw.get("thread_id") or ""
    if not isinstance(thread, str):
        raise SmokeProtocolError("request thread_id must be text")
    created_at = raw.get("created_at") or ""
    if not isinstance(created_at, str):
        raise SmokeProtocolError("request created_at must be text")
    recorded = raw.get("request_id")
    if recorded is not None and str(recorded) != request_id:
        raise SmokeProtocolError("request id does not match its file name")
    return build_request(
        request_id=request_id,
        task=task,
        thread_id=thread,
        deadline_seconds=raw.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS),
        created_at=created_at,
    )


def compose_notice(
    request: SmokeRequest, *, operator_name: str, operator_id: int, bot_id: int
) -> str:
    """The visible notice plus the task, within Discord's message limit.

    The bot mention is load-bearing: it is what makes this notice a hard ping, so
    the injected input reaches the reply path instead of a watch debounce. The
    notice states the three things the operator grant requires the room to be
    able to read for itself: no human typed it, root authorized it while AFK, and
    the permission actor is not the author of the text.
    """
    actor = f"{operator_name} ({operator_id})" if operator_name else str(operator_id)
    header = (
        f"\N{WARNING SIGN} HARNESS SMOKE TEST <@{bot_id}>\n"
        "No human typed this. Root authorized it while AFK.\n"
        f"Permission actor: {actor}, separate from the author of this text.\n"
        "Task follows.\n"
    )
    if len(header) > NOTICE_HEADER_LIMIT:
        raise SmokeProtocolError(
            f"notice header is {len(header)} characters; the limit is "
            f"{NOTICE_HEADER_LIMIT}"
        )
    notice = f"{header}{request.task}"
    if len(notice) > NOTICE_LIMIT:
        raise SmokeProtocolError(f"notice would be {len(notice)} characters")
    return notice


@dataclass
class SmokeRecord:
    """The single mutable record for one request: state and result together.

    ``status`` is the whole state machine. ``accepted`` and ``running`` are the
    only non-terminal states; everything in ``TERMINAL_STATUSES`` is final. A
    ``completed`` record means the turn returned, its own model call produced
    usable output, and the target channel received model output rather than only a
    notice or a progress placeholder — never that the task's goal was achieved,
    and never that a tool's own claim about itself was verified. ``reply_text`` is the
    harness's own fetch of the exact delivered ids, so it is evidence of what was
    delivered, not an evaluation, and ``reply_verified`` stays false.
    ``reply_readback`` names the ids that could not be read back and why: a
    delivery that happened is not undone by a harness readback failure.
    """

    request_id: str
    status: str
    created_at: str
    updated_at: str = ""
    channel_id: str = ""
    thread_id: str = ""
    notice_id: str = ""
    delivered_ids: list[str] = field(default_factory=list)
    returned: bool = False
    failure: str = ""
    reply_text: str = ""
    reply_verified: bool = False
    reply_readback: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, raw: dict) -> SmokeRecord:
        """Rebuild a record from disk, tolerating fields a later version adds."""
        return cls(
            request_id=str(raw.get("request_id") or ""),
            status=str(raw.get("status") or ""),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            channel_id=str(raw.get("channel_id") or ""),
            thread_id=str(raw.get("thread_id") or ""),
            notice_id=str(raw.get("notice_id") or ""),
            delivered_ids=[str(item) for item in raw.get("delivered_ids") or []],
            returned=bool(raw.get("returned", False)),
            failure=str(raw.get("failure") or ""),
            reply_text=str(raw.get("reply_text") or ""),
            reply_verified=bool(raw.get("reply_verified", False)),
            reply_readback=[str(item) for item in raw.get("reply_readback") or []],
        )

    def as_json(self) -> dict:
        return asdict(self)

    def write(self, path: Path) -> None:
        """Stamp the clock and publish this record atomically, mode 0600."""
        self.updated_at = iso_now()
        write_json_atomic(path, self.as_json())


def read_json_object(path: Path, what: str) -> dict:
    """Parse a JSON object. Surfacing a failure belongs to the caller."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise SmokeProtocolError(f"{what} {path} is not a JSON object")
    return raw


def _write_private(path: Path, payload: dict) -> None:
    """Write ``payload`` to ``path`` mode 0600, complete on disk before return."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def write_json_atomic(path: Path, payload: dict) -> None:
    """Replace ``path`` with ``payload`` atomically, readable only by its owner."""
    tmp = path.with_name(f".{path.name}.tmp")
    _write_private(tmp, payload)
    os.replace(tmp, path)


def create_json_exclusive(path: Path, payload: dict) -> None:
    """Publish a new file without a check-then-create race.

    ``os.link`` publishes an already complete file and fails if the name is
    taken, so two submitters cannot overwrite each other and a reader can never
    see half a request. The temporary is dot-prefixed: if the link loses the
    race, what is left behind is invisible to every scanner here instead of
    looking like a request.
    """
    tmp = path.with_name(f".{path.name}.new")
    _write_private(tmp, payload)
    os.link(tmp, path)
    os.unlink(tmp)


def request_path(settings: SmokeSettings, request_id: str) -> Path:
    """Where the operator's immutable request for ``request_id`` lives."""
    return settings.requests_dir / f"{request_id}.json"


def status_path(settings: SmokeSettings, request_id: str) -> Path:
    """Where the runtime's record for ``request_id`` lives.

    Same file name in a different directory: the name is the correlation, and the
    request file is never rewritten to carry state.
    """
    return settings.status_dir / f"{request_id}.json"


def request_files(settings: SmokeSettings) -> list[Path]:
    """Operator request files, oldest clock first.

    Ordered by file modification time, not by name: request ids are random, so a
    name-based order is not an arrival order. Dot-prefixed names are the
    temporaries of the two writers here and are never requests.

    A file that cannot be stamped right now — deleted between the directory scan
    and the stamp, or unreadable for the moment — is skipped, not an error: a
    withdrawn request is no reason to stop reading the ones still there, and the
    next poll picks it up if it is really there.
    """
    found = []
    for path in settings.requests_dir.glob("*.json"):
        if path.name.startswith("."):
            continue
        try:
            found.append((path.stat().st_mtime, path.name, path))
        except OSError:
            continue
    return [path for _, _, path in sorted(found)]
