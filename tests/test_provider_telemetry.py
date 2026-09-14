import asyncio
import json
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock

import pytest

from provider_telemetry import (
    CallMetrics,
    ChatCompletionMessage,
    OutputObservation,
    build_call_metrics,
    count_tokens,
    local_encoding,
    reported_count,
    reported_usage,
    request_text,
    token_count,
)
from providers import OllamaProvider, ProviderRequestError, ProviderResult
from test_provider_resilience import DONE, StreamResponse
from test_providers import (
    FakeEmptyResponse,
    FakeErrorResponse,
    FakeSequenceSession,
    FakeSession,
)


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("providers.asyncio.sleep", sleep)
    return sleep


def json_response(message=None, **fields):
    body = {"choices": [{"message": message or {"content": "hello"}}], **fields}
    return StreamResponse([json.dumps(body).encode()], "application/json")


def sse_frame(delta=None, **fields):
    body = {"choices": [{"delta": delta}]} if delta is not None else {}
    return b"data: " + json.dumps({**body, **fields}).encode() + b"\n\n"


def provider_for(responses, **kwargs):
    provider = OllamaProvider(
        "https://user:synthetic@example.test/v1?secret=synthetic",
        "model",
        8192,
        0.6,
        **kwargs,
    )
    provider.available = True
    provider._session = FakeSequenceSession(responses)
    return provider


def metrics_for(response, message=None, stream=True):
    observation = OutputObservation()
    observation.observe(message or {"content": "héllo 世界"}, 11.0)
    observation.finished_s = 14.0
    return build_call_metrics(
        response,
        {"messages": [{"role": "user", "content": "hello"}]},
        observation,
        provider="example.test",
        endpoint="primary",
        model="model",
        request_start=10.0,
        stream=stream,
        attempt=1,
    )


def test_tokenizer_is_cached_offline_and_matches_official_definition(monkeypatch):
    import requests
    import tiktoken
    from tiktoken_ext import openai_public

    def network_forbidden(*args, **kwargs):
        pytest.fail("tokenizer attempted network/registry lookup")

    monkeypatch.setattr(requests, "get", network_forbidden)
    monkeypatch.setattr(tiktoken, "get_encoding", network_forbidden)
    local_encoding.cache_clear()
    encoding = local_encoding()
    assert encoding is local_encoding()
    assert encoding.encode("hello world") == [15339, 1917]
    monkeypatch.setattr(
        openai_public,
        "load_tiktoken_bpe",
        lambda *args, **kwargs: encoding._mergeable_ranks,
    )
    definition = openai_public.cl100k_base()
    assert encoding._pat_str == definition["pat_str"]
    assert encoding._special_tokens == definition["special_tokens"]
    assert count_tokens("<|endoftext|>") > 1


def test_tokenizer_verifies_hash_even_when_disk_cache_disabled(monkeypatch):
    from pathlib import Path

    local_encoding.cache_clear()
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", "")
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"corrupt synthetic asset")
    with pytest.raises(ValueError, match="hash mismatch"):
        local_encoding()
    local_encoding.cache_clear()


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        -1,
        -0.5,
        1.5,
        float("nan"),
        float("inf"),
        float("-inf"),
        "1.0000000000000000001",
        "nan",
        "Infinity",
        "1e999999999",
        "1e9999999999999999999999999999",
        2**53,
        10**400,
        [],
        {},
    ],
)
def test_malformed_token_counts_are_unknown(value):
    assert token_count(value) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0),
        (12, 12),
        (12.0, 12),
        ("1200", 1200),
        ("1200.0", 1200),
        ("1.2e3", 1200),
        (" 12 ", 12),
    ],
)
def test_finite_integer_counts(value, expected):
    assert token_count(value) == expected


