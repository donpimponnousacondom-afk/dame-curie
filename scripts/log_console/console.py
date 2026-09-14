import os
import selectors
from collections.abc import Callable
from dataclasses import replace
from time import monotonic
from typing import TextIO

from .controls import ConsoleState
from .events import EventParser
from .health import HealthDisplay
from .history import EventHistory, NOT_RETAINED
from .input import KeyBuffer, LineBuffer, MAX_PENDING_BYTES
from .render import render_frame
from .terminal import Capabilities, Terminal


class Console:
    def __init__(self) -> None:
        self.parser = EventParser()
        self.history = EventHistory()
        self.state = ConsoleState()
        self.health = HealthDisplay()
        self.lines = LineBuffer()
        self.keys = KeyBuffer()

    def ingest(self, line: str | None, now: float) -> None:
        if line is None:
            event = replace(self.parser.parse(f"Console input record exceeded {MAX_PENDING_BYTES} bytes. {NOT_RETAINED}"),
                            kind="console.omitted", parse_error="InputRecordTooLarge")
            self.history.omitted_events += 1
        else:
            event = self.parser.parse(line)
        entry = self.history.append(event)
        if line is not None:
            self.health.feed(line, entry.sequence, now)
        self.health.prune(set(self.history.entries))

    def key(self, key: str) -> None:
        if self.state.key(key, self.history):
            raise KeyboardInterrupt

    def frame(self, width: int, height: int, *, color: bool):
        return render_frame(self.history, self.state, width, height, color=color,
                            hidden=frozenset(self.health.hidden), notes=tuple(self.health.notes.items()))

    def read_ready(self, key: selectors.SelectorKey, now: float) -> tuple[bool, bool]:
        chunk = os.read(key.fd, 64 if key.data == "keys" else 4096)
        if key.data == "keys":
            if not chunk:
                raise KeyboardInterrupt
            for character in self.keys.feed(chunk, now):
                self.key(character)
            running, changed = True, True
        else:
            for line in (self.lines.feed(chunk) if chunk else self.lines.finish()):
                self.ingest(line, now)
            running = bool(chunk)
            changed = self.state.view in {"live", "inspector"}
        return running, changed

    def loop(self, logs: TextIO, terminal: Terminal, stopped: Callable[[], bool]) -> None:
        dirty, running, painted = True, True, float("-inf")
        with selectors.DefaultSelector() as selector:
            selector.register(terminal.input, selectors.EVENT_READ, "keys")
            selector.register(logs, selectors.EVENT_READ, "logs")
            while running:
                ready = selector.select(timeout=0.1)
                if stopped():
                    raise KeyboardInterrupt
                now = monotonic()
                for key, _ in sorted(ready, key=lambda item: item[0].data != "keys"):
                    keep_open, changed = self.read_ready(key, now)
                    running, dirty = running and keep_open, dirty or changed
                for character in self.keys.flush(now):
                    self.key(character)
                    dirty = True
                dirty = self.health.flush(now) or dirty
                if terminal.resized or dirty and (now - painted >= 0.1 or not running):
                    terminal.paint(self.frame(*terminal.size(), color=terminal.caps.color))
                    dirty, painted = False, now


def run_console(logs: TextIO, output: TextIO, *, input: TextIO, caps: Capabilities, stopped: Callable[[], bool]) -> None:
    console = Console()
    try:
        with Terminal(input, output, caps).active() as terminal:
            console.loop(logs, terminal, stopped)
    finally:
        console.history.finish()
        console.health.flush(monotonic(), force=True)
