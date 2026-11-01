"""Tests for the new explanation-in-tool-calls + native-only dispatch.

The XML ``collect_tool_calls`` dispatcher is gone (Curie is native
function-calling only now). Root, 1 November 2026: tool markup in visible text
is no longer stripped (see test_review_fixes). These tests cover the
explanation contract:
- every tool schema gets an auto-injected ``explanation`` param,
- ``extract_explanation`` pulls it out of params before the tool runs,
- ``_sanitize_explanation`` strips tag-wrapped thoughts the model sneakily emits.
"""

import json
from types import SimpleNamespace

import pytest

from bot import DameCurieBot
from tool_registry import extract_explanation, _sanitize_explanation, record_explanation
from tool_schemas import (
    EXPLANATION_PARAM,
    TOOL_TAIL_MAX_CHARS,
    build_openai_tools,
    elide_tool_calls_for_history,
    message_chars,
    normalize_native_tool_calls,
    trim_tool_tail,
)


class _FakeTool:
    def get_description(self):
        return "fake tool"


TOOLS = {"send_file", "react", "send_message", "no_response", "create_site", "tts"}


# ---- explanation param injection on every tool schema ----


def test_every_tool_gets_reasoning_param():
    tools = {"send_message": _FakeTool(), "react": _FakeTool(), "no_response": _FakeTool()}
    out = {o["function"]["name"]: o for o in build_openai_tools(tools)}
    for name, fn in out.items():
        props = fn["function"]["parameters"]["properties"]
        assert "explanation" in props, f"{name} is missing the explanation param, damn it"


def test_reasoning_is_always_required():
    tools = {"send_message": _FakeTool()}
    out = build_openai_tools(tools)[0]
    required = out["function"]["parameters"].get("required", [])
    # explanation is always in required so the provider rejects empty calls
    # instead of silently dropping the trace. The tool's own required field
    # (content) is preserved alongside.
    assert required == ["explanation", "content"]
    assert next(iter(out["function"]["parameters"]["properties"])) == "explanation"


def test_reasoning_param_schema_is_stable():
    # same shape everywhere - no per-tool drift
    assert EXPLANATION_PARAM["type"] == "string"
    assert "plain" in EXPLANATION_PARAM["description"].lower()


# ---- extract_explanation / sanitize ----


def test_extract_reasoning_pops_it_out_of_params():
    explanation, params = extract_explanation(
        {"explanation": "because the user asked", "content": "hi"}
    )
    assert explanation == "because the user asked"
    assert params == {"content": "hi"}


def test_extract_reasoning_missing_returns_empty():
    explanation, params = extract_explanation({"content": "hi"})
    assert explanation == ""
    assert params == {"content": "hi"}


def test_extract_reasoning_handles_none_params():
    explanation, params = extract_explanation(None)
    assert explanation == ""
    assert params == {}


def test_sanitize_reasoning_strips_wrapped_thought_tags():
    assert _sanitize_explanation("<thoughts>why</thoughts> do it") == "why  do it"


def test_sanitize_reasoning_clamps_giant_input():
    out = _sanitize_explanation("x" * 5000)
    assert len(out) <= 1000
    assert out.endswith("…")


def test_sanitize_reasoning_empty_stays_empty():
    assert _sanitize_explanation("") == ""
    assert _sanitize_explanation(None) == ""


# ---- record_explanation end-to-end (fake bot) ----


def test_record_reasoning_writes_trace_and_swallows_errors():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    import asyncio

    bot = FakeBot()

    async def run():
        await record_explanation(
            bot, message=object(), tool_name="send_message",
            explanation="user wants a reply", params={"content": "hi", "explanation": "x"},
            result="__MESSAGE_SENT__",
        )

    asyncio.run(run())
    assert len(bot.traces) == 1
    t = bot.traces[0]
    assert t["tool"] == "send_message"
    assert t["thoughts"] == "user wants a reply"
    # explanation must NOT leak into the params_preview
    assert "explanation" not in t["params_preview"]
    assert t["params_preview"]["content"] == "hi"


def test_record_reasoning_empty_reasoning_records_a_stub():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    import asyncio

    bot = FakeBot()

    async def run():
        await record_explanation(
            bot, message=object(), tool_name="react",
            explanation="", params={"emoji": "👍"}, result="Reacted",
        )

    asyncio.run(run())
    assert bot.traces[0]["thoughts"] == "(no explanation provided by the model)"


