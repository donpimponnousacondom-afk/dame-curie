import asyncio
import copy
import json
from unittest.mock import AsyncMock

import pytest

from providers import (
    OpenAICompatibleProvider,
    ProviderEmptyResponseError,
    ProviderIncompleteResponseError,
    ProviderRequestError,
    ProviderUsageExhaustedError,
    USAGE_EXHAUSTED_MESSAGE,
    _is_content_policy_block,
    _is_policy_block_text,
)


@pytest.fixture(autouse=True)
def no_provider_retry_wait(monkeypatch):
    monkeypatch.setattr("providers.asyncio.sleep", AsyncMock())


class _FakeAsyncStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


def _sse_chunks_for(body):
    if not isinstance(body, dict):
        return []
    choices = body.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    delta = {"role": message.get("role", "assistant")}
    if "content" in message:
        delta["content"] = message.get("content") or ""
    if message.get("reasoning_content"):
        delta["reasoning_content"] = message["reasoning_content"]
    if message.get("reasoning_details"):
        delta["reasoning_details"] = message["reasoning_details"]
    if message.get("tool_calls"):
        delta["tool_calls"] = [
            {"index": i, **tc} for i, tc in enumerate(message["tool_calls"])
        ]
    frame = {"choices": [{"index": 0, "delta": delta, "finish_reason": "stop"}]}
    return [f"data: {json.dumps(frame)}\n\ndata: [DONE]\n\n".encode("utf-8")]


class FakeResponse:
    status = 200
    headers = {}

    def __init__(self):
        self.content = _FakeAsyncStream(_sse_chunks_for(self._json_body()))

    def _json_body(self):
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, *, content_type=None):
        return self._json_body()

    async def text(self):
        return ""


class FakeNoneJsonResponse(FakeResponse):
    """Returns None from json() — simulates a malformed/empty 200 response."""

    def _json_body(self):
        return None


class FakeToolCallResponse(FakeResponse):
    def _json_body(self):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"id": "1"}],
                    }
                }
            ]
        }


class FakeReasoningOnlyResponse(FakeResponse):
    def _json_body(self):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_details": [{"type": "reasoning.text", "text": "pong"}],
                    }
                }
            ]
        }


class FakeEmptyResponse(FakeResponse):
    """HTTP 200 with a valid assistant envelope but no usable output."""

    def _json_body(self):
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}


class FakeErrorResponse(FakeResponse):
    def __init__(self, status, text):
        self.status = status
        self._text = text
        self.content = _FakeAsyncStream([])

    async def text(self):
        return self._text


class FakeSession:
    def __init__(self, response=None):
        self.payloads = []
        self.urls = []
        self.closed = False
        self.response = response or FakeResponse()

    def post(self, url, json=None, timeout=None, headers=None):
        self.urls.append(url)
        self.payloads.append(copy.deepcopy(json))
        return self.response


class FakeSequenceSession(FakeSession):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)

    def post(self, url, json=None, timeout=None, headers=None):
        self.urls.append(url)
        self.payloads.append(copy.deepcopy(json))
        return self.responses.pop(0)


@pytest.mark.parametrize(
    "model",
    [
        "inclusionai/ling-3.0-flash",
        "inclusionai/ling-3.0-flash-fin:free",
        "inclusionai/ling-3.0-flash-sante:free",
        "unknown/new-model-2099",
    ],
)
@pytest.mark.parametrize("sampling", [{}, {"max_tokens": 64000, "temperature": 0.6}])
def test_openrouter_native_reasoning_and_sampling_defaults(model, sampling):
    provider = OpenAICompatibleProvider("https://openrouter.ai/api/v1", model, **sampling)
    provider.available = True
    provider._session = session = FakeSession()
    messages = [{"role": "user", "content": "hi"}]

    asyncio.run(provider.generate_chat_completion(messages))

    assert session.payloads == [{"model": model, "messages": messages, **sampling}]


@pytest.mark.parametrize("max_tokens", [None, 64000])
def test_openrouter_aux_override_does_not_mutate_main(max_tokens):
    from time import monotonic

    from turn_budget import ForegroundTurn, reset_foreground_turn, set_foreground_turn

    extra_body = {"reasoning": {"effort": "low"}, "provider": {"only": ["configured"], "allow_fallbacks": False}}
    original = copy.deepcopy(extra_body)
    provider = OpenAICompatibleProvider(
        "https://openrouter.ai/api/v1", "inclusionai/ling-3.0-flash-fin:free",
        max_tokens, 0.6, top_p=0.9, top_k=30, extra_body=extra_body,
    )
    provider.available = True
    provider._session = session = FakeSession()
    turn = ForegroundTurn(2, monotonic() + 60)
    token = set_foreground_turn(turn)

    async def run():
        messages = [{"role": "user", "content": "hi"}]
        await provider.generate_response(messages)
        await provider.generate_chat_completion(messages + [{"role": "assistant", "content": "ok"}])

    try:
        asyncio.run(run())
    finally:
        reset_foreground_turn(token)

    for payload in session.payloads:
        assert {key: value for key, value in payload.items() if key != "messages"} == {
            "model": "inclusionai/ling-3.0-flash-fin:free", "temperature": 0.6,
            "top_p": 0.9, "top_k": 30, **original,
            **({"max_tokens": 64000} if max_tokens is not None else {}),
        }
    assert turn.attempts == 2
    assert extra_body == original
    assert len(session.payloads[0]["messages"]) == 1
    assert len(session.payloads[1]["messages"]) == 2


