"""Drive the real foreground handler with synthetic transport and context fixtures."""

import asyncio
from contextlib import nullcontext
from dataclasses import replace
import json
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from bot import MaxwellBot, TokenBudgetTracker
from bot_tools import SendFileTool, SendMessageTool
from dirac_runtime import _NoticeInput
from provider_telemetry import CallMetrics
from providers import ProviderIncompleteResponseError, ProviderResult
from turn_budget import TurnBudgetExceeded, current_foreground_turn
from response_observability import DeliveryMeasurements, FOOTER_MARKER, RunningBuild


class Channel:
    id = 100
    guild = SimpleNamespace(id=9)

    def __init__(self):
        self.sent = []
        self.stop_after = None

    async def send(self, content=None, **kwargs):
        if self.stop_after is not None and len(self.sent) >= self.stop_after:
            return None
        assert len(content or "") <= 2000
        sent = SimpleNamespace(
            id=1000 + len(self.sent), channel=self, content=content, kwargs=kwargs
        )
        self.sent.append(sent)
        return sent


class Message:
    id = 7
    author = SimpleNamespace(id=7, bot=False, display_name="root")
    content = "hello"
    reference = None

    def __init__(self):
        self.channel = Channel()
        self.guild = self.channel.guild

    async def reply(self, content=None, **kwargs):
        reference = discord.MessageReference(
            message_id=int(self.id), channel_id=self.channel.id, guild_id=self.guild.id,
        )
        return await self.channel.send(content, reference=reference, **kwargs)


@pytest.fixture
def measured_call():
    return CallMetrics(
        call_id="A",
        provider="provider.example",
        endpoint="primary",
        model="model-A",
        input_tokens=123,
        output_tokens=50,
        reasoning_tokens=10,
        input_source="provider",
        output_source="provider",
        elapsed_ms=2000,
        ttft_ms=125,
        ttft_estimated=False,
        stream=True,
        attempt=1,
        output_bytes=160,
    )


@pytest.fixture
def foreground_bot():
    bot = SimpleNamespace(
        _control={"max_tool_iterations": 3, "footer_format": "{{MODEL}} {{TTFT}}"},
        config=SimpleNamespace(ENABLE_IMAGE_INPUT=False, OPENAI_MAX_TOKENS=1000),
        bot_name="Maxwell",
        user=SimpleNamespace(id=42),
        tools={},
        memory=SimpleNamespace(),
        _delivery_measurements=DeliveryMeasurements(),
        _replying_channels=set(),
        _active_requests={},
        _active_request_user={},
        _message_snapshots={},
        _message_update_state={},
        _current_progress_by_channel={},
        _last_bot_reply={},
        _token_tracker=TokenBudgetTracker(),
        _check_sleep_gate=AsyncMock(return_value=True),
        _begin_inflight_context=lambda message, content: {"message_ids": set()},
        _enter_live_typing=AsyncMock(),
        _exit_live_typing=AsyncMock(),
        _directly_addressed=lambda message: False,
        _arm_conversation_watch=Mock(),
        _record_rem_event=AsyncMock(),
        _is_short_live_turn=lambda *args: False,
        _extract_media=AsyncMock(return_value=([], [])),
        _extract_embeds=AsyncMock(return_value=[]),
        _extract_linked_media=AsyncMock(return_value=[]),
        _ensure_reply_chain_resolved=AsyncMock(),
        _iter_resolved_reply_chain=lambda message: [],
        _reply_media_message_id=lambda *args: None,
        _should_use_cached_media_context=lambda *args: False,
        _current_binary_media=lambda media: [],
        _format_media_summary=lambda *args: "",
        _message_carries_media=lambda message: False,
        _cache_media_context=Mock(),
        _message_update_fingerprint=lambda message: (),
        _message_media_fingerprint=lambda message: (),
        _progress_enabled=lambda guild: False,
        _build_messages=AsyncMock(return_value=[{"role": "user", "content": "hello"}]),
        _build_openai_tools=lambda *args, **kwargs: [],
        _select_tool_protocol=lambda tools: (False, []),
        _acquire_ai_slot=AsyncMock(),
        _release_ai_slot=AsyncMock(),
        _ensure_reasoning_trace=AsyncMock(),
        _render_custom_emojis=lambda text, guild: text,
        _extract_stickers_from_text=lambda text, guild: (text, []),
        _reply_typing=lambda *args, **kwargs: nullcontext(),
        _respect_slowmode=AsyncMock(),
        _mark_bot_sent=Mock(),
        add_message_to_memory=AsyncMock(),
        _mark_inbox_announced=AsyncMock(),
        _end_inflight_context=Mock(),
        _tick_media_context=Mock(),
        _flush_deferred_context_extraction=Mock(),
    )

    async def refresh(context, *args):
        return args

    bot._apply_inflight_refresh = refresh
    bot._wait_for_late_embeds = AsyncMock(side_effect=lambda message, content: message)
    bot._message_tool_platform = MethodType(MaxwellBot._message_tool_platform, bot)
    bot._compatible_tool_names = MethodType(MaxwellBot._compatible_tool_names, bot)
    bot._turn_tool_names = MethodType(MaxwellBot._turn_tool_names, bot)
    bot._preserve_input_actor = MaxwellBot._preserve_input_actor
    for name in (
        "_native_calls_from",
        "_usage_from",
        "_recover_text_tool_calls",
        "_send_with_slowmode",
    ):
        setattr(bot, name, MethodType(getattr(MaxwellBot, name), bot))
    bot._split_response = MaxwellBot._split_response
    return bot


