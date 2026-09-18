import fcntl
import io
import os
import pty
import re
import selectors
import signal
import struct
import subprocess
import sys
import termios
from pathlib import Path
from time import monotonic
from unittest.mock import Mock

import pytest

from scripts import log_filter
from scripts.log_console import terminal
from scripts.log_console.terminal import capabilities


WORKER = r'''
import fcntl
import os
import signal
import sys
import termios
sys.path.insert(0, sys.argv[1])
from scripts import log_filter
fcntl.ioctl(sys.stdin.fileno(), termios.TIOCSCTTY, 0)
os.tcsetpgrp(sys.stdin.fileno(), os.getpgrp())
mode = sys.argv[2]
producer = "import os, signal\n"
if mode == "partial":
    producer += "os.write(1, b'bot-1 | partial record without newline')\n"
elif mode == "flood":
    producer += "for i in range(100000): os.write(1, b'bot-1 | flood fixture\\n')\n"
elif mode == "event":
    producer += "os.write(1, b'bot-1 | 2026-09-12 10:22:48,123 - bot - INFO - EARLY-EVENT\\n')\n"
    producer += "os.write(1, b'bot-1 | 2026-09-12 10:22:49,123 - bot - INFO - READY-EVENT \\x1b]52;c;clipboard\\x07\\x1b[2J\\n')\n"
producer += "signal.pause()\n"
command = [sys.executable, "-B", "-u", "-c", producer]
original = log_filter.subprocess.Popen
children = []
def launch(argv, **kwargs):
    assert argv == command, "only the synthetic follower may be launched"
    assert kwargs["start_new_session"] and kwargs["stdin"] == subprocess.DEVNULL
    child = original(argv, **kwargs)
    children.append(child)
    return child
import subprocess
log_filter.subprocess.Popen = launch
numbers = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGTSTP, signal.SIGWINCH)
before = {number: signal.getsignal(number) for number in numbers}
old_path = sys.path.copy()
log_filter.follow_logs(command, {"PATH": "/usr/local/bin:/usr/bin:/bin"})
assert {number: signal.getsignal(number) for number in numbers} == before
assert sys.path == old_path
assert len(children) == 1 and children[0].returncode is not None
print("RESTORED CHILD_REAPED", flush=True)
'''


def read_until(fd, marker, *, timeout=8):
    data = b""
    deadline = monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while marker not in data and monotonic() < deadline:
            ready = selector.select(max(0, deadline - monotonic()))
            if ready:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                data += chunk
    assert marker in data, f"synthetic PTY marker absent: {marker!r}; tail={data[-1500:]!r}"
    return data


@pytest.fixture
def tty_worker(tmp_path):
    opened = []
    processes = []

    def start(mode, *, no_color=False):
        master, slave = pty.openpty()
        opened.extend((master, slave))
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 180, 0, 0))
        original = termios.tcgetattr(slave)
        env = {"HOME": str(tmp_path), "PATH": "/usr/local/bin:/usr/bin:/bin", "TERM": "screen-256color"}
        if no_color:
            env["NO_COLOR"] = ""
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", WORKER, str(Path(__file__).parents[1]), mode],
            stdin=slave, stdout=slave, stderr=slave, cwd=tmp_path, env=env, start_new_session=True,
        )
        processes.append(process)
        return process, master, slave, original

    yield start
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
    for fd in opened:
        os.close(fd)


@pytest.mark.parametrize("mode", ["silent", "partial", "flood"])
@pytest.mark.parametrize("action", ["q", "ctrl-c", "sigterm", "ctrl-c+sigterm"])
def test_actual_pty_exit_restores_tty_and_reaps_only_follower(tty_worker, tmp_path, mode, action):
    sentinel = subprocess.Popen([sys.executable, "-B", "-c", "import signal; signal.pause()"],
                                env={"HOME": str(tmp_path)}, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        process, master, slave, original = tty_worker(mode)
        read_until(master, b"Curie logs")
        active = termios.tcgetattr(slave)
        assert not active[3] & termios.ICANON and not active[3] & termios.ECHO
        started = monotonic()
        if action == "sigterm":
            process.send_signal(signal.SIGTERM)
        else:
            os.write(master, b"q" if action == "q" else b"\x03")
            if action == "ctrl-c+sigterm":
                process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=5) == 0
        assert monotonic() - started < 4
        output = read_until(master, b"RESTORED CHILD_REAPED")
        assert b"\x1b[?1049l" in output
        assert termios.tcgetattr(slave) == original
        assert sentinel.poll() is None
    finally:
        sentinel.terminate()
        sentinel.wait(timeout=5)


