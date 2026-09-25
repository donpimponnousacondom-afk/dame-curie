from dataclasses import dataclass, field
from time import monotonic

from .append_events import AppendHistory, AppendParser, Record, correlation
from .append_render import HELP, LEVELS, Snapshot, event_block, evidence_parts, heading
from .append_repeats import AppendRepeats
from .append_terminal import AppendWriter, TerminalLease
from .events import LogEvent
from .scopes import SCOPE_KEYS, SERVICE_SCOPES, VIEWER_SCOPE


@dataclass
class Filters:
    minimum: int = 1
    scopes: set[str] = field(default_factory=lambda: set(SCOPE_KEYS.values()))
    ollama: bool = False
    folded: bool = True
    tool_depth: int = 0
    provider_depth: int = 0

    def visible(self, event: LogEvent) -> bool:
        """Unknown severity remains visible at INFO, not falsely relabelled INFO."""
        if event.scope == VIEWER_SCOPE:
            return True
        level = "WARNING" if event.level == "WARN" else event.level
        rank = LEVELS.index(level) if level in LEVELS else 1
        local_service = SERVICE_SCOPES[0][0].search(event.service or "") is not None
        return rank >= self.minimum and event.scope in self.scopes and (self.ollama or not local_service)

    def depth(self, event: LogEvent) -> int:
        """Expansion raises detail to JSON; explicit evidence depth takes precedence."""
        depth = self.tool_depth if event.scope == "tool" else self.provider_depth if event.scope == "provider" else 0
        return max(depth, int(not self.folded))