@pytest.fixture
def raw_update_foreground(foreground_bot):
    bot = object.__new__(MaxwellBot)
    bot.__dict__.update(vars(foreground_bot))
    bot._connection = SimpleNamespace(user=foreground_bot.user)
    bot._message_tool_platform = MethodType(MaxwellBot._message_tool_platform, bot)
    bot._compatible_tool_names = MethodType(MaxwellBot._compatible_tool_names, bot)
    bot._turn_tool_names = MethodType(MaxwellBot._turn_tool_names, bot)
    bot._inflight_context = {}
    bot._media_context = {}
    bot._recent_users = {}
    bot._blacklist = set()
    bot._is_admin = lambda user_id: False
    bot._update_recent_users = Mock()
    bot._load_control = Mock()
    for name in (
        "_begin_inflight_context", "_end_inflight_context", "_apply_inflight_refresh",
        "_wait_for_late_embeds", "_message_update_fingerprint", "_message_media_fingerprint",
    ):
        delattr(bot, name)
    bot._send_with_slowmode = MethodType(MaxwellBot._send_with_slowmode, bot)
    message = Message()
    message.embeds = []
    bot.get_channel = lambda channel_id: message.channel

    async def build_messages(current, content, **kwargs):
        if bot._build_messages.await_count == 1:
            await bot.on_raw_message_edit(SimpleNamespace(
                cached_message=message, message_id=message.id, channel_id=message.channel.id,
                data={"content": "edited request", "embeds": [{"title": "late preview"}]},
            ))
        return [{"role": "user", "content": bot._message_memory_content(current)}]

    bot._build_messages = AsyncMock(side_effect=build_messages)
    return bot, message


