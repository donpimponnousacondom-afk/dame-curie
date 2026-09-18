import curses
import os
import re
import signal
import termios
import tty
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TextIO


PADDING = re.compile(r"\$<[\d.]+[*/]?>")


def escape(value: bytes) -> str:
    return PADDING.sub("", value.decode("ascii"))


@dataclass(frozen=True)
class Capabilities:
    cup: bytes
    erase: bytes
    enter: bytes
    leave: bytes
    hide: bytes
    show: bytes
    foreground: bytes | None
    reset: bytes

    @property
    def color(self) -> bool:
        return self.foreground is not None


def capabilities(input: TextIO, output: TextIO, env: Mapping[str, str]) -> Capabilities | None:
    result = None
    if input.isatty() and output.isatty() and env.get("TERM", "dumb") not in {"", "dumb", "unknown"}:
        try:
            curses.setupterm(term=env["TERM"], fd=output.fileno())
            cup, erase, enter, leave = (curses.tigetstr(name) for name in ("cup", "el", "smcup", "rmcup"))
            reset = curses.tigetstr("sgr0") or b""
            foreground = curses.tigetstr("setaf") if reset and "NO_COLOR" not in env and curses.tigetnum("colors") >= 8 else None
            if cup and erase and enter and leave:
                result = Capabilities(cup, erase, enter, leave, curses.tigetstr("civis") or b"",
                                      curses.tigetstr("cnorm") or b"", foreground, reset)
        except curses.error:
            pass
    return result


class Terminal:
    def __init__(self, input: TextIO, output: TextIO, caps: Capabilities) -> None:
        self.input, self.output, self.caps = input, output, caps
        self.resized = True

    def resize(self, signum, frame) -> None:
        self.resized = True

    @contextmanager
    def active(self):
        fd = self.input.fileno()
        attributes = termios.tcgetattr(fd)
        handler = signal.getsignal(signal.SIGWINCH)
        try:
            signal.signal(signal.SIGWINCH, self.resize)
            tty.setcbreak(fd, termios.TCSANOW)
            self.output.write(escape(self.caps.enter + self.caps.hide))
            self.output.flush()
            yield self
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, attributes)
            finally:
                signal.signal(signal.SIGWINCH, handler)
                self.output.write(escape((self.caps.reset if self.caps.color else b"") + self.caps.show + self.caps.leave))
                self.output.flush()

    def size(self) -> tuple[int, int]:
        size = os.get_terminal_size(self.output.fileno())
        return max(1, size.columns - 1), max(1, size.lines)

    def paint(self, lines) -> None:
        _, height = self.size()
        for row in range(height):
            self.output.write(escape(curses.tparm(self.caps.cup, row, 0)))
            if row < len(lines):
                line = lines[row]
                foreground = self.caps.foreground
                if line.timestamp and foreground is not None:
                    self.output.write(escape(curses.tparm(foreground, line.color)))
                    self.output.write(line.text[:line.timestamp])
                    self.output.write(escape(self.caps.reset) + line.text[line.timestamp:])
                else:
                    self.output.write(line.text)
            self.output.write(escape(self.caps.erase))
        self.output.flush()
        self.resized = False
