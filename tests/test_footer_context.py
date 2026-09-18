import asyncio
from collections import OrderedDict
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import MaxwellBot, ToolCircuitBreaker
from error_reporting import PUBLIC_ERROR_TEXT
import response_observability as observability


class Memory:
    def __init__(self, rows):
        self.rows = rows

    async def get_channel_memory(self, channel_id):
        return self.rows

    def get_server_prompt(self, server_id):
        return None


def make_bot(rows=None):
    bot = SimpleNamespace(
        _tool_breaker=ToolCircuitBreaker(failure_threshold=999, recovery_seconds=0),
        _control={
            "base_personality": "test", "cross_context_enabled": False,
            "emoji_context_enabled": False, "long_term_memory_enabled": False,
            "memory_context_budget": 30000, "memory_history_messages": 20,
            "music_context_enabled": False, "tools_enabled": False,
            "entity_memory_enabled": False, "footer_enabled": True,
            "footer_format": "CURRENT TEMPLATE MUST NOT BE RECONSTRUCTED",
        },
        _drugged_until={}, _guild_emojis={}, _recent_users={},
        _conversation_watch={}, _tool_system_prompt=lambda *args, **kwargs: "",
        bot_name="Dame Curie", memory=Memory(rows if rows is not None else []),
        user=SimpleNamespace(display_name="Dame Curie", name="curie", id=1),
        _payload_attr_list=lambda *args: [],
    )
    for name in (
        "_reply_parent", "_replying_to_own_message", "_render_reply_parent",
        "_author_is_self", "_iter_resolved_reply_chain", "_reply_parent_context_lines",
        "_directly_addressed", "_conversation_watch_active", "_is_short_live_turn",
    ):
        setattr(bot, name, getattr(MaxwellBot, name).__get__(bot))
    return bot


def message(content="next question", *, channel_id=123, message_id=789, author_id=456):
    return SimpleNamespace(
        content=content, id=message_id, channel=SimpleNamespace(id=channel_id, name="general"),
        author=SimpleNamespace(id=author_id, display_name="Curie" if author_id == 1 else "root", bot=False),
        guild=None, mentions=[], reference=None, attachments=[], embeds=[], stickers=[],
    )


def delivered(bot, text, *, channel_id=123, message_id=900, fenced=False, replace=False):
    footer = observability.render_footer(text, None, "Dame Curie", code_block=fenced)
    content = f"answer\n{footer}"
    if fenced:
        content = f"```\n{content}\n```"
    sent = message(content, channel_id=channel_id, message_id=message_id, author_id=1)
    observability.record_delivery(bot, sent.channel, sent, None, replace=replace)
    return sent


@pytest.mark.parametrize("fenced", [False, True])
def test_exact_delivered_footer_reaches_actual_next_payload_without_memory_mutation(fenced):
    rows = [{
        "author": "Dame Curie", "author_id": "1", "content": "answer",
        "timestamp": "2026-09-11T10:00:00+00:00", "message_id": "900",
    }]
    before = deepcopy(rows)
    bot = make_bot(rows)
    actual = "Sent TTFT 125ms | TPS 25.0 | model-wire-v1"
    sent = delivered(bot, actual, fenced=fenced)
    wire_before = sent.content
    bot._control["footer_format"] = "NEW TEMPLATE NOT ACTUALLY SENT"
    current = message("What did your footer say?")
    input_before = current.content
    payload = asyncio.run(MaxwellBot._build_messages(bot, current, current.content))
    assert payload[-1]["role"] == "user"
    assert actual in str(payload[-1]["content"])
    assert actual not in str(payload[0]["content"])
    assert "NEW TEMPLATE NOT ACTUALLY SENT" not in str(payload)
    assert all(observability.FOOTER_MARKER not in str(item["content"]) for item in payload)
    assert rows == before
    assert current.content == input_before
    assert sent.content == wire_before
    assert actual not in MaxwellBot._message_memory_content(bot, sent)
    assert observability.FOOTER_MARKER not in MaxwellBot._message_memory_content(bot, sent)


def test_actual_payload_is_channel_isolated_and_uses_latest_delivered_value():
    bot = make_bot()
    delivered(bot, "old-in-channel", message_id=900)
    delivered(bot, "other-channel-private-footer", channel_id=456, message_id=901)
    delivered(bot, "latest-in-channel", message_id=902)
    first = message(channel_id=123)
    second = message(channel_id=999)
    first_payload = asyncio.run(MaxwellBot._build_messages(bot, first, first.content))
    second_payload = asyncio.run(MaxwellBot._build_messages(bot, second, second.content))
    assert "latest-in-channel" in str(first_payload[-1]["content"])
    assert "old-in-channel" not in str(first_payload)
    assert "other-channel-private-footer" not in str(first_payload)
    assert "latest-in-channel" not in str(second_payload)
    assert "other-channel-private-footer" not in str(second_payload)


