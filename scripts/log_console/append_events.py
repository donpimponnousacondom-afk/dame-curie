import json
from collections import OrderedDict
from dataclasses import dataclass, replace

from .events import EventParser, LogEvent
from .grouping import error_event
from .history import stored_event
from .recognizers import COMPOSE, Envelope, Recognition
from .safety import JSONValue, REDACTED, SGR, terminal_text

RECORD_BYTES = 64 * 1024
ENCODED_BYTES = 256 * 1024
HISTORY_BYTES = 2 * 1024 * 1024
HISTORY_RECORDS = 500
MAX_DEPTH = 32
MAX_STRUCTURES = 4096


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


class AppendParser(EventParser):
    def __init__(self) -> None:
        super().__init__()
        self.continuity_lost = False

    def content(
        self, envelope: Envelope, service: str | None,
    ) -> tuple[Recognition | None, str, dict[str, JSONValue], str | None]:
        """Track multiline hiding before format-aware redaction; never raw-fallback."""
        message = self.redactor.text(envelope.message, service=service, redacted=True)
        if len(self.redactor.private_keys) + len(self.redactor.config_depth) > HISTORY_RECORDS:
            self.continuity_lost = True
            self.redactor.private_keys.clear()
            self.redactor.config_depth.clear()
        if self.continuity_lost or not bounded_structure(message):
            self.continuity_lost = True
            result = (None, "Evidence omitted: redaction continuity unavailable; restart viewer.", {}, "Omitted")
        elif message == REDACTED:
            result = (None, REDACTED, {}, None)
        else:
            result = super().content(replace(envelope, message=message), service)
            if result[3] is not None:
                result = (result[0], "Evidence omitted: malformed structured record.", {}, result[3])
        return result

    def record(self, line: str | None) -> LogEvent:
        """Fail closed after framing gaps rather than expose subsequent secret fragments."""
        text = line or ""
        compose = COMPOSE.fullmatch(SGR.sub("", text).rstrip("\r\n"))
        if line is None or (compose and len(compose["service"].encode("utf-8", errors="surrogatepass")) > 256):
            self.continuity_lost = True
        if self.continuity_lost:
            text = "Evidence omitted: oversized/unsafe record lost redaction continuity; restart viewer."
        event = self.parse(text)
        if self.continuity_lost:
            event = replace(event, kind="viewer.omitted", parse_error="RedactionContinuityLost")
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
                event = replace(
                    event, message="Evidence omitted: serialized record exceeds 256 KiB.",
                    source_line="[omitted, including source metadata]", service=None, logger=None,
                    details={}, parse_error="SerializedBudget",
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
