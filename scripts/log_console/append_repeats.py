from dataclasses import dataclass

from ..log_filter import ANSI, HEALTH, WINDOW
from .append_events import Record


@dataclass
class Repeat:
    started: float
    first: int
    last: int
    first_timestamp: str
    last_timestamp: str
    count: int = 0

    def summary(self) -> str:
        """Describe display suppression, never rewrite the original row."""
        return (f"[REPEAT out-of-band] additional={self.count} "
                f"first_receive#{self.first} last_receive#{self.last} "
                f"first_timestamp={self.first_timestamp} last_timestamp={self.last_timestamp}\n")


class AppendRepeats:
    def __init__(self) -> None:
        self.pending: dict[str, Repeat] = {}

    def suppress(self, record: Record, now: float) -> bool:
        """Only the exact existing local health recognizer can suppress a row."""
        event = record.event
        match = HEALTH.fullmatch(ANSI.sub("", event.source_line).rstrip("\r\n"))
        key = "|".join((match["service"], match["origin"], match["request"].split()[0])) if match else ""
        if not key or len(key.encode("utf-8")) > 256:
            return False
        batch = self.pending.get(key)
        if batch is not None:
            batch.last, batch.last_timestamp = record.sequence, event.timestamp
            batch.count += 1
        elif len(self.pending) < 500:
            self.pending[key] = Repeat(now, record.sequence, record.sequence, event.timestamp, event.timestamp)
        return batch is not None

    def flush(self, now: float, *, force: bool = False) -> list[str]:
        """Expire bounded groups after thirty seconds, even without another arrival."""
        result = []
        for key, batch in tuple(self.pending.items()):
            if force or now - batch.started >= WINDOW:
                if batch.count:
                    result.append(batch.summary())
                del self.pending[key]
        return result
