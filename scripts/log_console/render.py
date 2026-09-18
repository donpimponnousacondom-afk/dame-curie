import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .controls import LEVELS, VERBOSITY_NOTE, ConsoleState
from .events import LogEvent
from .history import EventHistory, HistoryEntry
from .paging import fit, page_text
from .safety import terminal_text
from .scopes import SCOPE_KEYS


@dataclass(frozen=True)
class PaintLine:
    text: str
    timestamp: int = 0
    color: int = 6


def timestamp_text(event: LogEvent) -> str:
    source = event.timestamp_origin
    if source == "producer" and event.source_timezone == "unspecified":
        source += "; TZ unspecified"
    return terminal_text(f"[{event.timestamp} {source}]")


def compact_timestamp(event: LogEvent) -> str:
    timestamp = event.timestamp
    if event.timestamp_origin != "producer" or event.source_timezone != "unspecified":
        timestamp = datetime.fromisoformat(timestamp).astimezone().isoformat()
    clock = re.match(r"\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?", timestamp.split("T", 1)[-1])
    shown = clock[0] if clock else timestamp
    origin = "P?" if event.timestamp_origin == "producer" and event.source_timezone == "unspecified" else {
        "producer": "P", "docker": "D", "observed": "O",
    }[event.timestamp_origin]
    return terminal_text(f"[{shown} {origin}]")


def image_summary(event: LogEvent) -> str:
    tool = event.details.get("tool")
    fields = [tool if isinstance(tool, str) else "image", event.kind.rsplit(".", 1)[-1]]
    for key in ("outcome", "model", "status", "elapsed_ms", "request_id", "endpoint"):
        value = event.details.get(key)
        if isinstance(value, (str, int, float, bool)):
            fields.append(f"{key}={value}")
    return " ".join(fields) + " [full details in history]"


SUMMARY_RENDERERS: dict[str, Callable[[LogEvent], str]] = {
    "image.request.start": image_summary, "image.request.done": image_summary,
}


def summary(event: LogEvent) -> str:
    if event.live_collapsed:
        text = "subagent event [always folded in live/lists; Enter inspects selected history]"
    elif event.kind in SUMMARY_RENDERERS:
        text = SUMMARY_RENDERERS[event.kind](event)
    else:
        text = event.message.split("\n", 1)[0]
        if event.parse_error:
            text = f"[unparsed: {event.parse_error}] " + text
    return terminal_text(text)


def event_evidence(event: LogEvent) -> str:
    parts = [timestamp_text(event), f"service={event.service} logger={event.logger} level={event.level} scope={event.scope} kind={event.kind}",
             f"source_timestamp={event.source_timestamp} source_timezone={event.source_timezone}",
             f"docker_timestamp={event.docker_timestamp} observed_at={event.observed_at}"]
    if event.parse_error:
        parts.append(f"Unparsed evidence: {event.parse_error}; not a parsed payload.")
    prompts = {key: value for key, value in event.details.items()
               if key in {"prompt", "requested_prompt"} and isinstance(value, str)}
    if event.details:
        metadata = {key: value for key, value in event.details.items() if key not in prompts}
        parts.append("Details (redacted JSON):\n" + json.dumps(metadata, ensure_ascii=False))
        parts.extend(f"{key} (exact text, credential-redacted):\n{value}" for key, value in prompts.items())
    else:
        parts.append("Message:\n" + event.message)
    parts.append("Source evidence (redacted, not raw Docker bytes):\n" + event.source_line)
    return terminal_text("\n\n".join(parts))


def entry_evidence(entry: HistoryEntry) -> str:
    heading = f"Entry {entry.sequence}: {len(entry.records)} retained record(s); boundary={entry.boundary}"
    if entry.partial_reason:
        heading += "\nPARTIAL: " + entry.partial_reason
    return heading + "\n\n" + "\n\n".join(event_evidence(event) for event in entry.events)


def heading(entry: HistoryEntry, width: int, *, selected: bool = False, note: str = "") -> PaintLine:
    event = entry.first
    stamp = compact_timestamp(event)
    scope = next((key for key, value in SCOPE_KEYS.items() if value == event.scope), "s")
    context = f"{event.level[0] if event.level else '-'} {scope}" if width < 110 else f"{event.scope}/{event.service} {event.level or '-'}"
    label = f" {'>' if selected else ''}#{entry.sequence} {context} "
    suffix = f" [{len(entry.records)} records; {entry.boundary}]" if entry.is_error else ""
    text = fit(stamp + terminal_text(label) + (note or summary(event)) + suffix, width)
    color = 1 if entry.is_error else (3 if event.level in {"WARNING", "WARN"} else 6)
    return PaintLine(text, min(len(stamp), len(text)), color)