@pytest.mark.parametrize("reasoning", [
    {}, {"reasoning": {"enabled": False}}, {"reasoning": {"effort": "low"}},
    {"reasoning_effort": "none"}, {"thinking": {"type": "disabled", "budget_tokens": 0}},
    {"max_tokens": 64000, "temperature": 0.2, "top_p": 0.8, "top_k": 0},
    {"stream_options": {"include_usage": True}, "tool_choice": "none"},
    {"reasoning": None, "vendor_options": {"thinking": {"enabled": False}}},
])
def test_openrouter_reasoning_override_restores_native_default(reasoning):
    original = copy.deepcopy(reasoning)
    provider = OpenAICompatibleProvider(
        "https://openrouter.ai/api/v1", "inclusionai/ling-3.0-flash-fin:free",
        extra_body=reasoning,
    )
    provider.available = True
    provider._session = session = FakeSession()
    messages = [{"role": "user", "content": "hi"}]

    asyncio.run(provider.generate_chat_completion(messages))

    assert session.payloads == [{"model": provider.model, "messages": messages, **original}]
    assert reasoning == original


@pytest.mark.parametrize(
    "base_url",
    ["http://localhost:11434/v1", "https://openrouter.ai.example.test/v1", "https://openrouter.ai/api/v1"],
)
def test_non_openrouter_reasoning_disable_protocol_is_preserved(base_url):
    extra_body = {"reasoning_effort": "none", "reasoning": {"effort": "none"}, "thinking": {"type": "disabled", "budget_tokens": 0}}
    original = copy.deepcopy(extra_body)
    provider = OpenAICompatibleProvider(base_url, "unknown/new-model", extra_body=extra_body)
    provider.available = True
    provider._session = session = FakeSession()

    asyncio.run(provider.generate_chat_completion([]))

    assert session.payloads == [{"model": "unknown/new-model", "messages": [], **original}]
    assert extra_body == original


@pytest.mark.parametrize("body,typed", [
    ({"temperature": 0.2}, {"temperature": 0.6}),
    ({"max_tokens": 64000}, {"max_tokens": 8192}),
    ({"top_p": 0.8}, {"top_p": 0.9}),
    ({"top_k": 20}, {"top_k": 30}),
    ({"model": "other-model"}, {}),
])
def test_reasoning_protocol_uses_selected_endpoint(body, typed):
    original = copy.deepcopy(body)
    with pytest.raises(ValueError, match="OPENAI_EXTRA_BODY conflicts with configured"):
        OpenAICompatibleProvider("http://localhost:11434/v1", "local-model", extra_body=body, **typed)
    assert body == original


