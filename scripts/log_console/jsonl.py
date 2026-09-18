from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import TextIO

from .events import EventParser


def write_jsonl(
    lines: Iterable[str], output: TextIO, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    parser = EventParser()
    for line in lines:
        output.write(parser.parse(line, observed_at=clock()).json_line())
        output.flush()
