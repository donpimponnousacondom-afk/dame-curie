"""Per-response measurements with an offline, fixed-tokenizer fallback."""

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache
from pathlib import Path
from uuid import uuid4

import tiktoken
from tiktoken.load import load_tiktoken_bpe


@dataclass(frozen=True, slots=True)
class CallMetrics:
    call_id: str
    provider: str
    endpoint: str
    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    input_source: str
    output_source: str
    elapsed_ms: float
    ttft_ms: float
    ttft_estimated: bool
    stream: bool
    attempt: int
    output_bytes: int

    @property
    def tps(self) -> float:
        return (
            self.output_tokens * 1000 / self.elapsed_ms if self.elapsed_ms > 0 else 0.0
        )

    @property
    def estimated(self) -> bool:
        return self.output_source != "provider"


class ChatCompletionMessage(dict):
    __slots__ = ("metrics", "usage")

    def __init__(self, message: dict, *, metrics: CallMetrics, usage: dict):
        super().__init__(message)
        self.metrics = metrics
        self.usage = dict(usage)


@cache
def local_encoding() -> tiktoken.Encoding:
    path = Path(__file__).resolve().parent / "assets/tokenizers/cl100k_base.tiktoken"
    expected_hash = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Local cl100k_base asset hash mismatch")
    ranks = load_tiktoken_bpe(str(path), expected_hash=expected_hash)
    return tiktoken.Encoding(
        name="cl100k_base",
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s",
        mergeable_ranks=ranks,
        special_tokens={
            "<|endoftext|>": 100257,
            "<|fim_prefix|>": 100258,
            "<|fim_middle|>": 100259,
            "<|fim_suffix|>": 100260,
            "<|endofprompt|>": 100276,
        },
    )


def count_tokens(text: str) -> int:
    return len(local_encoding().encode(text, disallowed_special=()))


def text_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in value
            if isinstance(part, str)
            or isinstance(part, dict)
            and part.get("type") in ("text", "output_text", "input_text")
            and isinstance(part.get("text"), str)
        )
    return ""


def reasoning_content(message: dict) -> str:
    text = text_content(message.get("reasoning_content")) or text_content(
        message.get("reasoning")
    )
    if not text:
        details = message.get("reasoning_details")
        if isinstance(details, list):
            text = "".join(
                item.get("text", item.get("summary", ""))
                for item in details
                if isinstance(item, dict)
                and item.get("type") in ("reasoning.text", "reasoning.summary")
                and isinstance(item.get("text", item.get("summary", "")), str)
            )
    return text


@dataclass(slots=True)
class OutputObservation:
    content: dict[int, list[str]] = field(default_factory=dict)
    reasoning: dict[int, list[str]] = field(default_factory=dict)
    tools: dict[tuple[int, int], dict[str, str]] = field(default_factory=dict)
    first_token_s: float | None = None
    finished_s: float = 0.0

    def observe(self, message: dict, now: float, *, choice_index: int = 0) -> None:
        content = text_content(message.get("content"))
        reasoning = reasoning_content(message)
        self.content.setdefault(choice_index, []).append(content)
        self.reasoning.setdefault(choice_index, []).append(reasoning)
        generated = bool(content or reasoning)
        calls = message.get("tool_calls")
        for index, call in enumerate(calls if isinstance(calls, list) else []):
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                continue
            fn = call["function"]
            slot = self.tools.setdefault(
                (choice_index, call.get("index", index)), {"name": "", "arguments": ""}
            )
            name, arguments = fn.get("name"), fn.get("arguments")
            if isinstance(name, str):
                slot["name"] += name
                generated |= bool(name)
            if isinstance(arguments, str):
                slot["arguments"] += arguments
                generated |= bool(arguments)
            elif isinstance(arguments, dict):
                slot["arguments"] = json.dumps(arguments, ensure_ascii=False)
                generated = True
        if generated and self.first_token_s is None:
            self.first_token_s = now

    def visible_text(self) -> str:
        return "".join("".join(parts) for parts in self.content.values()) + "".join(
            tool["name"] + tool["arguments"] for tool in self.tools.values()
        )

    def reasoning_text(self) -> str:
        return "".join("".join(parts) for parts in self.reasoning.values())


def token_count(value: object) -> int | None:
    result = None
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 2**53 - 1
    ):
        result = value
    elif (
        isinstance(value, float)
        and math.isfinite(value)
        and 0 <= value <= 2**53 - 1
        and value.is_integer()
    ):
        result = int(value)
    elif (
        isinstance(value, str)
        and len(value) <= 128
        and re.fullmatch(
            r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,9})?",
            value.strip(),
        )
    ):
        numeric = Decimal(value.strip())
        if 0 <= numeric <= 2**53 - 1 and numeric == numeric.to_integral_value():
            result = int(numeric)
    return result