@pytest.mark.parametrize("cached_proxy", [False, True])
def test_notice_update_builds_with_actor_and_refreshed_poster_snapshot(
    raw_update_foreground, measured_call, cached_proxy
):
    """An in-flight rebuild must not substitute the notice poster for its actor."""
    bot, notice = raw_update_foreground
    operator = notice.author
    poster = SimpleNamespace(id=bot.user.id, bot=True, display_name="Dame")
    notice.author = poster
    injected = _NoticeInput(notice, operator)
    bot._is_admin = lambda user_id: user_id == operator.id
    bot.config.ENABLE_IMAGE_INPUT = True
    image_url = "https://synthetic.example/updated.png"
    image = {"is_image": True, "b64": "c3ludGhldGlj", "mime_type": "image/png"}
    bot._extract_context_media = AsyncMock(return_value=[image])
    bot._format_media_summary = Mock(return_value="refreshed visual")
    bot._current_binary_media = lambda media: []

    async def build_messages(current, content, *, has_media, media_summary):
        """Inspect the real refresh boundary without booting unrelated RAG machinery."""
        assert current.author is operator
        assert current.notice_author is poster
        assert bot._is_admin(current.author.id)
        if bot._build_messages.await_count == 1:
            await bot.on_raw_message_edit(SimpleNamespace(
                cached_message=injected if cached_proxy else notice,
                message_id=notice.id, channel_id=notice.channel.id,
                data={
                    "content": "edited notice",
                    "embeds": [{"title": "late preview", "image": {"url": image_url}}],
                },
            ))
        else:
            assert content == current.content == "edited notice"
            assert current.embeds[0].title == "late preview"
            assert has_media is True
            assert media_summary == "refreshed visual"
            assert bot._format_media_summary.call_args.args == ([image], [image])
        return [{"role": "user", "content": f"actor={current.author.id}: {content}"}]

    bot._build_messages = AsyncMock(side_effect=build_messages)
    bot._generate_response = AsyncMock(return_value=ProviderResult("Answer", metrics=measured_call))
    bot._dispatch_tool_calls = AsyncMock(return_value=("Answer", [], []))
    asyncio.run(bot._handle_message(injected))

    assert bot._build_messages.await_count == 2
    bot._extract_context_media.assert_awaited_once()
    assert bot._extract_context_media.call_args.args[0].embeds[0].image.url == image_url
    bot._generate_response.assert_awaited_once()
    prompt = bot._generate_response.call_args.args[0]
    assert prompt == [{"role": "user", "content": f"actor={operator.id}: edited notice"}]
    assert bot._generate_response.call_args.kwargs["media"] == [image]
    assert bot._dispatch_tool_calls.call_args.args[0].author is operator
    refreshed = bot._message_snapshots[str(notice.id)]
    assert refreshed.author is operator
    assert refreshed.notice_author is poster
    assert refreshed.content == "edited notice"
    assert notice.content == "hello" and notice.embeds == []
    assert len(notice.channel.sent) == 1


def configure_dispatch(bot):
    tool = SendMessageTool(bot)

    async def dispatch(
        message, response, *, native_tool_calls=None, response_metrics=None, **kwargs
    ):
        results = []
        for call in native_tool_calls or []:
            function = call["function"]
            if function["name"] == "send_message":
                result = await tool.execute(
                    message,
                    _response_metrics=response_metrics,
                    **json.loads(function["arguments"]),
                )
                results.append("Tool send_message: " + result)
            else:
                results.append("Tool web_search: synthetic result")
        return str(response), results, []

    bot._dispatch_tool_calls = AsyncMock(side_effect=dispatch)