@pytest.mark.parametrize("fenced", [False, True])
def test_fetched_pre_restart_reply_footer_is_visible_but_storage_quote_stays_clean(fenced):
    bot = make_bot()
    old_footer = "Pre-restart TTFT 711ms | TPS 19.3"
    footer = observability.render_footer(old_footer, None, "Dame Curie", code_block=fenced)
    raw = f"historic answer\n{footer}"
    if fenced:
        raw = f"```\n{raw}\n```"
    parent = message(raw, message_id=777, author_id=1)
    current = message("Explain that footer")
    current.reference = SimpleNamespace(message_id=777, resolved=None)
    current.channel.fetch_message = AsyncMock(return_value=parent)

    async def build():
        await MaxwellBot._ensure_reply_chain_resolved(bot, current)
        return await MaxwellBot._build_messages(bot, current, current.content)

    payload = asyncio.run(build())
    current.channel.fetch_message.assert_awaited_once_with(777)
    assert old_footer in str(payload[-1]["content"])
    assert all(observability.FOOTER_MARKER not in str(item["content"]) for item in payload)
    assert old_footer in MaxwellBot._render_reply_parent(bot, current, parent)
    assert old_footer not in MaxwellBot._message_memory_content(bot, parent)
    stored_quote = MaxwellBot._reply_meta_from_message(bot, current)
    assert "historic answer" in stored_quote["reply_to_content"]
    assert old_footer not in stored_quote["reply_to_content"]
    assert observability.FOOTER_MARKER not in stored_quote["reply_to_content"]
    assert parent.content == raw
    assert current.content == "Explain that footer"
    assert bot.memory.rows == []
    assert not getattr(bot, "_delivered_footers", {})


@pytest.mark.parametrize("fenced", [False, True])
def test_footer_text_extracts_only_actual_marked_wire_footer(fenced):
    bot = make_bot()
    sent = delivered(bot, "actual sent footer", fenced=fenced)
    assert observability.footer_text(sent.content) == "actual sent footer"


@pytest.mark.parametrize("text", [
    "", "ordinary answer", "answer\n-# unmarked footer",
    "answer\n-# marked-but-not-final" + observability.FOOTER_MARKER + "\nmore body",
    "answer\nplain-text-with-marker" + observability.FOOTER_MARKER,
    PUBLIC_ERROR_TEXT,
])
def test_footer_text_does_not_invent_footer(text):
    assert observability.footer_text(text) == ""


def test_footer_cache_is_bounded_and_string_keyed():
    bot = make_bot()
    for index in range(1025):
        delivered(bot, f"wire-footer-{index}", message_id=index)
    assert isinstance(bot._delivered_footers, OrderedDict)
    assert len(bot._delivered_footers) == 1024
    assert ("123", "0") not in bot._delivered_footers
    assert ("123", "1024") in bot._delivered_footers
    assert "wire-footer-1024" in observability.latest_delivered_footer(bot, "123")


def test_edit_replaces_actual_footer_and_removal_drops_stale_value():
    bot = make_bot()
    delivered(bot, "original wire footer")
    edited = delivered(bot, "edited wire footer", replace=True)
    annotation = observability.latest_delivered_footer(bot, "123")
    assert "edited wire footer" in annotation
    assert "original wire footer" not in annotation
    assert len(bot._delivered_footers) == 1
    edited.content = "edited answer without a footer"
    observability.record_delivery(bot, edited.channel, edited, None, replace=True)
    assert observability.latest_delivered_footer(bot, "123") == ""
    assert ("123", "900") not in bot._delivered_footers


def test_public_generic_error_never_acquires_a_fake_footer_in_model_payload():
    bot = make_bot()
    notice = message(PUBLIC_ERROR_TEXT, message_id=900, author_id=1)
    observability.record_delivery(bot, notice.channel, notice, None)
    current = message("What happened?")
    payload = asyncio.run(MaxwellBot._build_messages(bot, current, current.content))
    assert observability.latest_delivered_footer(bot, "123") == ""
    assert "CURRENT TEMPLATE MUST NOT BE RECONSTRUCTED" not in str(payload)
    assert all(observability.FOOTER_MARKER not in str(item["content"]) for item in payload)
    assert notice.content == PUBLIC_ERROR_TEXT
    assert not getattr(bot, "_delivered_footers", {})


def test_non_discord_delivery_does_not_leak_into_discord_footer_context():
    bot = make_bot()
    sent = message("answer\n-# telegram-only" + observability.FOOTER_MARKER, author_id=1)
    observability.record_delivery(bot, sent.channel, sent, None, platform="telegram")
    assert observability.latest_delivered_footer(bot, "123") == ""


