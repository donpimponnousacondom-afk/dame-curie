"""Task-local limits and settlement for one foreground model/tool turn."""

import contextvars
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field


class TurnBudgetExceeded(RuntimeError):
    """A foreground turn exhausted its local output, attempt, or deadline budget."""

    def __init__(self, reason: str):
        self.reason = reason
        messages = {
            "output_tokens": "Foreground turn output allowance exhausted",
            "provider_attempts": "Foreground turn provider-attempt allowance exhausted",
            "deadline": "Foreground turn deadline expired",
        }
        super().__init__(messages[reason])


@dataclass(slots=True)
class OutputReservation:
    """Requested output and timeout reserved for one actual generation POST."""

    output_tokens: int
    timeout_seconds: float
    settled: bool = False


@dataclass(slots=True)
class ForegroundTurn:
    """Shared budget and discovery state for one task-local foreground turn.

    Child tasks created from the same input inherit this ContextVar and share
    this object; they do not receive a free output or attempt allowance.
    """

    output_remaining: int
    attempt_limit: int
    deadline: float
    attempts: int = 0
    expanded_tool_groups: set[str] = field(default_factory=set)
    media_keys: set[str] = field(default_factory=set)
    media_bytes: int = 0
    media_count: int = 0
    _cleanup: Callable[[], Awaitable[None]] | None = None

    @classmethod
    def from_controls(cls, control: Mapping[str, object]) -> ForegroundTurn:
        output = _positive_control(control.get("turn_output_token_budget"), 32768)
        attempts = _positive_control(control.get("turn_generation_attempt_budget"), 12)
        seconds = _positive_control(control.get("turn_deadline_seconds"), 600)
        return cls(output, attempts, time.monotonic() + seconds)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def reserve(self, requested_tokens: int, timeout_seconds: float) -> OutputReservation:
        """Reserve an HTTP attempt immediately before posting its final payload."""
        if self.attempts >= self.attempt_limit:
            raise TurnBudgetExceeded("provider_attempts")
        remaining_time = self.remaining_seconds
        if remaining_time <= 0:
            raise TurnBudgetExceeded("deadline")
        reserved = min(requested_tokens, self.output_remaining)
        if reserved <= 0:
            raise TurnBudgetExceeded("output_tokens")
        self.attempts += 1
        self.output_remaining -= reserved
        return OutputReservation(reserved, min(float(timeout_seconds), remaining_time))

    def settle(self, reservation: OutputReservation, explicit_output_tokens: int | None) -> None:
        """Refund only the unused part of an explicitly reported output count."""
        if reservation.settled:
            return
        reservation.settled = True
        if explicit_output_tokens is not None:
            self.output_remaining = max(
                0, self.output_remaining + reservation.output_tokens - explicit_output_tokens
            )

    def admit_media(self, identifier: str, decoded_bytes: int) -> bool:
        """Deduplicate and cap accepted tool media across this foreground turn."""
        if identifier in self.media_keys or self.media_count >= 12:
            return False
        if self.media_bytes + decoded_bytes > 20 * 1024 * 1024:
            return False
        self.media_keys.add(identifier)
        self.media_count += 1
        self.media_bytes += decoded_bytes
        return True

    def set_cleanup(self, cleanup: Callable[[], Awaitable[None]]) -> None:
        self._cleanup = cleanup

    def clear_cleanup(self) -> None:
        self._cleanup = None

    async def cleanup(self) -> None:
        if self._cleanup is not None:
            cleanup = self._cleanup
            self._cleanup = None
            await cleanup()


def _positive_control(value: object, default: int) -> int:
    """Use a positive integer control or its safe built-in default."""
    try:
        parsed = int(value) if not isinstance(value, bool) else default
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return parsed if parsed > 0 else default


_CURRENT_FOREGROUND_TURN: contextvars.ContextVar[ForegroundTurn | None] = (
    contextvars.ContextVar("dame_curie_foreground_turn", default=None)
)


def current_foreground_turn() -> ForegroundTurn | None:
    """Return the foreground budget inherited by the current task, if any."""
    return _CURRENT_FOREGROUND_TURN.get()


TOOL_GROUPS_CONTEXT: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "dame_curie_tool_groups", default=None
)


def current_tool_groups() -> set[str] | None:
    """Return a bound catalog or the foreground turn's discovered groups."""
    groups = TOOL_GROUPS_CONTEXT.get()
    if groups is not None:
        return groups
    turn = current_foreground_turn()
    return turn.expanded_tool_groups if turn is not None else None


def set_foreground_turn(turn: ForegroundTurn) -> contextvars.Token[ForegroundTurn | None]:
    """Bind one turn to the current task and its same-input child tasks."""
    return _CURRENT_FOREGROUND_TURN.set(turn)


def reset_foreground_turn(token: contextvars.Token[ForegroundTurn | None]) -> None:
    """Restore the task's previous foreground turn after handling completes."""
    _CURRENT_FOREGROUND_TURN.reset(token)