@pytest.mark.parametrize(
    "usage, expected",
    [
        (
            {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "completion_tokens_details": {"reasoning_tokens": 7},
                }
            },
            (10, 20, 7),
        ),
        (
            {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "output_tokens_details": {"reasoning_tokens": 7},
                }
            },
            (10, 20, 7),
        ),
        (
            {
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 13,
                    "thoughtsTokenCount": 7,
                }
            },
            (10, 20, 7),
        ),
        (
            {
                "usage": {"completion_tokens": 20},
                "usageMetadata": {"candidatesTokenCount": 13, "thoughtsTokenCount": 7},
            },
            (None, 20, 7),
        ),
        ({"usage": {"completion_tokens": 0, "output_tokens": 99}}, (None, 99, None)),
        (
            {
                "usage": {
                    "completion_tokens": float("nan"),
                    "output_tokens": 20,
                    "completion_tokens_details": [],
                }
            },
            (None, 20, None),
        ),
        (
            {"usage": {"completion_tokens_details": {"reasoning_tokens": 7}}},
            (None, None, 7),
        ),
        ({"usage": None}, (None, None, None)),
    ],
)
def test_reported_usage_aliases_and_reasoning_totals(usage, expected):
    assert reported_usage(usage) == expected


@pytest.mark.parametrize("stream", [False, True])
def test_whole_window_tps_and_provenance(stream):
    metrics = metrics_for(
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 7},
            }
        },
        stream=stream,
    )
    assert isinstance(metrics, CallMetrics)
    assert metrics.output_tokens == 20
    assert metrics.reasoning_tokens == 7
    assert metrics.tps == 5
    assert metrics.elapsed_ms == 4000
    assert metrics.ttft_ms == (1000 if stream else 4000)
    assert metrics.ttft_estimated is (not stream)
    assert metrics.input_source == metrics.output_source == "provider"
    assert not metrics.estimated
    assert metrics.output_bytes == len("héllo 世界".encode())
    with pytest.raises(FrozenInstanceError):
        metrics.model = "changed"
    assert not hasattr(metrics, "__dict__")


def test_reasoning_only_usage_estimates_visible_not_observed_reasoning_twice():
    metrics = metrics_for(
        {"usage": {"completion_tokens_details": {"reasoning_tokens": 7}}},
        {"content": "answer", "reasoning_content": "observed thought"},
    )
    assert metrics.output_tokens == count_tokens("answer") + 7
    assert metrics.output_source == "mixed"
    assert metrics.estimated
    assert metrics.input_source == "cl100k_base"


def test_missing_usage_never_invents_hidden_reasoning():
    metrics = metrics_for({})
    assert metrics.reasoning_tokens is None
    assert metrics.output_tokens == count_tokens("héllo 世界")
    assert metrics.output_source == "cl100k_base"


@pytest.mark.parametrize(
    "message",
    [
        {"role": "assistant"},
        {"content": "", "reasoning": None},
        {"tool_calls": [{"id": "abc", "type": "function", "function": {}}]},
        {
            "reasoning_details": [
                {"type": "reasoning.encrypted", "data": "opaque", "signature": "opaque"}
            ]
        },
        {
            "reasoning_details": [
                {"type": "reasoning.text", "id": "abc", "signature": "opaque"}
            ]
        },
    ],
)
def test_metadata_never_starts_ttft(message):
    observation = OutputObservation()
    observation.observe(message, 12)
    assert observation.first_token_s is None
    assert observation.visible_text() == observation.reasoning_text() == ""


@pytest.mark.parametrize(
    "message",
    [
        {"content": "hello"},
        {"reasoning_content": "thinking"},
        {"reasoning": "thinking"},
        {"reasoning_details": [{"type": "reasoning.text", "text": "thinking"}]},
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "thinking"}]},
        {"tool_calls": [{"function": {"name": "tool"}}]},
        {"tool_calls": [{"function": {"arguments": "{"}}]},
        {"tool_calls": [{"function": {"arguments": {}}}]},
    ],
)
def test_generated_payload_starts_ttft(message):
    observation = OutputObservation()
    observation.observe(message, 12)
    observation.observe({"content": "later"}, 15)
    assert observation.first_token_s == 12


