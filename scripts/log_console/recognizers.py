import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .safety import JSONValue


DATE_TIME = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
COMPOSE = re.compile(r"^(?P<service>[\w.-]+)\s+\| ?(?P<body>.*)$", re.DOTALL)
DOCKER_TIME = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})) "
    r"(?P<body>.*)$", re.DOTALL,
)
PYTHON_LOG = re.compile(
    rf"^(?P<timestamp>{DATE_TIME}) - (?P<logger>[\w.-]+) - "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) - (?P<body>.*)$", re.DOTALL,
)
GIN_LOG = re.compile(
    r"^\[GIN\]\s+(?P<timestamp>\d{4}/\d{2}/\d{2} - \d{2}:\d{2}:\d{2})"
    r"(?P<body>\s*\|.*)$", re.DOTALL,
)
GO_LOG = re.compile(
    rf"^time=(?P<timestamp>{DATE_TIME}) level=(?P<level>DEBUG|INFO|WARN|ERROR) "
    r"(?P<body>.*)$", re.DOTALL,
)
BASIC_LOG = re.compile(
    r"^(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL):(?P<logger>[\w.-]+):(?P<body>.*)$",
    re.DOTALL,
)
IMAGE_LOG = re.compile(r"^Image request (?P<phase>start|done) (?P<payload>.*)$", re.DOTALL)


@dataclass(frozen=True)
class Envelope:
    message: str
    source_timestamp: str | None = None
    logger: str | None = None
    level: str | None = None


@dataclass(frozen=True)
class Recognition:
    kind: str
    scope: str
    details: dict[str, JSONValue] = field(default_factory=dict)
    detail_prefix: str | None = None
    parse_error: str | None = None


type EnvelopeRecognizer = Callable[[str], Envelope | None]
type EventRecognizer = Callable[[Envelope, str | None], Recognition | None]


def python_log(text: str) -> Envelope | None:
    match = PYTHON_LOG.fullmatch(text)
    return Envelope(match["body"], match["timestamp"], match["logger"], match["level"]) if match else None


def gin_log(text: str) -> Envelope | None:
    match = GIN_LOG.fullmatch(text)
    return Envelope(match["body"].lstrip(), match["timestamp"], "gin") if match else None


def go_log(text: str) -> Envelope | None:
    match = GO_LOG.fullmatch(text)
    return Envelope(match["body"], match["timestamp"], level=match["level"]) if match else None


def basic_log(text: str) -> Envelope | None:
    match = BASIC_LOG.fullmatch(text)
    return Envelope(match["body"], logger=match["logger"], level=match["level"]) if match else None


def image_request(envelope: Envelope, service: str | None) -> Recognition | None:
    match = IMAGE_LOG.fullmatch(envelope.message)
    if not match:
        return None
    try:
        details = json.loads(match["payload"])
    except (ValueError, RecursionError) as error:
        return Recognition("image.request.unparsed", "tool", parse_error=type(error).__name__)
    return Recognition(
        f"image.request.{match['phase']}", "tool", details,
        f"Image request {match['phase']} ",
    ) if isinstance(details, dict) else Recognition("image.request.unparsed", "tool", parse_error="ExpectedObject")


ENVELOPES: tuple[EnvelopeRecognizer, ...] = (python_log, gin_log, go_log, basic_log)
RECOGNIZERS: tuple[EventRecognizer, ...] = (image_request,)