def test_generate_chat_completion_model_override():
    provider = OpenAICompatibleProvider("http://example.test", "base-model", 10, 0.5)
    provider.available = True
    session = FakeSession()
    provider._session = session

    async def run():
        message = await provider.generate_chat_completion(
            [{"role": "user", "content": "hi"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "ltm_list",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
        assert message["content"] == "ok"

    asyncio.run(run())
    assert session.payloads[0]["model"] == "base-model"
    assert "tool_choice" not in session.payloads[0]
    assert "stream" not in session.payloads[0]
    assert "stream_options" not in session.payloads[0]
    assert (
        session.payloads[0]["max_tokens"] == 10
    )  # configured max_tokens always included
    assert session.payloads[0]["tools"][0]["function"]["name"] == "ltm_list"


def test_generate_chat_completion_usage_exhausted_error():
    provider = OpenAICompatibleProvider("http://example.test", "base-model", 10, 0.5)
    provider.available = True
    session = FakeSession(
        FakeErrorResponse(
            429,
            '{"error":{"code":"model_cooldown","message":"All credentials are cooling down"}}',
        )
    )
    provider._session = session

    async def run():
        with pytest.raises(ProviderUsageExhaustedError) as exc_info:
            await provider.generate_chat_completion([{"role": "user", "content": "hi"}])
        assert exc_info.value.user_message == USAGE_EXHAUSTED_MESSAGE

    asyncio.run(run())
    assert len(session.payloads) == 1


@pytest.mark.parametrize("streaming", [{}, {"stream": False}, {"stream": True, "stream_options": {"include_usage": False}}])
def test_generate_chat_completion_falls_back_to_secondary_provider(streaming):
    extra_body = {
        "reasoning": {"effort": "low"}, "provider": {"only": ["configured"], "allow_fallbacks": False},
        "tool_choice": "required", **streaming,
    }
    original = copy.deepcopy(extra_body)
    provider = OpenAICompatibleProvider(
        "http://primary.test/v1", "unknown/new-model", 64000, 0.5,
        top_p=0.9, top_k=20, extra_body=extra_body,
    )
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(503, "down"), FakeErrorResponse(503, "down"), FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
    options = copy.deepcopy((messages, tools))

    message = asyncio.run(provider.generate_chat_completion(messages, tools=tools))

    assert message["content"] == "ok"
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 3
    assert session.payloads == [{
        "model": "unknown/new-model", "messages": messages, "tools": tools,
        "max_tokens": 64000, "temperature": 0.5, "top_p": 0.9, "top_k": 20, **original,
    }] * 3
    assert extra_body == original
    assert (messages, tools) == options


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_generate_chat_completion_retries_primary_before_fallback(status):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSequenceSession([FakeErrorResponse(status, "down"), FakeResponse()])
    messages = [{"role": "user", "content": "hi"}]

    message = asyncio.run(provider.generate_chat_completion(messages))

    assert message["content"] == "ok"
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 2
    assert session.payloads == [{"model": "primary-model", "messages": messages}] * 2


@pytest.mark.parametrize("streaming", [{}, {"stream": False}, {"stream": True}])
@pytest.mark.parametrize("attempts,empty_retries,empty_count,count,succeeds", [
    (2, 1, 1, 2, True), (1, 1, 1, 1, False), (5, 0, 1, 1, False),
    (5, 1, 2, 2, False), (3, 2, 2, 3, True),
])
def test_empty_200_gets_non_streaming_recovery_within_total_budget(streaming, attempts, empty_retries, empty_count, count, succeeds):
    provider = OpenAICompatibleProvider(
        "http://primary.test/v1", "primary-model", 64000,
        retry_attempts=attempts, empty_response_retries=empty_retries, extra_body=streaming,
    )
    provider.available = True
    provider._session = session = FakeSequenceSession([FakeEmptyResponse() for _ in range(empty_count)] + [FakeResponse()])
    messages = [{"role": "user", "content": "hi"}]

    if succeeds:
        message = asyncio.run(provider.generate_chat_completion(messages))
        assert message["content"] == "ok"
    else:
        with pytest.raises(ProviderEmptyResponseError):
            asyncio.run(provider.generate_chat_completion(messages))

    assert session.urls == ["http://primary.test/v1/chat/completions"] * count
    assert session.payloads == [{"model": "primary-model", "messages": messages, "max_tokens": 64000, **streaming}] * count


@pytest.mark.parametrize("method", ["generate_response", "generate_chat_completion"])
@pytest.mark.parametrize("override", [
    {"model": "other"}, {"max_tokens": 1}, {"temperature": 0.2},
    {"disable_reasoning": True}, {"fast_fallback": True}, {"prefer_fallback": True},
])
def test_prefer_fallback_routes_first_request_to_fallback(method, override):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSession()

    with pytest.raises(TypeError):
        asyncio.run(getattr(provider, method)([{"role": "user", "content": "hi"}], **override))

    assert session.urls == []
    assert session.payloads == []


def test_prefer_fallback_fails_over_to_primary():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(404, '{"error":{"message":"configured endpoint unavailable"}}'), FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    with pytest.raises(ProviderRequestError, match="configured endpoint unavailable"):
        asyncio.run(provider.generate_chat_completion(messages))

    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads == [{"model": "primary-model", "messages": messages}]
    assert len(session.responses) == 1


def test_429_rate_limit_skips_to_fallback_without_doomed_retry():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(429, '{"error":{"code":429,"message":"xiaomi/mimo-v2.5 is temporarily rate-limited upstream. Please retry shortly"}}'),
        FakeResponse(), FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    async def run():
        assert (await provider.generate_chat_completion(messages))["content"] == "ok"
        assert (await provider.generate_chat_completion(messages))["content"] == "ok"

    asyncio.run(run())
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 3
    assert session.payloads == [{"model": "primary-model", "messages": messages, "max_tokens": 10, "temperature": 0.5}] * 3


def test_append_tool_call_arguments_accepts_dict():
    """GLM-style providers send arguments as an object, not a JSON string."""
    from providers import _append_tool_call_arguments, _extract_partial_reasoning

    slot = {"function": {"name": "send_message", "arguments": ""}}
    _append_tool_call_arguments(
        slot,
        {"reasoning": "replying", "content": "hello"},
    )
    args = slot["function"]["arguments"]
    assert isinstance(args, str)
    parsed = json.loads(args)
    assert parsed["content"] == "hello"
    assert _extract_partial_reasoning(args) == "replying"
    assert _extract_partial_reasoning(parsed) == "replying"


def test_append_tool_call_arguments_concatenates_strings():
    from providers import _append_tool_call_arguments

    slot = {"function": {"name": "send_message", "arguments": ""}}
    _append_tool_call_arguments(slot, '{"reasoning": "')
    _append_tool_call_arguments(slot, 'hi", "content": "yo"}')
    assert slot["function"]["arguments"] == '{"reasoning": "hi", "content": "yo"}'


def test_read_sse_native_tool_call_with_object_arguments():
    """A single SSE delta with arguments as a dict must not TypeError."""
    from providers import _read_sse_response

    frame = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "send_message",
                                "arguments": {
                                    "reasoning": "answering",
                                    "content": "hi",
                                },
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    class Resp:
        content = _FakeAsyncStream(
            [f"data: {json.dumps(frame)}\n\ndata: [DONE]\n\n".encode("utf-8")]
        )

    async def run():
        return await _read_sse_response(Resp())

    merged = asyncio.run(run())
    calls = merged["choices"][0]["message"]["tool_calls"]
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "send_message"
    parsed = json.loads(calls[0]["function"]["arguments"])
    assert parsed["content"] == "hi"


@pytest.mark.parametrize("streaming", [{}, {"stream": True}])
def test_generate_response_returns_native_tool_calls(streaming):
    """generate_response now supports native tool_calls instead of rejecting them."""
    provider = OpenAICompatibleProvider("http://example.test", "base-model", 10, 0.5, extra_body=streaming)
    provider.available = True
    provider._session = FakeSession(FakeToolCallResponse())

    async def run():
        content = await provider.generate_response([{"role": "user", "content": "hi"}])
        # Content may be empty when the model only emits tool_calls
        assert content == ""
        assert len(provider._last_tool_calls) == 1
        assert provider._last_tool_calls[0]["id"] == "1"
        assert content.tool_calls == provider._last_tool_calls

    asyncio.run(run())


def test_context_overflow_clamp_survives_retry():
    provider = OpenAICompatibleProvider("http://example.test", "base-model", 64000, 0.5, retry_attempts=2)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, "maximum context length is 10000 tokens. you requested about 65000 tokens"),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    async def run():
        with pytest.raises(ProviderRequestError, match="maximum context length is 10000"):
            await provider.generate_chat_completion(messages)
        assert len(session.payloads) == 1
        assert (await provider.generate_chat_completion(messages))["content"] == "ok"

    asyncio.run(run())
    assert session.payloads == [{"model": "base-model", "messages": messages, "max_tokens": 64000, "temperature": 0.5}] * 2


def test_none_json_body_retries_and_falls_back():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSequenceSession([FakeNoneJsonResponse(), FakeNoneJsonResponse(), FakeResponse()])
    messages = [{"role": "user", "content": "hi"}]

    message = asyncio.run(provider.generate_chat_completion(messages))

    assert message["content"] == "ok"
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 3
    assert session.payloads == [{"model": "primary-model", "messages": messages}] * 3


def test_degraded_endpoint_skips_to_fallback_without_retry():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, '{"status":400,"title":"Bad Request","detail":"Function id abc: DEGRADED function cannot be invoked"}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    async def run():
        with pytest.raises(ProviderRequestError, match="DEGRADED function cannot be invoked"):
            await provider.generate_chat_completion(messages)
        assert len(session.payloads) == 1
        assert (await provider.generate_chat_completion(messages))["content"] == "ok"

    asyncio.run(run())
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 2
    assert session.payloads == [{"model": "primary-model", "messages": messages}] * 2


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "mimo-v2.5", "unknown/new-model"])
def test_vision_model_used_for_images(model):
    provider = OpenAICompatibleProvider("http://primary.test/v1", model, 10, 0.5, api_key="pk")
    provider.available = True
    provider._session = session = FakeSession()
    messages = [{"role": "user", "content": "look"}]
    media = [{"b64": "abc", "mime_type": "image/png"}]
    original = copy.deepcopy((messages, media))

    message = asyncio.run(provider.generate_chat_completion(messages, media=media))

    assert message["content"] == "ok"
    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads == [{
        "model": model, "max_tokens": 10, "temperature": 0.5,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]}],
    }]
    assert (messages, media) == original