def test_sse_ttft_ignores_preamble_and_end_before_postprocessing(monkeypatch):
    now = [10.0]
    monkeypatch.setattr("providers.time.perf_counter", lambda: now[0])

    class TimedResponse(StreamResponse):
        async def iter_any(self):
            for timestamp, chunk in self.chunks:
                now[0] = timestamp
                yield chunk

    response = TimedResponse(
        [
            (11, sse_frame({"role": "assistant"})),
            (12, sse_frame(usage={"prompt_tokens": 9})),
            (
                13,
                sse_frame(
                    {"tool_calls": [{"index": 0, "id": "opaque", "type": "function"}]}
                ),
            ),
            (14, sse_frame({"content": "hello"})),
            (18, sse_frame(usage={"completion_tokens": 20})),
            (20, DONE),
        ]
    )
    provider = provider_for([response])
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.ttft_ms == 4000
    assert result.metrics.elapsed_ms == 10000
    assert result.metrics.tps == 2
    assert result.metrics.stream
    assert result.metrics.input_tokens == 9
    assert result.metrics.output_tokens == 20


@pytest.mark.parametrize("stream", [True, False])
def test_actual_response_format_and_timing_before_tokenization(monkeypatch, stream):
    now = [10.0]
    monkeypatch.setattr("providers.time.perf_counter", lambda: now[0])
    import provider_telemetry

    real_count = count_tokens

    def slow_tokenize(text):
        now[0] = 900
        return real_count(text)

    monkeypatch.setattr(provider_telemetry, "count_tokens", slow_tokenize)

    class TimedResponse(StreamResponse):
        async def json(self, **kwargs):
            now[0] = 14
            return {"choices": [{"message": {"content": "hello"}}]}

        async def iter_any(self):
            now[0] = 12
            yield sse_frame({"content": "hello"})
            now[0] = 14
            yield DONE

    response = TimedResponse([], "text/event-stream" if stream else "application/json")
    provider = provider_for([response])
    if stream:
        original = provider._request_payload

        def forced_json(*args, **kwargs):
            data = original(*args, **kwargs)
            data["stream"] = False
            data.pop("stream_options", None)
            return data

        monkeypatch.setattr(provider, "_request_payload", forced_json)
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.stream is stream
    assert result.metrics.elapsed_ms == 4000
    assert result.metrics.ttft_estimated is (not stream)
    assert result.metrics.ttft_ms == (2000 if stream else 4000)


def test_no_observed_generation_has_estimated_ttft():
    observation = OutputObservation(finished_s=15)
    metrics = build_call_metrics(
        {},
        {"messages": []},
        observation,
        provider="host",
        endpoint="primary",
        model="m",
        request_start=10,
        stream=True,
        attempt=1,
    )
    assert metrics.ttft_estimated
    assert metrics.ttft_ms == metrics.elapsed_ms == 5000
    assert metrics.output_tokens == 0


def test_unicode_tools_stream_and_json_counts_match():
    args = json.dumps(
        {"text": "héllo 世界", "reasoning": "réfléchir"}, ensure_ascii=False
    )
    message = {
        "content": "Answer",
        "reasoning_content": "思考",
        "tool_calls": [{"function": {"name": "lookup", "arguments": args}}],
    }
    stream = StreamResponse(
        [
            sse_frame({"content": "Ans", "reasoning_content": "思"}),
            sse_frame({"content": "wer", "reasoning_content": "考"}),
            sse_frame(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"name": "look", "arguments": args[:10]},
                        }
                    ]
                }
            ),
            sse_frame(
                {
                    "tool_calls": [
                        {"index": 0, "function": {"name": "up", "arguments": args[10:]}}
                    ]
                }
            ),
            DONE,
        ]
    )
    provider = provider_for([stream, json_response(message)])
    results = [asyncio.run(provider.generate_response([])) for _ in range(2)]
    assert (
        results[0].metrics.output_tokens
        == results[1].metrics.output_tokens
        == count_tokens("Answerlookup" + args + "思考")
    )
    assert results[0].metrics.output_bytes == results[1].metrics.output_bytes


def test_promoted_reasoning_and_custom_json_are_counted_once():
    custom = '{"name": "lookup", "arguments": {"reasoning": "test", "text": "世界"}}'
    provider = provider_for(
        [json_response({"content": None, "reasoning_content": "answer"})]
    )
    provider._reasoning_content_is_answer = lambda *args: True
    promoted = asyncio.run(provider.generate_response([]))
    assert promoted == "answer"
    assert promoted.metrics.output_tokens == count_tokens("answer")
    provider._session = FakeSession(
        StreamResponse([sse_frame({"content": custom}), DONE])
    )
    result = asyncio.run(provider.generate_response([], custom_tool_calls=True))
    assert result.tool_calls
    assert result.metrics.output_tokens == count_tokens(custom)
    assert result.metrics.output_bytes == len(custom.encode())


