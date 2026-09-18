import re

from .events import LogEvent


IMAGE_FAILURES = frozenset({"http_error", "non_json", "decode_error", "connection_error", "timeout", "error"})
TRACEBACK_STARTS = (
    "Traceback (most recent call last):", "+ Exception Group Traceback (most recent call last):",
    "During handling of the above exception, another exception occurred:",
    "The above exception was the direct cause of the following exception:",
)
TRACEBACK_FRAME = re.compile(r'^\s*(?:\|\s*)?File "[^"\n]+", line \d+')
GIN_FAILURE = re.compile(r"^\|\s*[45]\d{2}\s*\|")


def record_boundary(event: LogEvent) -> bool:
    return event.source_timestamp is not None or event.level is not None or event.kind not in {"text", "unparsed"}


def traceback_fragment(event: LogEvent) -> bool:
    text = event.message.strip()
    return not record_boundary(event) and (
        text.startswith(TRACEBACK_STARTS) or TRACEBACK_FRAME.match(event.message) is not None
    )


def error_event(event: LogEvent) -> bool:
    outcome = event.details.get("outcome")
    return event.parse_error is not None or event.level in {"ERROR", "CRITICAL"} or (
        event.kind == "image.request.done" and isinstance(outcome, str) and outcome in IMAGE_FAILURES
    ) or (event.logger == "gin" and GIN_FAILURE.match(event.message) is not None) or traceback_fragment(event)