def test_select_tool_protocol_native_wins_over_custom():
    """CUSTOM_TOOL_CALLS must not drop tools= when native function calling is on."""
    tools = [{"type": "function", "function": {"name": "send_message"}}]
    bot = SimpleNamespace(
        config=SimpleNamespace(CUSTOM_TOOL_CALLS=True),
        _control={"native_tool_calls": True, "tools_enabled": True},
    )
    bot._native_tools_enabled = lambda: True
    custom, provider_tools = DameCurieBot._select_tool_protocol(bot, tools)
    assert custom is False
    assert provider_tools == tools


def test_select_tool_protocol_custom_only_when_native_off():
    tools = [{"type": "function", "function": {"name": "send_message"}}]
    bot = SimpleNamespace(
        config=SimpleNamespace(CUSTOM_TOOL_CALLS=True),
        _control={"native_tool_calls": False, "tools_enabled": True},
    )
    bot._native_tools_enabled = lambda: False
    custom, provider_tools = DameCurieBot._select_tool_protocol(bot, tools)
    assert custom is True
    assert provider_tools is None


def test_normalize_native_tool_calls_decodes_provider_argument_shapes():
    """Native arguments are objects or fully consumed JSON objects."""
    body = r"<pre>line one\nline two</pre>"
    calls = [
        {"id": "direct", "function": {"name": "create_site", "arguments": {"body": body}}},
        {
            "id": "nested",
            "function": {"name": "create_site", "arguments": json.dumps(json.dumps({"body": body}))},
        },
    ]
    normalized = normalize_native_tool_calls(calls)
    assert [call["arguments"]["body"] for call in normalized] == [body] * 2
    assert normalized[1]["raw_name"] == "create_site"
    assert normalized[0]["raw"] is calls[0]
    assert calls[1]["function"]["arguments"] == json.dumps(json.dumps({"body": body}))
    finite = normalize_native_tool_calls([
        {"id": "finite", "function": {"name": "tool_create_site", "arguments": {
            "values": [0.0, -1.25, 1e300], "nested": {"value": 1e-300},
        }}},
    ])[0]
    assert finite["raw_name"] == "tool_create_site"
    assert finite["name"] == "create_site"
    assert finite["arguments"] == {"values": [0.0, -1.25, 1e300], "nested": {"value": 1e-300}}

    # Three decode or unwrap steps are accepted: two wrappers and a JSON string.
    (three_steps,) = normalize_native_tool_calls([{"function": {
        "name": "shell",
        "arguments": {"arguments": {"parameters": json.dumps({"command": "x"})}},
    }}])
    assert three_steps["arguments"] == {"command": "x"}
    for bad_name, kind in ((5, "int"), ([], "list"), (False, "bool")):
        message = rf"of call 1 of 1 has type {kind}, not str$"
        with pytest.raises(ValueError, match=message):
            normalize_native_tool_calls([{"function": {"name": bad_name}}])
    message = r"call 1 of 1: character 0 \(from 0\) of the name"
    with pytest.raises(ValueError, match=message):
        normalize_native_tool_calls([{"function": {"name": "\ud800"}}])
    # Each error names the call and its one exact cause.
    place = "Malformed native tool-call batch: call 1 of 1 ('create_site'): "
    non_finite = place + "the arguments hold a non-finite number"
    for arguments, cause in (
        (
            json.dumps({"body": body}) + "<provider-markup>",
            place + "the arguments have text after the JSON value, from character "
            f"{len(json.dumps({'body': body}))} of the decoded text (from 0)",
        ),
        ("42", place + "the arguments decode to type int, not a JSON object"),
        ("[]", place + "the arguments decode to type list, not a JSON object"),
        (
            "body=value",
            place + "the arguments are not valid JSON: Expecting value at "
            "character 0 of the decoded text (from 0)",
        ),
        ('{"value":NaN}', non_finite),
        ('{"value":Infinity}', non_finite),
        ('{"value":-Infinity}', non_finite),
        ('{"value":1e10000}', non_finite),
        ('{"value":-1e10000}', non_finite),
        ('{"nested":{"values":[0,NaN]}}', non_finite),
        ('{"nested":[{"value":-Infinity}]}', non_finite),
        ('{"arguments":{"value":Infinity}}', non_finite),
        (json.dumps('{"nested":[{"value":1e10000}]}'), non_finite),
        ('{"a":1', place + "the arguments leave 1 open bracket"),
        ('{"a":"x}', place + "the arguments end inside a string"),
        (
            '{"a":1}}',
            place + "the arguments close an unopened bracket at character 7 (from 0)",
        ),
        (
            json.dumps(json.dumps(json.dumps(json.dumps({"a": 1})))),
            place + "the arguments need more than 3 decode or unwrap steps",
        ),
        (
            '{"a":"\ud800"}',
            "Malformed native tool-call batch: call 1 of 1 ('create_site'): "
            "character 6 (from 0) of the arguments is not valid UTF-8",
        ),
    ):
        with pytest.raises(ValueError) as raised:
            normalize_native_tool_calls(
                [{"function": {"name": "create_site", "arguments": arguments}}]
            )
        assert str(raised.value) == cause
    for arguments in (
        {"value": float("nan")},
        {"nested": [float("inf")]},
        {"value": float("-inf")},
        {"nested": {"values": [0.0, float("nan")]}},
        {"parameters": {"value": float("inf")}},
    ):
        with pytest.raises(ValueError, match="hold a non-finite number$"):
            normalize_native_tool_calls(
                [{"function": {"name": "create_site", "arguments": arguments}}]
            )
    for bad in ({"nested": [float("nan")]}, '{"nested":[{"value":1e10000}]}'):
        batch = [calls[0], {"id": "bad", "function": {"name": "create_site", "arguments": bad}}]
        with pytest.raises(ValueError, match="call 2 of 2 .* non-finite number$"):
            normalize_native_tool_calls(batch)
        assert batch[0]["function"]["arguments"] == {"body": body}
    nested = "0"
    for _ in range(33):
        nested = f'{{"value":{nested}}}'
    with pytest.raises(ValueError, match="nest deeper than 32 levels$"):
        normalize_native_tool_calls([{"function": {"name": "create_site", "arguments": nested}}])

    wide = json.dumps({"value": "é" * 7_997}, ensure_ascii=False, separators=(",", ":"))
    assert len(wide) < 16_000
    oversized_calls = [
        {"function": {"name": "é" * 65, "arguments": "{}"}},
        {"id": "é" * 65, "function": {"name": "create_site", "arguments": "{}"}},
    ]
    for call in oversized_calls:
        with pytest.raises(ValueError, match="is longer than 128 bytes$"):
            normalize_native_tool_calls([call])
        with pytest.raises(ValueError, match="is longer than 128 bytes$"):
            normalize_native_tool_calls([call], allow_oversized_arguments=True)
    wide_envelope = {"id": "meta", "function": {"name": "x", "arguments": "{}"}, "meta": "é" * 20_000}
    with pytest.raises(ValueError, match="batch envelope reaches .* at call 1 of 1"):
        normalize_native_tool_calls([wide_envelope])
    (envelope_refused,) = normalize_native_tool_calls(
        [wide_envelope], allow_oversized_arguments=True
    )
    assert envelope_refused["oversized_arguments"] is False
    assert envelope_refused["batch_limit_error"].startswith("the batch envelope is 40,0")
    assert envelope_refused["batch_limit_error"].endswith("bytes; the limit is 40,000")
    with pytest.raises(ValueError, match="bytes; the limit is 16,000$"):
        normalize_native_tool_calls([{"function": {"name": "create_site", "arguments": wide}}])
    oversized = normalize_native_tool_calls(
        [{"id": "oversized-id", "function": {"name": "create_site", "arguments": wide}}],
        allow_oversized_arguments=True,
    )[0]
    assert oversized["id"] == "oversized-id"
    assert oversized["raw_name"] == "create_site"
    assert oversized["arguments"] == {}
    assert oversized["oversized_arguments"] is True
    assert oversized["raw"] is None
    assert oversized["batch_limit_error"] == ""
    with pytest.raises(ValueError, match="text after the JSON value"):
        normalize_native_tool_calls(
            [{"function": {"name": "create_site", "arguments": wide + "!"}}],
            allow_oversized_arguments=True,
        )
    with pytest.raises(ValueError, match="hold a non-finite number$"):
        normalize_native_tool_calls(
            [{"function": {"name": "create_site", "arguments": wide[:-1] + ',"bad":NaN}'}}],
            allow_oversized_arguments=True,
        )
    with pytest.raises(ValueError, match="call 2 of 2 .* repeats the id 'duplicate'$"):
        normalize_native_tool_calls(
            [
                {"id": "duplicate", "function": {"name": "create_site", "arguments": wide}},
                {"id": "duplicate", "function": {"name": "create_site", "arguments": "{}"}},
            ],
            allow_oversized_arguments=True,
        )
    batch_argument = json.dumps({"value": "é" * 6_000}, ensure_ascii=False)
    oversized_batch = [
        {"id": str(index), "function": {"name": "x", "arguments": batch_argument}}
        for index in range(3)
    ]
    with pytest.raises(ValueError, match="the batch reaches .* at call 3 of 3"):
        normalize_native_tool_calls(oversized_batch)
    many_calls = [{"id": str(index), "function": {"name": "x", "arguments": "{}"}} for index in range(11)]
    with pytest.raises(ValueError, match="the response has 11 calls; the limit is 10$"):
        normalize_native_tool_calls(many_calls)
    many_refused = normalize_native_tool_calls(many_calls, allow_oversized_arguments=True)
    assert [call["id"] for call in many_refused] == [str(index) for index in range(11)]
    assert {call["batch_limit_error"] for call in many_refused} == {
        "the response has 11 calls; the limit is 10"
    }
    batch_refused = normalize_native_tool_calls(oversized_batch, allow_oversized_arguments=True)
    assert [call["oversized_arguments"] for call in batch_refused] == [False, False, False]
    assert {call["batch_limit_error"] for call in batch_refused} == {
        f"the batch carries {3 * len(batch_argument.encode('utf-8')):,} bytes of "
        "arguments; the limit is 32,000"
    }
    with pytest.raises(ValueError, match="hold a non-string key$"):
        normalize_native_tool_calls([{"function": {"name": "x", "arguments": {"nested": {1: "bad"}}}}])