@pytest.mark.parametrize("reasoning", [{}, {"reasoning_effort": "none"}, {"thinking": {"type": "enabled"}}])
def test_kimi_k27_vision_enables_thinking(reasoning):
    original = copy.deepcopy(reasoning)
    provider = OpenAICompatibleProvider("http://primary.test/v1", "kimi-k2.7-code", extra_body=reasoning)
    provider.available = True
    provider._session = session = FakeSession()

    message = asyncio.run(provider.generate_chat_completion(
        [{"role": "user", "content": "look"}], media=[{"b64": "abc", "mime_type": "image/png"}],
    ))

    assert message["content"] == "ok"
    assert {key: value for key, value in session.payloads[0].items() if key != "messages"} == {"model": "kimi-k2.7-code", **original}
    assert reasoning == original


def test_vision_model_not_used_for_text():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "deepseek-v4-flash", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSession()
    messages = [{"role": "user", "content": "hi"}]

    message = asyncio.run(provider.generate_chat_completion(messages))

    assert message["content"] == "ok"
    assert session.payloads == [{"model": "deepseek-v4-flash", "messages": messages, "max_tokens": 10, "temperature": 0.5}]


def test_image_unsupported_skips_text_only_primary():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "deepseek-v4-flash", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, '{"error":{"message":"unknown variant `image_url`, expected `text`"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "look"}]
    media = [{"b64": "abc", "mime_type": "image/png"}]
    original = copy.deepcopy((messages, media))

    with pytest.raises(ProviderRequestError, match="unknown variant `image_url`"):
        asyncio.run(provider.generate_chat_completion(messages, media=media))

    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads[0]["model"] == "deepseek-v4-flash"
    assert session.payloads[0]["messages"][0]["content"][-1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}
    assert (messages, media) == original
    assert len(session.responses) == 1


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "deepseek/deepseek-v4.1-flash:nitro", "grok-4.6", "unknown/new-model"])
@pytest.mark.parametrize("streaming", [{}, {"stream": True}])
def test_reasoning_only_response_is_terminal(model, streaming):
    provider = OpenAICompatibleProvider(
        "http://primary.test/v1", model, 10, 0.5,
        retry_attempts=5, empty_response_retries=3, extra_body=streaming,
    )
    provider.available = True
    session = FakeSequenceSession([FakeReasoningOnlyResponse(), FakeResponse()])
    provider._session = session

    with pytest.raises(ProviderIncompleteResponseError):
        asyncio.run(provider.generate_chat_completion([{"role": "user", "content": "hi"}]))

    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert len(session.payloads) == len(session.responses) == 1


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "grok-4.6"])
@pytest.mark.parametrize("answer", [
    {"content": "answer"},
    {"content": None, "tool_calls": [{
        "id": "call_1", "type": "function",
        "function": {"name": "lookup", "arguments": '{"query":"synthetic"}'},
    }]},
])
def test_reasoning_with_answer_or_native_tool_calls_is_preserved(model, answer):
    provider = OpenAICompatibleProvider("http://example.test", model, 10, 0.5, extra_body={"stream": True})
    provider.available = True
    response = FakeReasoningOnlyResponse()
    response.content = _FakeAsyncStream(_sse_chunks_for({"choices": [{"message": {
        "role": "assistant", "reasoning_content": "private scratchpad", **answer,
    }}]}))
    session = FakeSession(response)
    provider._session = session

    message = asyncio.run(provider.generate_chat_completion([{"role": "user", "content": "hi"}]))

    assert (message.get("content") or "") == (answer.get("content") or "")
    assert message.get("tool_calls") == answer.get("tool_calls")
    assert message["reasoning_content"] == "private scratchpad"
    assert len(session.payloads) == 1


