import json
from collections import OrderedDict
from dataclasses import dataclass, replace

from .events import LogEvent
from .grouping import error_event, record_boundary, traceback_fragment
from .safety import JSONValue


DEFAULT_MAX_EVENTS = 500
DEFAULT_MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
NOT_RETAINED = "Evidence not retained in console history; inspect the authoritative Docker logs."


def stored_event(record: str) -> LogEvent:
    fields = json.loads(record)
    del fields["schema_version"]
    return LogEvent(**fields)


@dataclass(frozen=True)
class HistoryEntry:
    sequence: int
    records: tuple[str, ...]
    is_error: bool
    boundary: str
    partial_reason: str | None = None
    omitted_events: int = 0

    @property
    def evidence_bytes(self) -> int:
        return sum(len(record) for record in self.records)

    @property
    def events(self) -> tuple[LogEvent, ...]:
        return tuple(stored_event(record) for record in self.records)

    @property
    def first(self) -> LogEvent:
        return stored_event(self.records[0])

    def omitted(self, count: int) -> HistoryEntry:
        first = self.first
        original_kind = first.details["original_kind"] if first.kind == "history.omitted" else first.kind
        details: dict[str, JSONValue] = {"omitted_events": count, "original_kind": original_kind}
        request_id = first.details.get("request_id")
        if isinstance(request_id, str) and len(request_id.encode("utf-8", errors="surrogatepass")) <= 256:
            details["request_id"] = request_id
        marker = replace(first, kind="history.omitted", message=NOT_RETAINED, source_line=NOT_RETAINED, details=details)
        return replace(self, records=(marker.json_line(),), omitted_events=count,
                       partial_reason="whole event/error group exceeded the retained-history budget")


@dataclass(frozen=True)
class StreamTail:
    sequence: int
    is_error: bool


class EventHistory:
    def __init__(self, *, max_events: int = DEFAULT_MAX_EVENTS,
                 max_evidence_bytes: int = DEFAULT_MAX_EVIDENCE_BYTES) -> None:
        if max_events < 1 or max_evidence_bytes < 1:
            raise ValueError("history limits must be positive")
        self.max_events = max_events
        self.max_evidence_bytes = max_evidence_bytes
        self.event_count = 0
        self.evidence_bytes = 0
        self.evicted_entries = 0
        self.omitted_events = 0
        self.sequence = 0
        self.streams: OrderedDict[str | None, StreamTail] = OrderedDict()
        self.entries: OrderedDict[int, HistoryEntry] = OrderedDict()

    def recent(self, *, errors_only: bool = False) -> tuple[HistoryEntry, ...]:
        return tuple(entry for entry in reversed(self.entries.values()) if not errors_only or entry.is_error)

    def discard(self, sequence: int) -> None:
        entry = self.entries.pop(sequence)
        self.event_count -= len(entry.records)
        self.evidence_bytes -= entry.evidence_bytes

    def retain(self, entry: HistoryEntry) -> HistoryEntry:
        if entry.sequence in self.entries:
            self.discard(entry.sequence)
        if len(entry.records) > self.max_events or entry.evidence_bytes > self.max_evidence_bytes:
            count = entry.omitted_events or len(entry.records)
            self.omitted_events += count if not entry.omitted_events else 0
            entry = entry.omitted(count)
        if len(entry.records) <= self.max_events and entry.evidence_bytes <= self.max_evidence_bytes:
            while self.entries and (self.event_count + len(entry.records) > self.max_events
                                    or self.evidence_bytes + entry.evidence_bytes > self.max_evidence_bytes):
                self.discard(next(iter(self.entries)))
                self.evicted_entries += 1
            self.entries[entry.sequence] = entry
            self.event_count += len(entry.records)
            self.evidence_bytes += entry.evidence_bytes
        return entry

    def append(self, event: LogEvent) -> HistoryEntry:
        record = event.json_line()
        snapshot = stored_event(record)
        tail = self.streams.get(snapshot.service)
        previous = self.entries.get(tail.sequence) if tail else None
        continuation = tail is not None and tail.is_error and not record_boundary(snapshot)
        if continuation and previous is not None:
            if previous.omitted_events:
                self.omitted_events += 1
                entry = previous.omitted(previous.omitted_events + 1)
            else:
                entry = replace(previous, records=(*previous.records, record))
        else:
            if previous is not None and previous.is_error and previous.boundary == "open":
                self.entries[previous.sequence] = replace(previous, boundary="next-record")
            self.sequence += 1
            is_error = continuation or error_event(snapshot)
            partial = "preceding error lines are outside retained history" if continuation else (
                "traceback fragment has no preceding retained producer record" if traceback_fragment(snapshot) else None
            )
            entry = HistoryEntry(self.sequence, (record,), is_error, "open" if is_error else "standalone", partial)
        entry = self.retain(entry)
        self.streams[snapshot.service] = StreamTail(entry.sequence, entry.is_error)
        self.streams.move_to_end(snapshot.service)
        if len(self.streams) > self.max_events:
            self.streams.popitem(last=False)
        return entry

    def finish(self) -> None:
        for sequence, entry in self.entries.items():
            if entry.boundary == "open":
                self.entries[sequence] = replace(
                    entry, boundary="stream-ended",
                    partial_reason=entry.partial_reason or "stream ended before a following producer record",
                )