def tool_call(name, **arguments):
    return {
        "id": "tool-1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


@pytest.mark.parametrize("delivery", ["file_caption", "plain_final", "file_then_final"])
def test_foreground_raw_update_preserves_file_and_final_reply(
    raw_update_foreground, measured_call, delivery
):
    async def scenario():
        bot, message = raw_update_foreground
        file_tool = SendFileTool(bot)
        file_results = []
        calls = []
        if delivery != "plain_final":
            calls.append(tool_call(
                "send_file", filename="result.txt", content="synthetic artifact", caption="Here is the result",
            ))
        if delivery == "file_then_final":
            calls.append(tool_call("web_search", query="synthetic followup"))
        responses = [ProviderResult("Final answer", tool_calls=calls, metrics=measured_call)]
        if delivery == "file_then_final":
            responses.append(ProviderResult("Final answer", metrics=measured_call))

        async def dispatch(current, response, *, native_tool_calls=None, **kwargs):
            results = []
            for call in native_tool_calls or []:
                function = call["function"]
                if function["name"] == "send_file":
                    result = await file_tool.execute(current, **json.loads(function["arguments"]))
                    file_results.append(result)
                    results.append("Tool send_file: " + result)
                else:
                    assert function["name"] == "web_search"
                    results.append("Tool web_search: synthetic result")
            return str(response), results, []

        bot._dispatch_tool_calls = AsyncMock(side_effect=dispatch)
        bot._generate_response = AsyncMock(side_effect=responses)
        await bot._handle_message(message)

        assert bot._build_messages.await_count == 2
        refreshed = bot._dispatch_tool_calls.call_args.args[0]
        assert refreshed.content == "edited request"
        assert refreshed.embeds[0].title == "late preview"
        prompt = bot._generate_response.call_args_list[0].args[0][0]["content"]
        assert "edited request" in prompt and "late preview" in prompt
        assert message.content == "hello" and message.embeds == []
        assert bot._generate_response.await_count == len(responses)
        assert len(message.channel.sent) == (2 if delivery == "file_then_final" else 1)
        for sent in message.channel.sent:
            reference = sent.kwargs["reference"].to_message_reference_dict()
            assert str(reference["message_id"]) == str(message.id)
            assert str(reference["channel_id"]) == str(message.channel.id)
        if delivery != "plain_final":
            assert file_results[0].startswith("__FILE_SENT__")
            assert "__CAPTION_SENT__" in file_results[0]
            attachment = message.channel.sent[0]
            assert attachment.content == "Here is the result"
            assert attachment.kwargs["file"].filename == "result.txt"
            assert attachment.kwargs["file"].fp.getvalue() == b"synthetic artifact"
        if delivery != "file_caption":
            final = message.channel.sent[-1]
            assert final.kwargs.get("file") is None
            assert final.content.startswith("Final answer\n")
            assert final.content.endswith(FOOTER_MARKER)
            assert bot._delivery_measurements.lookup("100", str(final.id))[1] is measured_call

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode",
    [
        "plain", "terminal", "followup", "followup_incomplete", "empty_followup", "incomplete",
        "incomplete_partial", "reasoning_only", "incomplete_empty", "output_exhausted",
        "attempts_exhausted",
        "deadline", "upstream_timeout", "cancelled",
    ],
)
def test_real_foreground_handler_preserves_producing_call(
    foreground_bot, measured_call, mode
):
    async def scenario():
        bot, message = foreground_bot, Message()
        first = measured_call
        second = replace(first, call_id="B", model="model-B", ttft_ms=777)
        configure_dispatch(bot)
        if mode == "deadline":
            bot._control["turn_deadline_seconds"] = 1
            bot._generate_response = Mock(
                side_effect=lambda *args, **kwargs: asyncio.sleep(2)
            )
        elif mode == "output_exhausted":
            bot._generate_response = AsyncMock(
                side_effect=TurnBudgetExceeded("output_tokens")
            )
        elif mode == "attempts_exhausted":
            bot._generate_response = AsyncMock(
                side_effect=TurnBudgetExceeded("provider_attempts")
            )
        elif mode == "upstream_timeout":
            bot._generate_response = AsyncMock(
                side_effect=TimeoutError("synthetic upstream timeout")
            )
        elif mode == "cancelled":
            bot._generate_response = AsyncMock(side_effect=asyncio.CancelledError())
        elif mode in {
            "incomplete", "incomplete_partial", "reasoning_only", "incomplete_empty"
        }:
            partial = (
                " ".join(f"segment-{index:04d}" for index in range(1200))
                + " UNDELIVERED-TAIL"
                if mode in {"incomplete", "incomplete_partial"}
                else "private reasoning sentinel"
                if mode == "reasoning_only"
                else " \n "
            )
            incomplete = ProviderIncompleteResponseError(
                partial_content=partial,
                finish_reason="length",
                usage={
                    "input_tokens": 123,
                    "output_tokens": 50,
                    "reasoning_tokens": 10,
                },
                metrics=first,
                classification=(
                    "reasoning_only" if mode == "reasoning_only" else "output_token_limit"
                ),
            )
            if mode == "incomplete_partial":
                message.channel.stop_after = 1
            bot._generate_response = AsyncMock(side_effect=incomplete)
        elif mode == "plain":
            responses = [ProviderResult("plain answer", metrics=first)]
            bot._generate_response = AsyncMock(side_effect=responses)
        elif mode == "terminal":
            responses = [
                ProviderResult(
                    "",
                    tool_calls=[tool_call("send_message", content="done")],
                    metrics=first,
                )
            ]
            bot._generate_response = AsyncMock(side_effect=responses)
        elif mode in {"followup", "followup_incomplete"}:
            responses = [
                ProviderResult(
                    '{"name":"send_message","arguments":{"content":"checking"}}',
                    metrics=first,
                ),
                ProviderResult("finished answer", metrics=second),
            ]
            if mode == "followup_incomplete":
                incomplete = ProviderIncompleteResponseError(
                    partial_content="provider follow-up partial",
                    finish_reason="length",
                    usage={
                        "input_tokens": 222,
                        "output_tokens": 60,
                        "reasoning_tokens": 15,
                    },
                    metrics=second,
                    classification="output_token_limit",
                )
                responses[1] = incomplete
                bot._recover_text_tool_calls = Mock(
                    wraps=bot._recover_text_tool_calls
                )
            bot._generate_response = AsyncMock(side_effect=responses)
        else:
            responses = [
                ProviderResult(
                    "partial answer",
                    tool_calls=[tool_call("web_search", query="test")],
                    metrics=first,
                ),
                ProviderResult("", metrics=second),
            ]
            bot._generate_response = AsyncMock(side_effect=responses)
        if mode == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await MaxwellBot._handle_message(bot, message)
            assert not message.channel.sent
        else:
            await MaxwellBot._handle_message(bot, message)
        if mode in {
            "incomplete", "incomplete_partial", "followup_incomplete",
            "reasoning_only", "incomplete_empty", "output_exhausted",
            "attempts_exhausted", "deadline", "upstream_timeout", "cancelled",
        }:
            expected_generations = 2 if mode == "followup_incomplete" else 1
            assert bot._generate_response.call_count == expected_generations
            if mode != "deadline":
                assert bot._generate_response.await_count == expected_generations
            if mode == "followup_incomplete":
                assert bot._dispatch_tool_calls.await_count == 1
                assert bot._recover_text_tool_calls.call_count == 1
            else:
                assert not bot._dispatch_tool_calls.await_args_list
            assert current_foreground_turn() is None
            assert not bot._replying_channels
            assert "100" not in bot._active_requests
            assert "100" not in bot._active_request_user
            assert bot._end_inflight_context.called
            if mode in {"incomplete", "incomplete_partial"}:
                assert bot._token_tracker._prompt_tokens == 123
                assert bot._token_tracker._completion_tokens == 50
                assert bot._token_tracker._total_tokens == 0
                assert incomplete.partial_content == partial
                assert incomplete.finish_reason == "length"
                assert message.channel.sent[0].content.startswith(
                    "INCOMPLETE RESPONSE:"
                )
                assert bot._delivery_measurements.lookup(
                    "100", str(message.channel.sent[0].id)
                )[1] is first
                assistant_memory = [
                    call.args[1]
                    for call in bot.add_message_to_memory.call_args_list
                    if call.args[1].get("author_is_bot")
                ]
                assistant_events = [
                    call for call in bot._record_rem_event.call_args_list
                    if call.args[1] == "assistant"
                ]
                assert assistant_memory
                assert len(assistant_events) == 1
                if mode == "incomplete":
                    assert len(message.channel.sent) > 1
                    assert any(
                        "UNDELIVERED-TAIL" in sent.content
                        for sent in message.channel.sent
                    )
                    assert message.channel.sent[-1].content.endswith(FOOTER_MARKER)
                    assert "model-A" in message.channel.sent[-1].content
                    assert "125ms" in message.channel.sent[-1].content
                    assert all(
                        bot._delivery_measurements.lookup("100", str(sent.id))[1]
                        is first
                        for sent in message.channel.sent
                    )
                    assert any(
                        "UNDELIVERED-TAIL" in item["content"]
                        for item in assistant_memory
                    )
                else:
                    sent = message.channel.sent[0]
                    assert len(message.channel.sent) == 1
                    assert "UNDELIVERED-TAIL" not in sent.content
                    assert len(assistant_memory) == 1
                    assert assistant_memory[0]["message_id"] == f"bot_reply:{sent.id}"
                    assert "INCOMPLETE RESPONSE" in assistant_memory[0]["content"]
                    assert "UNDELIVERED-TAIL" not in assistant_memory[0]["content"]
                    assert "Delivery incomplete" in assistant_memory[0]["content"]
                    assert "UNDELIVERED-TAIL" not in assistant_events[0].args[2]
                    assert "Delivery incomplete" in assistant_events[0].args[2]
            elif mode == "followup_incomplete":
                assert incomplete.partial_content == "provider follow-up partial"
                assert incomplete.finish_reason == "length"
                assert bot._token_tracker._prompt_tokens == 222
                assert bot._token_tracker._completion_tokens == 60
                assert bot._token_tracker._total_tokens == 0
                assert len(message.channel.sent) == 2
                assert message.channel.sent[0].content.startswith("checking")
                sent = message.channel.sent[1]
                assert sent.content.startswith("INCOMPLETE RESPONSE:")
                assert "provider follow-up partial" in sent.content
                assert sent.content.endswith(FOOTER_MARKER)
                assert "model-B" in sent.content and "777ms" in sent.content
                assert bot._delivery_measurements.lookup("100", str(sent.id))[1] is second
                assistant_memory = [
                    call.args[1]
                    for call in bot.add_message_to_memory.call_args_list
                    if call.args[1].get("author_is_bot")
                ]
                assert len(assistant_memory) == 1
                assert assistant_memory[0]["content"] == (
                    "INCOMPLETE RESPONSE: The provider stopped at the output-token limit. "
                    "No tool calls from this response were executed.\n\n"
                    "provider follow-up partial"
                )
                assistant_events = [
                    call for call in bot._record_rem_event.call_args_list
                    if call.args[1] == "assistant"
                ]
                assert len(assistant_events) == 1
                assert assistant_events[0].args[2] == assistant_memory[0]["content"]
            elif mode == "reasoning_only":
                assert len(message.channel.sent) == 1
                assert "reasoning without a usable answer" in message.channel.sent[0].content
                assert "private reasoning sentinel" not in message.channel.sent[0].content
                assert message.channel.sent[0].content.endswith(FOOTER_MARKER)
                assert bot._delivery_measurements.lookup(
                    "100", str(message.channel.sent[0].id)
                )[1] is first
            elif mode == "incomplete_empty":
                assert len(message.channel.sent) == 1
                assert "stopped at the output-token limit" in message.channel.sent[0].content
                assert "INCOMPLETE RESPONSE" not in message.channel.sent[0].content
                assert message.channel.sent[0].content.endswith(FOOTER_MARKER)
            elif mode == "output_exhausted":
                assert "output allowance exhausted" in message.channel.sent[0].content
                assert "No additional provider attempt" in message.channel.sent[0].content
            elif mode == "attempts_exhausted":
                assert "provider-attempt allowance exhausted" in message.channel.sent[0].content
                assert "No additional provider attempt" in message.channel.sent[0].content
            elif mode == "deadline":
                assert "foreground turn deadline" in message.channel.sent[0].content.lower()
                assert "No further model requests were made" in message.channel.sent[0].content
            elif mode == "upstream_timeout":
                assert all(
                    "foreground turn deadline" not in sent.content.lower()
                    for sent in message.channel.sent
                )
            return
        assert bot._generate_response.await_count == len(responses)
        assert message.channel.sent
        assert all(
            "something broke" not in sent.content for sent in message.channel.sent
        )
        expected = [first, second] if mode == "followup" else [first]
        assert len(message.channel.sent) == len(expected)
        for sent, metrics in zip(message.channel.sent, expected):
            assert sent.content.endswith(FOOTER_MARKER)
            assert metrics.model in sent.content
            assert bot._delivery_measurements.lookup("100", str(sent.id))[1] is metrics
        dispatches = bot._dispatch_tool_calls.call_args_list
        assert dispatches[0].kwargs["response_metrics"] is first
        if mode == "followup":
            assert dispatches[1].kwargs["response_metrics"] is second
        if mode == "empty_followup":
            assert message.channel.sent[0].content.startswith("partial answer")
            assert "model-B" not in message.channel.sent[0].content
        for call in bot.add_message_to_memory.call_args_list:
            assert FOOTER_MARKER not in call.args[1]["content"]
        for call in bot._record_rem_event.call_args_list:
            assert FOOTER_MARKER not in call.args[2]

    asyncio.run(scenario())