def test_reasoning_aliases_and_details_are_not_duplicated():
    observation = OutputObservation()
    observation.observe(
        {
            "reasoning_content": "thought",
            "reasoning": "thought",
            "reasoning_details": [{"type": "reasoning.text", "text": "thought"}],
        },
        12,
    )
    assert observation.reasoning_text() == "thought"


def test_input_fallback_text_schema_unicode_and_opaque_exclusion():
    plain = {
        "messages": [{"role": "user", "content": "héllo 世界"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    },
                },
            }
        ],
    }
    media = {
        **plain,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "héllo 世界"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,PRIVATE"},
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"data": "PRIVATE", "format": "wav"},
                    },
                ],
                "signature": "PRIVATE",
            }
        ],
    }
    assert request_text(plain) == request_text(media)
    assert "PRIVATE" not in request_text(media)
    assert "héllo 世界" in request_text(media)
    assert "parameters" in request_text(media)
    assert request_text({"messages": []}) != request_text(plain)


@pytest.mark.parametrize("attempts", [1, 2, 5])
@pytest.mark.parametrize("status", [400, 422])
def test_usage_rejection_is_cached_and_corrected_within_budget(
    attempts, status, no_wait
):
    provider = provider_for(
        [
            FakeErrorResponse(status, "Unknown parameter: stream_options"),
            json_response(),
        ],
        retry_attempts=attempts,
    )
    if attempts == 1:
        with pytest.raises(ProviderRequestError):
            asyncio.run(provider.generate_response([]))
        assert len(provider._session.payloads) == 1
    else:
        result = asyncio.run(provider.generate_response([]))
        assert result.metrics.attempt == 2
        assert len(provider._session.payloads) == 2
        assert "stream_options" not in provider._session.payloads[1]
    assert provider._stream_usage_unsupported == {"primary"}
    no_wait.assert_not_awaited()
    provider._session = FakeSession(json_response())
    asyncio.run(provider.generate_response([]))
    assert "stream_options" not in provider._session.payloads[0]


def test_corrected_endpoint_is_pinned_not_switched_by_fast_fallback(no_wait):
    provider = provider_for(
        [FakeErrorResponse(422, "include_usage is not supported"), json_response()],
        fallback_base_url="https://fallback.test",
        fallback_model="fallback-model",
    )
    result = asyncio.run(provider.generate_response([], fast_fallback=True))
    assert result.metrics.attempt == 2
    assert result.metrics.endpoint == "primary"
    assert provider._session.urls[0] == provider._session.urls[1]
    fallback = provider._endpoints[1]
    assert provider._request_payload(fallback, [])["stream_options"] == {
        "include_usage": True
    }
    no_wait.assert_not_awaited()


def test_correction_does_not_extend_budget_on_final_rejection(no_wait):
    provider = provider_for(
        [
            FakeErrorResponse(400, "unsupported stream_options"),
            FakeErrorResponse(400, "unsupported unrelated"),
        ],
        retry_attempts=2,
    )
    with pytest.raises(ProviderRequestError):
        asyncio.run(provider.generate_response([]))
    assert len(provider._session.payloads) == 2
    no_wait.assert_not_awaited()


def test_forced_json_removes_stream_options(no_wait):
    provider = provider_for([FakeEmptyResponse(), json_response()], retry_attempts=2)
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.attempt == 2
    assert provider._session.payloads[0]["stream_options"] == {"include_usage": True}
    assert not provider._session.payloads[1]["stream"]
    assert "stream_options" not in provider._session.payloads[1]
    assert [call.args[0] for call in no_wait.await_args_list] == [10]


@pytest.mark.parametrize(
    "usage",
    [
        None,
        [],
        "bad",
        {
            "prompt_tokens": float("nan"),
            "completion_tokens": float("inf"),
            "completion_tokens_details": "bad",
        },
    ],
)
def test_malformed_telemetry_does_not_retry_valid_response(usage, no_wait):
    provider = provider_for([json_response(usage=usage)])
    result = asyncio.run(provider.generate_response([]))
    assert result == "hello"
    assert result.metrics.output_source == "cl100k_base"
    assert len(provider._session.payloads) == 1
    no_wait.assert_not_awaited()


