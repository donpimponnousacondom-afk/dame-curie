"""OpenAI-compatible remote inference provider for Dame Curie."""

import asyncio
import contextlib
import copy
import json
import logging
import re
import sys
import time
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from functools import wraps
from typing import Concatenate
from urllib.parse import urlsplit

import aiohttp

from error_reporting import capture_incident, redact_sensitive_text, register_secrets
from image_media import normalize_image_part
from provider_telemetry import (
    CallMetrics,
    ChatCompletionMessage,
    OutputObservation,
    build_call_metrics,
    local_encoding,
    merge_usage,
    reasoning_content,
    reported_count,
    reported_usage,
    token_count,
)
from turn_budget import TurnBudgetExceeded, current_foreground_turn

logger = logging.getLogger(__name__)

# asyncio holds only a weak reference to a running task, so a bare
# `create_task(...)` whose result nobody keeps can be garbage-collected
# mid-flight and silently cancel the work. Keep a strong ref until it's done.
from utils import _spawn_background as _fire_and_forget  # noqa: E402


# Matches the `reasoning` string value inside a (possibly partial) tool-call
# arguments JSON. Models emit reasoning as the FIRST field, well before any
# huge field like send_file's `content`, so once this regex matches the value's
# closing quote is in hand and we can surface the reasoning to the live
# progress message without waiting for the rest of the stream.
_PARTIAL_REASONING_RE = re.compile(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"')


# ---------------------------------------------------------------------------
# Custom streaming tool-call protocol
# ---------------------------------------------------------------------------
#
# Native OpenAI-style tool_calls= doesn't stream incrementally on
# minimax-m3:cloud (or similar Ollama-cloud chat completion models): the
# entire {name, arguments} block arrives in ONE final delta at 88-100% of
# stream time, leaving the bot's "working on it…" progress message silent
# for the full 10-30s of generation.
#
# The "bare JSON on its own line" protocol sidesteps this: the model emits
# the tool call as part of the normal text stream (not the API's tool_calls
# field), and our SSE reader incrementally extracts it AS IT STREAMS. The
# model already knows raw JSON (no new syntax to learn) and the marker
# lands at ~12% of stream time vs ~88% for native — a real per-token
# progress signal for the user.
#
# Protocol shape (one JSON object on its own line, no fence, no tag):
#
#     {"name": "<tool>", "arguments": {<JSON object>}}
#
# The text around the JSON (the model's reply to the user) is preserved
# as normal assistant content. The JSON object is stripped from the
# visible reply so the user doesn't see raw JSON, but is captured into
# the ProviderResult.tool_calls so the rest of the dispatch flow treats
# it exactly like a native tool call.
#
# Streaming extraction (custom_tool_call_buffer below) does this:
#   1. Accumulates text deltas into a single buffer.
#   2. As soon as a `{"name": "..."` substring is visible, fires a
#      ``on_partial_name`` callback so the progress message can switch
#      from "thinking: …" to "<tool>: …" — even if the args haven't
#      finished streaming.
#   3. As soon as the outer JSON's closing brace is matched (counting
#      braces + tracking strings/escapes), parses it and returns a
#      native-format tool call list.
#   4. Continues looking for more tool calls (the model can chain
#      several in one response).
#
# The parser is conservative: if braces don't balance, the buffer is
# retained (we haven't hit the closing brace yet, just keep streaming).
# If JSON.parse fails on what we thought was complete, we rewind by one
# character and try again — handles the edge case where a brace inside
# a string fooled the counter.

# Matches the opening of a tool call — `{"name": "<tool>"`. We use this to
# find the start position even before we know the full JSON will parse.
_CUSTOM_TOOL_OPEN_RE = re.compile(r'\{\s*"name"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')

# Opener-match failure recovery threshold. If the brace counter can't find
# a balanced close inside this many characters after a `{"name":` match,
# we give up on this opener and look for the next one. Prevents a single
# pathological opener (think: HTML file contents with embedded
# unbalanced `'{"name": "...' substrings from a prior tool's args, or
# a stray `"` inside CSS that strands the string-state counter) from
# silently disabling extraction for the rest of the stream.
_GIVE_UP_BYTES = 65536

# When no opener regex match is found in the unreleased buffer, how many
# bytes of recent text we hold back before emitting everything else as
# visible. The opener `{"name": "<value>"` can be up to ~50 chars depending
# on the tool name; 256 chars is comfortably larger and keeps a near-zero
# memory footprint. This is what lets the buffer find a tool call whose
# opener arrives split across many small SSE deltas — without it, the
# leading chunk would be released as visible and the partial opener lost
# forever.
_HOLD_BACK = 256

# Conservative upper bound on the length of one opener match
# (e.g. `{"name": "<30-char tool name>"}`). If the unreleased tail is
# no longer than this, no future chunk can still split an opener
# across a boundary — release it all as visible. Keeping a separate
# constant from _HOLD_BACK (which is the "ambiguous" window for chunks
# still arriving) makes the intent obvious at the call site.
_CUSTOM_TOOL_OPEN_RE_MAX_LEN = 64


class _CustomToolCallBuffer:
    """Incrementally extracts bare-JSON tool calls from a streaming text delta.

    Constructed per-SSE-response. The SSE loop calls .feed(delta) for every
    text delta, then .drain() at the end to catch any final parse.

    For each tool call found:
      - ``on_partial_name(name)`` fires the moment ``{"name": "<tool>"`` is
        visible (mid-stream, even if args are still streaming) so the
        progress message can switch its UI prefix.
      - The completed tool call is appended to ``completed`` as a dict in
        the SAME shape as the provider's native tool_calls: ``{"id", "type",
        "function": {"name", "arguments"}}``. Callers can splice it
        straight into the existing dispatch flow.

    Anything in the stream that isn't a tool call JSON is preserved as
    ``text`` — the model's reply to the user, minus the JSON objects we
    stripped out.
    """

    def __init__(self, on_partial_name=None):
        self._buf = ""
        self.text_parts: list[str] = []
        self.completed: list[dict] = []
        self._on_partial_name = on_partial_name
        self._announced_names: set[str] = set()

    @property
    def has_pending_json(self) -> bool:
        """True when the buffer holds a bare-JSON tool call that's still
        being parsed (opener seen, close not yet). The progress UI can
        use this to show 'still writing…' instead of 'frozen' when the
        visible-content delta is empty for several frames.
        """
        return self._buf.rfind("{") > self._buf.rfind("}")

    def feed(self, delta: str) -> str:
        """Accumulate a new text delta. Extracts any complete bare-JSON
        tool calls and returns the newly-revealed VISIBLE text for this
        delta.

        Design: ``_buf`` is the running buffer. ``_released_len`` is the
        byte offset up to which text has been emitted as visible. On
        each feed:
          1. Append delta to _buf.
          2. Search _buf for the first opener past _released_len.
          3. If found, the text from _released_len to the opener is
             plain visible — emit it now and advance _released_len to
             the opener position. Then try to find a balanced end for
             the opener.
          4. If balanced end found, parse the candidate. Real tool
             call → append to completed, advance _released_len past
             the closer, and loop. Parse fail / wrong shape → advance
             past opener's first char (false-positive recovery) and
             loop.
          5. If no balanced end (opener mid-JSON): hold; the prefix
             already released covers everything safe. Any text after
             the opener (still buffering) is hidden.
          6. If no opener at all in the buffer: emit everything up to
             ``len(_buf) - _HOLD_BACK`` as visible. The trailing
             _HOLD_BACK window is held back so a chunk boundary can't
             split a fresh opener (max opener length is ~50 chars;
             _HOLD_BACK is comfortably larger).

        Works regardless of chunk size: we always search the full _buf
        from _released_len onward, so a tool call spanning 100 tiny
        deltas is found the moment the closing brace arrives. Text
        before the opener is released immediately, so the caller sees
        "All done!" the moment it streams in (not at drain time).
        """
        if not delta:
            return ""
        if not hasattr(self, "_released_len"):
            self._released_len = 0
        self._buf += delta
        newly_visible_total = ""
        while True:
            m = _CUSTOM_TOOL_OPEN_RE.search(self._buf, self._released_len)
            if not m:
                # No opener in the unreleased region. The only thing
                # that could be a "starter" for a future opener is a
                # bare `{` that's not yet followed by enough text. Find
                # the last `{` in the unreleased region and hold back
                # from there — anything before that `{` cannot grow
                # into an opener, so it's safe to release as visible.
                # If there's no `{` at all, release the whole thing.
                unreleased = self._buf[self._released_len :]
                last_open = unreleased.rfind("{")
                if last_open == -1:
                    # No possible opener prefix. Release all.
                    release_to = len(self._buf)
                else:
                    # Hold back from the last `{` onward; release
                    # everything before it as visible.
                    release_to = self._released_len + last_open
                if release_to > self._released_len:
                    nv = self._buf[self._released_len : release_to]
                    self.text_parts.append(nv)
                    self._released_len = release_to
                    newly_visible_total += nv
                break
            # Opener found. Text BEFORE the opener is plain visible.
            if m.start() > self._released_len:
                prefix = self._buf[self._released_len : m.start()]
                self.text_parts.append(prefix)
                self._released_len = m.start()
                newly_visible_total += prefix
            # Fire partial-name callback (idempotent).
            opener_name = m.group(1)
            if (
                self._on_partial_name is not None
                and opener_name not in self._announced_names
            ):
                self._announced_names.add(opener_name)
                with contextlib.suppress(Exception):
                    self._on_partial_name(str(opener_name))
            # Try to find a balanced end for this opener.
            end = _find_balanced_json_end(self._buf, m.start())
            if end is None:
                # Opener mid-JSON. Hold unless the held region is huge (unescaped
                # quotes in embedded HTML, CSS `{`, etc.) — then skip the
                # false opener so a later valid tool call can still parse.
                if len(self._buf) - m.start() > _GIVE_UP_BYTES:
                    self._released_len = m.start() + 1
                    continue
                break
            # Validate by parsing. Must go through
            # _safe_parse_tool_call_candidate, NOT bare json.loads: that
            # is where the unescaped-HTML-quote repair lives. With plain
            # json.loads here, a create_site whose body contains
            # `href="..."` failed to parse, the opener was skipped as a
            # "false positive", and the whole malformed blob shipped to
            # the channel as raw visible text while the tool never ran —
            # the exact 2026-08-02 incident the repair pass was written
            # for. The repair was only ever reachable from a dead code
            # path, so the live streaming path never benefited from it.
            candidate = self._buf[m.start() : end]
            obj = _safe_parse_tool_call_candidate(candidate)
            if obj is None:
                # Balanced but not valid JSON even after repair — false
                # positive. Skip past the opener's first char and keep
                # searching.
                self._released_len = m.start() + 1
                continue
            if not isinstance(obj, dict) or not obj.get("name"):
                # Not a tool-call shape. Advance past the opener.
                self._released_len = m.start() + 1
                continue
            # Real tool call. Append to completed and advance past
            # the closer; loop continues for any further text/calls.
            tool_name = str(obj.get("name", ""))
            args = obj.get("arguments", {})
            if not isinstance(args, dict):
                args = {}
            self.completed.append(
                {
                    "id": f"call_custom_{len(self.completed) + 1}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
            self._released_len = end
        return newly_visible_total

    def drain(self) -> None:
        """Final call after the stream ends. Emit any remaining unreleased
        text as visible. If there's a partial tool call still in flight
        (opener received but no closing brace), it can't have been a real
        tool call — the stream is over — so emit the held opener region as
        visible text too.
        """
        if not hasattr(self, "_released_len"):
            return
        held = self._buf[self._released_len :]
        if held:
            self.text_parts.append(held)
            self._released_len = len(self._buf)
        # If _buf grew unreasonably large pointing at a never-closed
        # opener, that opener was a false positive (e.g. it appeared
        # mid-string); drop the held region so we don't carry junk.
        # (We only get here after the loop above stopped finding a
        # balanced end for the opener.)


def _find_balanced_json_end(text: str, start: int) -> int | None:
    """Find the index just past the closing brace of the JSON object that
    starts at ``text[start]``. Returns None if the braces don't balance
    (i.e. the stream hasn't delivered the closing brace yet).

    Counts ``{``/``}`` while correctly ignoring braces that appear inside
    JSON string literals (which can happen for things like ``"content": "{...}"``
    in file contents containing CSS with braces).
    """
    depth = 0
    in_str = False
    escape = False
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return None


# Failure recovery for tool-call candidates whose ``body`` field
# contains unescaped ``"`` characters from HTML attribute syntax
# (e.g. ``target="_blank"``, ``href="..."``). Without the repair
# pass, ``json.loads`` raises ``JSONDecodeError`` because the
# balancer thinks the body string terminated early; the parser then
# ships the entire malformed JSON blob as raw visible text to the
# channel instead of executing the tool. See Z3ki's 2026-08-02
# "old-cartographers" create_site in #boing — the LLM emitted
# ~14 KB of partially-quoted HTML, the parser walked to EOF looking
# for a balanced close, the tool call never ran, and the user got a
# wall of broken text in 4 chunked Discord messages instead of a
# working site.


def _repair_unescaped_html_quotes(candidate: str) -> str | None:
    """Repair tool-call candidate JSON whose ``body`` field contains
    unescaped ``"`` characters from HTML attribute syntax (e.g.
    ``target="_blank"``, ``href="..."``).

    Returns the repaired candidate string, or ``None`` if no repair
    was applicable.

    Strategy:
      1. Locate the ``"body": "`` opener.
      2. Walk forward, tracking JSON escape state, until we hit an
         UNESCAPED ``"`` followed by ``}}`` — that's the body string
         terminator followed by the close of the ``arguments`` object
         and the close of the outer object. (LLMs that emit malformed
         HTML bodies almost always structure the close this way.)
      3. Re-encode the raw body slice with ``json.dumps`` (which
         properly escapes ``"`` and ``\\``), strip the outer quotes,
         and splice it back into the candidate.

    This is intentionally narrow — it only fires when a raw
    ``json.loads(candidate)`` already failed AND a ``"body": "`` field
    exists in the candidate. Clean JSON never reaches this path.
    """
    m = re.search(r'"body"\s*:\s*"', candidate)
    if not m:
        return None
    body_value_start = m.end()
    # Try each plausible terminator, cheapest-first, and keep the first
    # one that actually reparses into an object.
    for body_value_end in _body_terminator_candidates(candidate, body_value_start):
        body_escaped, repaired_any = _escape_body_slice(
            candidate, body_value_start, body_value_end
        )
        if not repaired_any:
            continue
        repaired = (
            candidate[:body_value_start] + body_escaped + candidate[body_value_end:]
        )
        try:
            obj, _end = json.JSONDecoder().raw_decode(repaired)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return repaired
    return None


def _body_terminator_candidates(candidate: str, body_value_start: int) -> list[int]:
    """Positions of every unescaped ``"`` in the body that could be the
    string's closing quote — i.e. one followed (modulo whitespace) by
    ``,`` or ``}``.

    The old code hardcoded a single terminator: an unescaped ``"``
    immediately followed by ``}}``. That only holds when ``body`` is the
    LAST key in ``arguments``. With ``{"body": "...", "title": "T"}`` the
    scan blew straight past the real terminator to the ``"}}`` at the end
    of the object, so ``title`` (and every other trailing key) was
    swallowed into the body string and silently lost.

    Quotes inside HTML attributes (``href="x"``) are followed by ``>``,
    ``/``, letters, etc. — never ``,`` or ``}`` — so they are not
    candidates. A body containing a literal ``",`` (e.g. ``said "hi",``)
    can still produce a false candidate, which is why the caller
    validates each one by reparsing and moves on if it does not hold.
    """
    out: list[int] = []
    i = body_value_start
    escape = False
    while i < len(candidate):
        ch = candidate[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\":
            escape = True
            i += 1
            continue
        if ch == '"':
            j = i + 1
            while j < len(candidate) and candidate[j] in " \t\r\n":
                j += 1
            if j < len(candidate) and candidate[j] in ",}":
                out.append(i)
        i += 1
    return out


def _escape_body_slice(
    candidate: str, body_value_start: int, body_value_end: int
) -> tuple[str, bool]:
    r"""Re-escape the raw body slice. Returns ``(escaped, repaired_any)``.

    The body has a mix of already JSON-escaped sequences (``\\"``,
    ``\\\\``, ``\\n``) and bare ``"`` from HTML attributes that the LLM
    forgot to escape. Some bodies also contain bare newlines (the LLM
    emitted real newline chars instead of ``\\n`` escape sequences),
    which JSON forbids inside string literals. Walk the slice and:
      - preserve only sequences ``\\X`` where X is a real JSON escape
        char (``"``, ``\\``, ``/``, ``b``, ``f``, ``n``, ``r``, ``t``,
        ``u``) — these are the LLM's correct JSON escape attempts,
      - escape bare ``"``,
      - escape bare ``\\`` that is NOT followed by a JSON escape char
        (the LLM typo'd ``</div>`` as ``</div\\`` etc.),
      - escape bare control characters (literal newline, tab, CR).
    """
    body_chars: list[str] = []
    repaired_any = False
    i = body_value_start
    JSON_ESCAPE_CHARS = set('"\\/bfnrtu')
    while i < body_value_end:
        ch = candidate[i]
        if ch == "\\" and i + 1 < body_value_end:
            nxt = candidate[i + 1]
            if nxt in JSON_ESCAPE_CHARS:
                # Already-escaped JSON sequence; pass through as-is.
                body_chars.append(ch)
                body_chars.append(nxt)
                i += 2
                continue
            # Literal backslash not followed by a valid JSON escape char.
            # Escape it so the reparsed JSON keeps the backslash.
            body_chars.append("\\\\")
            repaired_any = True
            i += 1
            continue
        if ch == "\\":
            # Lone trailing backslash immediately before the terminator.
            # Left bare it would escape the closing quote and break the
            # reparse, so escape it too.
            body_chars.append("\\\\")
            repaired_any = True
            i += 1
            continue
        if ch == '"':
            body_chars.append('\\"')
            repaired_any = True
            i += 1
            continue
        if ch == "\n":
            body_chars.append("\\n")
            repaired_any = True
            i += 1
            continue
        if ch == "\r":
            body_chars.append("\\r")
            repaired_any = True
            i += 1
            continue
        if ch == "\t":
            body_chars.append("\\t")
            repaired_any = True
            i += 1
            continue
        body_chars.append(ch)
        i += 1
    return "".join(body_chars), repaired_any


def _safe_parse_tool_call_candidate(candidate: str):
    """Parse a candidate tool-call JSON, with one repair pass for the
    common failure mode of unescaped ``"`` characters in embedded HTML
    (``body`` fields with ``target="_blank"``, ``href="..."``,
    etc).

    Returns the parsed dict on success, ``None`` if it cannot be parsed
    even after the repair attempt. Caller treats ``None`` as a
    false-positive opener and keeps searching.

    Three attempts:
      1. ``json.loads`` — clean JSON.
      2. ``json.JSONDecoder().raw_decode`` — tolerates trailing garbage
         (the LLM sometimes appends a hallucinated ``<parameter>`` tag
         after the JSON close, which we should ignore).
      3. ``_repair_unescaped_html_quotes`` + ``raw_decode`` — escapes
         unescaped ``"``, bare newlines, and bare backslashes inside
         a ``"body": "..."`` field, then parses.
    """
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        obj, _end = json.JSONDecoder().raw_decode(candidate)
        return obj
    except (json.JSONDecodeError, ValueError):
        pass
    repaired = _repair_unescaped_html_quotes(candidate)
    if repaired is None:
        return None
    try:
        obj, _end = json.JSONDecoder().raw_decode(repaired)
        return obj
    except (json.JSONDecodeError, ValueError):
        return None


async def _safe_call(cb, *args, **kwargs):
    """Await an SSE callback, swallowing any exception. Used for fire-and-forget
    callbacks (``_fire_and_forget(_safe_call(...))``) so a buggy callback
    never crashes the streaming read loop."""
    try:
        await cb(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.debug("SSE callback raised: %s", e)


def _append_tool_call_arguments(slot: dict, incoming) -> None:
    """Accumulate streaming tool-call arguments onto ``slot``.

    OpenAI streams ``function.arguments`` as JSON *strings* that must be
    concatenated. Some OpenAI-compatible providers (GLM-5.x on OpenCode
    Zen Go) send a finished object in one delta instead — concatenating
    that with ``""`` raises TypeError and kills the turn.
    """
    fn = slot.setdefault("function", {})
    existing = fn.get("arguments") or ""
    if isinstance(existing, dict):
        existing = json.dumps(existing, ensure_ascii=False)
    if isinstance(incoming, dict):
        fn["arguments"] = json.dumps(incoming, ensure_ascii=False)
        return
    if incoming is None:
        fn["arguments"] = existing
        return
    fn["arguments"] = existing + (
        incoming if isinstance(incoming, str) else str(incoming)
    )


def _extract_partial_reasoning(arguments: str) -> str:
    """Best-effort pull of the `reasoning` string from a PARTIAL arguments JSON.

    Returns '' until the reasoning value's closing quote has arrived (i.e. the
    model is still emitting it). Once complete, returns the decoded string.
    Used to update the in-channel progress message with the model's real intent
    mid-stream, instead of a static "generating…" for the whole generation.
    """
    if not arguments:
        return ""
    if isinstance(arguments, dict):
        r = arguments.get("reasoning")
        return r if isinstance(r, str) else ""
    if not isinstance(arguments, str):
        arguments = str(arguments)
    # Fast path: the whole arguments object already parses.
    try:
        parsed = json.loads(arguments)
        if isinstance(parsed, dict):
            r = parsed.get("reasoning")
            if isinstance(r, str):
                return r
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    # Partial JSON: grab the reasoning value once its closing quote landed.
    m = _PARTIAL_REASONING_RE.search(arguments)
    if not m:
        return ""
    raw = m.group(1)
    try:
        return json.loads('"' + raw + '"')  # decode \n, \", etc.
    except (json.JSONDecodeError, ValueError):
        return raw


_PROVIDER_DIAGNOSTIC_BODY_LIMIT = 64 * 1024
_SSE_LENGTH_DRAIN_BYTES = 64 * 1024
_SSE_LENGTH_DRAIN_SECONDS = 1.0
_MAX_PARTIAL_CONTENT_CHARS = 16 * 1024
_MAX_VALID_PROVIDER_TOKEN_COUNT = 2**53 - 1


def _explicit_output_tokens(response: dict) -> int | None:
    """Accept only consistent, validated provider-reported output counters."""
    counts: list[int] = []
    for source, keys in (
        (response.get("usage"), ("completion_tokens", "output_tokens", "eval_count")),
        (response, ("eval_count", "completion_tokens", "output_tokens")),
    ):
        if isinstance(source, dict):
            for key in keys:
                if key in source:
                    count = token_count(source[key])
                    if count is None:
                        return None
                    counts.append(count)
    gemini = response.get("usageMetadata")
    if isinstance(gemini, dict) and {
        "candidatesTokenCount", "thoughtsTokenCount"
    } & gemini.keys():
        candidates = token_count(gemini.get("candidatesTokenCount"))
        thoughts = token_count(gemini.get("thoughtsTokenCount"))
        if candidates is None or thoughts is None:
            return None
        combined = candidates + thoughts
        if combined > _MAX_VALID_PROVIDER_TOKEN_COUNT:
            return None
        counts.append(combined)
    if counts and all(count == counts[0] for count in counts):
        return counts[0]
    return None


class _ProviderDiagnostics:
    def __init__(self):
        self.attempts: list[str] = []
        self.current: dict = {}
        self.body = bytearray()
        self.body_bytes_seen = 0
        self.body_truncated = False
        self.response_text = ""
        self.response_text_chars_seen = 0
        self.response_text_truncated = False
        self.failed = False
        self.first_exception: BaseException | None = None

    def append_body(self, chunk: bytes) -> None:
        self.body_bytes_seen += len(chunk)
        if (
            not self.body_truncated
            and len(self.body) + len(chunk) <= _PROVIDER_DIAGNOSTIC_BODY_LIMIT
        ):
            self.body.extend(chunk)
        elif not self.body_truncated:
            head_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT // 2
            tail_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT - head_size
            prefix_size = max(0, head_size - len(self.body))
            head = bytes(self.body[:head_size]) + chunk[:prefix_size]
            remainder = chunk[prefix_size:]
            tail = (
                remainder[-tail_size:]
                if len(remainder) >= tail_size
                else (bytes(self.body[head_size:]) + remainder)[-tail_size:]
            )
            self.body = bytearray(head + tail)
            self.body_truncated = True
        else:
            head_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT // 2
            tail_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT - head_size
            tail = (
                chunk[-tail_size:]
                if len(chunk) >= tail_size
                else (bytes(self.body[head_size:]) + chunk)[-tail_size:]
            )
            self.body = bytearray(self.body[:head_size] + tail)

    def body_text(self) -> str:
        if not self.body_truncated:
            return self.body.decode(self.body_encoding, errors="replace")
        head_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT // 2
        omitted = self.body_bytes_seen - len(self.body)
        marker = f"\n[... {omitted} response bytes omitted from provider diagnostics ...]\n"
        return (
            self.body[:head_size].decode(self.body_encoding, errors="replace")
            + marker
            + self.body[head_size:].decode(self.body_encoding, errors="replace")
        )

    def capture_text(self, text: str) -> None:
        self.response_text_chars_seen = len(text)
        if len(text) <= _PROVIDER_DIAGNOSTIC_BODY_LIMIT:
            self.response_text = text
            return
        head_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT // 2
        tail_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT - head_size
        self.response_text = (
            text[:head_size]
            + (
                f"\n[... {len(text) - head_size - tail_size} response characters "
                "omitted from provider diagnostics ...]\n"
            )
            + text[-tail_size:]
        )
        self.response_text_truncated = True

    def begin(self, endpoint, path: str, attempt: int, maximum: int, data: dict, timeout: int):
        self.finish_attempt()
        self.started_s = time.perf_counter()
        self.current = {
            "attempt": f"{attempt}/{maximum}",
            "endpoint": endpoint.name,
            "url": f"{endpoint.base_url}{'' if endpoint.base_url.endswith('/') else '/'}{path}",
            "model": data.get("model", endpoint.model),
            "timeout_seconds": timeout,
            "parameters": copy.deepcopy({key: value for key, value in data.items() if key != "messages"}),
            "messages": [
                {
                    "role": message.get("role"),
                    "fields": {key: type(value).__name__ for key, value in message.items()},
                    "field_lengths": {
                        key: len(value) for key, value in message.items()
                        if isinstance(value, (str, list, dict))
                    },
                    "content_parts": [part.get("type") for part in message.get("content", []) if isinstance(part, dict)]
                    if isinstance(message.get("content"), list) else [],
                }
                for message in data.get("messages", [])
            ],
        }
        logger.info(
            "Provider request settings source=configured-profile endpoint=%s url=%s model=%s parameters=%s",
            endpoint.name,
            redact_sensitive_text(self.current["url"]),
            redact_sensitive_text(str(self.current["model"])),
            redact_sensitive_text(json.dumps(
                {key: value for key, value in self.current["parameters"].items() if key != "tools"},
                ensure_ascii=False,
            )),
        )
        self.body = bytearray()
        self.body_bytes_seen = 0
        self.body_truncated = False
        self.body_encoding = "utf-8"
        self.response_text = ""
        self.response_text_chars_seen = 0
        self.response_text_truncated = False
        self.http_response = None

    def response(self, resp):
        self.http_response = resp
        self.current["status"] = resp.status
        self.current["headers_ms"] = (time.perf_counter() - self.started_s) * 1000
        self.current["response_headers"] = {
            key: value for key, value in resp.headers.items()
            if key.lower() in {
                "content-type", "content-length", "date", "server", "retry-after",
                "request-id", "x-request-id", "x-correlation-id", "traceparent",
                "cf-ray", "openai-processing-ms", "x-envoy-upstream-service-time",
            } or key.lower().startswith(("x-ratelimit-", "ratelimit-"))
            or key.lower().endswith(("-request-id", "-trace-id"))
        }
        if resp.status != 200:
            self.current["response_body_complete"] = False
            self.failure(f"HTTP {resp.status}")

    def json_response(self, resp, result: object):
        cached_body = getattr(resp, "_body", None)
        if isinstance(cached_body, bytes):
            self.body_encoding = resp.get_encoding()
            self.append_body(cached_body)
        else:
            self.capture_text(json.dumps(result, ensure_ascii=False, default=str))

    def failure(self, summary: str, exception: BaseException | None = None):
        self.failed = True
        cached_body = getattr(self.http_response, "_body", None)
        if not self.body and not self.response_text and isinstance(cached_body, bytes):
            self.append_body(cached_body)
            if isinstance(exception, UnicodeDecodeError):
                self.body_encoding = exception.encoding
        self.current.setdefault("failures", []).append(summary)
        if exception is not None:
            if self.first_exception is None:
                self.first_exception = exception
            group_id = getattr(self.first_exception, "incident_id", None)
            if group_id and not getattr(exception, "incident_id", None):
                exception.incident_id = group_id
            self.current.setdefault("exceptions", []).append(
                "".join(traceback.format_exception(exception))
            )

    def finish_attempt(self):
        if self.current:
            self.current["elapsed_ms"] = (time.perf_counter() - self.started_s) * 1000
            self.current["response_body_bytes_observed"] = self.body_bytes_seen
            self.current["response_body_capture_truncated"] = self.body_truncated or self.response_text_truncated
            self.current["response_body_capture_chars_observed"] = self.response_text_chars_seen
            exceptions = self.current.pop("exceptions", [])
            record = json.dumps(self.current, ensure_ascii=False, indent=2, default=str)
            if self.current.get("failures"):
                body = self.response_text or self.body_text()
                record += "\nReceived response body (observed text only):\n" + body
            if exceptions:
                record += "\nUnderlying exception context:\n" + "\n".join(exceptions)
            self.attempts.append(record)
            self.current = {}

    def capture(self, summary: str, exception: BaseException | None = None):
        if self.failed:
            self.finish_attempt()
            details = "\n\n".join(self.attempts)
            exception = exception if exception is not None else self.first_exception
            group_id = getattr(self.first_exception, "incident_id", None)
            if exception is not None:
                if group_id and not getattr(exception, "incident_id", None):
                    exception.incident_id = group_id
                exception.incident_details = details
            incident_id = capture_incident("provider", summary, exception=exception, details=details)
            if exception is not None and incident_id is not None:
                exception.incident_id = incident_id


async def _read_sse_response(
    resp: aiohttp.ClientResponse,
    on_tool_call_name=None,
    on_token=None,
    custom_tool_calls: bool = False,
    observation: OutputObservation | None = None,
    incident: _ProviderDiagnostics | None = None,
) -> dict:
    """Read an OpenAI-style SSE chat-completions stream and reassemble it into
    the same dict shape a non-streamed `await resp.json()` would return.

    If ``on_tool_call_name`` is provided, it's awaited the first time a
    tool_call delta arrives with a function name. This lets the caller
    update a live progress message mid-stream — e.g. show
    "send_file: …" while the model is still generating the tool arguments
    (the file content), instead of waiting for the entire response to finish.

    If ``on_token`` is provided, it's called (fire-and-forget, NEVER awaited
    inline) on every content and reasoning delta so the caller can show a
    live progress message with a rolling preview of the model's own words.
    Inline awaiting would back-pressure the SSE read on a slow Discord edit
    and stall the upstream. The callback gets a small dict with the new
    delta (NOT an accumulator) plus a flag distinguishing reasoning from
    visible content::

        {"reasoning": str, "content": str, "tool_name": str|None}

    ``tool_name`` is set only on the delta that first introduces a tool call
    name (so the callback can switch the progress UI from "model is
    thinking" to "tool_name: …" the moment the model decides).

    The OpenAI streaming protocol sends one JSON object per ``data:`` line, each
    with the same frame structure but only the *delta* of what changed since
    the previous frame:

        data: {"choices": [{"delta": {"role": "assistant"}, "index": 0}]}
        data: {"choices": [{"delta": {"content": "hello"}, "index": 0}]}
        data: {"choices": [{"delta": {"content": " world"}, "index": 0}]}
        data: {"choices": [{"delta": {"tool_calls": [...]}, "index": 0}]}
        data: {"choices": [{"finish_reason": "stop", "index": 0}]}
        data: [DONE]

    We accumulate content strings, tool_calls (pinned by ``index``), and any
    usage payload that streams in at the end, then return a dict that matches
    the non-streamed response shape so the rest of the request handler does
    not need to care which mode produced the response.

    Returns the merged dict, plus (via a sentinel) the time the first content
    delta was received — encoded as ``__first_token_ms__`` in the returned
    dict and popped by the caller.

    Raises RuntimeError if the stream is malformed (no choices ever arrive) so
    the upstream retry logic can take over.
    """
    merged: dict = {"choices": [{}]}
    tool_calls_by_index: dict[int, dict] = {}
    content_parts: list[str] = []
    role: str | None = None
    finish_reason: str | None = None
    reasoning_parts: list[str] = []
    observation = observation if observation is not None else OutputObservation()
    done = False
    # When custom_tool_calls=True, we route text deltas through this buffer
    # which incrementally extracts bare-JSON tool calls ({"name": "...",
    # "arguments": {...}}) and synthesizes native-format tool_calls. This
    # is the workaround for providers (Ollama cloud's minimax-m3) that
    # bundle the entire tool_call into one final delta and never stream
    # it incrementally. With this on, the tool name lands in the
    # progress UI at ~12% of stream time vs ~88% with native tools=.
    # See _CustomToolCallBuffer for the protocol details.
    custom_buffer: _CustomToolCallBuffer | None = (
        _CustomToolCallBuffer(
            on_partial_name=lambda nm: (
                # 2026-07-21: fire BOTH callbacks when the JSON
                # opener is seen mid-stream. The old code only fired
                # on_token (so the progress UI could switch its
                # 'thinking:' → 'using <tool>…' transition) but
                # skipped on_tool_call_name. That meant the bot's
                # _on_tool_call_name callback (which sets
                # _current_tool on the progress and triggers
                # progress.update() with the tool's reasoning once
                # run_one() dispatches) was never invoked — and the
                # progress buffer kept the raw streaming JSON
                # content instead of the natural-language reasoning
                # the model wrote. Now both fire on opener, so the
                # progress UI immediately shows the tool name AND
                # the subsequent update() replaces the buffer with
                # the actual reasoning sentence.
                on_token({"content": "", "reasoning": "", "tool_name": nm})
                if on_token is not None
                else None
            )
        )
        if custom_tool_calls
        else None
    )

    # Bridge: the custom protocol's on_partial_name callback can't
    # directly invoke the bot's async on_tool_call_name (it's sync
    # from inside the brace-balancer). Wire it through a fire-and-
    # forget task so the bot's _on_tool_call_name fires as soon as
    # the tool name is parsed, not only when run_one() reaches it.
    if custom_tool_calls and on_tool_call_name is not None:
        # Patch the on_partial_name to also schedule on_tool_call_name
        original = custom_buffer._on_partial_name

        def _bridge(nm, _orig=original, _cb=on_tool_call_name):
            if _orig is not None:
                _orig(nm)
            try:
                _fire_and_forget(_safe_call(_cb, nm, ""))
            except RuntimeError:
                pass

        custom_buffer._on_partial_name = _bridge

    buf = b""
    byte_count = data_count = malformed_count = choice_count = 0
    error_event = False
    length_limited = False
    length_drain_deadline = 0.0
    length_drain_bytes = 0
    length_drain_timed_out = False
    stream = aiter(resp.content.iter_any())
    while not done:
        try:
            if length_limited and length_drain_bytes >= _SSE_LENGTH_DRAIN_BYTES:
                break
            if length_limited:
                remaining_time = (
                    length_drain_deadline - asyncio.get_running_loop().time()
                )
                if remaining_time <= 0:
                    length_drain_timed_out = True
                    break
                raw_chunk = await asyncio.wait_for(anext(stream), timeout=remaining_time)
            else:
                raw_chunk = await anext(stream)
        except StopAsyncIteration:
            break
        except asyncio.TimeoutError:
            if not length_limited:
                raise
            length_drain_timed_out = True
            break
        except aiohttp.ClientError as error:
            if not length_limited:
                raise
            if incident is not None:
                incident.failure("Provider length-response usage drain interrupted", error)
            break
        byte_count += len(raw_chunk)
        if incident is not None:
            incident.append_body(raw_chunk)
        if length_limited:
            remaining_bytes = _SSE_LENGTH_DRAIN_BYTES - length_drain_bytes
            raw_chunk = raw_chunk[:remaining_bytes]
            length_drain_bytes += len(raw_chunk)
        buf += raw_chunk
        while b"\n" in buf and not done:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                if error_event and not length_limited:
                    raise ProviderUpstreamError(None)
                error_event = False
                continue
            if line.startswith(b"event:"):
                error_event = line[6:].strip() == b"error"
                continue
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].lstrip()
            if payload == b"[DONE]":
                if error_event and not length_limited:
                    raise ProviderUpstreamError(None)
                done = True
                break
            if not payload:
                continue
            data_count += 1
            try:
                obj = json.loads(payload)
            except ValueError as e:
                if incident is not None:
                    incident.failure("Provider stream contains malformed JSON", e)
                if error_event and not length_limited:
                    raise ProviderUpstreamError(payload.decode("utf-8", errors="replace")) from None
                malformed_count += 1
                continue
            if not length_limited and (
                error_event
                or isinstance(obj, dict)
                and (obj.get("error") is not None or obj.get("type") == "error")
            ):
                raise ProviderUpstreamError(
                    obj.get("error", obj) if isinstance(obj, dict) else obj
                )
            if not isinstance(obj, dict):
                if length_limited:
                    continue
                raise ProviderResponseError(
                    f"Provider stream has non-object JSON: data_frames={data_count}"
                )
            for choice in obj.get("choices", []) or []:
                if length_limited:
                    break
                choice_count += 1
                idx = choice.get("index", 0)
                # Ensure the choices slot for this index exists.
                while len(merged["choices"]) <= idx:
                    merged["choices"].append({})
                delta = choice.get("delta") or {}
                observation.observe(delta, time.perf_counter(), choice_index=idx)
                if delta.get("role"):
                    role = delta["role"]
                visible_content_delta = ""
                if "content" in delta and delta["content"] is not None:
                    content_parts.append(delta["content"])
                    # Custom tool-call protocol: pipe text deltas through
                    # the extractor so tool calls embedded as bare JSON
                    # in the text stream get parsed incrementally and
                    # stripped from the visible content. Native path:
                    # leave content_parts alone.
                    #
                    # feed() returns the VISIBLE portion of this delta
                    # (JSON already stripped, or "" while a tool-call
                    # opener is still balancing). That return value — not
                    # the raw delta — is what the on_token progress
                    # preview below must use. Using the raw delta here
                    # used to leak the model's literal bare-JSON tool
                    # call (e.g. '{"name": "shell", "arguments": {...')
                    # into the "thinking: …" status line character by
                    # character, since native tool_name detection for the
                    # custom protocol only fires once the opener is fully
                    # parsed, not as raw text streams in.
                    if custom_buffer is not None:
                        visible_content_delta = custom_buffer.feed(delta["content"])
                    else:
                        visible_content_delta = delta["content"]
                # Reasoning deltas: OpenAI/DeepSeek-style models use
                # `reasoning_content`; Ollama cloud's minimax-m3 emits a
                # `reasoning` field on the same delta. Treat both the same
                # way so the bot's existing reasoning handler picks them up.
                reason = reasoning_content(delta)
                if reason:
                    reasoning_parts.append(reason)
                # Per-token progress callback (fire-and-forget, NEVER awaited
                # inline). A slow Discord edit must not back-pressure the SSE
                # read — that would stall the upstream provider and add visible
                # latency to the stream. We hand the caller a small dict with
                # the NEW deltas from this frame plus an empty tool_name that
                # the tool_call block below may fill in.
                #
                # 2026-07-21: in the custom tool-call protocol, the model
                # often emits the entire reasoning + tool call as a single
                # huge JSON object — so the visible-content delta is empty
                # for most frames and the progress UI just sits on
                # "working on it…". Pass a short HEAD of the raw content
                # as a "still streaming" preview so the user sees the
                # model is alive and writing. The bot's tick() rate-limits
                # this anyway (3s between edits), so the volume is
                # harmless.
                if on_token is not None:
                    tok_content = visible_content_delta
                    tok_reason = reasoning_content(delta)
                    # 2026-07-21: when the custom buffer is mid-JSON
                    # (model is emitting a bare-JSON tool call), DON'T
                    # surface the raw content as a progress preview.
                    # The raw text is JSON like 'name send_file ,
                    # arguments reason ing ...' which fills the
                    # progress buffer with unreadable fragments. The
                    # bot's _on_tool_call_name callback (bridged from
                    # on_partial_name) sets the tool name so the line
                    # shows 'using <tool>…' until run_one() lands with
                    # the actual natural-language reasoning via
                    # progress.update(name, tool_reasoning).
                    if (
                        not tok_content
                        and not tok_reason
                        and custom_buffer is not None
                        and custom_buffer.has_pending_json
                    ):
                        # Skip the on_token callback only — do NOT continue the
                        # choice loop or we drop native tool_calls on this delta.
                        pass
                    elif tok_content or tok_reason:
                        try:
                            on_token(
                                {
                                    "content": tok_content,
                                    "reasoning": tok_reason,
                                    "tool_name": None,
                                }
                            )
                        except Exception as e:
                            # Same as above: never break the stream for a
                            # progress-callback error.
                            logger.debug("on_token callback failed: %s", e)
                if delta.get("tool_calls"):
                    for tc_delta in delta["tool_calls"]:
                        tc_idx = tc_delta.get("index", 0)
                        slot = tool_calls_by_index.get(tc_idx)
                        if slot is None:
                            slot = {
                                "id": tc_delta.get("id"),
                                "type": tc_delta.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                            tool_calls_by_index[tc_idx] = slot
                        if tc_delta.get("id"):
                            slot["id"] = tc_delta["id"]
                        if tc_delta.get("type"):
                            slot["type"] = tc_delta["type"]
                        fn = tc_delta.get("function") or {}
                        if fn.get("name"):
                            slot["function"]["name"] = (
                                slot["function"].get("name", "") + fn["name"]
                            )
                            # Fire the tool-name callback the first time we
                            # see it. This is the *old* path kept for
                            # backwards-compat (legacy callers still use it).
                            # The new ``on_token`` path below also surfaces
                            # the tool name to the per-token progress callback
                            # so the UI can switch from "model is thinking"
                            # to "<tool_name>: …" the moment the model
                            # commits to a tool.
                            if on_tool_call_name is not None and not slot.get(
                                "_name_sent"
                            ):
                                slot["_name_sent"] = True
                                cb = on_tool_call_name
                                args = (slot["function"]["name"], "")
                                try:
                                    _fire_and_forget(_safe_call(cb, *args))
                                except RuntimeError:
                                    with contextlib.suppress(Exception):
                                        await cb(*args)
                            # Same signal on the new per-token path. The
                            # token callback is fire-and-forget so a slow
                            # Discord edit doesn't stall the SSE read.
                            if on_token is not None and not slot.get(
                                "_token_name_sent"
                            ):
                                slot["_token_name_sent"] = True
                                try:
                                    on_token(
                                        {
                                            "content": "",
                                            "reasoning": "",
                                            "tool_name": slot["function"]["name"],
                                        }
                                    )
                                except Exception as e:
                                    # A broken UI callback must never kill the
                                    # token stream mid-generation.
                                    logger.debug("on_token callback failed: %s", e)
                        if fn.get("arguments"):
                            _append_tool_call_arguments(slot, fn["arguments"])
                            # Surface the model's reasoning mid-stream so the
                            # progress message shows intent (not a static
                            # "generating…") during long argument generation
                            # (e.g. send_file's content). Reasoning is
                            # usually the first field emitted, so it completes
                            # well before the big fields. Fires once per call.
                            if on_tool_call_name is not None and not slot.get(
                                "_reasoning_sent"
                            ):
                                reason = _extract_partial_reasoning(
                                    slot["function"]["arguments"]
                                )
                                if reason:
                                    slot["_reasoning_sent"] = True
                                    cb = on_tool_call_name
                                    args = (slot["function"]["name"], reason)
                                    try:
                                        _fire_and_forget(_safe_call(cb, *args))
                                    except RuntimeError:
                                        with contextlib.suppress(Exception):
                                            await cb(*args)
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
                    if finish_reason == "length":
                        length_limited = True
                        length_drain_deadline = (
                            asyncio.get_running_loop().time() + _SSE_LENGTH_DRAIN_SECONDS
                        )
                        length_drain_bytes = min(len(buf), _SSE_LENGTH_DRAIN_BYTES)
                        if len(buf) > _SSE_LENGTH_DRAIN_BYTES:
                            buf = buf[:_SSE_LENGTH_DRAIN_BYTES]
            # Some providers stream usage in the final frame (Anthropic-style
            # models on OpenRouter do this; OpenAI does it when
            # stream_options.include_usage=true).
            for usage_key in ("usage", "usageMetadata"):
                usage_value = obj.get(usage_key)
                if isinstance(usage_value, dict):
                    merge_usage(merged.setdefault(usage_key, {}), usage_value)
            merge_usage(merged, {
                key: obj[key] for key in ("prompt_eval_count", "eval_count") if key in obj
            })
        else:
            # No inner break — keep iterating. Outer loop continues.
            continue
        # Inner break hit [DONE]; stop reading.
        break

    observation.finished_s = time.perf_counter()
    diagnostics = (
        f"bytes={byte_count} data_frames={data_count} choices={choice_count} "
        f"malformed_frames={malformed_count} done={done} trailing_bytes={len(buf)}"
    )
    if incident is not None and length_limited:
        incident.current["usage_drain_complete"] = done
        incident.current["usage_drain_timed_out"] = length_drain_timed_out
    if error_event and not length_limited:
        raise ProviderUpstreamError(None)
    if buf.strip() and not done and not length_limited:
        raise ProviderResponseError(f"Provider stream has an unterminated tail: {diagnostics}")
    if malformed_count:
        logger.warning("Provider stream skipped malformed frames: %s", diagnostics)
    if (
        not tool_calls_by_index
        and not content_parts
        and not role
        and finish_reason is None
        and (custom_buffer is None or not custom_buffer.completed)
    ):
        raise ProviderResponseError(f"Provider stream produced no choices: {diagnostics}")

    # Custom tool-call protocol: drain any final tail and merge results.
    # The extracted tool calls use the same native shape (id, type, function)
    # so the rest of the dispatch path treats them identically to native
    # tool_calls=. The visible content has any bare-JSON tool calls already
    # stripped out (the model wrote them as a single line; the user sees
    # the surrounding reply without the raw JSON).
    if custom_buffer is not None:
        if not length_limited:
            custom_buffer.drain()
        if custom_buffer.completed and not length_limited:
            for tc in custom_buffer.completed:
                tool_calls_by_index[len(tool_calls_by_index)] = tc
        if custom_buffer.completed or length_limited:
            content_parts = ["".join(custom_buffer.text_parts)]

    # Sort tool calls by their index so the order matches the model's intent.
    # Strip the internal callback-tracking flags ("_name_sent"/"_reasoning_sent")
    # so they never leak into the tool_calls we hand back to the provider.
    tool_calls_list = [] if length_limited else [
        {
            k: v
            for k, v in tool_calls_by_index[idx].items()
            if not str(k).startswith("_")
        }
        for idx in sorted(tool_calls_by_index)
    ]
    message: dict = {"role": role or "assistant"}
    if content_parts:
        message["content"] = "".join(content_parts)
    if reasoning_parts:
        message["reasoning_content"] = "".join(reasoning_parts)
    if tool_calls_list:
        message["tool_calls"] = tool_calls_list

    # The first (and typically only) choice carries the finished message.
    merged["choices"][0] = {
        "index": 0,
        "message": message,
        "finish_reason": finish_reason,
    }
    merged["__first_token_s__"] = observation.first_token_s
    if length_limited:
        merged["__usage_drain_complete__"] = done
    return merged


# When an endpoint returns a 429 (rate-limited / usage-exhausted), we temporarily
# steer traffic away from it for this long instead of retrying it in the same
# request. This avoids hammering a shared upstream pool (e.g. OpenRouter's
# pooled free keys) that is already rate-limiting us, which only makes the
# limit worse. Override via OPENAI_ENDPOINT_COOLDOWN_SECONDS.
DEFAULT_ENDPOINT_COOLDOWN_SECONDS = 60.0
# Reserve up to this many remaining attempts for non-streaming recovery
# when HTTP 200 responses contain no assistant content or tool call.
DEFAULT_EMPTY_RESPONSE_RETRIES = 2

USAGE_EXHAUSTED_MESSAGE = (
    "The api is down cuz yall drained the usage and im not rich so wait like 2 hours"
)

AUDIO_FORMATS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
}

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".avif": "image/avif",
    ".apng": "image/apng",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".m4v": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".3gp": "video/3gpp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma",
}


class ProviderUsageExhaustedError(RuntimeError):
    """Raised when the upstream provider is out of quota, credits, or cooldown capacity."""

    user_message = USAGE_EXHAUSTED_MESSAGE


class ProviderRequestError(RuntimeError):
    """A deterministic non-2xx that every available endpoint already rejected.

    Retrying with the same payload reproduces it exactly, so the retry loop
    re-raises this instead of sleeping through its remaining attempts.
    """


class ProviderResponseError(RuntimeError):
    """A malformed or incomplete HTTP 200 response, not a native-tool rejection."""


class ProviderIncompleteResponseError(ProviderResponseError):
    def __init__(
        self,
        *,
        partial_content: str,
        finish_reason: str | None,
        usage: dict[str, int],
        metrics: CallMetrics,
        classification: str,
    ):
        self.partial_content = partial_content[:_MAX_PARTIAL_CONTENT_CHARS]
        self.partial_content_truncated = len(partial_content) > _MAX_PARTIAL_CONTENT_CHARS
        self.finish_reason = finish_reason[:80] if isinstance(finish_reason, str) else None
        self.usage = dict(usage)
        self.metrics = metrics
        self.classification = classification
        self.incident_details = json.dumps(
            {
                "classification": classification,
                "finish_reason": self.finish_reason,
                "usage": self.usage,
                "metrics": asdict(metrics),
            },
            ensure_ascii=False,
            default=str,
        )
        messages = {
            "output_token_limit": "The provider stopped at the output token limit.",
            "reasoning_only": "The provider returned reasoning without an answer.",
        }
        super().__init__(messages[classification])


class ProviderUpstreamError(ProviderResponseError):
    """An explicit HTTP 200 upstream failure with content-free diagnostics."""

    def __init__(self, error: object):
        incident_details = json.dumps(error, ensure_ascii=False, default=str)
        if len(incident_details) > _PROVIDER_DIAGNOSTIC_BODY_LIMIT:
            head_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT // 2
            tail_size = _PROVIDER_DIAGNOSTIC_BODY_LIMIT - head_size
            omitted = len(incident_details) - head_size - tail_size
            incident_details = (
                incident_details[:head_size]
                + f"\n[... {omitted} diagnostic characters omitted ...]\n"
                + incident_details[-tail_size:]
            )
        self.incident_details = incident_details
        details = error if isinstance(error, dict) else {}
        known_labels = {
            "rate_limit_exceeded", "rate_limit_error", "concurrency_limit_exceeded",
            "insufficient_quota", "quota_exceeded", "model_cooldown",
            "invalid_request_error", "invalid_input", "context_length_exceeded",
            "tool_use_failed", "unsupported_parameter", "model_not_found",
            "server_error", "internal_server_error", "overloaded_error",
            "authentication_error", "permission_error",
        }
        labels = {}
        for field in ("code", "type"):
            value = details.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
                labels[field] = str(value)
            elif isinstance(value, str) and value in known_labels:
                labels[field] = value
            else:
                labels[field] = "unknown"
        message = details.get("message", error if isinstance(error, str) else "")
        message = message if isinstance(message, str) else ""
        signals = " ".join((message[:8192], labels["code"], labels["type"])).lower()
        category = "unknown"
        for name, pattern in (
            ("concurrency_limit", r"concurren|too many simultaneous"),
            ("quota", r"quota|credit|billing|model_cooldown"),
            ("rate_limit", r"rate.?limit|too many requests|\b429\b"),
            ("context_limit", r"context.{0,32}(length|limit|window)|maximum context"),
            ("tool_input", r"tool|function.call"),
            ("invalid_input", r"invalid.{0,24}(request|input|parameter)|unsupported.parameter|\b400\b"),
            ("model_unavailable", r"model.not.found|model.{0,24}unavailable"),
            ("authentication", r"authentication|unauthorized|\b401\b"),
            ("permission", r"permission|forbidden|\b403\b"),
            ("overload", r"overload|capacity|\b503\b"),
            ("server_error", r"server.error|\b50[024]\b"),
        ):
            if re.search(pattern, signals):
                category = name
                break
        super().__init__(
            f"Provider upstream error: category={category} code={labels['code']} "
            f"type={labels['type']} message_chars={len(message)}"
        )


class ProviderEmptyResponseError(RuntimeError):
    """Every provider attempt completed without a usable assistant response."""

    user_message = "The model returned an empty response after retries. Please try again in a moment."


class ProviderResult(str):
    """A ``str`` subclass carrying per-call ``tool_calls`` / ``usage``.

    Behaves exactly like a ``str`` everywhere a string is expected (f-strings,
    ``len()``, ``or ""``, ``str()``, slicing, etc.), but also exposes the
    native tool calls and token usage for *this specific call* so the caller
    does not have to read shared provider instance state.

    Reading ``provider._last_tool_calls`` / ``provider._last_usage`` after an
    ``await`` was racy: with ``ai_concurrency > 1`` (or background ticks sharing
    the same provider), a concurrent ``generate_response`` could overwrite the
    shared state between the call and the consume, causing one channel to
    execute another channel's tool calls. Attaching the values to the returned
    object makes the handoff per-call and race-free.
    """

    __slots__ = ("tool_calls", "usage", "assistant_message", "metrics")

    def __new__(
        cls,
        content,
        tool_calls: list | None = None,
        usage: dict | None = None,
        assistant_message: dict | None = None,
        metrics: CallMetrics | None = None,
    ):
        inst = super().__new__(
            cls, content if isinstance(content, str) else str(content or "")
        )
        inst.tool_calls = list(tool_calls) if tool_calls else []
        inst.usage = dict(usage) if usage else {}
        inst.assistant_message = assistant_message
        inst.metrics = metrics
        return inst


def _is_usage_exhausted_error(status: int, error_text: str) -> bool:
    """Detect true quota/credit exhaustion — not ordinary rate limits.

    Transient 429 rate limits must still get normal retry/backoff. Only treat as
    exhausted when the body clearly indicates cooldown, quota, or credits.

    2026-08-30 fix for Google Antigravity pooled false positive:
    - Antigravity-manager pools 5 Google accounts; a single 429 with
      reason=QuotaExhausted for gemini-3-flash on ONE account is NOT global
      exhaustion — combined quota may still be 70% (observed 2026-08-30).
      The manager still serves other accounts/models, so the provider must
      treat this as transient and fall back, not raise USAGE_EXHAUSTED.
    - Google's error is "QuotaExhausted" (no space) not "quota exceeded",
      so the old marker list missed it (false negative) while also flagging
      single-model hits as global (false positive). Both are fixed here.
    """
    text = (error_text or "").lower()
    # Explicit exhaustion / cooldown markers (avoid bare "usage" / "rate limit").
    markers = (
        "model_cooldown",
        "cooling down",
        "insufficient_quota",
        "insufficient credits",
        "credit balance",
        "quota exceeded",
        "quotaexhausted",  # Google Antigravity: QuotaExhausted (no space)
        "quota_exhausted",
        "resource_exhausted",
        "resource exhausted",
        "out of credits",
        "out of quota",
        "billing hard limit",
        "spend limit",
    )
    if status != 429:
        return False
    is_rate_limit = (
        "rate limit" in text or "rate_limit" in text or "too many requests" in text
    )
    is_quota_marker = any(m in text for m in markers)
    if is_rate_limit and not is_quota_marker:
        return False
    # Antigravity pooled false-positive guard: single-model QuotaExhausted
    # (e.g. gemini-3-flash, gemini-2.5-pro) on one pooled account should be
    # transient, not global. Only treat as global exhausted if the error
    # carries a stronger billing/credit signal or no specific model is named.
    if is_quota_marker:
        # If the text names a specific Gemini/Claude model, it's likely per-model
        # cooldown from the pool, not the whole API being drained.
        has_model = any(
            tok in text
            for tok in (
                "gemini",
                "claude",
                "flash",
                "pro",
                "quotaexhausted",
                "quota_exhausted",
            )
        )
        has_global = any(
            g in text
            for g in (
                "billing",
                "credit",
                "insufficient",
                "out of",
                "spend limit",
                "model_cooldown",
                "cooling down",
            )
        )
        if has_model and not has_global and not is_rate_limit:
            # Single entry like 'QuotaExhausted for gemini-3-flash' — transient, fall back to Grok/other model
            # unless the payload explicitly says combined/global is exhausted.
            # Check for combined/global hint: if manager said so, it would mention billing or multiple accounts
            return False
        if has_model and is_rate_limit:
            # "rate limited ... QuotaExhausted ... gemini-3-flash" — also transient pooled case
            # Only global if billing/credit is mentioned
            if not has_global:
                return False
    return is_quota_marker


def _is_policy_block_text(text: str) -> bool:
    """True when a 200-OK *reply body* is actually Gemini's prompt-block notice.

    .normal.man's gateway (and Google's OpenAI-compat surface) do not return an HTTP error for a
    blocked prompt — they hand back a normal 200 whose message content is:

        The prompt could not be submitted. The prompt contains sensitive words
        that violate Google's (...use-policy). Try rephrasing the prompt. ...

    Nothing upstream flags it, so Maxwell relayed it into the channel verbatim
    (logged 2026-08-21, #villa-31 and #poketwo-spawns). These markers are the
    provider's own boilerplate; a genuine reply does not contain them. A false
    positive only costs us one turn answered by the fallback model, so this is
    deliberately eager.
    """
    t = (text or "").lower()
    return any(
        m in t
        for m in (
            "the prompt could not be submitted",
            "contains sensitive words",
            "policies.google.com/terms/generative-ai/use-policy",
            "ai.google.dev/gemini-api/docs/troubleshooting",
        )
    )


def _is_content_policy_block(status: int, error_text: str) -> bool:
    """True when the provider refused the *prompt* on content-policy grounds.

    Gemini (and OpenAI-compatible proxies in front of it) reject the request
    outright rather than returning a completion, e.g.

        The prompt could not be submitted. The prompt contains sensitive words
        that violate Google's use policy. Try rephrasing the prompt.

    The native API signals the same thing as promptFeedback.blockReason
    (PROHIBITED_CONTENT / BLOCKLIST / SPII / SAFETY). None of it is transient:
    retrying the identical payload against the same endpoint always loses, so
    this cools the endpoint and fails straight over to the fallback model.
    """
    text = (error_text or "").lower()
    if status not in (400, 403, 422, 451, 200):
        return False
    markers = (
        "sensitive words",
        "could not be submitted",
        "generative-ai/use-policy",
        "prohibited_content",
        "blocked_reason",
        "blockreason",
        "safety_ratings",
        "content policy",
        "content_policy",
        "content_filter",
        "responsibleaipolicyviolation",
    )
    return any(m in text for m in markers)


def _is_media_unsupported_error(status: int, error_text: str) -> bool:
    """True when the endpoint rejected image/video/audio content parts."""
    text = (error_text or "").lower()
    if status == 404 and "support input audio" in text:
        return True
    if status in (400, 404) and (
        "unknown variant `image_url`" in text
        or "unknown variant `video_url`" in text
        or "unknown variant `input_audio`" in text
        or ("expected `text`" in text and "image_url" in text)
    ):
        return True
    # OpenRouter phrases a text-only routing failure as a bare 404:
    #   {"error":{"message":"No endpoints found that support image input"}}
    # This has no `image_url` token in it, so the checks above missed it and
    # every image turn hard-failed instead of falling back (logged 2026-08-12).
    if status in (400, 404) and "no endpoints found that support" in text:
        return True
    # Generic provider phrasings: "model does not support image input",
    # "does not support images", "image input is not supported".
    if status in (400, 404, 415, 422):
        for media_word in ("image", "images", "audio", "video", "multimodal"):
            if (
                f"not support {media_word}" in text
                or f"{media_word} input is not supported" in text
                or f"{media_word} input not supported" in text
            ):
                return True
    return False


@dataclass(frozen=True)
class ProviderEndpoint:
    name: str
    base_url: str
    model: str
    api_key: str = ""


def normalize_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url or any(char.isspace() for char in base_url):
        raise ValueError("base_url must be an http(s) URL without whitespace")
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
        raise ValueError("base_url must be an http(s) API root without query or fragment")
    return base_url


def track_provider_activity[**P, R](
    operation: Callable[Concatenate[OpenAICompatibleProvider, P], Awaitable[R]],
) -> Callable[Concatenate[OpenAICompatibleProvider, P], Awaitable[R]]:
    """Keep idle reload from closing transports used outside the bot's AI semaphore."""
    @wraps(operation)
    async def tracked(provider: OpenAICompatibleProvider, *args: P.args, **kwargs: P.kwargs) -> R:
        provider.active_requests += 1
        try:
            return await operation(provider, *args, **kwargs)
        finally:
            provider.active_requests -= 1

    return tracked


class OpenAICompatibleProvider:
    """OpenAI-compatible LLM Provider with multimodal support using /v1/chat/completions"""

    def __init__(
        self,
        base_url: str,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        api_key: str = "",
        retry_attempts: int = 5,
        enable_audio_input: bool = False,
        empty_response_retries: int = 2,
        top_p: float | None = None,
        top_k: int | None = None,
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, object] | None = None,
    ):
        local_encoding()
        self.active_requests = 0
        if extra_body is not None and not isinstance(extra_body, dict):
            raise ValueError("OPENAI_EXTRA_BODY must be a JSON object")
        if extra_headers is not None and not isinstance(extra_headers, dict):
            raise ValueError("OPENAI_EXTRA_HEADERS must be a JSON object")
        self.extra_headers = dict(extra_headers or {})
        self.extra_body = copy.deepcopy(extra_body or {})
        self.base_url = normalize_base_url(base_url)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.api_key = api_key
        register_secrets((self.api_key,))
        if type(retry_attempts) is not int or retry_attempts < 1:
            raise ValueError("retry_attempts must be a positive integer")
        if type(empty_response_retries) is not int or empty_response_retries < 0:
            raise ValueError("empty_response_retries must be a non-negative integer")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must not be blank")
        self.retry_attempts = retry_attempts
        self.empty_response_retries = empty_response_retries
        self.enable_audio_input = enable_audio_input
        self._endpoints = [ProviderEndpoint("primary", self.base_url, self.model, self.api_key)]
        self._headers()
        self._request_payload(self._endpoints[0], [])
        self._session = None
        self.available = False
        self._last_usage: dict = {}
        self._last_tool_calls: list = []
        self._last_assistant_message: dict | None = None

    def _headers(self, endpoint: ProviderEndpoint | None = None) -> dict[str, str]:
        if endpoint is not None and endpoint != self._endpoints[0]:
            raise ValueError("Endpoint conflicts with configured provider profile")
        api_key = self.api_key
        headers = self.extra_headers.copy()
        names = [key.lower() for key in headers]
        if len(names) != len(set(names)):
            raise ValueError("OPENAI_EXTRA_HEADERS contains conflicting header names")
        if api_key and "authorization" in names:
            raise ValueError("OPENAI_API_KEY conflicts with OPENAI_EXTRA_HEADERS Authorization")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _request_payload(
        self,
        endpoint: ProviderEndpoint,
        chat_messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        if endpoint != self._endpoints[0]:
            raise ValueError("Endpoint conflicts with configured provider profile")
        data = copy.deepcopy(self.extra_body)
        configured = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }
        for key, value in configured.items():
            if value is not None:
                if key in {"max_tokens", "top_k"} and type(value) is not int:
                    raise ValueError(f"{key} must be an integer")
                if key in {"temperature", "top_p"} and type(value) not in {int, float}:
                    raise ValueError(f"{key} must be a number")
                if key in data and (type(data[key]) is not type(value) or data[key] != value):
                    raise ValueError(f"OPENAI_EXTRA_BODY conflicts with configured {key}")
                data[key] = value
        json.dumps(data, allow_nan=False)
        for key, value in (("messages", chat_messages), ("tools", tools)):
            if value is not None:
                if key in data and data[key] != value:
                    raise ValueError(f"OPENAI_EXTRA_BODY conflicts with runtime {key}")
                data[key] = copy.deepcopy(value)
        return data

    async def _get_session(self):
        if self._session is None or self._session.closed:
            # Do NOT use the untrusted-fetch SSRF resolver for this session.
            # Operator-configured OpenAI-compatible endpoints may be private
            # proxies; they are trusted configuration, not user input.
            # SSRF protection belongs on the shared session used by tools like
            # fetch_url, which DO accept untrusted URLs.
            connector = aiohttp.TCPConnector(
                limit=16,
                limit_per_host=6,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=aiohttp.ClientTimeout(total=None)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @track_provider_activity
    async def initialize(self):
        session = await self._get_session()
        initialized = False
        for endpoint in self._endpoints:
            incident = _ProviderDiagnostics()
            incident.begin(endpoint, "models", 1, 1, {}, 10)
            attempt_exception = sys.exception()
            try:
                async with session.get(
                    f"{endpoint.base_url}{'' if endpoint.base_url.endswith('/') else '/'}models",
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers=self._headers(endpoint),
                ) as resp:
                    incident.response(resp)
                    if resp.status == 200:
                        initialized = True
                        logger.info(
                            f"Provider endpoint initialized: {endpoint.name} ({endpoint.model})"
                        )
                    else:
                        incident.capture_text(await resp.text())
                        incident.current["response_body_complete"] = True
                        logger.warning(
                            f"Provider endpoint {endpoint.name} /models returned {resp.status}"
                        )
            except (aiohttp.ClientError, OSError) as e:
                incident.failure("Provider initialization failed", e)
                incident.capture("Provider initialization failed", e)
                logger.error(
                    f"Provider endpoint {endpoint.name} initialization failed: {type(e).__name__}"
                )
            else:
                incident.capture("Provider initialization failed")
            finally:
                active_exception = sys.exception()
                if active_exception is not attempt_exception and isinstance(active_exception, asyncio.CancelledError) and incident.current:
                    incident.capture("Provider initialization failures before cancellation")
        self.available = initialized
        return initialized

    @track_provider_activity
    async def generate_response(
        self,
        messages: list[dict],
        images: list[str] | None = None,
        media: list[dict] | None = None,
        timeout: int = 3600,
        on_tool_call_name=None,
        on_token=None,
        custom_tool_calls: bool = False,
        tools: list[dict] | None = None,
    ) -> str:
        """Generate response. images is legacy b64 list, media is list of {b64, mime_type}.

        When the model returns native OpenAI-style ``tool_calls``, content may be
        empty. Those calls are stored on ``self._last_tool_calls`` (raw provider
        format) and ``self._last_assistant_message`` for the orchestration loop.
        Callers that pass ``tools=`` must check ``_last_tool_calls`` before treating
        empty content as a failure.

        If ``on_tool_call_name`` is provided, it's forwarded to the streaming
        layer so the caller gets a callback the moment a tool call name arrives
        mid-stream — useful for updating a live progress message during long
        generations (e.g. send_file where the model spends 20+ seconds
        generating file contents in the tool arguments).
        """
        message = await self.generate_chat_completion(
            messages,
            images=images,
            media=media,
            timeout=timeout,
            on_tool_call_name=on_tool_call_name,
            on_token=on_token,
            custom_tool_calls=custom_tool_calls,
            tools=tools,
        )

        tool_calls = message.get("tool_calls") or []
        tool_calls = tool_calls if isinstance(tool_calls, list) else []
        usage = getattr(message, "usage", {})
        # Keep the shared stash for backward-compat callers / tests, but callers
        # should prefer the ProviderResult attributes (race-free).
        self._last_tool_calls = tool_calls
        self._last_assistant_message = message
        content = message.get("content") or ""
        # Multimodal / some providers return content as a list of parts
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                elif isinstance(part, str):
                    parts.append(part)
            content = "".join(parts)
        content = content if isinstance(content, str) else str(content or "")
        if not content and not tool_calls:
            raise RuntimeError("Empty response from provider")
        return ProviderResult(
            content,
            tool_calls=tool_calls,
            usage=usage,
            assistant_message=message,
            metrics=getattr(message, "metrics", None),
        )

    @track_provider_activity
    async def generate_chat_completion(
        self,
        messages: list[dict],
        images: list[str] | None = None,
        media: list[dict] | None = None,
        tools: list[dict] | None = None,
        timeout: int = 3600,
        on_tool_call_name=None,
        on_token=None,
        custom_tool_calls: bool = False,
    ) -> dict:
        """Generate an OpenAI-compatible assistant message, optionally with tools.

        If ``on_tool_call_name`` is provided, it's called (fire-and-forget) the
        first time a tool_call delta with a function name arrives in the SSE
        stream. This lets callers update a live progress message mid-generation.
        """
        if not self.available:
            logger.warning("Provider marked unavailable; retrying initialization")
            await self.initialize()
            if not self.available:
                raise RuntimeError("Provider not available")

        chat_messages = copy.deepcopy(messages)

        all_media = []
        if media:
            all_media.extend(media)
        if images:
            all_media.extend(
                {"b64": img_b64, "mime_type": "image/png"} for img_b64 in images
            )

        payload_media: list[dict] = [
            m
            for m in all_media
            if m.get("b64")
            and (
                str(m.get("mime_type", "")).startswith(("image/", "video/"))
                or (
                    str(m.get("mime_type", "")).startswith("audio/")
                    and getattr(self, "enable_audio_input", False)
                )
            )
        ]

        if payload_media:
            target = None
            for msg in chat_messages:
                content = msg.get("content", "")
                if msg["role"] == "user" and (
                    "[User attached image" in content
                    or "[User attached media" in content
                    or "Media available to inspect" in content
                    or "Audio/video available to inspect" in content
                    or "Images available to inspect" in content
                    or "Server emoji/sticker reference sheet" in content
                ):
                    target = msg
                    break
            if target is None:
                for msg in reversed(chat_messages):
                    if msg["role"] == "user":
                        target = msg
                        break
            if target is not None:
                content = target.get("content", "")
                parts = list(content) if isinstance(content, list) else [{"type": "text", "text": content}]
                attached = 0
                for m in payload_media:
                    mime = m["mime_type"]
                    b64 = m["b64"]
                    uri = f"data:{mime};base64,{b64}"
                    if mime.startswith("image/"):
                        parts.append({"type": "image_url", "image_url": {"url": uri}})
                    elif mime.startswith("audio/") and getattr(
                        self, "enable_audio_input", False
                    ):
                        audio_format = AUDIO_FORMATS.get(
                            mime.split(";", 1)[0].lower(), "wav"
                        )
                        parts.append(
                            {
                                "type": "input_audio",
                                "input_audio": {"data": b64, "format": audio_format},
                            }
                        )
                    elif mime.startswith("video/"):
                        parts.append({"type": "video_url", "video_url": {"url": uri}})
                    else:
                        continue
                    attached += 1
                target["content"] = parts
                logger.info(f"Attached {attached} multimodal item(s) to message")
            else:
                logger.warning(
                    f"No user message found to attach {len(payload_media)} multimodal item(s)"
                )

        for message in chat_messages:
            content = message.get("content")
            if isinstance(content, list):
                message["content"] = [
                    await normalize_image_part(part) if part.get("type") == "image_url" else part
                    for part in content
                ]

        session = await self._get_session()
        last_error = None
        incident = _ProviderDiagnostics()
        endpoint = self._endpoints[0]
        payload = self._request_payload(endpoint, chat_messages, tools=tools)
        max_attempts = self.retry_attempts
        attempt = 0
        empty_response_recoveries = 0
        while attempt < max_attempts:
            attempt += 1
            data = copy.deepcopy(payload)
            turn = current_foreground_turn()
            if turn is not None:
                try:
                    timeout = turn.reserve_attempt(timeout)
                except TurnBudgetExceeded as e:
                    incident.capture("Provider turn budget exhausted after upstream failures", e)
                    raise
            observation = OutputObservation()
            request_start = time.perf_counter()
            media_parts = sum(
                1
                for msg in chat_messages
                for part in (
                    msg.get("content") if isinstance(msg.get("content"), list) else []
                )
                if isinstance(part, dict) and part.get("type") != "text"
            )
            logger.info(
                "Provider timing start endpoint=%s model=%s attempt=%s/%s messages=%s media_parts=%s timeout=%s max_tokens=%s tools=%s",
                endpoint.name,
                data.get("model"),
                attempt,
                max_attempts,
                len(chat_messages),
                media_parts,
                timeout,
                data.get("max_tokens"),
                len(data.get("tools") or []),
            )
            incident.begin(endpoint, "chat/completions", attempt, max_attempts, data, timeout)
            attempt_exception = sys.exception()
            try:
                async with session.post(
                    f"{endpoint.base_url}{'' if endpoint.base_url.endswith('/') else '/'}chat/completions",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=timeout, connect=10),
                    headers=self._headers(endpoint),
                ) as resp:
                    headers_ms = (time.perf_counter() - request_start) * 1000
                    incident.response(resp)
                    if resp.status != 200:
                        error_text = await resp.text()
                        incident.capture_text(error_text)
                        incident.current["response_body_complete"] = True
                        detail = redact_sensitive_text(incident.response_text)
                        if _is_usage_exhausted_error(resp.status, error_text):
                            raise ProviderUsageExhaustedError(
                                f"Provider usage exhausted: HTTP {resp.status}: {detail}"
                            )
                        if resp.status in (429, 500, 502, 503, 504):
                            raise RuntimeError(f"Provider API error: {resp.status}: {detail}")
                        logger.warning(
                            "Provider timing status endpoint=%s status=%s headers_ms=%.1f body_chars=%s",
                            endpoint.name,
                            resp.status,
                            headers_ms,
                            len(error_text),
                        )
                        raise ProviderRequestError(f"Provider API error: {resp.status}: {detail}")

                    content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    safe_content_type = (
                        content_type if content_type in {
                            "text/event-stream", "application/json", "application/problem+json",
                            "text/html", "text/plain",
                        } else "other" if content_type else "missing"
                    )
                    if content_type == "text/event-stream":
                        response_format = "sse"
                    elif content_type == "application/json" or content_type.endswith("+json"):
                        response_format = "json"
                    else:
                        response_format = "sse" if data.get("stream") else "json"
                    usage_drain_complete = None
                    if response_format == "sse":
                        merged = await _read_sse_response(
                            resp,
                            on_tool_call_name=on_tool_call_name,
                            on_token=on_token,
                            custom_tool_calls=custom_tool_calls,
                            observation=observation,
                            incident=incident,
                        )
                        usage_drain_complete = merged.get("__usage_drain_complete__")
                        result = {
                            k: v for k, v in merged.items() if not k.startswith("__")
                        }
                    else:
                        try:
                            result = await resp.json(content_type=None)
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            incident.capture_text(
                                e.doc
                                if isinstance(e, json.JSONDecodeError)
                                else e.object.decode("utf-8", errors="replace")
                            )
                            incident.failure("Provider JSON decoding failed", e)
                            raise ProviderResponseError(
                                f"Provider JSON decoding failed: error_type={type(e).__name__}"
                            ) from None
                        incident.json_response(resp, result)
                        observation.finished_s = time.perf_counter()
                    if not isinstance(result, dict):
                        incident.failure("HTTP 200 with non-dict JSON body")
                        logger.warning(
                            "Provider %s returned 200 with non-dict JSON body (type=%s)",
                            endpoint.name,
                            type(result).__name__,
                        )
                        if await self._retry_after_attempt(
                            attempt,
                            endpoint,
                            f"Provider {endpoint.name} returned non-dict JSON body",
                            max_attempts=max_attempts,
                        ):
                            continue
                        raise ProviderResponseError(
                            "No response from provider (non-dict JSON body)"
                        )
                    if result.get("error") is not None or result.get("type") == "error":
                        raise ProviderUpstreamError(result.get("error", result))
                    choices = result.get("choices", [])
                    if not choices:
                        raise ProviderResponseError("Provider JSON response produced no choices")

                    message = choices[0].get("message", {})
                    if response_format == "json":
                        for index, choice in enumerate(choices):
                            observation.observe(
                                choice.get("message", {}), observation.finished_s,
                                choice_index=index,
                            )
                    content = message.get("content") or ""
                    if isinstance(content, list):
                        content = "".join(
                            str(p.get("text") or "")
                            if isinstance(p, dict)
                            else (p if isinstance(p, str) else "")
                            for p in content
                        )
                    finish_reason = choices[0].get("finish_reason")
                    incomplete_classification = None
                    partial_content = ""
                    if finish_reason == "length":
                        incomplete_classification = "output_token_limit"
                        if content and not _is_policy_block_text(content):
                            partial_content = content
                        if partial_content:
                            opener = _CUSTOM_TOOL_OPEN_RE.search(partial_content)
                            if opener is not None:
                                partial_content = partial_content[:opener.start()]
                    elif (
                        not content.strip()
                        and not message.get("tool_calls")
                        and reasoning_content(message)
                    ):
                        incomplete_classification = "reasoning_only"
                    if incomplete_classification is not None:
                        metrics = build_call_metrics(
                            result, data, observation,
                            provider=urlsplit(endpoint.base_url).hostname or "unknown",
                            endpoint=endpoint.name, model=data["model"],
                            request_start=request_start, stream=response_format == "sse",
                            attempt=attempt,
                        )
                        reported_input, _, reported_reasoning = reported_usage(result)
                        reported_output = _explicit_output_tokens(result)
                        raw_usage = result.get("usage")
                        raw_usage = raw_usage if isinstance(raw_usage, dict) else {}
                        usage_metadata = result.get("usageMetadata")
                        usage_metadata = usage_metadata if isinstance(usage_metadata, dict) else {}
                        reported_total = reported_count(raw_usage, "total_tokens")
                        if reported_total is None:
                            reported_total = reported_count(usage_metadata, "totalTokenCount")
                        if reported_total is None:
                            reported_total = reported_count(result, "total_tokens")
                        available_usage = {
                            key: value
                            for key, value in (
                                ("input_tokens", reported_input),
                                ("output_tokens", reported_output),
                                ("reasoning_tokens", reported_reasoning),
                                ("total_tokens", reported_total),
                            )
                            if value is not None
                        }
                        incomplete = ProviderIncompleteResponseError(
                            partial_content=partial_content,
                            finish_reason=finish_reason,
                            usage=available_usage,
                            metrics=metrics,
                            classification=incomplete_classification,
                        )
                        incident.current["incomplete_response"] = {
                            "classification": incomplete.classification,
                            "finish_reason": incomplete.finish_reason,
                            "reported_usage": incomplete.usage,
                            "metrics": asdict(metrics),
                        }
                        if response_format == "sse" and finish_reason == "length":
                            incident.current["usage_drain_complete"] = usage_drain_complete
                        raise incomplete
                    if content and _is_policy_block_text(content):
                        raise ProviderRequestError("Prompt was blocked by the provider's content policy")
                    if not content and not message.get("tool_calls"):
                        incident.failure("HTTP 200 with empty content and no tool calls")
                        # Some providers return choices with a message but blank content (e.g. refusals, reasoning-only, or bugs).
                        logger.warning(
                            "Provider %s returned 200 with empty content (tool_calls=%s) message_field_count=%s",
                            endpoint.name,
                            bool(message.get("tool_calls")),
                            len(message),
                        )
                        if empty_response_recoveries < self.empty_response_retries:
                            empty_response_recoveries += 1
                            if await self._retry_after_attempt(
                                attempt,
                                endpoint,
                                f"Provider {endpoint.name} returned empty response",
                                max_attempts=max_attempts,
                            ):
                                continue
                        raise ProviderEmptyResponseError("Empty response from provider")

                    metrics = build_call_metrics(
                        result, data, observation,
                        provider=urlsplit(endpoint.base_url).hostname or "unknown",
                        endpoint=endpoint.name, model=data["model"],
                        request_start=request_start, stream=response_format == "sse",
                        attempt=attempt,
                    )
                    usage = {
                        "prompt_tokens": metrics.input_tokens,
                        "completion_tokens": metrics.output_tokens,
                        "total_tokens": metrics.input_tokens + metrics.output_tokens,
                    }
                    self._last_usage = dict(usage)
                    logger.info(
                        "Provider timing done endpoint=%s status=%s headers_ms=%.1f total_ms=%.1f content_chars=%s tool_calls=%s tokens=%s",
                        endpoint.name,
                        resp.status,
                        headers_ms,
                        metrics.elapsed_ms,
                        len(content or ""),
                        len(message.get("tool_calls") or []),
                        usage["total_tokens"],
                    )
                    incident.capture("Provider request recovered after upstream failures")
                    return ChatCompletionMessage(message, metrics=metrics, usage=usage)
            except asyncio.TimeoutError as e:
                incident.failure("Provider request timeout", e)
                logger.warning(
                    "Provider timing timeout endpoint=%s elapsed_ms=%.1f timeout=%s",
                    endpoint.name,
                    (time.perf_counter() - request_start) * 1000,
                    timeout,
                )
                if await self._retry_after_attempt(
                    attempt,
                    endpoint,
                    f"Provider {endpoint.name} timeout",
                    max_attempts=max_attempts,
                ):
                    continue
                failure = RuntimeError(f"Provider request timed out after {timeout}s")
                failure.__cause__ = e
                incident.capture("Provider request timed out", failure)
                raise failure from e
            except ProviderUsageExhaustedError as e:
                incident.failure("Provider usage exhausted", e)
                incident.capture("Provider usage exhausted", e)
                raise
            except ProviderRequestError as e:
                incident.failure("Provider request rejected", e)
                incident.capture("Provider request rejected", e)
                raise
            except RuntimeError as e:
                incident.failure("Provider response failure", e)
                last_error = e
                if isinstance(e, (ProviderIncompleteResponseError, ProviderEmptyResponseError)):
                    incident.capture("Provider response incomplete", e)
                    raise
                if isinstance(e, ProviderResponseError):
                    logger.warning(
                        "Provider response failure endpoint=%s status=%s format=%s content_type=%s reason=%s",
                        endpoint.name, resp.status, response_format, safe_content_type, e,
                    )
                if await self._retry_after_attempt(
                    attempt,
                    endpoint,
                    f"Provider {endpoint.name} error: {type(e).__name__}",
                    max_attempts=max_attempts,
                ):
                    continue
                incident.capture("Provider response failure", e)
                raise
            except (aiohttp.ClientError, OSError) as e:
                incident.failure("Provider transport or response failure", e)
                last_error = e
                if await self._retry_after_attempt(
                    attempt,
                    endpoint,
                    f"Provider {endpoint.name} error: {type(e).__name__}",
                    max_attempts=max_attempts,
                ):
                    continue
                failure = RuntimeError(f"Provider call failed: {type(last_error).__name__}")
                failure.__cause__ = e
                incident.capture("Provider transport or response failure", failure)
                raise failure from e
            finally:
                active_exception = sys.exception()
                if active_exception is not attempt_exception and isinstance(active_exception, asyncio.CancelledError) and incident.current:
                    incident.capture("Provider failures before request cancellation")
        failure = RuntimeError("Provider call failed after retries")
        incident.capture("Provider call failed after retries", failure)
        raise failure

    async def _retry_after_attempt(
        self,
        attempt: int,
        endpoint: ProviderEndpoint,
        reason: str,
        *,
        max_attempts: int | None = None,
    ) -> bool:
        max_attempts = max_attempts or self.retry_attempts
        if attempt >= max_attempts:
            return False
        wait = 10 * attempt
        logger.warning(
            "%s (attempt %s/%s), retrying in %ss...",
            reason, attempt, max_attempts, wait,
        )
        if wait:
            await asyncio.sleep(wait)
        return True