def test_sticker_only_send_preserves_empty_clean_chunk_and_registers_once(
    measured_call,
):
    async def scenario():
        bot = SimpleNamespace(
            _control={},
            bot_name="Maxwell",
            _delivery_measurements=DeliveryMeasurements(),
            _extract_stickers_from_text=lambda text, guild: ("", ["sticker"]),
        )
        message = Message()
        tool = SendMessageTool(bot)
        tool._chunks = lambda text, limit: [] if not text else [text]
        result = await tool.execute(
            message, content="sticker:wave", _response_metrics=measured_call
        )
        assert result == "__MESSAGE_SENT__\n"
        assert len(message.channel.sent) == 1
        sent = message.channel.sent[0]
        assert sent.content == ""
        assert sent.kwargs["stickers"] == ["sticker"]
        assert (
            bot._delivery_measurements.lookup("100", str(sent.id))[1] is measured_call
        )
        assert len(bot._delivery_measurements.records) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("command", ["version", "footer status", "help"])
def test_multichar_prefix_commands_and_help_fit_discord(command):
    async def scenario():
        bot = SimpleNamespace(
            _control={},
            command_prefix="!!",
            _is_admin=lambda uid: True,
            _running_build=RunningBuild(
                "a" * 40, "branch", "date", "subject", False, "start", "3.14"
            ),
        )
        bot._handle_footer_command = MethodType(MaxwellBot._handle_footer_command, bot)
        message = Message()
        message.content = "!!" + command
        await MaxwellBot._handle_command(bot, message)
        assert message.channel.sent
        assert not any(
            "Something went wrong" in sent.content for sent in message.channel.sent
        )
        text = "\n".join(sent.content for sent in message.channel.sent)
        assert {
            "version": "Provenance: checkout at boot",
            "footer status": "Footer: on",
            "help": "!!footer",
        }[command] in text
        assert all(len(sent.content) <= 2000 for sent in message.channel.sent)

    asyncio.run(scenario())


