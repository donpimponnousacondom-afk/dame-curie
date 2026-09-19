import os
import select
import signal
import subprocess
import sys
from collections.abc import Callable
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from time import monotonic, sleep

from .append_controls import dispatch
from .append_events import AppendLines
from .append_state import AppendState
from .append_terminal import AppendWriter, TerminalLease
from .input import AppendKeys

READ_QUOTA = 16 * 1024
EOF_GRACE = 0.250
TERM_GRACE = 5.0
REAP_GRACE = 1.0
GROUP_GRACE = 1.0
CLEANUP_INTERVAL = 0.050


@dataclass(frozen=True)
class AppendResult:
    requested: bool
    incomplete: bool


class AppendLoop:
    def __init__(self, source_fd: int, terminal: TerminalLease) -> None:
        self.source_fd = source_fd
        self.terminal = terminal
        self.writer = AppendWriter(terminal.output_fd)
        self.state = AppendState(terminal, self.writer)
        self.lines = AppendLines()
        self.keys = AppendKeys()
        self.eof_deadline = 0.0

    def keyboard(self) -> None:
        """Check foreground ownership immediately before every key read."""
        if not self.terminal.foreground():
            self.terminal.stop = "terminal foreground ownership lost"
            return
        try:
            chunk = os.read(self.terminal.input_fd, 64)
        except BlockingIOError:
            return
        if not chunk:
            self.terminal.stop = "keyboard EOF"
        else:
            for key in self.keys.feed(chunk, monotonic()):
                if self.terminal.stop:
                    break
                dispatch(self.state, key)

    def source(self) -> None:
        """The source is an owned binary pipe, never a TextIO iterator."""
        try:
            chunk = os.read(self.source_fd, READ_QUOTA)
        except BlockingIOError:
            return
        self.lines.pending.extend(chunk)
        self.lines.eof = not chunk

    def poll(self) -> None:
        """poll supports pipe/TTY and regular-file output without epoll assumptions."""
        poller = select.poll()
        if not self.lines.eof and not self.lines.ready():
            poller.register(self.source_fd, select.POLLIN)
        if self.terminal.keys:
            poller.register(self.terminal.input_fd, select.POLLIN)
        if self.writer.blocks:
            poller.register(self.terminal.output_fd, select.POLLOUT)
        timeout = 0 if self.lines.ready() and not self.eof_deadline else 100
        if self.eof_deadline:
            timeout = min(timeout, max(0, int((self.eof_deadline - monotonic()) * 1000)))
        ready = dict(poller.poll(timeout))
        if self.terminal.stop:
            return
        if self.terminal.input_fd in ready and self.terminal.keys:
            self.keyboard()
        if self.source_fd in ready and not self.terminal.stop:
            self.source()
        if self.terminal.output_fd in ready and not self.terminal.stop:
            self.writer.write_ready()

    def finish_source(self) -> None:
        """Clean EOF has a bounded output grace, not a lossless-export promise."""
        if self.lines.eof and not self.lines.pending and not self.eof_deadline:
            self.state.source_status = "EOF"
            self.state.flush_repeats(force=True)
            self.state.notice("source EOF; draining admitted output for at most 250 ms")
            self.eof_deadline = monotonic() + EOF_GRACE

    def run(self, source_exit: Callable[[], int | None]) -> AppendResult:
        """Bound ingress, records, key bytes and writes independently each iteration."""
        os.set_blocking(self.source_fd, False)
        self.state.notice(
            f"screen append-only; keys={'on' if self.terminal.keys else 'off'}; "
            "h help; Space pause; i local state; q/Ctrl-C viewer only. "
            "INFO/all scopes; Ollama hidden; adapted provenance; known-pattern redaction only. "
            "Unmarked paste can run keys; --no-keys disables them."
        )
        if self.terminal.regular:
            self.state.notice("regular-file output: plaintext/keyless; filesystem writes may block (no terminal latency guarantee)")
        while not self.terminal.stop and not self.writer.broken:
            if not self.terminal.foreground():
                self.terminal.stop = "terminal foreground ownership lost"
                break
            self.keys.expire(monotonic())
            if self.keys.disabled and not self.state.keys_disabled_noticed:
                self.state.keys_disabled_noticed = self.state.notice("keys disabled: incomplete control sequence; Ctrl-C exits")
            if self.state.parser.continuity_lost and not self.state.evidence_lost_noticed:
                self.state.evidence_lost_noticed = self.state.notice("evidence disabled: redaction continuity lost; subsequent records omitted; restart viewer")
            self.state.flush_repeats()
            self.writer.notices()
            for line in self.lines.take():
                if self.terminal.stop:
                    break
                self.state.receive(line)
            self.finish_source()
            if self.eof_deadline and ((not self.writer.blocks and source_exit() is not None) or monotonic() >= self.eof_deadline):
                break
            self.poll()
        requested = bool(self.terminal.stop) or self.writer.broken
        incomplete = not requested and bool(self.writer.blocks or self.writer.dropped.count or self.writer.replay_omitted or self.state.history.omitted)
        return AppendResult(requested, incomplete)


def follower_status(process: subprocess.Popen[bytes]) -> int | None:
    """Observe exit without reaping: its PID must remain reserved until group cleanup."""
    status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if status is None:
        return None
    return status.si_status if status.si_code == os.CLD_EXITED else -status.si_status


def stop_follower(process: subprocess.Popen[bytes]) -> bool:
    """Keep the leader unreaped through group signals, then verify disappearance."""
    with ExitStack() as cleanup:
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGTSTP):
            cleanup.callback(signal.signal, number, signal.getsignal(number))
            signal.signal(number, signal.SIG_IGN)
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        deadline = monotonic() + TERM_GRACE
        while follower_status(process) is None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            sleep(min(CLEANUP_INTERVAL, remaining))
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=REAP_GRACE)
        except subprocess.TimeoutExpired:
            return False
        deadline = monotonic() + GROUP_GRACE
        gone = False
        while not gone:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                gone = True
            except PermissionError:
                break
            remaining = deadline - monotonic()
            if gone or remaining <= 0:
                break
            sleep(min(CLEANUP_INTERVAL, remaining))
    return gone


def follow_screen(command: list[str], env: dict[str, str], *, no_keys: bool) -> None:
    """Keep the existing source selection but isolate its stdin/session and cleanup."""
    terminal = TerminalLease(sys.stdin.fileno(), sys.stdout.fileno(), no_keys=no_keys)
    process = subprocess.Popen(
        command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=False, bufsize=0, start_new_session=True,
    )
    try:
        with terminal.active():
            result = AppendLoop(process.stdout.fileno(), terminal).run(lambda: follower_status(process))
            returncode = follower_status(process)
    finally:
        try:
            complete = stop_follower(process)
        finally:
            process.stdout.close()
        if not complete:
            raise RuntimeError("Screen viewer follower cleanup incomplete after TERM/KILL/reap/group-verification deadlines")
    if not result.requested and returncode != 0:
        raise RuntimeError("Screen viewer source exited unexpectedly or did not exit at EOF")
    if result.incomplete:
        raise RuntimeError("Screen viewer output/evidence incomplete; bounded output grace or admission budget exhausted")