def test_403_region_error_skips_to_fallback_without_retry():
    extra_body = {"provider": {"only": ["configured"], "allow_fallbacks": False}}
    original = copy.deepcopy(extra_body)
    provider = OpenAICompatibleProvider("http://primary.test/v1", "deepseek-v4-flash", extra_body=extra_body)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(403, '{"type":"error","error":{"type":"RegionError","message":"China opt in"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    with pytest.raises(ProviderRequestError, match="China opt in"):
        asyncio.run(provider.generate_chat_completion(messages))

    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads == [{"model": "deepseek-v4-flash", "messages": messages, **original}]
    assert extra_body == original
    assert len(session.responses) == 1


def test_video_parts_are_not_attached():
    provider = OpenAICompatibleProvider(
        "http://primary.test/v1",
        "deepseek-v4-flash",
        10,
        0.5,
    )
    provider.available = True
    session = FakeSession()
    provider._session = session

    async def run():
        message = await provider.generate_chat_completion(
            [{"role": "user", "content": "look"}],
            media=[
                {"b64": "vid", "mime_type": "video/mp4"},
                {"b64": "img", "mime_type": "image/png"},
            ],
        )
        assert message["content"] == "ok"

    asyncio.run(run())
    content = session.payloads[0]["messages"][0]["content"]
    types = [p.get("type") for p in content if isinstance(p, dict)]
    assert "image_url" in types
    assert "video_url" in types
    assert session.payloads[0]["model"] == "deepseek-v4-flash"
    assert {"type": "video_url", "video_url": {"url": "data:video/mp4;base64,vid"}} in content


def test_openrouter_image_unsupported_routes_to_another_endpoint():
    extra_body = {"provider": {"only": ["configured"], "allow_fallbacks": False}}
    original = copy.deepcopy(extra_body)
    provider = OpenAICompatibleProvider("https://openrouter.ai/api/v1", "text-only-model", extra_body=extra_body)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(404, '{"error":{"message":"No endpoints found that support image input","code":404}}'),
        FakeResponse(),
    ])

    with pytest.raises(ProviderRequestError, match="No endpoints found that support image input"):
        asyncio.run(provider.generate_chat_completion(
            [{"role": "user", "content": "look"}], media=[{"b64": "img", "mime_type": "image/png"}],
        ))

    assert session.urls == ["https://openrouter.ai/api/v1/chat/completions"]
    assert session.payloads[0]["provider"] == original["provider"]
    assert session.payloads[0]["messages"][0]["content"][-1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,img"}}
    assert extra_body == original
    assert len(session.responses) == 1


@pytest.mark.parametrize("mime,part", [("image/png", "image_url"), ("video/mp4", "video_url"), ("audio/mpeg", "input_audio")])
def test_media_unsupported_everywhere_falls_back_to_text_only(mime, part):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "text-only-model", enable_audio_input=True)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(404, '{"error":{"message":"No endpoints found that support this media"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "what is this"}]
    media = [{"b64": "img", "mime_type": mime}]
    original = copy.deepcopy((messages, media))

    with pytest.raises(ProviderRequestError, match="No endpoints found that support this media"):
        asyncio.run(provider.generate_chat_completion(messages, media=media))

    assert len(session.payloads) == 1
    assert session.payloads[0]["messages"][0]["content"][0] == {"type": "text", "text": "what is this"}
    assert session.payloads[0]["messages"][0]["content"][1]["type"] == part
    assert (messages, media) == original
    assert len(session.responses) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 415, 422, 451])