@pytest.mark.parametrize("no_color", [False, True], ids=["color", "NO_COLOR"])
def test_actual_pty_timestamps_respect_no_color_and_neutralize_terminal_injection(tty_worker, no_color):
    process, master, slave, original = tty_worker("event", no_color=no_color)
    output = read_until(master, b"\\x1b]52")
    os.write(master, b"q")
    assert process.wait(timeout=5) == 0
    output += read_until(master, b"RESTORED CHILD_REAPED")
    assert b"\x1b]52;c;clipboard" not in output and b"\x1b[2J" not in output
    assert b"\\x1b]52" in output
    colors = re.findall(rb"\x1b\[(?:3[0-7]|9[0-7]|38;5;\d+)m", output)
    assert bool(colors) is not no_color
    assert termios.tcgetattr(slave) == original


def test_actual_pty_consumes_escape_sequences_and_literal_escape_returns_live(tty_worker):
    process, master, slave, original = tty_worker("event")
    read_until(master, b"READY-EVENT")
    os.write(master, b"r")
    read_until(master, b"Curie logs | recent")
    for chunk in (b"\x1b", b"[", b"1;2A", b"i"):
        os.write(master, chunk)
    read_until(master, b"selected_entry=2")
    os.write(master, b"\x1b")
    read_until(master, b"Curie logs | live")
    os.write(master, b"q")
    assert process.wait(timeout=5) == 0
    assert termios.tcgetattr(slave) == original


