import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable, Iterable
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import monotonic
from typing import TextIO

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HEALTH = re.compile(
    r'^(?P<service>(?:[\w.-]+[-_])?ollama(?:[-_]\d+)?)\s+\|\s*'
    r'\[GIN\]\s+\d{4}/\d{2}/\d{2}\s+-\s+\d{2}:\d{2}:\d{2}\s*'
    r'\|\s*200\s*\|[^|\r\n]+\|\s*(?P<origin>127\.0\.0\.1|::1)\s*'
    r'\|\s*(?P<request>HEAD\s+"/"|POST\s+"/api/show")\s*$'
)
WINDOW = 30.0


@dataclass
class Repeats:
    started: float
    latest: str
    count: int = 0

    def summary(self, now: float) -> str:
        elapsed = min(now - self.started, WINDOW)
        return (self.latest.rstrip("\r\n")
                + f" [{self.count} additional repeats in {elapsed:g}s; latest occurrence shown]\n")


def coalesce_logs(lines: Iterable[str], output: TextIO, *, clock: Callable[[], float] = monotonic) -> None:
    pending: dict[tuple[str, str, str], Repeats] = {}
    try:
        for line in lines:
            now = clock()
            match = HEALTH.fullmatch(ANSI.sub("", line).rstrip("\r\n"))
            key = (match["service"], match["origin"], match["request"].split()[0]) if match else None
            batch = pending.get(key) if key is not None else None
            repeated = False
            if batch is not None and now - batch.started <= WINDOW:
                repeated = True
                batch.latest = line
                batch.count += 1
            for old_key, old_batch in list(pending.items()):
                if now - old_batch.started >= WINDOW:
                    if old_batch.count:
                        output.write(old_batch.summary(now))
                    del pending[old_key]
            if not repeated:
                output.write(line)
                if key is not None:
                    pending[key] = Repeats(now, line)
            output.flush()
    finally:
        now = clock()
        for batch in pending.values():
            if batch.count:
                output.write(batch.summary(now))
        output.flush()


def select_stream(output_format: str, stopped: Callable[[], bool]) -> tuple[Callable[[Iterable[str], TextIO], None], bool]:
    stream: Callable[[Iterable[str], TextIO], None] = coalesce_logs
    interactive = False
    if output_format == "jsonl" or output_format in {"auto", "console"} and sys.stdin.isatty() and sys.stdout.isatty():
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        try:
            if output_format == "jsonl":
                from scripts.log_console.jsonl import write_jsonl
                stream = write_jsonl
            else:
                from scripts.log_console.terminal import capabilities
                caps = capabilities(sys.stdin, sys.stdout, os.environ)
                if caps is not None:
                    from scripts.log_console.console import run_console
                    stream = partial(run_console, input=sys.stdin, caps=caps, stopped=stopped)
                    interactive = True
        finally:
            sys.path.pop(0)
    return stream, interactive


@dataclass
class StopRequest:
    stopped: bool = False

    def signal(self, signum, frame) -> None:
        self.stopped = True

    def interrupt(self, signum, frame) -> None:
        if not self.stopped:
            self.stopped = True
            raise KeyboardInterrupt


@contextmanager
def follower_signals(request: StopRequest, *, interactive: bool):
    numbers = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
    if interactive:
        numbers += (signal.SIGQUIT, signal.SIGTSTP)
    handlers = {number: signal.getsignal(number) for number in numbers}
    try:
        for number in handlers:
            signal.signal(number, request.signal if interactive else request.interrupt)
        yield
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


def wait_for_follower(process: subprocess.Popen[str], request: StopRequest) -> int:
    while not request.stopped:
        try:
            return process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass
    raise KeyboardInterrupt


def follow_logs(command: list[str], env: dict[str, str], *, output_format: str = "auto") -> None:
    request = StopRequest()
    stream, interactive = select_stream(output_format, lambda: request.stopped)
    input_options = {"stdin": subprocess.DEVNULL} if interactive else {}
    with follower_signals(request, interactive=interactive), subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="surrogateescape", start_new_session=True, **input_options) as process:
        try:
            stream(process.stdout, sys.stdout)
            returncode = wait_for_follower(process, request) if interactive else process.wait()
        except KeyboardInterrupt:
            returncode = 0
        finally:
            request.stopped = True
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    if returncode:
        raise RuntimeError("Compose command failed")