def test_unhandled_4xx_fails_over_instead_of_raising(status):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "dead-slug", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(status, '{"error":{"message":"This model is unavailable for free."}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    with pytest.raises(ProviderRequestError, match=f"Provider API error: {status}:.*This model is unavailable for free"):
        asyncio.run(provider.generate_chat_completion(messages))

    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads == [{"model": "dead-slug", "messages": messages, "max_tokens": 10, "temperature": 0.5}]
    assert len(session.responses) == 1


def test_unhandled_4xx_single_endpoint_still_raises():
    """With nowhere to fail over to, the error must surface."""
    provider = OpenAICompatibleProvider("http://primary.test/v1", "dead-slug", 10, 0.5)
    provider.available = True
    session = FakeSession(FakeErrorResponse(404, '{"error":{"message":"gone"}}'))
    provider._session = session

    async def run():
        with pytest.raises(RuntimeError, match="Provider API error: 404"):
            await provider.generate_chat_completion([{"role": "user", "content": "hi"}])

    asyncio.run(run())
    assert len(session.payloads) == 1


@pytest.mark.parametrize("sampling", [{}, {"temperature": 0.9}])
def test_temperature_constraint_is_learned_and_resent(sampling):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "picky-model", **sampling)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, '{"error":{"message":"invalid temperature: only 0.6 is allowed for this model"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "hi"}]

    async def run():
        with pytest.raises(ProviderRequestError, match="only 0.6 is allowed"):
            await provider.generate_chat_completion(messages)
        assert len(session.payloads) == 1
        assert (await provider.generate_chat_completion(messages))["content"] == "ok"

    asyncio.run(run())
    assert session.payloads == [{"model": "picky-model", "messages": messages, **sampling}] * 2


def test_media_incapable_endpoint_is_remembered_across_calls():
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model")
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(404, '{"error":{"message":"No endpoints found that support image input"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "look"}]
    media = [{"b64": "img", "mime_type": "image/png"}]
    original = copy.deepcopy((messages, media))

    async def run():
        with pytest.raises(ProviderRequestError, match="support image input"):
            await provider.generate_chat_completion(messages, media=media)
        assert len(session.payloads) == 1
        assert (await provider.generate_chat_completion(messages, media=media))["content"] == "ok"

    asyncio.run(run())
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 2
    assert session.payloads[0] == session.payloads[1]
    assert session.payloads[1]["messages"][0]["content"][-1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,img"}}
    assert (messages, media) == original


@pytest.mark.parametrize("body", [
    {"tool_choice": "required"}, {"stream": True, "stream_options": {"include_usage": False}},
    {"reasoning": {"effort": "low"}}, {"provider": {"only": ["configured"], "allow_fallbacks": False}},
])
def test_media_incapable_is_learned_from_a_404(body):
    original = copy.deepcopy(body)
    provider = OpenAICompatibleProvider("http://primary.test/v1", "unknown/new-model", extra_body=body)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, '{"error":{"message":"Unsupported configured request parameter"}}'),
        FakeResponse(),
    ])
    messages = [{"role": "user", "content": "look"}]
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]

    async def run():
        with pytest.raises(ProviderRequestError, match="Unsupported configured request parameter"):
            await provider.generate_chat_completion(messages, tools=tools)
        assert len(session.payloads) == 1
        assert (await provider.generate_chat_completion(messages, tools=tools))["content"] == "ok"

    asyncio.run(run())
    assert session.urls == ["http://primary.test/v1/chat/completions"] * 2
    assert session.payloads == [{"model": "unknown/new-model", "messages": messages, "tools": tools, **original}] * 2
    assert body == original


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_failover_respects_total_attempt_budget(attempts):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model", retry_attempts=attempts)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(503, "temporarily unavailable") for _ in range(attempts)
    ] + [FakeResponse()])
    messages = [{"role": "user", "content": "hi"}]

    with pytest.raises(RuntimeError, match="Provider API error: 503:.*temporarily unavailable"):
        asyncio.run(provider.generate_chat_completion(messages))

    assert session.urls == ["http://primary.test/v1/chat/completions"] * attempts
    assert session.payloads == [{"model": "primary-model", "messages": messages}] * attempts
    assert len(session.responses) == 1


