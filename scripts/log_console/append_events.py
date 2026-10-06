import json
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from .events import EventParser, LogEvent
from .grouping import error_event
from .history import stored_event
from .recognizers import COMPOSE, IMAGE_LOG, Envelope, Recognition
from .safety import JSONValue, REDACTED, SGR, terminal_text
from .scopes import VIEWER_SCOPE

RECORD_BYTES = 64 * 1024
ENCODED_BYTES = 256 * 1024
HISTORY_BYTES = 2 * 1024 * 1024
HISTORY_RECORDS = 500
MAX_DEPTH = 32
MAX_STRUCTURES = 4096
# Fixed assertions: an omitted record never re-renders any of its retained bytes.
OMITTED_CONTINUITY = "Evidence omitted: source bytes were never redacted; restart viewer."
OMITTED_SERVICE = "Evidence omitted: service prefix exceeds 256 bytes; one record omitted."
OMITTED_STRUCTURE = "Evidence omitted: structured record exceeds the nesting bound."
OMITTED_MALFORMED = "Evidence omitted: malformed structured record."
OMITTED_BUDGET = "Evidence omitted: serialized record exceeds 256 KiB."


class AppendLines:
    def __init__(self) -> None:
        self.pending = bytearray()
        self.discarding = False
        self.eof = False

    def ready(self) -> bool:
        """Keep framed backlog ahead of further source reads."""
        return b"\n" in self.pending or len(self.pending) > RECORD_BYTES or self.eof

    def take(self) -> list[str | None]:
        """Frame at most sixteen records, discarding oversize bodies to newline."""
        records = []
        while len(records) < 16 and self.pending:
            end = self.pending.find(b"\n")
            if end < 0 and not self.eof:
                if len(self.pending) > RECORD_BYTES or self.discarding:
                    if not self.discarding:
                        records.append(None)
                    self.pending.clear()
                    self.discarding = True
                break
            size = end + 1 if end >= 0 else len(self.pending)
            if not self.discarding:
                records.append(
                    self.pending[:size].decode("utf-8", errors="surrogateescape")
                    if size <= RECORD_BYTES else None
                )
            del self.pending[:size]
            self.discarding = False
        return records


def json_candidate(text: str) -> bool:
    """Identify the generic and image-request formats parsed as JSON."""
    return text.startswith(("{", "[")) or IMAGE_LOG.fullmatch(text) is not None


def bounded_structure(text: str) -> bool:
    """Reject excessive JSON nesting/containers before recursive legacy parsing."""
    depth = structures = 0
    quoted = escaped = False
    for char in text:
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            if char in "[{":
                depth += 1
                structures += 1
            elif char in "]}":
                depth = max(0, depth - 1)
        if depth > MAX_DEPTH or structures > MAX_STRUCTURES:
            return False
    return True


def omitted_event(
    kind: str, message: str, parse_error: str, *, timestamp: str | None = None,
) -> LogEvent:
    """One record is replaced by a fixed assertion; the retained bytes are never re-rendered."""
    observed = datetime.now(UTC).isoformat()
    return LogEvent(
        timestamp=timestamp or observed, timestamp_origin="docker" if timestamp else "observed",
        source_timestamp=None, source_timezone=None, docker_timestamp=timestamp, observed_at=observed,
        service=None, logger=None, level=None,
        scope=VIEWER_SCOPE, kind=kind, message=message, details={}, source_line=message,
        parse_error=parse_error,
    )


class AppendParser(EventParser):
    def __init__(self) -> None:
        super().__init__()
        self.continuity_lost = False

    def content(
        self, envelope: Envelope, service: str | None,
    ) -> tuple[Recognition | None, str, dict[str, JSONValue], str | None]:
        """Keep complete JSON spans local; scan rejected fragments before omitting them."""
        candidate = json_candidate(envelope.message)
        bounded = not candidate or bounded_structure(envelope.message)
        parse_error = None
        if candidate and bounded:
            parsed = EventParser(envelopes=self.envelopes, recognizers=self.recognizers).content(envelope, service)
            parse_error = parsed[3]
            if parse_error is None:
                if service in self.redactor.private_keys or service in self.redactor.config_depth:
                    parsed = (None, REDACTED, {}, None)
                return parsed
        message = self.redactor.text(envelope.message, service=service, redacted=True)
        if len(self.redactor.private_keys) + len(self.redactor.config_depth) > HISTORY_RECORDS:
            self.continuity_lost = True
            self.redactor.private_keys.clear()
            self.redactor.config_depth.clear()
        if self.continuity_lost:
            result = (None, OMITTED_CONTINUITY, {}, "RedactionContinuityLost")
        elif message == REDACTED:
            result = (None, REDACTED, {}, None)
        elif not bounded:
            result = (None, OMITTED_STRUCTURE, {}, "Omitted")
        elif candidate:
            result = (None, OMITTED_MALFORMED, {}, parse_error)
        else:
            result = super().content(replace(envelope, message=message), service)
        return result

    def record(self, line: str | None) -> LogEvent:
        """Omit safely scanned rejections locally; fail closed after actual continuity loss."""
        if line is None:
            self.continuity_lost = True
        if self.continuity_lost:
            return omitted_event("viewer.omitted", OMITTED_CONTINUITY, "RedactionContinuityLost")
        event = self.parse(line)
        compose = COMPOSE.fullmatch(SGR.sub("", line).rstrip("\r\n"))
        if event.parse_error is not None:
            event = omitted_event(
                "viewer.omitted", event.message, event.parse_error, timestamp=event.docker_timestamp,
            )
        elif compose and len(compose["service"].encode("utf-8", errors="surrogatepass")) > 256:
            event = omitted_event("viewer.omitted", OMITTED_SERVICE, "ServicePrefixOmitted")
        return event


@dataclass(frozen=True)
class Record:
    sequence: int
    encoded: str
    warning: bool

    @property
    def event(self) -> LogEvent:
        """Decode on demand instead of retaining a second payload copy."""
        return stored_event(self.encoded)


class AppendHistory:
    def __init__(self) -> None:
        self.records: OrderedDict[int, Record] = OrderedDict()
        self.sequence = 0
        self.bytes = 0
        self.evicted = 0
        self.omitted = 0

    def append(self, event: LogEvent) -> Record:
        """Retain independent records, never correlate traceback fragments by proximity."""
        self.sequence += 1
        parts = []
        size = 0
        fields = {"schema_version": 1, **vars(event)}
        for part in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(fields):
            size += len(part)
            if size > ENCODED_BYTES:
                event = omitted_event(
                    "viewer.omitted", OMITTED_BUDGET, "SerializedBudget",
                )
                parts = [event.json_line()]
                break
            parts.append(part)
        encoded = "".join(parts)
        record = Record(self.sequence, encoded, event.level in {"WARNING", "WARN"} or error_event(event))
        self.omitted += event.parse_error is not None
        while self.records and (len(self.records) >= HISTORY_RECORDS or self.bytes + len(encoded) > HISTORY_BYTES):
            _, removed = self.records.popitem(last=False)
            self.bytes -= len(removed.encoded)
            self.evicted += 1
        self.records[record.sequence] = record
        self.bytes += len(encoded)
        return record


def correlation(event: LogEvent) -> str:
    """Only the existing typed image contract establishes a request ID here."""
    value = event.details.get("request_id")
    return terminal_text(f"image.request_id={value}") if (
        event.kind in {"image.request.start", "image.request.done"}
        and isinstance(value, str) and value
    ) else ""
