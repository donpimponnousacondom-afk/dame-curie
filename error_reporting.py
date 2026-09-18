import copy
import fcntl
import json
import logging
import os
import re
import stat
import sys
import tempfile
import threading
import traceback
import weakref
from asyncio import CancelledError
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote
from uuid import uuid4

PUBLIC_ERROR_TEXT = "I waited, waited and I am losing things like tears in the rain 🕊️"

_REDACTED = "[REDACTED]"
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?"
    r"(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|$)",
    re.DOTALL,
)
_HEADER = re.compile(
    r'''(?im)(?<![\w?&-])(["']?(?:authorization|proxy-authorization|cookie|set-cookie)["']?\s*[:=]\s*)'''
    r'''(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\r\n,}]+)'''
)
_SECRET_FIELD = re.compile(
    r'''(?i)(["']?\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)["']?\s*[:=]\s*)'''
    r'''(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}&#]+)'''
)
_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:api[_-]?key|key|token|access[_-]?token|refresh[_-]?token|"
    r"auth|authorization|password|secret|signature|sig|"
    r"x-amz-(?:credential|signature|security-token))=)[^&#\s\"'<>]*"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/\s@]+@")
_configuration_lock = threading.RLock()
_secrets: tuple[str, ...] = ()
_store: IncidentStore | None = None
_context: ContextVar[dict[str, str]] = ContextVar("incident_context", default={})
_capturing: ContextVar[bool] = ContextVar("incident_capture_active", default=False)


class IncidentStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class Incident:
    incident_id: str
    timestamp: str
    source: str
    summary: str
    traceback: str
    details: str
    context: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))

    def format_report(self) -> str:
        parts = [
            f"Incident: {self.incident_id}",
            f"UTC: {self.timestamp}",
            f"Source: {self.source}",
            f"Summary: {self.summary}",
        ]
        parts.extend(f"{key}: {value}" for key, value in self.context.items())
        if self.details:
            parts.extend(("", "Details:", self.details))
        if self.traceback:
            parts.extend(("", "Traceback:", self.traceback))
        return "\n".join(parts)

    def to_dict(self) -> dict[str, str | dict[str, str]]:
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "summary": self.summary,
            "traceback": self.traceback,
            "details": self.details,
            "context": dict(self.context),
        }


def register_secrets(values: Iterable[str]) -> None:
    global _secrets
    with _configuration_lock:
        _secrets = tuple(sorted(set(_secrets).union(v for v in values if v), key=len, reverse=True))


def _redact(text: str) -> str:
    for secret in _secrets:
        text = text.replace(secret, _REDACTED)
    text = _PRIVATE_KEY.sub(_REDACTED, text)
    text = _HEADER.sub(lambda match: match[1] + _REDACTED, text)
    text = _SECRET_FIELD.sub(lambda match: match[1] + _REDACTED, text)
    text = _SECRET_QUERY.sub(lambda match: match[1] + _REDACTED, text)
    return _URL_CREDENTIALS.sub(lambda match: match[1] + _REDACTED + "@", text)


def redact_sensitive_text(text: str) -> str:
    text = _redact(text)
    for secret in _secrets:
        text = text.replace(quote(secret, safe=""), _REDACTED)
    return text


def _exception_chain(exception: BaseException | None) -> list[BaseException]:
    pending = [exception] if exception is not None else []
    found: list[BaseException] = []
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        elif current.__context__ is not None:
            pending.append(current.__context__)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(reversed(current.exceptions))
    return found


def _merge_text(previous: str, current: str) -> str:
    if not current or current in previous:
        return previous
    if not previous or previous in current:
        return current
    return previous + "\n\n" + current


def _make_incident(
    incident_id: str, source: str, summary: str, exception: BaseException | None,
    details: str, context: dict[str, str] | None, chain: list[BaseException],
) -> Incident:
    full_traceback = ""
    if exception is not None:
        formatted = traceback.TracebackException.from_exception(
            exception, capture_locals=False,
            max_group_width=sys.maxsize, max_group_depth=sys.maxsize,
        )
        full_traceback = "".join(formatted.format(chain=True))
    for member in chain:
        if member.__suppress_context__ and member.__cause__ is None and member.__context__ is not None:
            suppressed = traceback.TracebackException.from_exception(
                member.__context__, capture_locals=False,
                max_group_width=sys.maxsize, max_group_depth=sys.maxsize,
            )
            full_traceback = _merge_text(full_traceback, "".join(suppressed.format(chain=True)))
        diagnostics = getattr(member, "incident_details", "")
        if isinstance(diagnostics, str):
            details = _merge_text(details, diagnostics)
    identifiers = _context.get() | (context or {})
    return Incident(
        incident_id=incident_id,
        timestamp=datetime.now(UTC).isoformat(),
        source=_redact(source), summary=_redact(summary),
        traceback=_redact(full_traceback), details=_redact(details),
        context={_redact(key): _redact(value) for key, value in identifiers.items()},
    )


def _merge_incident(previous: Incident, current: Incident) -> Incident:
    observation = current.details
    if (previous.source, previous.summary) != (current.source, current.summary):
        observation = f"Source: {current.source}\nSummary: {current.summary}\n{observation}"
    return Incident(
        incident_id=previous.incident_id, timestamp=previous.timestamp,
        source=previous.source, summary=previous.summary,
        traceback=_merge_text(previous.traceback, current.traceback),
        details=_merge_text(previous.details, observation),
        context=dict(previous.context) | dict(current.context),
    )


class IncidentStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).absolute()
        self.last_error: str | None = None
        self._lock = threading.RLock()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._lock:
            token = _capturing.set(True)
            try:
                self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                lock_path = self.path.with_name(self.path.name + ".lock")
                fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
                with os.fdopen(fd, "a") as lock_file:
                    if not stat.S_ISREG(os.fstat(lock_file.fileno()).st_mode):
                        raise IncidentStorageError("Incident lock is not a regular file.")
                    os.fchmod(lock_file.fileno(), 0o600)
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                        self.last_error = None
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except IncidentStorageError as exc:
                self.last_error = str(exc)
                raise
            except OSError as exc:
                self.last_error = f"Incident storage unavailable ({type(exc).__name__})."
                raise IncidentStorageError(self.last_error) from None
            finally:
                _capturing.reset(token)

    def _load(self) -> list[Incident]:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return []
        with os.fdopen(fd, "r", encoding="utf-8") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise IncidentStorageError("Incident history is not a regular file.")
            os.fchmod(file.fileno(), 0o600)
            try:
                payload = json.load(file)
                if not isinstance(payload, dict) or set(payload) != {"version", "incidents"}:
                    raise ValueError
                rows = payload["incidents"]
                if type(payload["version"]) is not int or payload["version"] != 1 or not isinstance(rows, list) or len(rows) > 10:
                    raise ValueError
                incidents = [self._decode(row) for row in rows]
                if len({item.incident_id for item in incidents}) != len(incidents):
                    raise ValueError
            except (ValueError, TypeError, RecursionError):
                raise IncidentStorageError("Stored incident history is malformed; original file preserved.") from None
        return incidents

    @staticmethod
    def _decode(row: object) -> Incident:
        fields = {"incident_id", "timestamp", "source", "summary", "traceback", "details", "context"}
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError
        if not all(isinstance(row[key], str) for key in fields - {"context"}):
            raise ValueError
        if not row["incident_id"] or datetime.fromisoformat(row["timestamp"]).utcoffset() != UTC.utcoffset(None):
            raise ValueError
        context = row["context"]
        if not isinstance(context, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in context.items()):
            raise ValueError
        return Incident(**row)

    def _save(self, incidents: list[Incident]) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as file:
                temporary = Path(file.name)
                os.fchmod(file.fileno(), 0o600)
                json.dump({"version": 1, "incidents": [item.to_dict() for item in incidents]}, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def record(
        self, source: str, summary: str, *, exception: BaseException | None = None,
        details: str = "", context: dict[str, str] | None = None,
    ) -> str:
        with self._locked():
            incidents = self._load()
            chain = _exception_chain(exception)
            incident_id = next(
                (value for member in chain if isinstance(value := getattr(member, "incident_id", None), str) and value),
                uuid4().hex,
            )
            current = _make_incident(incident_id, source, summary, exception, details, context, chain)
            index = next((i for i, item in enumerate(incidents) if item.incident_id == incident_id), None)
            if index is None:
                incidents.insert(0, current)
            else:
                incidents[index] = _merge_incident(incidents[index], current)
            for member in chain:
                member.__dict__["incident_id"] = incident_id
            self._save(incidents[:10])
        return incident_id

    def get(self, index: int) -> Incident | None:
        result = None
        if 0 <= index < 10:
            with self._locked():
                incidents = self._load()
                if index < len(incidents):
                    result = incidents[index]
        return result


def configure_incident_store(path: Path, *, secrets: Iterable[str] = ()) -> IncidentStore:
    global _store
    with _configuration_lock:
        register_secrets(secrets)
        _store = IncidentStore(path)
        return _store


def get_incident_store() -> IncidentStore | None:
    return _store


@contextmanager
def incident_context(**identifiers: str) -> Iterator[None]:
    token = _context.set(_context.get() | identifiers)
    try:
        yield
    finally:
        _context.reset(token)


def capture_incident(
    source: str, summary: str, *, exception: BaseException | None = None,
    details: str = "", context: dict[str, str] | None = None,
) -> str | None:
    store = get_incident_store()
    incident_id = None
    if store is not None and not _capturing.get() and not isinstance(exception, CancelledError):
        token = _capturing.set(True)
        try:
            incident_id = store.record(source, summary, exception=exception, details=details, context=context)
        except IncidentStorageError:
            pass
        except Exception as exc:
            store.last_error = f"Incident capture failed ({type(exc).__name__}); no diagnostic payload emitted."
        finally:
            _capturing.reset(token)
    return incident_id


class IncidentLoggingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.last_error: str | None = None
        self._handled_records: weakref.WeakSet[logging.LogRecord] = weakref.WeakSet()

    def handle(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        if _capturing.get():
            return False
        return super().handle(record)

    def emit(self, record: logging.LogRecord) -> None:
        store = get_incident_store()
        recorded_id = getattr(record, "incident_id", None)
        if (record.levelno < logging.WARNING or store is None or _capturing.get()
                or record in self._handled_records
                or isinstance(recorded_id, str) and recorded_id):
            return
        active_exception = sys.exception()
        exception = record.exc_info[1] if record.exc_info else None
        if record.levelno < logging.ERROR and exception is None and active_exception is None:
            return
        if exception is None:
            attached_exception = getattr(record, "incident_exception", None)
            exception = attached_exception if isinstance(attached_exception, BaseException) else active_exception
        if isinstance(exception, CancelledError):
            return
        token = _capturing.set(True)
        try:
            copied = copy.copy(record)
            if copied.exc_info:
                copied.exc_text = None
            formatted = self.format(copied)
            source = _context.get().get("source", record.name)
            store.record(source, record.getMessage(), exception=exception, details=formatted)
            self._handled_records.add(record)
            self.last_error = None
        except IncidentStorageError as exc:
            self.last_error = str(exc)
        except Exception as exc:
            self.last_error = f"Incident logging capture failed ({type(exc).__name__}); no diagnostic payload emitted."
            store.last_error = self.last_error
        finally:
            _capturing.reset(token)