@pytest.mark.parametrize("attempts", [1, 2])
def test_media_strip_retry_respects_total_attempt_budget(attempts):
    provider = OpenAICompatibleProvider("http://primary.test/v1", "primary-model", retry_attempts=attempts)
    provider.available = True
    provider._session = session = FakeSequenceSession([
        FakeErrorResponse(400, '{"error":{"message":"unknown variant `image_url`, expected `text`"}}'),
        FakeResponse(),
    ])

    with pytest.raises(ProviderRequestError, match="Provider API error: 400"):
        asyncio.run(provider.generate_chat_completion(
            [{"role": "user", "content": "what is this"}], media=[{"b64": "img", "mime_type": "image/png"}],
        ))

    assert len(session.payloads) == 1
    assert session.payloads[0]["messages"][0]["content"] == [
        {"type": "text", "text": "what is this"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,img"}},
    ]
    assert len(session.responses) == 1


def test_retry_loop_cannot_spin_forever_on_endless_deterministic_400s():
    """The while loop must still terminate when every reply is a fresh 400."""
    provider = OpenAICompatibleProvider(
        "http://primary.test/v1",
        "primary-model",
        10,
        0.5,
        retry_attempts=3,
    )
    provider.available = True

    class EndlessErrorSession(FakeSession):
        def post(self, url, json=None, timeout=None, headers=None):
            self.urls.append(url)
            self.payloads.append(copy.deepcopy(json))
            return FakeErrorResponse(400, '{"error":{"message":"nope"}}')

    session = EndlessErrorSession()
    provider._session = session

    async def run():
        with pytest.raises(RuntimeError):
            await provider.generate_chat_completion([{"role": "user", "content": "hi"}])

    asyncio.run(run())
    assert session.urls == ["http://primary.test/v1/chat/completions"]
    assert session.payloads == [{"model": "primary-model", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10, "temperature": 0.5}]


GEMINI_PROMPT_BLOCK = (
    "The prompt could not be submitted. The prompt contains sensitive words that "
    "violate Google's (https://policies.google.com/terms/generative-ai/use-policy). "
    "Try rephrasing the prompt. If you think this was an error, "
    "(https://ai.google.dev/gemini-api/docs/troubleshooting)."
)


def test_policy_block_text_detected_and_normal_replies_are_not():
    """Gemini hands the prompt block back as a 200 body; Maxwell relayed it."""
    assert _is_policy_block_text(GEMINI_PROMPT_BLOCK)
    assert _is_policy_block_text("the prompt could not be submitted")
    # Ordinary replies, including plain model refusals, must not trip it.
    assert not _is_policy_block_text("yo whats good")
    assert not _is_policy_block_text("I cannot fulfill this request.")
    assert not _is_policy_block_text("")


def test_content_policy_http_error_detected_without_false_positives():
    assert _is_content_policy_block(400, GEMINI_PROMPT_BLOCK)
    assert _is_content_policy_block(400, '{"blockReason":"PROHIBITED_CONTENT"}')
    # Adjacent 400s that have their own handlers must not be swallowed here.
    assert not _is_content_policy_block(400, "maximum context length is 8192 tokens")
    assert not _is_content_policy_block(400, "DEGRADED function cannot be invoked")
    assert not _is_content_policy_block(400, "unknown variant `image_url`")
    assert not _is_content_policy_block(429, GEMINI_PROMPT_BLOCK)


def test_policy_block_fails_over_once_and_never_returns_the_notice():
    provider = OpenAICompatibleProvider(
        base_url="http://primary.test",
        model="gemini-3.7-flash-low",
        max_tokens=256,
        temperature=0.7,
        retry_attempts=3,
    )
    provider.available = True

    calls = []

    class _BlockedResponse(FakeResponse):
        def _json_body(self):
            return {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": GEMINI_PROMPT_BLOCK,
                        },
                        "finish_reason": "stop",
                    }
                ]
            }

    class _AnswerResponse(FakeResponse):
        def _json_body(self):
            return {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "real answer"},
                        "finish_reason": "stop",
                    }
                ]
            }

    class PolicyBlockSession(FakeSession):
        def post(self, url, json=None, timeout=None, headers=None):
            calls.append(url)
            self.urls.append(url)
            self.payloads.append(copy.deepcopy(json))
            return _BlockedResponse() if "primary.test" in url else _AnswerResponse()

    provider._session = PolicyBlockSession()

    async def run():
        return await provider.generate_chat_completion(
            [{"role": "user", "content": "something spicy"}]
        )

    with pytest.raises(ProviderRequestError, match="Prompt was blocked by the provider's content policy"):
        asyncio.run(run())

    assert calls == ["http://primary.test/chat/completions"]
    assert provider._session.payloads == [{
        "model": "gemini-3.7-flash-low", "max_tokens": 256, "temperature": 0.7,
        "messages": [{"role": "user", "content": "something spicy"}],
    }]


