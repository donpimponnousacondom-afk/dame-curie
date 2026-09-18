from dataclasses import dataclass

from ..log_filter import ANSI, HEALTH, WINDOW


@dataclass
class HealthRepeat:
    started: float
    latest: int
    count: int = 0


class HealthDisplay:
    def __init__(self) -> None:
        self.pending: dict[tuple[str, str, str], HealthRepeat] = {}
        self.hidden: set[int] = set()
        self.notes: dict[int, str] = {}

    def reveal(self, batch: HealthRepeat, now: float) -> None:
        if batch.count:
            self.hidden.discard(batch.latest)
            self.notes[batch.latest] = f"[{batch.count} additional repeats in {min(now - batch.started, WINDOW):g}s; latest occurrence shown]"

    def feed(self, line: str, sequence: int, now: float) -> None:
        match = HEALTH.fullmatch(ANSI.sub("", line).rstrip("\r\n"))
        key = (match["service"], match["origin"], match["request"].split()[0]) if match else None
        batch = self.pending.get(key)
        repeated = batch is not None and now - batch.started <= WINDOW
        if repeated:
            batch.latest, batch.count = sequence, batch.count + 1
            self.hidden.add(sequence)
        self.flush(now)
        if key is not None and not repeated:
            if len(self.pending) >= 500:
                self.reveal(self.pending.pop(next(iter(self.pending))), now)
            self.pending[key] = HealthRepeat(now, sequence)

    def flush(self, now: float, *, force: bool = False) -> bool:
        changed = False
        for key, batch in tuple(self.pending.items()):
            if force or now - batch.started >= WINDOW:
                self.reveal(batch, now)
                changed = changed or bool(batch.count)
                del self.pending[key]
        return changed

    def prune(self, retained: set[int]) -> None:
        self.hidden.intersection_update(retained)
        for sequence in tuple(self.notes):
            if sequence not in retained:
                del self.notes[sequence]
