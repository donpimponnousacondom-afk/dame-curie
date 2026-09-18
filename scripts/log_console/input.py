import re
from collections.abc import Iterator


MAX_PENDING_BYTES = 2 * 1024 * 1024
ESCAPE_KEY = re.compile(r"^\x1b(?:\[[0-?]*[ -/]*[@-~]|O.)")


class LineBuffer:
    def __init__(self, *, limit: int = MAX_PENDING_BYTES) -> None:
        self.limit = limit
        self.pending = bytearray()
        self.discarding = False

    def feed(self, chunk: bytes) -> Iterator[str | None]:
        parts = chunk.split(b"\n")
        for index, part in enumerate(parts):
            if not self.discarding:
                self.pending.extend(part)
                if len(self.pending) > self.limit:
                    self.pending.clear()
                    self.discarding = True
                    yield None
            if index < len(parts) - 1:
                if not self.discarding:
                    yield self.pending.decode("utf-8", errors="surrogateescape") + "\n"
                self.pending.clear()
                self.discarding = False

    def finish(self) -> Iterator[str]:
        if self.pending:
            yield self.pending.decode("utf-8", errors="surrogateescape")
            self.pending.clear()


class KeyBuffer:
    def __init__(self) -> None:
        self.pending = ""
        self.updated = 0.0

    def feed(self, chunk: bytes, now: float) -> list[str]:
        self.pending += chunk.decode("ascii", errors="ignore")
        self.updated = now
        keys = []
        while self.pending:
            if self.pending == "\x1b":
                break
            if self.pending.startswith(("\x1b[", "\x1bO")):
                match = ESCAPE_KEY.match(self.pending)
                if not match:
                    if len(self.pending) > 64:
                        self.pending = ""
                    break
                arrow = {"\x1b[A": "[", "\x1bOA": "[", "\x1b[B": "]", "\x1bOB": "]"}.get(match[0])
                if arrow:
                    keys.append(arrow)
                self.pending = self.pending[match.end():]
            else:
                keys.append(self.pending[0])
                self.pending = self.pending[1:]
        return keys

    def flush(self, now: float) -> list[str]:
        keys = []
        if self.pending and now - self.updated >= 0.1:
            keys = ["\x1b"] if self.pending == "\x1b" else []
            self.pending = ""
        return keys