class AppendState:
    def __init__(self, terminal: TerminalLease, writer: AppendWriter) -> None:
        self.terminal = terminal
        self.writer = writer
        self.filters = Filters()
        self.parser = AppendParser()
        self.history = AppendHistory()
        self.repeats = AppendRepeats()
        self.paused = False
        self.resume_after = 0
        self.candidates: tuple[int, ...] = ()
        self.selected: int | None = None
        self.snapshot: Snapshot | None = None
        self.page_number = 0
        self.source_status = "following"
        self.keys_disabled_noticed = False
        self.evidence_lost_noticed = False

    def notice(self, text: str) -> bool:
        """Notices are explicitly outside live receive ordering."""
        return self.writer.submit("[NOTICE out-of-band] " + text + "\n")

    def receive(self, line: str | None) -> None:
        """Ingest independently of all display controls and selected evidence."""
        record = self.history.append(self.parser.record(line))
        if not self.paused and self.filters.visible(record.event):
            now = monotonic()
            if not self.filters.folded or not self.repeats.suppress(record, now):
                self.writer.submit(event_block(
                    record, "LIVE", self.filters.depth(record.event), self.terminal.geometry(), color=self.terminal.color,
                ), sequence=record.sequence)

    def flush_repeats(self, *, force: bool = False) -> None:
        """Summaries remain display-only; history always contains every admitted record."""
        for text in self.repeats.flush(monotonic(), force=force):
            self.writer.submit(text)

    def pause(self) -> None:
        """Anchor catch-up to completed display, not the most recently ingested record."""
        if not self.paused:
            self.resume_after = self.writer.completed_live
            self.paused = True
            self.writer.pause()
            self.flush_repeats(force=True)

    def choices(self, *, errors: bool = False, scope: str = "") -> list[Record]:
        """The error view deliberately ignores severity, scope and Ollama visibility."""
        return [record for record in self.history.records.values() if (
            record.warning if errors else self.filters.visible(record.event) and (not scope or record.event.scope in {scope, VIEWER_SCOPE})
        )]

    def pin(self, record: Record, candidates: tuple[int, ...]) -> None:
        """Capture once so eviction, filter changes and resize cannot swap evidence."""
        self.candidates = candidates
        self.selected = record.sequence
        self.snapshot = Snapshot.build(evidence_parts(record, 2), self.terminal.geometry(), f"receive#{record.sequence}")
        self.page_number = 0

    def replay(self, label: str, *, count: int = 20, errors: bool = False, scope: str = "", freeze: bool = True) -> None:
        """Replay oldest-to-newest within a frozen, bounded matching candidate set."""
        candidates = self.choices(errors=errors, scope=scope)
        chosen = candidates[-count:]
        text = f"[REPLAY out-of-band] {label}; retained={len(candidates)} shown={len(chosen)}\n"
        for record in chosen:
            if count <= 5:
                text += event_block(record, "REPLAY", self.filters.depth(record.event), self.terminal.geometry(), color=self.terminal.color)
            else:
                text += heading(record, "REPLAY", color=self.terminal.color, width=self.terminal.geometry()[0])
        if self.writer.submit(text, replay=tuple(record.sequence for record in chosen)) and freeze:
            if candidates:
                self.pin(candidates[-1], tuple(record.sequence for record in candidates))
            else:
                self.candidates, self.selected, self.snapshot = (), None, None

    def resume(self) -> None:
        """Report unavailable/limited catch-up rather than silently dumping a backlog."""
        if self.paused:
            after = self.resume_after
            candidates = [record for record in self.choices() if record.sequence > after]
            first = next(iter(self.history.records), self.history.sequence + 1)
            unavailable = max(0, first - after - 1)
            self.notice(
                f"resume: received since completed LIVE watermark={self.history.sequence - after}; "
                f"evicted in that range={unavailable}; retained matching={len(candidates)}; "
                f"catch-up limit omissions={max(0, len(candidates) - 20)}; "
                f"cancelled live blocks: {self.writer.suppressed.text()}"
            )
            text = "[REPLAY out-of-band] bounded resume catch-up (may repeat a partial pre-pause row)\n"
            text += "".join(heading(record, "REPLAY", color=self.terminal.color, width=self.terminal.geometry()[0])
                            for record in candidates[-20:])
            self.writer.submit(text, replay=tuple(record.sequence for record in candidates[-20:]))
            self.paused = False

    def navigate(self, delta: int) -> None:
        """Never re-anchor an evicted frozen candidate to a newly arrived event."""
        self.pause()
        candidates = self.candidates or tuple(record.sequence for record in self.choices())
        if not candidates:
            self.notice("no retained matching candidates")
            return
        index = candidates.index(self.selected) if self.candidates else len(candidates) - 1
        target = max(0, min(len(candidates) - 1, index + delta))
        if target == index and self.candidates:
            self.notice("frozen candidate boundary; selection and snapshot unchanged")
            return
        sequence = candidates[target]
        record = self.history.records.get(sequence)
        if record is None:
            self.notice(f"receive#{sequence} evicted; unavailable; selection unchanged")
        else:
            snapshot = Snapshot.build(evidence_parts(record, 2), self.terminal.geometry(), f"receive#{sequence}")
            text, page = snapshot.page(0)
            if self.writer.submit(text, replay=(sequence,)):
                self.candidates = candidates
                self.selected, self.snapshot, self.page_number = sequence, snapshot, page

    def inspect(self) -> None:
        """Enter inspects the pinned snapshot or selects the latest current match."""
        self.pause()
        if self.snapshot is not None and self.snapshot.label != "help":
            self.show_page(0)
        else:
            candidates = self.choices()
            if candidates:
                record = candidates[-1]
                snapshot = Snapshot.build(evidence_parts(record, 2), self.terminal.geometry(), f"receive#{record.sequence}")
                text, page = snapshot.page(0)
                if self.writer.submit(text, replay=(record.sequence,)):
                    self.candidates = tuple(record.sequence for record in candidates)
                    self.selected, self.snapshot, self.page_number = record.sequence, snapshot, page
            else:
                self.notice("no retained matching evidence")

    def show_page(self, number: int) -> None:
        """A rejected page does not advance navigation state."""
        if self.snapshot is None:
            self.notice("no pinned snapshot; Enter inspects, h pins help")
        else:
            text, actual = self.snapshot.page(number)
            if number < 0 or actual != number:
                self.notice("pinned page boundary; clamped")
            replay = (self.selected,) if self.selected is not None else ()
            if self.writer.submit(text, replay=replay):
                self.page_number = actual

    def help(self) -> None:
        """Help shares the single snapshot budget rather than a second evidence ring."""
        self.pause()
        snapshot = Snapshot.build((HELP,), self.terminal.geometry(), "help")
        text, page = snapshot.page(0)
        if self.writer.submit(text):
            self.snapshot, self.page_number = snapshot, page
            self.candidates, self.selected = (), None

    def inspector(self) -> None:
        """Only report counters and correlation actually available in retained records."""
        covered = sum(bool(correlation(record.event)) for record in self.history.records.values())
        lag = monotonic() - min(block.queued_at for block in self.writer.blocks) if self.writer.blocks else 0.0
        self.notice(
            f"LOCAL mode=screen paused={self.paused} minimum={LEVELS[self.filters.minimum]} "
            f"scopes={','.join(sorted(self.filters.scopes))} ollama={self.filters.ollama} "
            f"folded={self.filters.folded} T={self.filters.tool_depth} P={self.filters.provider_depth}\n"
            f"| source={self.source_status}; records={len(self.history.records)}/500 bytes={self.history.bytes}/2097152 "
            f"evicted={self.history.evicted} omitted={self.history.omitted}; receive#{self.history.sequence}\n"
            f"| queue blocks={len(self.writer.blocks)}/128 bytes={self.writer.bytes}/262144 oldest_age={lag:.3f}s "
            f"completed_live={self.writer.completed_live}; drops {self.writer.dropped.text()}\n"
            f"| out-of-band omitted blocks={self.writer.replay_omitted}; replay/page records {self.writer.replay_dropped.text()}; "
            f"pause suppression {self.writer.suppressed.text()}; image request ID coverage={covered}/{len(self.history.records)}; "
            "no generic request/turn/job joins; no runtime/private reads; retention bounds are not RSS bounds."
        )
