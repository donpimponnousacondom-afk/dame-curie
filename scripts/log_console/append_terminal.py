import fcntl
import os
import signal
import stat
import termios
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from time import monotonic
from types import FrameType

QUEUE_BYTES = 256 * 1024
QUEUE_BLOCKS = 128
BLOCK_BYTES = 64 * 1024
WRITE_QUOTA = 16 * 1024
EXIT_SIGNALS = (
    signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT,
    signal.SIGTSTP, signal.SIGTTIN, signal.SIGTTOU,
)
COLOR_TERMS = frozenset({
    "ansi", "linux", "xterm", "xterm-color", "xterm-256color",
    "screen", "screen-bce", "screen-256color", "screen-256color-bce",
    "screen.xterm-256color", "tmux", "tmux-256color",
    "rxvt", "rxvt-unicode", "rxvt-unicode-256color",
})


class TerminalOwnershipLost(RuntimeError):
    pass


class TerminalLease:
    def __init__(self, input_fd: int, output_fd: int, *, no_keys: bool) -> None:
        self.input_fd = input_fd
        self.output_fd = output_fd
        self.tty = os.isatty(input_fd) and os.isatty(output_fd)
        self.key_candidate = self.tty and not no_keys
        self.keys = self.key_candidate and self.foreground()
        self.color = self.tty and os.environ.get("TERM", "") in COLOR_TERMS and "NO_COLOR" not in os.environ
        self.regular = stat.S_ISREG(os.fstat(output_fd).st_mode)
        self.stop = ""

    def foreground(self) -> bool:
        """Recheck both descriptors; ownership can change after lease acquisition."""
        descriptors = (self.input_fd, self.output_fd) if self.key_candidate else (self.output_fd,)
        return all(not os.isatty(fd) or os.tcgetpgrp(fd) == os.getpgrp() for fd in descriptors)

    def request_stop(self, number: int, frame: FrameType | None) -> None:
        """Signals never enter the output queue or depend on a key byte."""
        self.stop = signal.Signals(number).name
        if number in {signal.SIGTTIN, signal.SIGTTOU}:
            raise TerminalOwnershipLost("Screen viewer lost terminal foreground ownership")

    def geometry(self) -> tuple[int, int]:
        """Resize applies to future appends, never pinned page geometry."""
        size = os.get_terminal_size(self.output_fd) if os.isatty(self.output_fd) else os.terminal_size((120, 24))
        return max(1, min(size.columns, 240)), max(1, min(size.lines, 83))

    def restore_mode(self, settings: list[int | list[bytes | int]]) -> None:
        """Restore a lost foreground lease without being stopped by SIGTTOU."""
        previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            termios.tcsetattr(self.input_fd, termios.TCSANOW, settings)
        finally:
            signal.signal(signal.SIGTTOU, previous)

    def reset_color(self) -> None:
        """Color reset is best effort and never a prerequisite for mode restoration."""
        try:
            if self.foreground():
                os.write(self.output_fd, b"\x1b[0m")
        except OSError:
            pass

    @contextmanager
    def signals(self) -> Iterator[None]:
        """Keep signal ownership outside both terminal and follower lifetimes."""
        handlers = {number: signal.getsignal(number) for number in EXIT_SIGNALS}
        saved_mask = signal.pthread_sigmask(signal.SIG_BLOCK, EXIT_SIGNALS)
        try:
            for number in handlers:
                signal.signal(number, self.request_stop)
            signal.pthread_sigmask(signal.SIG_SETMASK, saved_mask)
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_BLOCK, EXIT_SIGNALS)
            try:
                for number, handler in handlers.items():
                    signal.signal(number, handler)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, saved_mask)

    def quiesce(self) -> None:
        """Atomically ignore repeated exits before restoration, never restore originals."""
        saved_mask = signal.pthread_sigmask(signal.SIG_BLOCK, EXIT_SIGNALS)
        try:
            for number in EXIT_SIGNALS:
                signal.signal(number, signal.SIG_IGN)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, saved_mask)

    @contextmanager
    def active(self) -> Iterator[None]:
        """Restore terminal resources while the enclosing signal lease stays owned."""
        flags = {fd: fcntl.fcntl(fd, fcntl.F_GETFL) for fd in (self.input_fd, self.output_fd)}
        settings = termios.tcgetattr(self.input_fd) if self.keys else None
        with ExitStack() as cleanup:
            for fd, saved in flags.items():
                cleanup.callback(fcntl.fcntl, fd, fcntl.F_SETFL, saved)
            if self.color:
                cleanup.callback(self.reset_color)
            if settings is not None:
                cleanup.callback(self.restore_mode, settings)
            cleanup.callback(self.quiesce)
            fcntl.fcntl(self.output_fd, fcntl.F_SETFL, flags[self.output_fd] | os.O_NONBLOCK)
            if self.keys:
                changed = settings.copy()
                changed[6] = settings[6].copy()
                changed[3] = (changed[3] & ~(termios.ICANON | termios.ECHO)) | termios.ISIG
                changed[6][termios.VMIN] = 0
                changed[6][termios.VTIME] = 0
                termios.tcsetattr(self.input_fd, termios.TCSANOW, changed)
                fcntl.fcntl(self.input_fd, fcntl.F_SETFL, flags[self.input_fd] | os.O_NONBLOCK)
            yield