def live_lines(history: EventHistory, state: ConsoleState, width: int, height: int,
               hidden: frozenset[int], notes: dict[int, str]) -> list[PaintLine]:
    blocks = []
    used = 0
    for entry in history.recent():
        event = entry.first
        if entry.sequence in hidden or not state.visible(event):
            continue
        block = [heading(entry, width, note=notes.get(entry.sequence, ""))]
        depth = state.tool_depth if event.scope == "tool" else state.provider_depth if event.scope == "provider" else 2
        if not state.folded and not event.live_collapsed and depth:
            details = entry_evidence(entry) if depth == 2 else terminal_text(f"logger={event.logger} kind={event.kind} records={len(entry.records)}")
            page = page_text(details, width, max(1, height - 2), 0)
            block.extend(PaintLine(row) for row in page.rows)
            if page.count > 1:
                block.append(PaintLine(fit("[more retained evidence: r, Enter, n/N; display only]", width)))
        if used + len(block) > height:
            if not blocks:
                blocks.append(block[:height])
            break
        blocks.append(block)
        used += len(block)
    return [line for block in reversed(blocks) for line in block]


def help_text() -> str:
    return "\n".join((
        "Curie read-only log console; raw Docker logs remain authoritative.",
        "Time legend: P=producer, P?=producer timezone unspecified, D=Docker, O=observed.",
        "Live clocks show time-of-day and up to milliseconds; selected evidence retains full date/precision/zone.",
        "Narrow rows use D/I/W/E/C severity and single-letter scope; Enter shows full service/logger metadata.",
        "s/b/p/d/t/c/w/a toggle system/bot/provider/discord/tool/context/web/subagent scopes.",
        "T/P cycle tool/provider depth: 0 summary, 1 metadata, 2 full. f folds/unfolds live details.",
        VERBOSITY_NOTE,
        "r recent 20; e retained errors; Up/Down or [/] older/newer selection; Enter inspect selected entry.",
        "o toggles Ollama (hidden by default in live/recent; retained errors remain available with e).",
        "n/N next/previous evidence/help page; Esc returns live. History lists ignore live filters.",
        "i LOCAL console state only (no runtime probe). 0 resets local controls. ? help.",
        "q or Ctrl-C stops ONLY this follower, never the containerized bot.",
        "Subagent live/list details ALWAYS stay folded; only selected-history inspection expands.",
        "Jobs logger attribution is partial: descendant provider/tool logs need producer job identity.",
        "Paging/folding are display-only. Oversized/evicted evidence stays in original Docker logs.",
        "Known auth patterns are redacted; unknown opaque secrets cannot be discovered here.",
    ))


def inspector_text(history: EventHistory, state: ConsoleState, color: bool) -> str:
    return "\n".join((
        "LOCAL CONSOLE INSPECTOR — NOT a bot/container/runtime probe",
        f"retained_records={history.event_count}/{history.max_events}",
        f"retained_evidence_bytes={history.evidence_bytes}/{history.max_evidence_bytes} (not process RSS)",
        f"evicted_entries={history.evicted_entries} oversized_omitted_records={history.omitted_events}",
        f"minimum_display_level={LEVELS[state.verbosity]} folded={state.folded} color={color}",
        f"tool_depth={state.tool_depth} provider_depth={state.provider_depth}",
        f"selected_entry={state.selected} view={state.view}",
        "enabled_scopes=" + ",".join(sorted(state.enabled_scopes)),
        VERBOSITY_NOTE,
        "No configuration, environment, credentials or live runtime state is inspected.",
    ))


def render_frame(history: EventHistory, state: ConsoleState, width: int, height: int, *, color: bool,
                 hidden: frozenset[int] = frozenset(), notes: tuple[tuple[int, str], ...] = ()) -> list[PaintLine]:
    body_height = max(1, height - 3)
    title = f"Curie logs | {state.view} | {LEVELS[state.verbosity]} | {'folded' if state.folded else 'expanded'} | T={state.tool_depth} P={state.provider_depth}"
    scope_line = "Scopes " + " ".join(f"{key}{'+' if scope in state.enabled_scopes else '-'}" for key, scope in SCOPE_KEYS.items())
    scope_line += f" | o Ollama{'+' if state.show_ollama else '-'} | Time: local; P=src P?=TZ? D=Docker O=observed"
    if state.view == "live":
        body = live_lines(history, state, width, body_height, hidden, dict(notes))
    elif state.view in {"recent", "errors"}:
        choices = state.choices(history)
        index = next((i for i, entry in enumerate(choices) if entry.sequence == state.selected), 0)
        start = max(0, index - min(20, body_height) + 1)
        body = [heading(entry, width, selected=entry.sequence == state.selected)
                for entry in reversed(choices[start:start + min(20, body_height)])]
    else:
        entry = history.entries.get(state.selected)
        texts = {"help": help_text, "inspector": lambda: inspector_text(history, state, color)}
        text = texts[state.view]() if state.view in texts else (entry_evidence(entry) if entry else "Selected evidence is no longer retained; inspect authoritative Docker logs.")
        page = page_text(text, width, body_height, state.page)
        state.page = page.number
        title += f" | page {page.number + 1}/{page.count}"
        body = [PaintLine(row) for row in page.rows]
        if state.view == "evidence" and entry:
            scope_line = timestamp_text(entry.first)
    footer = "Up/Down scroll | o Ollama | r/e history | Enter inspect | n/N page | Esc live | ? help | q follower only"
    second = PaintLine(fit(scope_line, width), len(fit(scope_line, width)) if state.view == "evidence" and state.selected in history.entries else 0)
    return ([PaintLine(fit(title, width)), second] + body
            + [PaintLine("")] * max(0, body_height - len(body)) + [PaintLine(fit(footer, width))])[:height]