@pytest.fixture
def call_metrics():
    from provider_telemetry import CallMetrics

    return CallMetrics(
        call_id="footer-context-call", provider="provider.example", endpoint="primary",
        model="wire-model", input_tokens=123, output_tokens=50, reasoning_tokens=10,
        input_source="provider", output_source="provider", elapsed_ms=2000,
        ttft_ms=777, ttft_estimated=False, stream=True, attempt=1, output_bytes=160,
    )


def test_unmeasured_self_echo_preserves_original_measurement_registry(call_metrics):
    bot = make_bot()
    sent = delivered(bot, "actual measured wire footer")
    observability.record_delivery(bot, sent.channel, sent, call_metrics)
    registry_before = list(bot._delivery_measurements.records.items())
    observability.record_delivery(bot, sent.channel, sent, None, replace=False)
    assert list(bot._delivery_measurements.records.items()) == registry_before
    assert bot._delivery_measurements.lookup("123", "900")[1] is call_metrics
    assert "actual measured wire footer" in observability.latest_delivered_footer(bot, "123")


def test_edit_tool_records_returned_sdk_message_not_unchanged_original(call_metrics):
    from bot_tools import EditMessageTool

    bot = make_bot()
    original = delivered(bot, "OLD WIRE FOOTER")
    original_content = original.content
    returned = []

    async def sdk_edit(*, content):
        updated = message(content, message_id=original.id, author_id=1)
        returned.append(updated)
        return updated

    original.edit = AsyncMock(side_effect=sdk_edit)
    current = message("edit the previous answer")
    current.channel.fetch_message = AsyncMock(return_value=original)
    bot._control["footer_format"] = "EDITED {{TTFT}} | {{MODEL}}"
    result = asyncio.run(EditMessageTool(bot).execute(
        current, message_id="900", content="edited body", _response_metrics=call_metrics,
    ))
    assert "edited successfully" in result
    assert original.content == original_content
    assert returned[0] is not original
    actual_footer = observability.footer_text(returned[0].content)
    assert actual_footer == "EDITED 777ms | wire-model"
    annotation = observability.latest_delivered_footer(bot, "123")
    assert actual_footer in annotation
    assert "OLD WIRE FOOTER" not in annotation
    assert bot._delivery_measurements.lookup("123", "900")[1] is call_metrics
    payload = asyncio.run(MaxwellBot._build_messages(bot, current, "What does your footer say now?"))
    assert actual_footer in str(payload[-1]["content"])
    assert "OLD WIRE FOOTER" not in str(payload[-1]["content"])


@pytest.mark.parametrize("fenced", [False, True])
def test_message_excerpt_preserves_complete_footer_after_long_body(fenced):
    footer_text = "needle in footer | TTFT 7ms | TPS 13.0 | preserved-tail"
    footer = observability.render_footer(footer_text, None, "Dame Curie", code_block=fenced)
    raw = "long body " * 60 + "\n" + footer
    if fenced:
        raw = f"```\n{raw}\n```"
    sent = message(raw, author_id=1)
    excerpt = observability.discord_message_excerpt(sent, limit=150)
    assert footer_text in excerpt
    assert "long body " * 60 not in excerpt
    assert observability.FOOTER_MARKER not in excerpt
    assert sent.content == raw


@pytest.mark.parametrize("mode", ["query", "recent", "other-channel"])
def test_search_tool_matches_footer_and_returns_it_after_truncated_body(mode):
    from bot_tools import SearchMessagesTool

    bot = make_bot()
    footer_text = "needle in footer | TTFT 7ms | TPS 13.0 | preserved-tail"
    raw = "long body " * 60 + "\n" + observability.render_footer(footer_text, None, "Dame Curie")
    sent = message(raw, message_id=900, author_id=1)
    current = message("search previous messages")

    async def matching_history(*, limit):
        yield sent

    async def empty_history(*, limit):
        for item in ():
            yield item

    current.channel.history = matching_history
    if mode == "other-channel":
        current.channel.history = empty_history
        other = SimpleNamespace(
            id=456, name="other", history=matching_history,
            permissions_for=lambda user: SimpleNamespace(read_messages=True),
        )
        current.guild = SimpleNamespace(text_channels=[other], me=bot.user)
    query = "" if mode == "recent" else "NEEDLE IN FOOTER"
    result = asyncio.run(SearchMessagesTool(bot).execute(current, query=query, limit="1"))
    assert "900" in result
    assert footer_text in result
    assert "long body " * 60 not in result
    assert observability.FOOTER_MARKER not in result
    assert sent.content == raw
    assert bot.memory.rows == []
