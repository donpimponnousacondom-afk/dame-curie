import json
from collections.abc import Iterable
from dataclasses import dataclass

from .append_events import Record, correlation
from .paging import fit, row_spans
from .safety import terminal_text

SNAPSHOT_BYTES = 512 * 1024
PAGE_CHARACTERS = 6000
PAGE_ROWS = 80
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_COLORS = {"DEBUG": 90, "INFO": 32, "WARNING": 33, "WARN": 33, "ERROR": 31, "CRITICAL": 91}
SCOPE_COLORS = {"system": 37, "bot": 36, "provider": 35, "discord": 34,
                "tool": 33, "context": 32, "web": 36, "subagent": 95, "viewer": 91}
HELP = """Append-only screen viewer; controls affect this viewer only.
+ / = lower minimum severity; - raises it; absent producer events cannot be recovered.
s b p d t c w a toggle system/bot/provider/Discord/tool/context/web/subagent.
Viewer omission records are not scope-toggleable; an omitted record is never re-rendered.
o shows/hides received Ollama rows (hidden initially); never starts a service.
f toggles folding and replays five matches. T/P cycle tool/provider summary/JSON/evidence.
r pauses and replays twenty matches. e pauses and replays warnings/errors/failures UNFILTERED.
[ / ] or L / l navigate frozen older/newer candidates, not live arrivals.
Enter pauses and inspects selected evidence. n / N page the same immutable snapshot.
Space pauses/resumes display, NOT ingestion. Resume catch-up is limited to twenty rows.
0 resets INFO/all scopes/folded/summary/Ollama hidden; history is not cleared.
i appends LOCAL viewer state; no runtime/storage/private evidence reader.
? / h pauses and pins this help. q / Ctrl-C / Ctrl-D exit ONLY viewer/follower.
Ctrl-Z exits (does not suspend). ESC has no command; incomplete escapes disable keys.
Arrows, Alt sequences and marked paste are ignored. Unmarked paste can execute keys!
Use --no-keys when paste cannot be trusted. No implicit /dev/tty is opened.
Screen owns its prefix (normally Ctrl-A). Space first, then Screen prefix+[ for copy mode.
This viewer cannot detect Screen copy mode; Screen scrollback is separately finite.
Unknown level/time/correlation remain unknown. Scope is adapted logger/service attribution.
Only typed image request IDs establish correlation; traceback fragments remain separate.
Known patterns are redacted AFTER original persistence, not opaque custom secrets.
Live drops, retained-history eviction and preview truncation are distinct; not lossless export.
"""


def paint(text: str, code: int, color: bool) -> str:
    """Apply only viewer-owned SGR to already neutralized text."""
    return f"\x1b[{code}m{text}\x1b[0m" if color else text


def heading(record: Record, channel: str, *, color: bool, width: int) -> str:
    """Keep provenance and receive identity distinct from producer identity."""
    event = record.event
    timestamp = terminal_text(event.timestamp)
    origin = event.timestamp_origin + (";TZ?" if event.source_timezone == "unspecified" else "")
    level = event.level or "UNKNOWN"
    identity = correlation(event)
    text = event.message.split("\n", 1)[0]
    if event.details:
        text = " ".join(f"{key}={event.details[key]}" for key in ("tool", "outcome", "model", "status", "elapsed_ms") if key in event.details)
    safe = terminal_text(text).replace("\t", "\\t")
    preview = fit(safe[:512], max(12, width))
    if preview != safe or "\n" in event.message or event.details:
        preview += " [preview; Enter inspects]"
    return " ".join(part for part in (
        f"[{channel}]", f"{timestamp}({origin})",
        paint(level, LEVEL_COLORS.get(level, 37), color),
        paint(event.scope + "(adapted)", SCOPE_COLORS.get(event.scope, 37), color),
        paint(event.kind, 36, color), paint(f"receive#{record.sequence}", 94, color),
        paint(fit(identity[:256], 256), 35, color) if identity else "",
        paint(preview, 94 if event.details else 37, color),
    ) if part) + "\n"


def evidence_parts(record: Record, depth: int) -> Iterable[str]:
    """Stream sanitized captured metadata/evidence, with no external reads."""
    event = record.event
    yield f"receive#{record.sequence}; captured evidence only; fragments NOT request-correlated\n"
    fields = {"scope_attribution": "adapted logger/service (image kind recognized)", **vars(event)}
    if depth == 1:
        fields.pop("source_line")
        fields.pop("message")
    yield from json.JSONEncoder(ensure_ascii=False, indent=2).iterencode(fields)


@dataclass(frozen=True)
class Snapshot:
    text: str
    width: int
    height: int
    label: str

    @classmethod
    def build(cls, parts: Iterable[str], geometry: tuple[int, int], label: str) -> Snapshot:
        """Admit evidence incrementally into one immutable sanitized byte budget."""
        marker = "\n[PARTIAL: snapshot exceeds 512 KiB sanitized UTF-8 budget]"
        remaining = SNAPSHOT_BYTES - len(marker.encode("utf-8"))
        chunks = []
        for part in parts:
            encoded = terminal_text(part).replace("\t", "\\t").encode("utf-8")
            if len(encoded) > remaining:
                chunks.extend((encoded[:remaining].decode("utf-8", errors="ignore"), marker))
                break
            chunks.append(encoded.decode("utf-8"))
            remaining -= len(encoded)
        return cls("".join(chunks), *geometry, label)

    def segment(self, start: int) -> tuple[str, int]:
        """Wrap a bounded page without materializing offsets for the entire snapshot."""
        budget = PAGE_CHARACTERS - 256
        row_limit = min(PAGE_ROWS - 2, max(1, self.height - 3))
        excerpt = self.text[start:start + budget - 3 * row_limit]
        spans = row_spans(excerpt, max(1, self.width - 2))[:row_limit]
        rows = []
        end = start
        for left, right in spans:
            row = excerpt[left:right].removesuffix("\n")
            if sum(len(value) + 3 for value in rows) + len(row) + 3 > budget:
                break
            rows.append(row)
            end = start + right
        return "".join("| " + row + "\n" for row in rows), end

    def page(self, number: int, *, channel: str = "PAGE out-of-band") -> tuple[str, int]:
        """Recompute prior offsets from frozen geometry; retain no second payload ring."""
        if self.width < 4 or self.height < 4:
            return "[PAGE out-of-band] terminal too small; resize then reselect (minimum 4x4).\n", 0
        start = current = 0
        body, end = self.segment(start)
        while current < max(0, number) and end < len(self.text):
            start = end
            current += 1
            body, end = self.segment(start)
        suffix = "more" if end < len(self.text) else "end"
        header = f"[{channel}] {self.label} page={current + 1} chars={start}..{end} {suffix}"
        return fit(header, self.width) + "\n" + body, current


def event_block(record: Record, channel: str, depth: int, geometry: tuple[int, int], *, color: bool) -> str:
    """Preview detail without changing the operator's pinned snapshot."""
    text = heading(record, channel, color=color, width=geometry[0])
    if depth:
        preview_geometry = (min(geometry[0], 120), min(geometry[1], 10))
        snapshot = Snapshot.build(evidence_parts(record, depth), preview_geometry, f"{channel} receive#{record.sequence} preview")
        page, _ = snapshot.page(0, channel=f"{channel} detail")
        if len(page) > 1800:
            page = page[:1800] + "\n| [preview truncated; Enter for pinned evidence]\n"
        text += page
    return text