@pytest.mark.parametrize("tool_name,prefix", [
    ("image_generator", "Image generated, NOT sent:"),
    ("image_generator", "Image edited, NOT sent:"),
])
def test_foreground_deferred_image_has_one_preview_reply_and_preserves_metrics(
    foreground_bot, measured_call, tool_name, prefix
):
    async def scenario():
        bot, message = foreground_bot, Message()
        url = "https://cdn.discordapp.com/attachments/100/200/generated_image.png"
        text = f"Fresh shot: [generated_image.png]({url})\nhttps://example.com/article"
        final_metrics = replace(measured_call, call_id="B", model="final-model")

        async def dispatch(message, response, *, native_tool_calls=None, **kwargs):
            results = []
            if native_tool_calls:
                results = [f"Tool {tool_name}: {prefix} synthetic\nPermanent URL: {url}?ex=abc&hm=123"]
            return str(response), results, []

        bot._dispatch_tool_calls = AsyncMock(side_effect=dispatch)
        bot._generate_response = AsyncMock(side_effect=[
            ProviderResult("", tool_calls=[tool_call(tool_name, prompt="synthetic")], metrics=measured_call),
            ProviderResult(text, metrics=final_metrics),
            ProviderResult(text, metrics=measured_call),
        ])
        await MaxwellBot._handle_message(bot, message)
        assert len(message.channel.sent) == 1
        final = message.channel.sent[0]
        assert final.kwargs.get("file") is None
        assert "suppress_embeds" not in final.kwargs
        assert final.content.startswith(text)
        assert final.content.endswith(FOOTER_MARKER)
        assert bot._delivery_measurements.lookup("100", str(final.id))[1] is final_metrics
        assert bot.add_message_to_memory.call_args.args[1]["content"] == text
        assert bot._record_rem_event.call_args.args[2] == text
        following = Message()
        following.id = 8
        following.channel = message.channel
        await MaxwellBot._handle_message(bot, following)
        assert len(message.channel.sent) == 2
        assert message.channel.sent[-1].content.startswith(text)
        assert f"<{url}>" not in message.channel.sent[-1].content

    asyncio.run(scenario())