def merge_usage(target: dict, incoming: dict, *, details: bool = False) -> None:
    for key, value in incoming.items():
        if key in (
            "prompt_tokens",
            "input_tokens",
            "completion_tokens",
            "output_tokens",
            "total_tokens",
            "reasoning_tokens",
            "prompt_eval_count",
            "eval_count",
            "promptTokenCount",
            "candidatesTokenCount",
            "thoughtsTokenCount",
            "cached_tokens",
            "audio_tokens",
            "accepted_prediction_tokens",
            "rejected_prediction_tokens",
        ):
            count = token_count(value)
            if count is not None:
                target[key] = count
        elif (
            not details
            and key
            in (
                "completion_tokens_details",
                "output_tokens_details",
                "prompt_tokens_details",
                "input_tokens_details",
            )
            and isinstance(value, dict)
        ):
            merge_usage(target.setdefault(key, {}), value, details=True)


def prefer_reported(*counts: int | None) -> int | None:
    result = None
    for count in counts:
        if count is not None:
            result = count
            if count > 0:
                break
    return result


def reported_count(usage: dict, *keys: str) -> int | None:
    return prefer_reported(*(token_count(usage.get(key)) for key in keys))


def reported_usage(response: dict) -> tuple[int | None, int | None, int | None]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    gemini = response.get("usageMetadata")
    gemini = gemini if isinstance(gemini, dict) else {}
    input_tokens = prefer_reported(
        reported_count(usage, "prompt_tokens", "input_tokens", "prompt_eval_count"),
        reported_count(response, "prompt_eval_count"),
        reported_count(gemini, "promptTokenCount"),
    )
    thoughts = reported_count(gemini, "thoughtsTokenCount")
    candidates = reported_count(gemini, "candidatesTokenCount")
    output_tokens = prefer_reported(
        reported_count(usage, "completion_tokens", "output_tokens", "eval_count"),
        reported_count(response, "eval_count"),
        candidates + (thoughts or 0) if candidates is not None else None,
    )
    reasoning_counts = []
    for key in ("completion_tokens_details", "output_tokens_details"):
        details = usage.get(key)
        if isinstance(details, dict):
            reasoning_counts.append(reported_count(details, "reasoning_tokens"))
    reasoning_tokens = prefer_reported(
        *reasoning_counts,
        reported_count(usage, "reasoning_tokens"),
        thoughts,
    )
    total_tokens = reported_count(usage, "total_tokens")
    if (
        input_tokens is not None
        and total_tokens is not None
        and total_tokens >= input_tokens + (reasoning_tokens or 0)
    ):
        output_tokens = prefer_reported(output_tokens, total_tokens - input_tokens)
    return input_tokens, output_tokens, reasoning_tokens


def request_text(payload: dict) -> str:
    """Approximate chat framing as compact JSON, not provider-specific template tokens.

    Only textual message content and native tool payloads enter the estimate;
    image/audio/video parts and opaque signatures/base64 are not tokenized.
    Tool schemas retain their JSON structure. Media token costs remain unknown.
    """
    messages = []
    for message in payload.get("messages", []):
        item = {
            key: message[key]
            for key in ("role", "name", "tool_call_id")
            if key in message
        }
        item["content"] = text_content(message.get("content"))
        reasoning = reasoning_content(message)
        if reasoning:
            item["reasoning"] = reasoning
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            item["tool_calls"] = [
                {key: call[key] for key in ("id", "type", "function") if key in call}
                for call in calls
                if isinstance(call, dict)
            ]
        messages.append(item)
    framed = {"messages": messages}
    if payload.get("tools"):
        framed["tools"] = payload["tools"]
    return json.dumps(framed, ensure_ascii=False, separators=(",", ":"))


def build_call_metrics(
    response: dict,
    payload: dict,
    observation: OutputObservation,
    *,
    provider: str,
    endpoint: str,
    model: str,
    request_start: float,
    stream: bool,
    attempt: int,
) -> CallMetrics:
    """A zero reported output total contradicting generated payload is a placeholder.

    Estimate that output rather than reporting a fictitious zero; retain reported
    zero when no generated payload was observed. Hidden reasoning stays unknown.
    """
    input_tokens, output_tokens, reasoning_tokens = reported_usage(response)
    input_source = "provider" if input_tokens is not None else "cl100k_base"
    output_source = "provider"
    visible = observation.visible_text()
    reasoning = observation.reasoning_text()
    if output_tokens == 0 and (visible or reasoning):
        output_tokens = None
    if reasoning_tokens == 0 and reasoning:
        reasoning_tokens = None
    if input_tokens is None:
        input_tokens = count_tokens(request_text(payload))
    if output_tokens is None:
        if reasoning_tokens is not None:
            output_tokens = count_tokens(visible) + reasoning_tokens
            output_source = "mixed"
        else:
            output_tokens = count_tokens(visible + reasoning)
            output_source = "cl100k_base"
    elapsed_ms = max(0.0, (observation.finished_s - request_start) * 1000)
    ttft_estimated = not stream or observation.first_token_s is None
    ttft_ms = (
        elapsed_ms
        if ttft_estimated
        else max(0.0, (observation.first_token_s - request_start) * 1000)
    )
    return CallMetrics(
        call_id=uuid4().hex,
        provider=provider,
        endpoint=endpoint,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        input_source=input_source,
        output_source=output_source,
        elapsed_ms=elapsed_ms,
        ttft_ms=ttft_ms,
        ttft_estimated=ttft_estimated,
        stream=stream,
        attempt=attempt,
        output_bytes=len((visible + reasoning).encode("utf-8", errors="replace")),
    )