def test_record_reasoning_does_not_raise_on_bot_failure():
    class BrokenBot:
        async def _record_llm_trace(self, message, payload):
            raise RuntimeError("disk on fire")

    import asyncio

    async def run():
        # must NOT raise - a trace write failure must never kill the tool result
        await record_explanation(
            BrokenBot(), message=object(), tool_name="shell",
            explanation="x", params={"command": "ls"}, result="ok",
        )

    asyncio.run(run())  # no exception = pass


def test_elide_compacts_message_content():
    html = "<!DOCTYPE html><html><body>" + ("n" * 20_000) + "</body></html>"
    calls = [
        {
            "id": "3",
            "type": "function",
            "function": {
                "name": "send_message",
                "arguments": json.dumps({"content": html}),
            },
        },
    ]
    out = elide_tool_calls_for_history(calls)
    send_args = json.loads(out[0]["function"]["arguments"])
    assert send_args["content"].startswith("[large content omitted,")
    assert "20000" in send_args["content"] or str(len(html)) in send_args["content"]
    calls[0]["function"]["arguments"] = json.dumps(
        {"explanation": "r" * 9000, "query": "weather"}
    )
    reason_args = json.loads(elide_tool_calls_for_history(calls)[0]["function"]["arguments"])
    assert reason_args["explanation"].startswith("r" * 200)
    assert reason_args["explanation"].endswith("[9000 chars total; explanation shortened]")
    assert len(reason_args["explanation"]) <= 300
    assert reason_args["query"] == "weather"
    calls[0]["function"]["arguments"] = json.dumps(
        {"explanation": "r" * 9000, "query": "q" * 5000, "options": ["x" * 9000]}
    )
    out = elide_tool_calls_for_history(calls)
    bounded = out[0]["function"]["arguments"]
    assert len(bounded) <= 4000
    assert "r" * 301 not in bounded
    assert "q" * 2001 not in bounded
    assert len(calls[0]["function"]["arguments"]) > 20_000
    assert elide_tool_calls_for_history(out) == out

    text_tail = [
        {"role": "assistant", "content": "explanation " * 12000},
        {"role": "user", "content": "=== TOOL RESULTS ===\n" + "result " * 12000},
        {"role": "assistant", "content": "new round " * 12000},
        {"role": "user", "content": "=== TOOL RESULTS ===\n" + "fresh " * 12000},
    ]
    text_trimmed = trim_tool_tail(text_tail)
    assert len(text_trimmed) == 4
    assert sum(message_chars(msg) for msg in text_trimmed) <= TOOL_TAIL_MAX_CHARS
    assert "truncated from tool history" in text_trimmed[0]["content"]
    with pytest.raises(ValueError, match="Orphan tool result"):
        trim_tool_tail([{"role": "tool", "tool_call_id": "orphan", "content": "x"}])
    with pytest.raises(ValueError, match="mismatched native"):
        trim_tool_tail(
            [
                {"role": "assistant", "tool_calls": [{"id": "c1"}]},
                {"role": "tool", "tool_call_id": "c2", "content": "x"},
            ]
        )