def test_foreground_image_previews_remain_enabled_across_channels(
    foreground_bot, measured_call
):
    async def scenario():
        bot, first, other = foreground_bot, Message(), Message()
        other.id, other.channel.id = 8, 200
        url = "https://cdn.discordapp.com/attachments/100/200/generated_image.png"
        ready, release = asyncio.Event(), asyncio.Event()

        async def dispatch(message, response, *, native_tool_calls=None, **kwargs):
            results = []
            if native_tool_calls:
                results = [f"Tool image_generator: Image generated, NOT sent: synthetic\nPermanent URL: {url}?ex=abc"]
                ready.set()
                await release.wait()
            return str(response), results, []

        bot._dispatch_tool_calls = AsyncMock(side_effect=dispatch)
        bot._generate_response = AsyncMock(side_effect=[
            ProviderResult("", tool_calls=[tool_call("image_generator", prompt="synthetic")]),
            ProviderResult(url, metrics=measured_call),
            ProviderResult(url, metrics=measured_call),
        ])
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(MaxwellBot._handle_message(bot, first))
            await asyncio.wait_for(ready.wait(), timeout=1)
            await MaxwellBot._handle_message(bot, other)
            release.set()
        assert other.channel.sent[-1].content.startswith(url + "\n")
        assert first.channel.sent[-1].content.startswith(url + "\n")

    asyncio.run(scenario())


