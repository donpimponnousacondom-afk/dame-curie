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


class AppendKeys:
    def __init__(self) -> None:
        self.state = "idle"
        self.prefix = bytearray()
        self.started = 0.0
        self.disabled = False
        self.string_escape = False
        self.paste_tail = bytearray()
        self.utf8_remaining = 0
        self.parameters_done = False

    def expire(self, now: float) -> None:
        """Never timeout back into command dispatch halfway through a sequence."""
        if self.state != "idle" and now - self.started >= 2.0:
            self.disabled = True
        if self.disabled:
            self.prefix.clear()
            self.paste_tail.clear()

    def feed(self, chunk: bytes, now: float) -> list[str]:
        """Consume split controls/paste/UTF-8 as a stream, not individual key reads."""
        self.expire(now)
        keys = []
        for byte in chunk:
            if self.disabled:
                break
            if self.state == "idle":
                if byte == 27 or byte >= 128:
                    self.begin(byte, now)
                elif byte not in {1, 0, 127}:
                    keys.append(chr(byte))
            elif self.state == "utf8":
                self.disabled = not 128 <= byte <= 191
                self.utf8_remaining -= 1
                if not self.utf8_remaining:
                    self.state = "idle"
            elif self.state == "paste":
                self.paste_tail.append(byte)
                del self.paste_tail[:-6]
                if self.paste_tail == b"\x1b[201~":
                    self.state = "idle"
                    self.paste_tail.clear()
            elif self.state in {"osc", "string"}:
                if (self.string_escape and byte == 92) or (self.state == "osc" and byte == 7):
                    self.state = "idle"
                self.string_escape = byte == 27
            else:
                self.control(byte)
        return keys

    def begin(self, byte: int, now: float) -> None:
        """C1 introducers must not expose their ASCII suffixes as commands either."""
        self.started = now
        self.prefix.clear()
        self.parameters_done = False
        controls = {27: "escape", 155: "csi", 143: "ss3", 157: "osc", 144: "string", 158: "string", 159: "string"}
        if byte in controls:
            self.state = controls[byte]
            if byte == 155:
                self.prefix.append(91)
        elif 194 <= byte <= 244:
            self.state = "utf8"
            self.utf8_remaining = 1 if byte < 224 else 2 if byte < 240 else 3
        elif byte != 156:
            self.disabled = True
        self.string_escape = False

    def control(self, byte: int) -> None:
        """Bound prefixes and consume finals without executing suffix letters."""
        if len(self.prefix) == 64:
            self.disabled = True
            self.prefix.clear()
            return
        self.prefix.append(byte)
        if self.state == "escape":
            self.state = {
                91: "csi", 79: "ss3", 93: "osc", 80: "string",
                94: "string", 95: "string",
            }.get(byte, "idle" if 48 <= byte < 127 else "intermediate")
            self.string_escape = False
            if byte == 27 or byte < 32 or byte >= 127:
                self.disabled = True
        elif self.state in {"csi", "ss3"}:
            if 64 <= byte <= 126:
                self.state = "paste" if self.prefix == b"[200~" else "idle"
            elif 32 <= byte <= 47:
                self.parameters_done = True
            elif not (48 <= byte <= 63 and not self.parameters_done):
                self.disabled = True
        elif self.state == "intermediate":
            if 48 <= byte <= 126:
                self.state = "idle"
            elif not 32 <= byte <= 47:
                self.disabled = True