@dataclass
class Block:
    data: bytes
    sequence: int = 0
    offset: int = 0
    queued_at: float = 0.0


@dataclass
class Gap:
    count: int = 0
    first: int = 0
    last: int = 0

    def add(self, sequence: int) -> None:
        """Ranges bracket affected records; they never imply contiguous loss."""
        self.count += 1
        self.first = min(self.first, sequence) if self.first else sequence
        self.last = max(self.last, sequence)

    def text(self) -> str:
        """Keep cumulative loss reporting bounded."""
        return f"count={self.count} receive-range={self.first}..{self.last} (not every sequence in range)"


class AppendWriter:
    def __init__(self, fd: int) -> None:
        self.fd = fd
        self.blocks: list[Block] = []
        self.bytes = 0
        self.completed_live = 0
        self.dropped = Gap()
        self.suppressed = Gap()
        self.replay_omitted = 0
        self.replay_dropped = Gap()
        self.reported = (0, 0)
        self.broken = False

    def discard(self, index: int, *, pause: bool = False) -> None:
        """Only whole unsent live blocks can be discarded."""
        block = self.blocks.pop(index)
        self.bytes -= len(block.data)
        (self.suppressed if pause else self.dropped).add(block.sequence)

    def reject(self, sequence: int, replay: tuple[int, ...]) -> bool:
        """Count out-of-band blocks separately from their affected replay records."""
        if sequence:
            self.dropped.add(sequence)
        else:
            self.replay_omitted += 1
            for received in replay:
                self.replay_dropped.add(received)
        return False

    def submit(self, text: str, *, sequence: int = 0, replay: tuple[int, ...] = ()) -> bool:
        """Priority blocks may overtake live rows, never a partially written block."""
        data = text.encode("utf-8")
        if len(data) > BLOCK_BYTES:
            return self.reject(sequence, replay)
        while len(self.blocks) >= QUEUE_BLOCKS or self.bytes + len(data) > QUEUE_BYTES:
            victim = next((i for i, block in enumerate(self.blocks) if block.sequence and not block.offset), None)
            if victim is None:
                return self.reject(sequence, replay)
            self.discard(victim)
        block = Block(data, sequence, queued_at=monotonic())
        index = len(self.blocks) if sequence else next(
            (i for i, queued in enumerate(self.blocks) if queued.sequence and not queued.offset), len(self.blocks),
        )
        self.blocks.insert(index, block)
        self.bytes += len(data)
        return True

    def pause(self) -> None:
        """Cancel unsent live output while leaving a partial block intact."""
        for index in range(len(self.blocks) - 1, -1, -1):
            if self.blocks[index].sequence and not self.blocks[index].offset:
                self.discard(index, pause=True)

    def notices(self) -> None:
        """Retry a bounded busy/gap notice when the terminal makes room."""
        current = (self.dropped.count, self.replay_omitted)
        if current != self.reported and len(self.blocks) < QUEUE_BLOCKS and self.bytes < QUEUE_BYTES - 2048:
            text = (f"[NOTICE out-of-band] live display drops: {self.dropped.text()}; "
                    f"out-of-band omitted blocks={self.replay_omitted}; "
                    f"replay/page record omissions: {self.replay_dropped.text()}; busy: retry rejected controls.\n")
            if self.submit(text):
                self.reported = current

    def write_ready(self) -> None:
        """One nonblocking writer owns all offsets and consumes at most 16 KiB."""
        remaining = WRITE_QUOTA
        while self.blocks and remaining:
            block = self.blocks[0]
            try:
                written = os.write(self.fd, block.data[block.offset:block.offset + remaining])
            except BlockingIOError:
                break
            except BrokenPipeError:
                self.broken = True
                break
            if not written:
                break
            remaining -= written
            block.offset += written
            if block.offset == len(block.data):
                self.bytes -= len(block.data)
                self.completed_live = max(self.completed_live, block.sequence)
                self.blocks.pop(0)