def test_foreground_image_link_progress_edit_preserves_preview(
    foreground_bot, measured_call, monkeypatch
):
    import bot as bot_module

    async def scenario():
        bot, message = foreground_bot, Message()
        url = "https://cdn.discordapp.com/attachments/100/200/generated_image.png"
        edited = []

        async def transition(content, *, on_delivered):
            sent = SimpleNamespace(id=900, channel=message.channel, content=content)
            edited.append(sent)
            on_delivered(sent)
            return True

        progress = SimpleNamespace(
            start_defer=AsyncMock(), stop=AsyncMock(),
            transition_to_final=AsyncMock(side_effect=transition),
        )
        monkeypatch.setattr(bot_module, "_make_tool_progress", lambda message: progress)
        bot._progress_enabled = lambda guild: True
        bot._dispatch_tool_calls = AsyncMock(side_effect=[
            ("", [f"Tool image_generator: Image generated, NOT sent: synthetic\nPermanent URL: {url}?ex=abc"], []),
            (f"[shot]({url})", [], []),
        ])
        bot._generate_response = AsyncMock(side_effect=[
            ProviderResult("", tool_calls=[tool_call("image_generator", prompt="synthetic")]),
            ProviderResult(f"[shot]({url})", metrics=measured_call),
        ])
        await MaxwellBot._handle_message(bot, message)
        assert not message.channel.sent
        assert len(edited) == 1
        assert edited[0].content.startswith(f"[shot]({url})\n")
        assert edited[0].content.endswith(FOOTER_MARKER)
        assert bot._delivery_measurements.lookup("100", "900")[1] is measured_call

    asyncio.run(scenario())


@pytest.mark.parametrize("name,result,caption", [
    ("image_generator", "__IMAGE_SENT__ Image sent", ""),
    ("send_media", "__MEDIA_SENT__ image.png\n__CAPTION_SENT__", "My caption"),
    ("send_file", "__FILE_SENT__ image.png\n__CAPTION_SENT__", "My caption"),
])
def test_foreground_delivered_image_or_caption_has_no_second_reply(
    foreground_bot, measured_call, name, result, caption
):
    async def scenario():
        bot, message = foreground_bot, Message()

        async def dispatch(message, response, **kwargs):
            await message.channel.send(caption, file=object())
            return str(response), [f"Tool {name}: {result}"], []

        bot._dispatch_tool_calls = AsyncMock(side_effect=dispatch)
        bot._generate_response = AsyncMock(return_value=ProviderResult(
            "Redundant commentary and image URL", tool_calls=[tool_call(name, auto_send=True)], metrics=measured_call
        ))
        await MaxwellBot._handle_message(bot, message)
        assert bot._generate_response.await_count == 1
        assert len(message.channel.sent) == 1
        assert message.channel.sent[0].content == caption
        assert message.channel.sent[0].kwargs["file"] is not None

    asyncio.run(scenario())