@pytest.mark.parametrize("format", ["auto", "console", "plain", "jsonl"])
def test_real_piped_follower_is_noninteractive_without_paint(tmp_path, format):
    program = (
        "import sys; sys.path.insert(0, sys.argv[1]); from scripts.log_filter import follow_logs; "
        "follow_logs([sys.executable, '-B', '-c', \"print('bot-1 | synthetic piped fixture')\"], {}, "
        "output_format=sys.argv[2])"
    )
    result = subprocess.run([sys.executable, "-B", "-c", program, str(Path(__file__).parents[1]), format],
                            input="q", capture_output=True, text=True, cwd=tmp_path,
                            env={"HOME": str(tmp_path), "TERM": "screen-256color"}, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stderr == "" and "\x1b" not in result.stdout
    if format == "jsonl":
        assert '"schema_version": 1' in result.stdout
    else:
        assert result.stdout == "bot-1 | synthetic piped fixture\n"


PIPED_WORKER = r'''
import os
import signal
import subprocess
import sys
sys.path.insert(0, sys.argv[1])
from scripts import log_filter
ready_read, ready_write = os.pipe()
producer = (
    "import os, signal\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    f"os.write({ready_write}, b'1'); os.close({ready_write})\n"
    "while True: signal.pause()\n"
)
command = [sys.executable, "-B", "-u", "-c", producer]
children = []
original = subprocess.Popen
class Reader:
    def __init__(self, stream):
        self.stream = stream
    def __iter__(self):
        print("SILENT_READ_WAIT", file=sys.stderr, flush=True)
        return iter(self.stream)
    def close(self):
        self.stream.close()
class Follower(original):
    def __init__(self, argv, **kwargs):
        assert argv == command and kwargs["start_new_session"]
        super().__init__(argv, pass_fds=(ready_write,), **kwargs)
        children.append(self)
        os.close(ready_write)
        assert os.read(ready_read, 1) == b"1"
        os.close(ready_read)
        self.stdout = Reader(self.stdout)
    def wait(self, timeout=None):
        if timeout == 5:
            print("TERM_GRACE_WAIT", file=sys.stderr, flush=True)
        return super().wait(timeout=timeout)
log_filter.subprocess.Popen = Follower
prior_calls = []
def previous(signum, frame):
    prior_calls.append(signum)
signal.signal(signal.SIGTERM, previous)
signal.signal(signal.SIGHUP, previous)
numbers = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
before = {number: signal.getsignal(number) for number in numbers}
old_path = sys.path.copy()
try:
    log_filter.follow_logs(command, {"PATH": "/usr/local/bin:/usr/bin:/bin"}, output_format=sys.argv[2])
    assert {number: signal.getsignal(number) for number in numbers} == before
    assert not prior_calls and sys.path == old_path
    assert len(children) == 1 and children[0].returncode == -signal.SIGKILL
    print("RESTORED CHILD_KILLED_AND_REAPED", file=sys.stderr, flush=True)
finally:
    for number in numbers:
        signal.signal(number, signal.SIG_IGN)
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
'''


@pytest.mark.parametrize("format,first_signal", [
    ("plain", signal.SIGTERM), ("jsonl", signal.SIGHUP),
    ("auto", signal.SIGINT), ("console", signal.SIGTERM),
], ids=["plain-TERM", "jsonl-HUP", "auto-INT", "console-fallback-TERM"])
def test_actual_piped_bursts_cannot_interrupt_term_resistant_child_cleanup(tmp_path, format, first_signal):
    sentinel = subprocess.Popen([sys.executable, "-B", "-c", "import signal; signal.pause()"],
                                env={"HOME": str(tmp_path)}, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    worker = subprocess.Popen(
        [sys.executable, "-B", "-c", PIPED_WORKER, str(Path(__file__).parents[1]), format],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=tmp_path, env={"HOME": str(tmp_path), "TERM": "screen-256color"}, start_new_session=True,
    )
    try:
        read_until(worker.stderr.fileno(), b"SILENT_READ_WAIT")
        started = monotonic()
        worker.send_signal(first_signal)
        read_until(worker.stderr.fileno(), b"TERM_GRACE_WAIT", timeout=2)
        assert monotonic() - started < 2
        for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT) * 3:
            worker.send_signal(number)
        stdout, stderr = worker.communicate(timeout=9)
        assert worker.returncode == 0, stderr.decode()
        assert monotonic() - started >= 4.5
        assert stdout == b"" and b"\x1b" not in stderr
        assert b"RESTORED CHILD_KILLED_AND_REAPED" in stderr
        assert sentinel.poll() is None
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait(timeout=5)
        sentinel.terminate()
        sentinel.wait(timeout=5)


def test_noninteractive_exit_request_raises_once_then_allows_cleanup():
    request = log_filter.StopRequest()
    with pytest.raises(KeyboardInterrupt):
        request.interrupt(signal.SIGTERM, None)
    for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        request.interrupt(number, None)
    assert request.stopped


def test_cleanup_ignores_first_exit_signal_even_after_normal_stream_completion(monkeypatch):
    process = Mock(pid=12345, stdout=io.StringIO(""))
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.wait.return_value = 0
    delivered = []

    def killpg(pid, number):
        delivered.append((pid, number))
        if number == signal.SIGTERM:
            for exit_signal in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                signal.getsignal(exit_signal)(exit_signal, None)

    monkeypatch.setattr(log_filter.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(log_filter.os, "killpg", killpg)
    monkeypatch.setattr(log_filter.sys, "stdout", io.StringIO())
    log_filter.follow_logs(["synthetic-follower"], {}, output_format="plain")
    assert delivered == [(12345, signal.SIGTERM), (12345, signal.SIGKILL)]


def test_capability_failure_and_dumb_terminal_do_not_paint(monkeypatch):
    class SyntheticTTY(io.StringIO):
        def isatty(self):
            return True

        def fileno(self):
            return 1

    assert capabilities(io.StringIO(), io.StringIO(), {"TERM": "screen-256color"}) is None
    input, output = SyntheticTTY(), SyntheticTTY()
    assert capabilities(input, output, {"TERM": "dumb"}) is None
    monkeypatch.setattr(terminal.curses, "setupterm", Mock(side_effect=terminal.curses.error("synthetic missing terminfo")))
    assert capabilities(input, output, {"TERM": "not-installed"}) is None
    monkeypatch.setattr(log_filter.sys, "stdin", input)
    monkeypatch.setattr(log_filter.sys, "stdout", output)
    monkeypatch.setenv("TERM", "dumb")
    stream, interactive = log_filter.select_stream("auto", lambda: False)
    assert stream is log_filter.coalesce_logs and not interactive
    assert output.getvalue() == ""
