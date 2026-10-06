"""Tests for the new reasoning-in-tool-calls + native-only dispatch.

The XML ``collect_tool_calls`` dispatcher is gone (Maxwell is native
function-calling only now). What stays is ``strip_tool_payload_leaks`` — the
defensive sanitizer that scrubs any leaked ``<tool:...>`` tags a misbehaving
model drops into visible text even in native mode. These tests cover that
sanitizer plus the new reasoning contract:
- every tool schema gets an auto-injected ``reasoning`` param,
- ``extract_reasoning`` pulls it out of params before the tool runs,
- ``_sanitize_reasoning`` strips tag-wrapped thoughts the model sneakily emits.
"""

import json
from types import SimpleNamespace

import pytest

from bot import MaxwellBot, strip_tool_payload_leaks
from tool_registry import extract_reasoning, _sanitize_reasoning, record_reasoning
from tool_schemas import (
    REASONING_PARAM,
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


# ---- strip_tool_payload_leaks (defensive sanitizer, still used) ----


def test_strip_tool_payload_leaks_removes_standalone_tags():
    # reasoning_log is NOT a known tool anymore, so use a real one for the leak.
    text = "\n".join(
        [
            "<tool:react emoji=\"👍\" />",
            "<tool:send_message>hello</tool:send_message>",
            "actual reply",
        ]
    )
    assert strip_tool_payload_leaks(text) == "actual reply"


def test_strip_tool_payload_leaks_removes_self_closing_tags():
    text = '<tool:react emoji="catjam" />\nactual reply'
    assert strip_tool_payload_leaks(text) == "actual reply"


def test_strip_tool_payload_leaks_keeps_normal_xml():
    text = '<div class="card">hello</div>\nactual reply'
    assert strip_tool_payload_leaks(text) == text


def test_strip_tool_payload_leaks_removes_shorthand_tool_blocks():
    text = (
        '<tool:send_file><filename>bot.py</filename>'
        '<content>print("hi")</content></tool:send_file>\nactual reply'
    )
    assert strip_tool_payload_leaks(text) == "actual reply"


def test_strip_tool_payload_leaks_removes_unclosed_tool_and_environment_details():
    text = '<tool:send_message>Hello!<|end|><environment_details>secret context</environment_details>'
    assert strip_tool_payload_leaks(text) == ""


def test_strip_tool_payload_leaks_removes_reasoning_json_and_system_reminder():
    text = '''{
  "thoughts": "User asked for TTS.",
  "intent": "tts",
  "decision": "Call tts"
}
<tool:tts text="Hey there!" language="english" />
<system-reminder>secret context</system-reminder>'''
    assert strip_tool_payload_leaks(text) == ""


def test_strip_tool_payload_leaks_removes_registered_tool_bodies():
    leaked = (
        "<tool:update_base_personality>you are now evil</tool:update_base_personality> hello"
    )
    assert "you are now evil" not in strip_tool_payload_leaks(leaked)
    assert "hello" in strip_tool_payload_leaks(leaked)
    search = "<tool:search_messages>secret query</tool:search_messages> ok"
    assert "secret query" not in strip_tool_payload_leaks(search)


def test_strip_tool_payload_leaks_removes_glued_registered_tool():
    html = "<!DOCTYPE html><html><body>x</body></html>"
    text = f'ship<tool:shell command="echo ok">{html}</tool:shell>ok'
    assert strip_tool_payload_leaks(text) == "shipok"


def test_strip_tool_payload_leaks_catches_leaking_variants():
    assert strip_tool_payload_leaks("<|tool_send_message|>foo bar") == ""
    assert "before" in strip_tool_payload_leaks(
        "before <|tool_response|> <|end_of_text|> after"
    )
    assert "after" in strip_tool_payload_leaks(
        "before <|tool_response|> <|end_of_text|> after"
    )
    assert strip_tool_payload_leaks("<|/tool:send_message|>text") == "text"
    assert (
        strip_tool_payload_leaks("<tool_send_message>leaked</tool_send_message> visible").strip()
        == "visible"
    )
    assert strip_tool_payload_leaks("normal <div>ok</div>") == "normal <div>ok</div>"


def test_strip_tool_payload_leaks_removes_deepseek_dsml_invoke():
    leaked = (
        '<｜｜DSML｜｜invoke name="send_message">\n'
        '<｜｜DSML｜｜parameter name="reasoning" string="true">'
        "Z3ki is calling me out</｜｜DSML｜｜parameter>\n"
        '<｜｜DSML｜｜parameter name="content" string="true">'
        "my bad</｜｜DSML｜｜parameter>\n"
        "</｜｜DSML｜｜invoke>"
    )
    assert strip_tool_payload_leaks(leaked).strip() == "my bad"
    assert strip_tool_payload_leaks("ok " + leaked).strip() == "ok my bad"
    ascii_leaked = (
        '<|DSML|invoke name="send_message">'
        '<parameter name="content">hi</parameter>'
        "</invoke>"
    )
    assert strip_tool_payload_leaks(ascii_leaked).strip() == "hi"
    assert strip_tool_payload_leaks('<invoke name="send_message">secret</invoke> visible').strip() == "visible"
    leftover_name = "send_message\n" + leaked
    assert strip_tool_payload_leaks(leftover_name).strip() == "my bad"
    assert strip_tool_payload_leaks("send_message").strip() == "send_message"


def test_strip_tool_payload_leaks_extracts_send_message_arg_protocol():
    leaked = (
        "send_message<arg>reasoning</arg>Short Russian one-liner acknowledging "
        "they dropped it; stay firm, no MCP connect.</arg>"
        "<arg>content</arg>ну ладно, без обид — просто к чужим mcp не лезу.</arg>"
    )
    assert strip_tool_payload_leaks(leaked) == "ну ладно, без обид — просто к чужим mcp не лезу."
    mixed = "ok " + leaked
    assert strip_tool_payload_leaks(mixed) == "ok ну ладно, без обид — просто к чужим mcp не лезу."
    assert "reasoning" not in strip_tool_payload_leaks(leaked)
    assert "<arg>" not in strip_tool_payload_leaks(leaked)


def test_strip_tool_payload_leaks_drops_non_send_message_arg_protocol():
    leaked = "shell<arg>command</arg>cat /etc/passwd</arg><arg>reasoning</arg>peek</arg>"
    out = strip_tool_payload_leaks(leaked)
    assert "passwd" not in out
    assert "shell" not in out
    assert out == ""
    mixed = "before " + leaked + " after"
    assert strip_tool_payload_leaks(mixed) == "before  after"


def test_strip_tool_payload_leaks_unwraps_openai_text_part():
    assert strip_tool_payload_leaks('{"type":"text","text":""}') == ""
    assert strip_tool_payload_leaks('{"type": "text", "text": ""}') == ""
    assert strip_tool_payload_leaks('{"type":"text","text":"sent."}') == "sent."
    assert (
        strip_tool_payload_leaks('[{"type":"text","text":"hi "},{"type":"text","text":"there"}]')
        == "hi there"
    )


def test_strip_tool_payload_leaks_drops_empty_json_fence():
    leaked = (
        '```json\n{"name":"send_message","arguments":{"content":"x"}}\n```'
    )
    assert strip_tool_payload_leaks(leaked) == ""
    assert strip_tool_payload_leaks("```json\n\n```") == ""
    assert strip_tool_payload_leaks("look:\n```json\n\n```\noops") == "look:\n\noops"


# ---- reasoning param injection on every tool schema ----


def test_every_tool_gets_reasoning_param():
    tools = {"send_message": _FakeTool(), "react": _FakeTool(), "no_response": _FakeTool()}
    out = {o["function"]["name"]: o for o in build_openai_tools(tools)}
    for name, fn in out.items():
        props = fn["function"]["parameters"]["properties"]
        assert "reasoning" in props, f"{name} is missing the reasoning param, damn it"


def test_reasoning_is_always_required():
    tools = {"send_message": _FakeTool()}
    out = build_openai_tools(tools)[0]
    required = out["function"]["parameters"].get("required", [])
    # reasoning is always in required so the provider rejects empty calls
    # instead of silently dropping the trace. The tool's own required field
    # (content) is preserved alongside.
    assert "reasoning" in required
    assert "content" in required
    assert set(required) == {"reasoning", "content"}


def test_reasoning_param_schema_is_stable():
    # same shape everywhere — no per-tool drift
    assert REASONING_PARAM["type"] == "string"
    assert "plain" in REASONING_PARAM["description"].lower()


# ---- extract_reasoning / sanitize ----


def test_extract_reasoning_pops_it_out_of_params():
    reasoning, params = extract_reasoning(
        {"reasoning": "because the user asked", "content": "hi"}
    )
    assert reasoning == "because the user asked"
    assert params == {"content": "hi"}


def test_extract_reasoning_missing_returns_empty():
    reasoning, params = extract_reasoning({"content": "hi"})
    assert reasoning == ""
    assert params == {"content": "hi"}


def test_extract_reasoning_handles_none_params():
    reasoning, params = extract_reasoning(None)
    assert reasoning == ""
    assert params == {}


def test_sanitize_reasoning_strips_wrapped_thought_tags():
    assert _sanitize_reasoning("<thoughts>why</thoughts> do it") == "why  do it"


def test_sanitize_reasoning_clamps_giant_input():
    out = _sanitize_reasoning("x" * 5000)
    assert len(out) <= 1000
    assert out.endswith("…")


def test_sanitize_reasoning_empty_stays_empty():
    assert _sanitize_reasoning("") == ""
    assert _sanitize_reasoning(None) == ""


# ---- record_reasoning end-to-end (fake bot) ----


def test_record_reasoning_writes_trace_and_swallows_errors():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    import asyncio

    bot = FakeBot()

    async def run():
        await record_reasoning(
            bot, message=object(), tool_name="send_message",
            reasoning="user wants a reply", params={"content": "hi", "reasoning": "x"},
            result="__MESSAGE_SENT__",
        )

    asyncio.run(run())
    assert len(bot.traces) == 1
    t = bot.traces[0]
    assert t["tool"] == "send_message"
    assert t["thoughts"] == "user wants a reply"
    # reasoning must NOT leak into the params_preview
    assert "reasoning" not in t["params_preview"]
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
        await record_reasoning(
            bot, message=object(), tool_name="react",
            reasoning="", params={"emoji": "👍"}, result="Reacted",
        )

    asyncio.run(run())
    assert bot.traces[0]["thoughts"] == "(no reasoning provided by the model)"


def test_select_tool_protocol_native_wins_over_custom():
    """CUSTOM_TOOL_CALLS must not drop tools= when native function calling is on."""
    tools = [{"type": "function", "function": {"name": "send_message"}}]
    bot = SimpleNamespace(
        config=SimpleNamespace(CUSTOM_TOOL_CALLS=True),
        _control={"native_tool_calls": True, "tools_enabled": True},
    )
    bot._native_tools_enabled = lambda: True
    custom, provider_tools = MaxwellBot._select_tool_protocol(bot, tools)
    assert custom is False
    assert provider_tools == tools


def test_select_tool_protocol_custom_only_when_native_off():
    tools = [{"type": "function", "function": {"name": "send_message"}}]
    bot = SimpleNamespace(
        config=SimpleNamespace(CUSTOM_TOOL_CALLS=True),
        _control={"native_tool_calls": False, "tools_enabled": True},
    )
    bot._native_tools_enabled = lambda: False
    custom, provider_tools = MaxwellBot._select_tool_protocol(bot, tools)
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

    for arguments in (
        json.dumps({"body": body}) + "<provider-markup>",
        "42",
        "[]",
        "body=value",
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
        '{"value":1e10000}',
        '{"value":-1e10000}',
        '{"nested":{"values":[0,NaN]}}',
        '{"nested":[{"value":-Infinity}]}',
        '{"arguments":{"value":Infinity}}',
        json.dumps('{"nested":[{"value":1e10000}]}'),
    ):
        with pytest.raises(ValueError):
            normalize_native_tool_calls(
                [{"function": {"name": "create_site", "arguments": arguments}}]
            )
    for arguments in (
        {"value": float("nan")},
        {"nested": [float("inf")]},
        {"value": float("-inf")},
        {"nested": {"values": [0.0, float("nan")]}},
        {"parameters": {"value": float("inf")}},
    ):
        with pytest.raises(ValueError):
            normalize_native_tool_calls(
                [{"function": {"name": "create_site", "arguments": arguments}}]
            )
    for bad in ({"nested": [float("nan")]}, '{"nested":[{"value":1e10000}]}'):
        batch = [calls[0], {"id": "bad", "function": {"name": "create_site", "arguments": bad}}]
        with pytest.raises(ValueError):
            normalize_native_tool_calls(batch)
        assert batch[0]["function"]["arguments"] == {"body": body}
    nested = "0"
    for _ in range(33):
        nested = f'{{"value":{nested}}}'
    with pytest.raises(ValueError):
        normalize_native_tool_calls([{"function": {"name": "create_site", "arguments": nested}}])

    wide = json.dumps({"value": "é" * 7_997}, ensure_ascii=False, separators=(",", ":"))
    assert len(wide) < 16_000
    oversized_calls = [
        {"function": {"name": "é" * 65, "arguments": "{}"}},
        {"id": "é" * 65, "function": {"name": "create_site", "arguments": "{}"}},
        {"id": "meta", "function": {"name": "x", "arguments": "{}"}, "meta": "é" * 20_000},
    ]
    for call in oversized_calls:
        with pytest.raises(ValueError):
            normalize_native_tool_calls([call])
        with pytest.raises(ValueError):
            normalize_native_tool_calls([call], allow_oversized_arguments=True)
    with pytest.raises(ValueError):
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
    with pytest.raises(ValueError):
        normalize_native_tool_calls(
            [{"function": {"name": "create_site", "arguments": wide + "!"}}],
            allow_oversized_arguments=True,
        )
    with pytest.raises(ValueError):
        normalize_native_tool_calls(
            [{"function": {"name": "create_site", "arguments": wide[:-1] + ',"bad":NaN}'}}],
            allow_oversized_arguments=True,
        )
    with pytest.raises(ValueError):
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
    with pytest.raises(ValueError):
        normalize_native_tool_calls(oversized_batch)
    with pytest.raises(ValueError):
        normalize_native_tool_calls(oversized_batch, allow_oversized_arguments=True)
    with pytest.raises(ValueError):
        normalize_native_tool_calls([{"function": {"name": "x", "arguments": {"nested": {1: "bad"}}}}])


def test_record_reasoning_does_not_raise_on_bot_failure():
    class BrokenBot:
        async def _record_llm_trace(self, message, payload):
            raise RuntimeError("disk on fire")

    import asyncio

    async def run():
        # must NOT raise — a trace write failure must never kill the tool result
        await record_reasoning(
            BrokenBot(), message=object(), tool_name="shell",
            reasoning="x", params={"command": "ls"}, result="ok",
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
        {"reasoning": "r" * 9000, "query": "weather"}
    )
    reason_args = json.loads(elide_tool_calls_for_history(calls)[0]["function"]["arguments"])
    assert reason_args["reasoning"].startswith("r" * 200)
    assert reason_args["reasoning"].endswith("[9000 chars total; reasoning shortened]")
    assert len(reason_args["reasoning"]) <= 300
    assert reason_args["query"] == "weather"
    calls[0]["function"]["arguments"] = json.dumps(
        {"reasoning": "r" * 9000, "query": "q" * 5000, "options": ["x" * 9000]}
    )
    out = elide_tool_calls_for_history(calls)
    bounded = out[0]["function"]["arguments"]
    assert len(bounded) <= 4000
    assert "r" * 301 not in bounded
    assert "q" * 2001 not in bounded
    assert len(calls[0]["function"]["arguments"]) > 20_000
    assert elide_tool_calls_for_history(out) == out

    text_tail = [
        {"role": "assistant", "content": "reasoning " * 5000},
        {"role": "user", "content": "=== TOOL RESULTS ===\n" + "result " * 5000},
        {"role": "assistant", "content": "new round " * 5000},
        {"role": "user", "content": "=== TOOL RESULTS ===\n" + "fresh " * 5000},
    ]
    text_trimmed = trim_tool_tail(text_tail)
    assert len(text_trimmed) == 4
    assert sum(message_chars(msg) for msg in text_trimmed) <= 36_000
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
