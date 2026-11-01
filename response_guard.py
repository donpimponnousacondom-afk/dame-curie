"""Prompt protections: transcript normalization and sampling parameters.

Root, 1 November 2026: the output scrubbers (scrub_repetitions,
break_echo_loop) are removed. Repetition in a reply stays visible.
"""
from __future__ import annotations

import re
from typing import Iterable


def sanitize_transcript(messages: Iterable[dict], *, max_chars: int = 120_000) -> list[dict]:
    """Normalize whitespace and remove adjacent duplicate turns before trimming."""
    result: list[dict] = []
    previous = None
    for message in messages:
        role = str(message.get("role", "user"))
        content = re.sub(r"\s+", " ", str(message.get("content", "")).strip())
        if not content:
            continue
        key = (role, content.casefold())
        if key == previous:
            continue
        result.append({**message, "role": role, "content": content})
        previous = key
    total = sum(len(str(m["content"])) for m in result)
    while total > max_chars and result:
        removed = result.pop(0)
        total -= len(str(removed["content"]))
    return result


def sampling_params(config: object) -> dict[str, float]:
    """Return supported provider penalties without sending null/unknown values."""
    result = {}
    for name in ("frequency_penalty", "presence_penalty"):
        value = getattr(config, name, None)
        if value is not None:
            result[name] = float(value)
    return result