def test_message_metadata_is_local_serializable_and_not_shared_state():
    provider = provider_for(
        [
            json_response(usage={"input_tokens": 3, "output_tokens": 4}),
            json_response(usage={"input_tokens": 30, "output_tokens": 40}),
        ]
    )
    first = asyncio.run(provider.generate_chat_completion([]))
    second = asyncio.run(provider.generate_chat_completion([]))
    assert isinstance(first, ChatCompletionMessage)
    assert first.metrics.output_tokens == first.usage["completion_tokens"] == 4
    assert second.metrics.output_tokens == 40
    assert first.metrics.call_id != second.metrics.call_id
    assert first.metrics.provider == "example.test"
    assert json.loads(json.dumps(first)) == {"content": "hello"}
    assert ProviderResult("legacy").metrics is None
    assert not hasattr(provider, "_last_metrics")


def test_concurrent_response_wrapping_never_reads_last_usage():
    provider = provider_for([])

    async def scenario():
        ready = asyncio.Event()
        release = asyncio.Event()

        async def completion(messages, **kwargs):
            text = messages[0]["content"]
            metrics = metrics_for(
                {"usage": {"output_tokens": 1 if text == "first" else 99}}
            )
            result = ChatCompletionMessage(
                {"content": text},
                metrics=metrics,
                usage={"completion_tokens": metrics.output_tokens},
            )
            if text == "first":
                ready.set()
                await release.wait()
            else:
                provider._last_usage = {"completion_tokens": 9999}
                release.set()
            return result

        provider.generate_chat_completion = completion
        first = asyncio.create_task(provider.generate_response([{"content": "first"}]))
        await ready.wait()
        second = await provider.generate_response([{"content": "second"}])
        return await first, second

    first, second = asyncio.run(scenario())
    assert first.usage["completion_tokens"] == first.metrics.output_tokens == 1
    assert second.usage["completion_tokens"] == second.metrics.output_tokens == 99
    assert first.metrics.call_id != second.metrics.call_id


def test_actual_selected_model_override_and_fallback():
    provider = provider_for([json_response()])
    primary = asyncio.run(provider.generate_response([], model="actual-override"))
    assert primary.metrics.model == "actual-override"
    provider = provider_for(
        [FakeErrorResponse(503, "unavailable"), json_response()],
        fallback_base_url="https://fallback.test",
        fallback_model="actual-fallback",
    )
    fallback = asyncio.run(
        provider.generate_response([], model="ignored-on-fallback", fast_fallback=True)
    )
    assert fallback.metrics.model == "actual-fallback"
    assert fallback.metrics.provider == "fallback.test"
    assert fallback.metrics.endpoint == "fallback"
    assert fallback.metrics.attempt == 2


def test_tokenizer_failure_precedes_provider_network_initialization(monkeypatch):
    def missing_asset():
        raise FileNotFoundError("required local tokenizer asset")

    initialize = AsyncMock()
    monkeypatch.setattr("providers.local_encoding", missing_asset)
    monkeypatch.setattr(OllamaProvider, "initialize", initialize)
    with pytest.raises(FileNotFoundError, match="local tokenizer"):
        provider_for([])
    initialize.assert_not_awaited()


def test_invalid_canonical_counts_fall_back_to_reported_string_aliases():
    assert reported_usage(
        {
            "usage": {
                "prompt_tokens": False,
                "input_tokens": "12.0",
                "completion_tokens": "Infinity",
                "output_tokens": "1.2e3",
                "completion_tokens_details": {"reasoning_tokens": []},
                "output_tokens_details": {"reasoning_tokens": "200"},
            }
        }
    ) == (12, 1200, 200)


