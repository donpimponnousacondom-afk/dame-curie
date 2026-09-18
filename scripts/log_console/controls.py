from dataclasses import dataclass, field

from .events import LogEvent
from .history import EventHistory, HistoryEntry
from .scopes import SCOPE_KEYS


LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_VALUE = {name: index for index, name in enumerate(LEVELS)} | {"WARN": 2}
VIEW_KEYS = {"r": "recent", "e": "errors", "i": "inspector", "?": "help", "\x1b": "live"}
VERBOSITY_NOTE = "+/- changes local display only; cannot create DEBUG records the application did not emit."


@dataclass
class ConsoleState:
    enabled_scopes: set[str] = field(default_factory=lambda: set(SCOPE_KEYS.values()))
    verbosity: int = 1
    folded: bool = True
    show_ollama: bool = False
    tool_depth: int = 2
    provider_depth: int = 2
    view: str = "live"
    list_view: str = "recent"
    selected: int | None = None
    page: int = 0

    def visible(self, event: LogEvent) -> bool:
        scope = event.scope if event.scope in SCOPE_KEYS.values() else "system"
        return (self.show_ollama or not (event.service or "").startswith("ollama")) and scope in self.enabled_scopes and LEVEL_VALUE.get(event.level or "INFO", 1) >= self.verbosity

    def choices(self, history: EventHistory) -> tuple[HistoryEntry, ...]:
        return tuple(entry for entry in history.recent(errors_only=self.list_view == "errors")
                     if self.list_view == "errors" or self.show_ollama or not (entry.first.service or "").startswith("ollama"))

    def key(self, key: str, history: EventHistory) -> bool:
        if key in {"q", "\x03"}:
            return True
        if key in SCOPE_KEYS:
            self.enabled_scopes.symmetric_difference_update({SCOPE_KEYS[key]})
        elif key in {"+", "-"}:
            self.verbosity = max(0, min(len(LEVELS) - 1, self.verbosity + (-1 if key == "+" else 1)))
        elif key == "o":
            self.show_ollama = not self.show_ollama
        elif key == "f":
            self.folded = not self.folded
        elif key in {"T", "P"}:
            field_name = "tool_depth" if key == "T" else "provider_depth"
            setattr(self, field_name, (getattr(self, field_name) + 1) % 3)
        elif key == "0":
            self.__dict__.update(vars(ConsoleState()))
        elif key in VIEW_KEYS:
            self.view, self.page = VIEW_KEYS[key], 0
            if self.view in {"recent", "errors"}:
                self.list_view = self.view
                choices = self.choices(history)
                self.selected = choices[0].sequence if choices else None
        elif key in {"[", "]"}:
            choices = self.choices(history)
            index = next((index for index, entry in enumerate(choices) if entry.sequence == self.selected), 0)
            if choices:
                index = max(0, min(len(choices) - 1, index + (1 if key == "[" else -1)))
                self.selected, self.page = choices[index].sequence, 0
                if self.view == "live":
                    self.view = self.list_view
        elif key in {"\r", "\n"}:
            if self.selected is None:
                choices = self.choices(history)
                self.selected = choices[0].sequence if choices else None
                self.view = self.list_view
            else:
                self.view = "evidence"
            self.page = 0
        elif key in {"n", "N"}:
            self.page = max(0, self.page + (1 if key == "n" else -1))
        return False
