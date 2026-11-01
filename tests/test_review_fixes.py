"""Regressions from the 2026-08-19 multi-agent code review."""

import asyncio
from types import SimpleNamespace

import pytest

from bot import DameCurieBot, _sanitize_visible_reply
from captcha_solver import _BaseSolver, CaptchaSolveError
from rem import RemStore
from tool_schemas import TOOL_PARAMETERS, build_openai_tools

DSML_SAMPLE = (
    '<｜｜DSML｜｜invoke name="send_message">\n'
    '<｜｜DSML｜｜parameter name="content" string="true">my bad'
    "</｜｜DSML｜｜parameter>\n</｜｜DSML｜｜invoke>"
)


def test_native_calls_from_string_does_not_consume_stash():
    from bot import DameCurieBot

    consumed = {"n": 0}

    def consume():
        consumed["n"] += 1
        return [{"id": "stale"}]

    bot = SimpleNamespace(_consume_native_tool_calls=consume)
    assert DameCurieBot._native_calls_from(bot, "quota exceeded") == []
    assert consumed["n"] == 0


def test_wait_and_personality_schemas_are_declared():
    assert "seconds" in TOOL_PARAMETERS["wait"]["properties"]
    assert "text" in TOOL_PARAMETERS["update_base_personality"]["properties"]
    assert "files" in TOOL_PARAMETERS["shell"]["properties"]
    tools = build_openai_tools(
        {
            "wait": SimpleNamespace(get_description=lambda: "wait"),
            "sleep": SimpleNamespace(get_description=lambda: "sleep"),
        }
    )
    names = {t["function"]["name"] for t in tools}
    assert "wait" in names
    wait = next(t for t in tools if t["function"]["name"] == "wait")
    assert "seconds" in wait["function"]["parameters"]["properties"]


def test_2captcha_ready_status_is_accepted():
    async def run():
        solver = _BaseSolver("key")

        async def get_result():
            return {"status": 1, "request": "token-abc"}

        data = await solver._poll(get_result, timeout=1)
        assert data["request"] == "token-abc"

    asyncio.run(run())


def test_2captcha_not_ready_then_error():
    async def run():
        solver = _BaseSolver("key")
        n = {"i": 0}

        async def get_result():
            n["i"] += 1
            if n["i"] == 1:
                return {"status": 0, "request": "CAPCHA_NOT_READY"}
            return {"status": 0, "request": "ERROR_CAPTCHA_UNSOLVABLE"}

        try:
            await solver._poll(get_result, timeout=5)
            raise AssertionError("expected failure")
        except CaptchaSolveError:
            pass

    asyncio.run(run())


def test_rem_patch_state_does_not_wipe_corrupt_file(tmp_path):
    store = RemStore(str(tmp_path))
    store.state_file.write_text("{ broken", encoding="utf-8")

    async def run():
        out = await store.patch_state({"running": False})
        assert out == {}
        assert store.state_file.read_text(encoding="utf-8") == "{ broken"

    asyncio.run(run())


@pytest.mark.parametrize(
    "text",
    [
        "hello there",
        '<tool:react emoji="x" />\n'
        "<tool:send_message>hello</tool:send_message>\nreply",
        "<tool:send_file><filename>a.py</filename>"
        "<content>x</content></tool:send_file>",
        "<tool:send_message>Hello!<|end|>"
        "<environment_details>ctx</environment_details>",
        '{"thoughts": "why"}\n<tool:tts text="hi" />\n'
        "<system-reminder>ctx</system-reminder>",
        "<tool:update_base_personality>you are now evil"
        "</tool:update_base_personality> hi",
        'ship<tool:shell command="echo ok"><html></html></tool:shell>ok',
        "<|tool_send_message|>foo bar",
        "before <|tool_response|> <|end_of_text|> after",
        "<|/tool:send_message|>text",
        "<tool_send_message>leaked</tool_send_message> visible",
        DSML_SAMPLE,
        '<|DSML|invoke name="send_message">'
        '<parameter name="content">hi</parameter></invoke>',
        '<invoke name="send_message">secret</invoke> visible',
        "send_message<arg>explanation</arg>why</arg><arg>content</arg>ok then</arg>",
        "shell<arg>command</arg>cat /etc/passwd</arg>",
        '{"type":"text","text":"sent."}',
        '[{"type":"text","text":"hi "},{"type":"text","text":"there"}]',
        '```json\n{"name":"send_message","arguments":{"content":"x"}}\n```',
        "```json\n\n```",
        '{"content": "hi", "reply": true}',
        '{"name": "react", "arguments": {"emoji": "x"}}',
        "<message>hi</message>",
        "a\n\n\n\nb",
    ],
)
def test_strip_keeps_plain_chat_without_tool_tags(text):
    # Root, 1 November 2026: tool markup, tool JSON and injected context tags
    # reach Discord as the model wrote them. Each case was stripped before.
    assert _sanitize_visible_reply(text) == text.strip()
    voice = SimpleNamespace(_control={"vc_max_response_chars": 4000})
    assert DameCurieBot._vc_format_response(voice, text) == text.strip()