def test_gemini_stream_reasoning_and_candidates_are_separate():
    provider = provider_for(
        [
            StreamResponse(
                [
                    sse_frame({"content": "hello"}),
                    sse_frame(
                        usageMetadata={
                            "promptTokenCount": "12",
                            "candidatesTokenCount": "15",
                            "thoughtsTokenCount": "5",
                        }
                    ),
                    DONE,
                ]
            )
        ]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.input_tokens == 12
    assert result.metrics.output_tokens == 20
    assert result.metrics.reasoning_tokens == 5
    assert result.metrics.output_source == "provider"


@pytest.mark.parametrize(
    "response, expected",
    [
        (
            {"usage": {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 7}},
            (10, 20, 7),
        ),
        (
            {
                "usage": {
                    "prompt_eval_count": "10",
                    "eval_count": "20",
                    "reasoning_tokens": "7",
                }
            },
            (10, 20, 7),
        ),
        ({"prompt_eval_count": 10, "eval_count": 20}, (10, 20, None)),
        (
            {"usage": {"input_tokens": 10, "total_tokens": 30, "reasoning_tokens": 7}},
            (10, 20, 7),
        ),
        (
            {
                "usage": {
                    "input_tokens": 10,
                    "total_tokens": 30,
                    "output_tokens": 15,
                    "reasoning_tokens": 7,
                }
            },
            (10, 15, 7),
        ),
        ({"usage": {"input_tokens": 10, "total_tokens": 9}}, (10, None, None)),
        (
            {"usage": {"input_tokens": 10, "total_tokens": 12, "reasoning_tokens": 7}},
            (10, None, 7),
        ),
        ({"usage": {"total_tokens": 30}}, (None, None, None)),
    ],
)
def test_known_usage_variants_and_consistent_reported_total_inference(
    response, expected
):
    assert reported_usage(response) == expected


@pytest.mark.parametrize("stream", [False, True])
def test_ollama_top_level_usage_survives_transport(stream):
    fields = {"prompt_eval_count": "10", "eval_count": "20"}
    response = (
        StreamResponse([sse_frame({"content": "hello"}, **fields), DONE])
        if stream
        else json_response(**fields)
    )
    result = asyncio.run(provider_for([response]).generate_response([]))
    assert result.metrics.input_tokens == 10
    assert result.metrics.output_tokens == 20
    assert result.metrics.input_source == result.metrics.output_source == "provider"


def test_total_only_never_subtracts_estimated_input():
    metrics = metrics_for({"usage": {"total_tokens": 10000}})
    assert metrics.output_tokens == count_tokens("héllo 世界")
    assert metrics.input_source == metrics.output_source == "cl100k_base"


@pytest.mark.parametrize(
    "message",
    [
        {"content": "visible"},
        {"reasoning_content": "thinking"},
        {"tool_calls": [{"function": {"name": "tool", "arguments": "{}"}}]},
    ],
)
def test_placeholder_zero_output_is_estimated_with_provenance(message):
    metrics = metrics_for({"usage": {"output_tokens": 0}}, message)
    assert metrics.output_tokens > 0
    assert metrics.output_source == "cl100k_base"
    assert metrics.estimated


def test_reported_zero_without_observed_output_is_retained():
    metrics = metrics_for({"usage": {"output_tokens": 0}}, {"role": "assistant"})
    assert metrics.output_tokens == 0
    assert metrics.output_source == "provider"
    assert not metrics.estimated


@pytest.mark.parametrize("invalid", [None, False, "Infinity", -1, 1.5, {}])
def test_stream_usage_keeps_last_valid_count_across_partial_trailers(invalid):
    provider = provider_for(
        [
            StreamResponse(
                [
                    sse_frame({"content": "hello"}),
                    sse_frame(usage={"prompt_tokens": 10, "completion_tokens": 123}),
                    sse_frame(usage={"completion_tokens": invalid}),
                    sse_frame(usage={"total_tokens": 133}),
                    DONE,
                ]
            )
        ]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.input_tokens == 10
    assert result.metrics.output_tokens == 123
    assert result.metrics.output_source == "provider"


def test_stream_usage_merges_nested_partial_details_without_summing():
    provider = provider_for(
        [
            StreamResponse(
                [
                    sse_frame({"content": "hello"}),
                    sse_frame(
                        usage={"completion_tokens_details": {"reasoning_tokens": 100}}
                    ),
                    sse_frame(
                        usage={
                            "completion_tokens_details": {
                                "accepted_prediction_tokens": 1
                            }
                        }
                    ),
                    sse_frame(
                        usage={"completion_tokens_details": {"reasoning_tokens": None}}
                    ),
                    sse_frame(usage={"completion_tokens_details": None}),
                    sse_frame(usage={"completion_tokens": 150}),
                    sse_frame(
                        usage={
                            "completion_tokens": 123,
                            "completion_tokens_details": {
                                "accepted_prediction_tokens": 1
                            },
                        }
                    ),
                    DONE,
                ]
            )
        ]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.reasoning_tokens == 100
    assert result.metrics.output_tokens == 123
    assert result.metrics.output_source == "provider"


@pytest.mark.parametrize("family", ["ollama", "gemini"])
def test_native_stream_counters_preserve_valid_values_and_accept_final_corrections(
    family,
):
    if family == "ollama":
        trailers = [
            {"prompt_eval_count": 10, "eval_count": 150},
            {"eval_count": None},
            {"eval_count": "123"},
            {"eval_count": "Infinity"},
        ]
    else:
        trailers = [
            {
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 100,
                    "thoughtsTokenCount": 50,
                }
            },
            {"usageMetadata": {"thoughtsTokenCount": None}},
            {"usageMetadata": {"candidatesTokenCount": "73"}},
        ]
    response = StreamResponse(
        [
            sse_frame({"content": "hello"}),
            *[sse_frame(**trailer) for trailer in trailers],
            DONE,
        ]
    )
    result = asyncio.run(provider_for([response]).generate_response([]))
    assert result.metrics.input_tokens == 10
    assert result.metrics.output_tokens == 123
    assert result.metrics.output_source == "provider"


@pytest.mark.parametrize(
    "values, expected",
    [
        ((0, 123, 456), 123),
        ((12, 123, 456), 12),
        ((None, 0, "Infinity"), 0),
        ((0, 0, None), 0),
        ((0, -1, False), 0),
        ((None, "Infinity", False), None),
    ],
)
def test_reported_aliases_prefer_first_positive_and_preserve_valid_zero(
    values, expected
):
    assert (
        reported_count(
            dict(zip(("first", "second", "third"), values)), "first", "second", "third"
        )
        == expected
    )


@pytest.mark.parametrize("stream", [False, True])
def test_positive_aliases_override_zero_placeholders_in_transport(stream):
    usage = {
        "prompt_tokens": 0,
        "input_tokens": 456,
        "completion_tokens": 0,
        "output_tokens": 123,
    }
    response = (
        StreamResponse([sse_frame({"content": "hello"}, usage=usage), DONE])
        if stream
        else json_response(usage=usage)
    )
    result = asyncio.run(provider_for([response]).generate_response([]))
    assert result.metrics.input_tokens == 456
    assert result.metrics.output_tokens == 123
    assert result.metrics.input_source == result.metrics.output_source == "provider"


@pytest.mark.parametrize("stream", [False, True])
def test_zero_aliases_and_invalid_later_aliases_keep_zero_input_and_estimate_generated_output(
    stream,
):
    usage = {
        "prompt_tokens": 0,
        "input_tokens": 0,
        "prompt_eval_count": None,
        "completion_tokens": 0,
        "output_tokens": 0,
        "eval_count": "Infinity",
    }
    response = (
        StreamResponse([sse_frame({"content": "hello"}, usage=usage), DONE])
        if stream
        else json_response(usage=usage)
    )
    result = asyncio.run(provider_for([response]).generate_response([]))
    assert result.metrics.input_tokens == 0
    assert result.metrics.input_source == "provider"
    assert result.metrics.output_tokens == count_tokens("hello")
    assert result.metrics.output_source == "cl100k_base"


def test_empty_output_retains_reported_zero_with_invalid_later_alias():
    metrics = metrics_for(
        {"usage": {"completion_tokens": 0, "output_tokens": None}},
        {"role": "assistant"},
    )
    assert metrics.output_tokens == 0
    assert metrics.output_source == "provider"


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "fields, expected",
    [
        (
            {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                    "reasoning_tokens": 100,
                },
                "prompt_eval_count": 456,
                "eval_count": 123,
            },
            (456, 123, 100),
        ),
        (
            {
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
                "usageMetadata": {
                    "promptTokenCount": 456,
                    "candidatesTokenCount": 23,
                    "thoughtsTokenCount": 100,
                },
            },
            (456, 123, 100),
        ),
        (
            {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "completion_tokens_details": {"reasoning_tokens": 7},
                    "reasoning_tokens": 100,
                },
                "prompt_eval_count": 456,
                "eval_count": 123,
            },
            (10, 20, 7),
        ),
        (
            {
                "usage": {
                    "prompt_tokens": 456,
                    "completion_tokens": 123,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 100},
                    "reasoning_tokens": None,
                }
            },
            (456, 123, 100),
        ),
        (
            {
                "usage": {
                    "prompt_tokens": 456,
                    "completion_tokens": 0,
                    "total_tokens": 579,
                    "reasoning_tokens": 100,
                }
            },
            (456, 123, 100),
        ),
    ],
)
def test_positive_known_family_locations_override_placeholders_without_summing(
    stream, fields, expected
):
    assert reported_usage(fields) == expected
    response = (
        StreamResponse([sse_frame({"content": "hello"}, **fields), DONE])
        if stream
        else json_response(**fields)
    )
    result = asyncio.run(provider_for([response]).generate_response([]))
    assert (
        result.metrics.input_tokens,
        result.metrics.output_tokens,
        result.metrics.reasoning_tokens,
    ) == expected
    assert result.metrics.input_source == result.metrics.output_source == "provider"