def test_audio_attaches_as_input_audio_when_enabled():
    provider = OpenAICompatibleProvider(
        "http://example.test", "omni-model", 10, 0.5, enable_audio_input=True
    )
    provider.available = True
    session = FakeSession()
    provider._session = session

    async def run():
        await provider.generate_chat_completion(
            [{"role": "user", "content": "[User attached media]"}],
            media=[{"b64": "AAA", "mime_type": "audio/mpeg"}],
        )

    asyncio.run(run())
    parts = session.payloads[0]["messages"][0]["content"]
    audio = [p for p in parts if isinstance(p, dict) and p.get("type") == "input_audio"]
    assert audio == [
        {"type": "input_audio", "input_audio": {"data": "AAA", "format": "mp3"}}
    ]


def test_audio_is_not_attached_when_disabled():
    provider = OpenAICompatibleProvider(
        "http://example.test", "text-model", 10, 0.5, enable_audio_input=False
    )
    provider.available = True
    session = FakeSession()
    provider._session = session

    async def run():
        await provider.generate_chat_completion(
            [{"role": "user", "content": "listen to this"}],
            media=[{"b64": "AAA", "mime_type": "audio/mpeg"}],
        )

    asyncio.run(run())
    content = session.payloads[0]["messages"][0]["content"]
    assert content == "listen to this"


@pytest.mark.parametrize("ingress", ["legacy", "media", "history"])
def test_svg_is_rasterized_at_provider_boundary_without_mutating_input(monkeypatch, ingress):
    import base64
    from types import SimpleNamespace

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    png = b"\x89PNG\r\n\x1a\nrendered"
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(png, None)))
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", AsyncMock(return_value=process))
    encoded = base64.b64encode(svg).decode()
    messages = [{"role": "user", "content": "inspect"}]
    options = {}
    if ingress == "legacy":
        options["images"] = [encoded]
    elif ingress == "media":
        options["media"] = [{"b64": encoded, "mime_type": "image/svg+xml"}]
    else:
        messages[0]["content"] = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded, "detail": "low"}}]
    original = copy.deepcopy((messages, options))
    provider = OpenAICompatibleProvider("http://example.test", "vision-model", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSession()
    asyncio.run(provider.generate_chat_completion(messages, **options))
    images = [part for part in session.payloads[0]["messages"][0]["content"] if part["type"] == "image_url"]
    assert len(images) == 1
    assert images[0]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(png).decode()
    assert (messages, options) == original


@pytest.mark.parametrize("blob,mime", [(b"\xff\xd8\xfftest", "image/jpeg"), (b"GIF89atest", "image/gif"), (b"RIFF1234WEBPtest", "image/webp")])
def test_legacy_images_keep_actual_raster_mime(blob, mime):
    import base64

    provider = OpenAICompatibleProvider("http://example.test", "vision-model", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSession()
    encoded = base64.b64encode(blob).decode()
    asyncio.run(provider.generate_chat_completion([{"role": "user", "content": "inspect"}], images=[encoded]))
    image = session.payloads[0]["messages"][0]["content"][-1]["image_url"]
    assert image["url"] == f"data:{mime};base64,{encoded}"


def test_invalid_svg_is_explicit_text_and_existing_image_parts_survive():
    import base64

    provider = OpenAICompatibleProvider("http://example.test", "vision-model", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSession()
    existing = {"type": "image_url", "image_url": {"url": "https://example.test/original.png"}}
    messages = [{"role": "user", "content": [{"type": "text", "text": "inspect"}, existing]}]
    asyncio.run(provider.generate_chat_completion(messages, images=[base64.b64encode(b"<svg>").decode()]))
    parts = session.payloads[0]["messages"][0]["content"]
    assert existing in parts
    assert parts[-1]["type"] == "text" and parts[-1]["text"].startswith("Error:")
    assert len([part for part in parts if part["type"] == "image_url"]) == 1


@pytest.mark.parametrize("blob,expected", [(b"<svg>", False), (b"\x89PNG\r\n\x1a\nexisting", True)])
def test_media_routing_uses_normalized_history_parts(blob, expected):
    import base64

    provider = OpenAICompatibleProvider("http://example.test", "vision-model", 10, 0.5)
    provider.available = True
    provider._session = session = FakeSession()
    messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(blob).decode()}}]}]
    original = copy.deepcopy(messages)

    asyncio.run(provider.generate_chat_completion(messages))

    part = session.payloads[0]["messages"][0]["content"][0]
    if expected:
        assert part == original[0]["content"][0]
    else:
        assert part["type"] == "text"
        assert part["text"].startswith("Error: image could not be attached")
    assert session.urls == ["http://example.test/chat/completions"]
    assert session.payloads[0]["model"] == "vision-model"
    assert messages == original