def test_zero_known_family_locations_survive_invalid_later_alternatives():
    assert reported_usage(
        {
            "usage": {
                "prompt_tokens": 0,
                "input_tokens": None,
                "completion_tokens": 0,
                "output_tokens": "Infinity",
                "completion_tokens_details": {"reasoning_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": False},
                "reasoning_tokens": None,
            },
            "prompt_eval_count": None,
            "eval_count": False,
            "usageMetadata": {
                "promptTokenCount": None,
                "thoughtsTokenCount": "Infinity",
            },
        }
    ) == (0, 0, 0)


def test_failed_attempt_time_is_not_accumulated(monkeypatch):
    now = [1.0]
    monkeypatch.setattr("providers.time.perf_counter", lambda: now[0])

    class SlowError(FakeErrorResponse):
        async def text(self):
            now[0] = 51
            return "synthetic error"

    class Success(StreamResponse):
        async def json(self, **kwargs):
            now[0] = 65
            return {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"completion_tokens": 8},
            }

    async def wait(seconds):
        now[0] += seconds

    monkeypatch.setattr("providers.asyncio.sleep", wait)
    provider = provider_for(
        [SlowError(503, "synthetic"), Success([], "application/json")]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.attempt == 2
    assert result.metrics.elapsed_ms == 4000
    assert result.metrics.ttft_ms == 4000
    assert result.metrics.tps == 2


def test_usage_correction_preserves_five_attempt_ceiling_and_waits(no_wait):
    provider = provider_for(
        [
            FakeErrorResponse(400, "unsupported stream_options"),
            *[FakeErrorResponse(503, "synthetic transient") for _ in range(3)],
            json_response(),
        ]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result.metrics.attempt == len(provider._session.payloads) == 5
    assert [call.args[0] for call in no_wait.await_args_list] == [20, 30, 40]
    assert all(
        "stream_options" not in payload for payload in provider._session.payloads[1:]
    )


@pytest.mark.parametrize(
    "usage",
    [
        None,
        [],
        "bad",
        {"completion_tokens": "Infinity"},
        {"completion_tokens": 10**400},
    ],
)
@pytest.mark.parametrize("stream", [True, False])
def test_malformed_stream_usage_does_not_retry_generated_response(
    usage, no_wait, stream
):
    provider = provider_for(
        [
            StreamResponse(
                [sse_frame({"content": "hello"}), sse_frame(usage=usage), DONE]
            )
            if stream
            else json_response(usage=usage)
        ]
    )
    result = asyncio.run(provider.generate_response([]))
    assert result == "hello"
    assert result.metrics.output_source == "cl100k_base"
    assert len(provider._session.payloads) == 1
    no_wait.assert_not_awaited()
