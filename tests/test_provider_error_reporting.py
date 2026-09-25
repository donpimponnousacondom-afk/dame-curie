import asyncio
import copy
import json
import logging
import time
from unittest.mock import AsyncMock

import aiohttp
import pytest

import error_reporting
import providers
from turn_budget import (
    ForegroundTurn,
    reset_foreground_turn,
    set_foreground_turn,
)
from providers import (
    OpenAICompatibleProvider,
    ProviderEmptyResponseError,
    ProviderIncompleteResponseError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderUpstreamError,
    ProviderUsageExhaustedError,
)


class Response:
    def __init__(self, body=b"", status=200, *, chunks=None, headers=None, error=None):
        self.raw_body = body
        self.status = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.chunks = chunks if chunks is not None else [body]
        self.content = self
        self.error = error
        self.read_chunks = 0
        self.json_calls = 0
        self.text_calls = 0
        self._body = None

    async def __aenter__(self):
        if self.error is not None:
            raise self.error
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get_encoding(self):
        return self.headers["Content-Type"].split("charset=")[-1] if "charset=" in self.headers["Content-Type"] else "utf-8"

    async def json(self, *, content_type=None):
        assert content_type is None
        self.json_calls += 1
        self._body = self.raw_body
        return json.loads(self.raw_body.decode(self.get_encoding()))

    async def text(self):
        self.text_calls += 1
        self._body = self.raw_body
        return self.raw_body.decode("utf-8")

    async def iter_any(self):
        for chunk in self.chunks:
            self.read_chunks += 1
            if chunk is None:
                await asyncio.Event().wait()
            yield chunk


class Session:
    closed = False

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, *, json, timeout, headers):
        self.requests.append((url, copy.deepcopy(json), timeout, dict(headers)))
        return self.responses.pop(0)

    def get(self, url, *, timeout, headers):
        self.requests.append((url, {}, timeout, dict(headers)))
        return self.responses.pop(0)


def provider_for(responses, **kwargs):
    provider = OpenAICompatibleProvider(
        "https://primary.example.test/v1", "synthetic-model", 8192, 0.6, **kwargs
    )
    provider.available = True
    provider._session = Session(responses)
    return provider


def success():
    return Response(b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}')


@pytest.fixture(autouse=True)
def incident_state(monkeypatch):
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())


@pytest.fixture
def private_store(tmp_path):
    return error_reporting.configure_incident_store(tmp_path / "incidents.json")


@pytest.fixture
def production_handler(private_store):
    handler = error_reporting.IncidentLoggingHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        yield private_store
    finally:
        root_logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def captured(monkeypatch):
    reports = []

    def capture(source, summary, *, exception=None, details="", context=None):
        reports.append({
            "source": source, "summary": summary, "exception": exception,
            "details": details, "context": context,
        })
        return f"synthetic-incident-{len(reports)}"

    monkeypatch.setattr(providers, "capture_incident", capture)
    return reports


@pytest.fixture(autouse=True)
def retry_sleep(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(providers.asyncio, "sleep", sleep)
    return sleep


MESSAGES = [{"role": "user", "content": "synthetic private prompt not needed in diagnostics"}]


@pytest.mark.parametrize("number", [1, 37, 50, 75, 100])
def test_numeric_openrouter_rejection_keeps_integer_and_full_support_diagnostics(production_handler, caplog, number):
    body = "reasoning.effort rejected as numeric; " + "FULL-UPSTREAM-DETAIL " * 1000 + "FINAL-SUPPORT-TAIL"
    response = Response(body.encode(), 400, headers={"X-Request-ID": "synthetic-effort-request"})
    provider = OpenAICompatibleProvider(
        "https://openrouter.ai/api/v1", "deepseek/deepseek-v4.1-flash", 8192, 0.6,
        api_key="synthetic-effort-key", retry_attempts=4, reasoning_control=lambda: number,
        extra_body={"provider": {"only": ["deepseek"]}},
    )
    provider.available = True
    provider._session = Session([response])
    with pytest.raises(ProviderRequestError):
        asyncio.run(provider.generate_chat_completion(MESSAGES))
    assert len(provider._session.requests) == 1
    payload = provider._session.requests[0][1]
    assert type(payload["reasoning"]["effort"]) is int
    assert payload["reasoning"] == {"enabled": True, "effort": number}
    assert payload["provider"] == {"only": ["deepseek"]}
    report = production_handler.get(0).format_report()
    assert body in report and "synthetic-effort-request" in report
    assert f'"effort": {number}' in report
    assert "synthetic-effort-key" not in report and MESSAGES[0]["content"] not in report
    assert body not in caplog.text
    assert production_handler.get(1) is None
    assert provider.deepseek_reasoning_level(provider._endpoints[0]) == number


def test_bounded_http400_body_is_private_with_exact_request_metadata(captured, caplog):
    body = "reason=" + "x" * 90_000 + "; missing reasoning_content in assistant continuation; END405"
    response = Response(body.encode(), 400, headers={
        "X-Request-ID": "synthetic-request-400", "CF-Ray": "synthetic-ray",
        "Retry-After": "7", "Set-Cookie": "synthetic-response-cookie",
    })
    provider = provider_for(
        [response], retry_attempts=4, api_key="synthetic-provider-key",
        extra_headers={"Cookie": "synthetic-request-cookie"},
        extra_body={"provider": {"only": ["synthetic-upstream"]}, "reasoning": {"effort": "high"}},
    )
    tools = [{"type": "function", "function": {"name": "synthetic_tool", "parameters": {"type": "object"}}}]
    with pytest.raises(ProviderRequestError) as caught:
        asyncio.run(provider.generate_chat_completion(MESSAGES, tools=tools, model="override-model"))
    error = caught.value
    assert str(error) == "Provider API error: 400"
    assert body not in str(error) + repr(error) + caplog.text
    assert body not in error.incident_details
    assert body[:100] in error.incident_details
    assert "END405" in error.incident_details
    assert "response characters omitted from provider diagnostics" in error.incident_details
    assert error.incident_id == "synthetic-incident-1"
    assert len(captured) == len(provider._session.requests) == 1
    report = captured[0]
    assert report["exception"] is error
    details = report["details"]
    for expected in (
        '"status": 400', '"attempt": "1/4"', '"model": "override-model"',
        '"max_tokens": 8192', '"temperature": 0.6', '"effort": "high"',
        "synthetic-upstream", "synthetic_tool", "synthetic-request-400", "synthetic-ray",
        "https://primary.example.test/v1/chat/completions", "ProviderRequestError",
    ):
        assert expected in details
    for excluded in (
        "Authorization", "Cookie", "synthetic-provider-key", "synthetic-request-cookie",
        "synthetic-response-cookie", MESSAGES[0]["content"],
    ):
        assert excluded not in details
    assert provider._session.requests[0][3]["Authorization"] == "Bearer synthetic-provider-key"
    assert response.text_calls == 1


@pytest.mark.parametrize("status", [500, 502, 503, 504, 429])
def test_retried_http_failures_recover_in_one_incident(status, captured, retry_sleep):
    first = "first upstream explanation " + "a" * 400
    second = "second upstream explanation " + "b" * 400
    provider = provider_for([
        Response(first.encode(), status), Response(second.encode(), status), success(),
    ], retry_attempts=3)
    provider.max_tokens = 16384
    turn = ForegroundTurn(32768, 12, time.monotonic() + 600)
    token = set_foreground_turn(turn)
    try:
        result = asyncio.run(provider.generate_response(MESSAGES))
    finally:
        reset_foreground_turn(token)
    assert result == "ok"
    assert len(provider._session.requests) == 3
    assert [request[1]["max_tokens"] for request in provider._session.requests] == [16384] * 3
    assert turn.attempts == 3
    assert turn.output_remaining == 16384
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10, 20]
    assert len(captured) == 1
    assert captured[0]["exception"] is None
    assert "recovered" in captured[0]["summary"]
    assert first in captured[0]["details"] and second in captured[0]["details"]
    assert '"attempt": "3/3"' in captured[0]["details"]
    assert '"content":"ok"' not in captured[0]["details"]


def test_invalid_encoding_http_error_keeps_cached_bytes_and_existing_decode_failure(captured):
    body = b"upstream non-UTF8 explanation: \xff" + b"x" * 405
    response = Response(body, 400)
    provider = provider_for([response], retry_attempts=1)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert isinstance(caught.value.__cause__, UnicodeDecodeError)
    assert body.decode("utf-8", errors="replace") in caught.value.incident_details
    assert '"status": 400' in caught.value.incident_details
    assert response.text_calls == 1
    assert len(captured) == len(provider._session.requests) == 1


def test_terminal_transient_failures_preserve_budget_and_exception(captured, retry_sleep):
    provider = provider_for([
        Response(b"first server explanation", 503), Response(b"last server explanation", 503),
    ], retry_attempts=2)
    with pytest.raises(RuntimeError, match="transient HTTP 503 failure after retries") as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert len(provider._session.requests) == 2
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]
    assert len(captured) == 1
    assert captured[0]["exception"] is caught.value
    assert "first server explanation" in caught.value.incident_details
    assert "last server explanation" in caught.value.incident_details

    provider = provider_for([
        Response(b"first refusal", 503), Response(b"second refusal", 503),
    ], retry_attempts=3)
    turn = ForegroundTurn(32768, 2, time.monotonic() + 600)
    token = set_foreground_turn(turn)
    try:
        with pytest.raises(RuntimeError, match="provider-attempt allowance exhausted") as budget_exit:
            asyncio.run(provider.generate_response(MESSAGES))
    finally:
        reset_foreground_turn(token)
    assert len(provider._session.requests) == turn.attempts == 2
    assert turn.output_remaining == 32768
    assert "first refusal" in budget_exit.value.incident_details
    assert "second refusal" in budget_exit.value.incident_details
    assert captured[-1]["exception"] is budget_exit.value


def test_http400_fallback_retains_both_endpoint_attempts(captured, retry_sleep):
    provider = provider_for(
        [Response(b"primary rejection " + b"a" * 405, 400), success()],
        retry_attempts=5, fallback_base_url="https://fallback.example.test/v1",
        fallback_model="fallback-model", fallback_api_key="synthetic-fallback-key",
    )
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert [request[1]["model"] for request in provider._session.requests] == ["synthetic-model", "fallback-model"]
    retry_sleep.assert_not_awaited()
    assert len(captured) == 1
    assert "primary rejection " + "a" * 405 in captured[0]["details"]
    assert "https://fallback.example.test/v1/chat/completions" in captured[0]["details"]


@pytest.mark.parametrize("rejection, field", [
    ("stream_options is an unsupported parameter", "stream_options"),
    ("tools are not supported", "tools"),
])
def test_payload_corrections_keep_attempt_budget_and_parameters(rejection, field, captured, retry_sleep):
    provider = provider_for([Response(rejection.encode(), 400), success()], retry_attempts=2)
    tools = [{"type": "function", "function": {"name": "synthetic_tool"}}]
    assert asyncio.run(provider.generate_response(MESSAGES, tools=tools)) == "ok"
    assert len(provider._session.requests) == 2
    assert field in provider._session.requests[0][1]
    assert field not in provider._session.requests[1][1]
    retry_sleep.assert_not_awaited()
    assert len(captured) == 1
    assert rejection in captured[0]["details"]


def test_quota_body_not_echoed_and_no_retry_added(captured, caplog, retry_sleep):
    body = "insufficient_quota: private balance explanation " + "q" * 405
    provider = provider_for([Response(body.encode(), 429)], retry_attempts=5)
    with pytest.raises(ProviderUsageExhaustedError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert len(provider._session.requests) == len(captured) == 1
    assert body in caught.value.incident_details
    assert "private balance" not in str(caught.value) + repr(caught.value) + caplog.text
    retry_sleep.assert_not_awaited()


@pytest.mark.parametrize("response_format", ["json", "sse"])
@pytest.mark.parametrize("kind", [
    "upstream", "length-text", "length-large", "length-custom", "length-native",
    "length-reasoning", "length-drain-timeout", "length-total-only",
    "length-input-total-only", "length-gemini-ambiguous", "length-zero-output",
    "reasoning-only",
    "reasoning-only-alias", "reasoning-only-details",
])
def test_http200_incomplete_response_is_typed_bounded_and_terminal(
    captured, caplog, retry_sleep, response_format, kind, monkeypatch,
):
    explanation = "private completion detail " + "x" * 405 + " complete private suffix"
    custom_call = json.dumps({"name": "wait", "arguments": {"seconds": 10, "reasoning": explanation}})
    messages = {
        "length-text": {"content": "Partial answer: " + explanation},
        "length-large": {"content": "P" * 20_000 + "TAIL"},
        "length-custom": {"content": "Before " + custom_call + " after"},
        "length-native": {"tool_calls": [{
            "index": 0, "id": "call_1", "type": "function",
            "function": {"name": "send_message", "arguments": '{"content":"' + explanation},
        }]},
        "length-reasoning": {"reasoning_content": explanation},
        "length-drain-timeout": {"content": "Partial answer before usage timeout."},
        "length-total-only": {"content": "Partial answer with total usage only."},
        "length-input-total-only": {"content": "Partial answer with input and total only."},
        "length-gemini-ambiguous": {"content": "Partial answer with ambiguous Gemini thoughts."},
        "length-zero-output": {"content": "Partial answer with zero output usage."},
        "reasoning-only": {"content": "  ", "reasoning_content": explanation},
        "reasoning-only-alias": {"content": None, "reasoning": explanation},
        "reasoning-only-details": {"content": "", "reasoning_details": [{"type": "reasoning.text", "text": explanation}]},
    }
    reported_usage = {
        "prompt_tokens": 17,
        "completion_tokens": 23,
        "total_tokens": 40,
        "completion_tokens_details": {"reasoning_tokens": 5},
    }
    reported_metadata = {}
    if kind == "length-total-only":
        reported_usage = {"total_tokens": 40}
    elif kind == "length-input-total-only":
        reported_usage = {"prompt_tokens": 17, "total_tokens": 40}
    elif kind == "length-zero-output":
        reported_usage = {"prompt_tokens": 17, "completion_tokens": 0, "total_tokens": 17}
    elif kind == "length-gemini-ambiguous":
        reported_usage = {}
        reported_metadata = {
            "promptTokenCount": 17,
            "candidatesTokenCount": 23,
            "totalTokenCount": 40,
        }
    payload = {"error": {"code": 400, "message": explanation, "metadata": {"raw": "useful upstream detail"}}}
    if kind != "upstream":
        payload = {"choices": [{
            "message" if response_format == "json" else "delta": messages[kind],
            "finish_reason": "length" if kind.startswith("length-") else "stop",
        }]}
        if kind.startswith("length-") and kind != "length-drain-timeout":
            if reported_usage:
                payload["usage"] = reported_usage
            if reported_metadata:
                payload["usageMetadata"] = reported_metadata
    if response_format == "json":
        body = b" \n" + json.dumps(payload, indent=2).encode() + b"\n "
        response = Response(body)
    else:
        prefix = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\nevent: error\n' if kind == "upstream" else b""
        if kind.startswith("length-"):
            prefix = b"data: " + json.dumps({"choices": [{"delta": messages[kind]}]}).encode() + b"\n\n"
            payload = {"choices": [{"finish_reason": "length"}]}
        body = prefix + b"data: " + json.dumps(payload).encode() + b"\n\n"
        if kind.startswith("length-") and kind != "length-drain-timeout":
            usage_frame = {"choices": []}
            if reported_usage:
                usage_frame["usage"] = reported_usage
            if reported_metadata:
                usage_frame["usageMetadata"] = reported_metadata
            usage_trailer = b"data: " + json.dumps(usage_frame).encode() + b"\n\n"
            response = Response(
                chunks=[body, usage_trailer + b"data: [DONE]\n\n", b"unread trailing transport data"],
                headers={"Content-Type": "text/event-stream"},
            )
        elif kind == "length-drain-timeout":
            monkeypatch.setattr(providers, "_SSE_LENGTH_DRAIN_SECONDS", 0.001)

            response = Response(
                chunks=[body, None],
                headers={"Content-Type": "text/event-stream"},
            )
        else:
            if kind.startswith("reasoning-only"):
                body += b"data: [DONE]\n\n"
            response = Response(
                chunks=[body, b"unread trailing transport data"],
                headers={"Content-Type": "text/event-stream"},
            )
    provider = provider_for(
        [response, success()], retry_attempts=1 if kind == "upstream" else 5, empty_response_retries=3,
        fallback_base_url="https://fallback.example.test/v1", fallback_model="fallback-model",
    )
    expected_error = ProviderUpstreamError if kind == "upstream" else ProviderIncompleteResponseError
    with pytest.raises(expected_error) as caught:
        asyncio.run(provider.generate_response(MESSAGES, custom_tool_calls=kind == "length-custom"))
    assert len(captured) == len(provider._session.requests) == len(provider._session.responses) == 1
    assert provider._session.requests[0][0] == "https://primary.example.test/v1/chat/completions"
    assert body.decode() in caught.value.incident_details
    assert explanation not in str(caught.value) + repr(caught.value) + caplog.text
    assert captured[0]["exception"] is caught.value
    assert "unread trailing transport data" not in captured[0]["details"]
    retry_sleep.assert_not_awaited()
    if kind == "upstream":
        assert "useful upstream detail" in captured[0]["details"]
    else:
        assert isinstance(caught.value, ProviderResponseError)
        if kind.startswith("length-"):
            assert caught.value.finish_reason == "length"
            assert caught.value.classification == "output_token_limit"
            assert str(caught.value) == "The provider stopped at the output token limit."
            assert not hasattr(caught.value, "tool_calls")
            assert not hasattr(caught.value, "assistant_message")
            if kind in {
                "length-text", "length-large", "length-custom", "length-drain-timeout",
                "length-total-only",
            }:
                assert caught.value.partial_content
            if kind == "length-text":
                assert caught.value.partial_content == messages[kind]["content"]
            if kind == "length-native":
                assert caught.value.partial_content == ""
            if kind == "length-large":
                assert len(caught.value.partial_content) == providers._MAX_PARTIAL_CONTENT_CHARS
                assert caught.value.partial_content_truncated
            if kind == "length-custom":
                assert "Before " in caught.value.partial_content
                if response_format == "sse":
                    assert " after" in caught.value.partial_content
                else:
                    assert " after" not in caught.value.partial_content
                assert "wait" not in caught.value.partial_content and "seconds" not in caught.value.partial_content
            if kind == "length-total-only":
                assert caught.value.usage == {"total_tokens": 40}
                assert caught.value.metrics.output_source == "cl100k_base"
            elif kind in {"length-input-total-only", "length-gemini-ambiguous"}:
                assert caught.value.usage == {
                    "input_tokens": 17,
                    "total_tokens": 40,
                }
                assert "output_tokens" not in caught.value.usage
            elif kind == "length-zero-output":
                assert caught.value.usage == {
                    "input_tokens": 17,
                    "output_tokens": 0,
                    "total_tokens": 17,
                }
            elif kind != "length-drain-timeout":
                assert caught.value.usage == {
                    "input_tokens": 17,
                    "output_tokens": 23,
                    "reasoning_tokens": 5,
                    "total_tokens": 40,
                }
                assert caught.value.metrics.input_tokens == 17
                assert caught.value.metrics.output_tokens == 23
                assert caught.value.metrics.output_source == "provider"
            if kind == "length-text" and response_format == "sse":
                assert '"usage_drain_complete": true' in captured[0]["details"]
            if kind == "length-drain-timeout" and response_format == "sse":
                assert caught.value.usage == {}
                assert '"usage_drain_complete": false' in captured[0]["details"]
                assert response.read_chunks == 2
        elif kind.startswith("reasoning-only"):
            assert caught.value.classification == "reasoning_only"
            assert str(caught.value) == "The provider returned reasoning without an answer."
            assert caught.value.partial_content == ""
    if response_format == "sse":
        assert response.read_chunks == (2 if kind.startswith("length-") else 1)
    else:
        assert response.json_calls == 1 and response.text_calls == 0


def test_http200_json_diagnostics_preserve_declared_text_encoding(captured):
    body = '{"error":{"message":"upstream explanation Ωé"}}'
    response = Response(body.encode("utf-16"), headers={"Content-Type": "application/json; charset=utf-16"})
    provider = provider_for([response], retry_attempts=1)
    with pytest.raises(ProviderUpstreamError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert body in caught.value.incident_details
    assert len(captured) == 1


@pytest.mark.parametrize("size", [405, 90_000])
def test_upstream_exception_keeps_private_details_without_public_body(size):
    explanation = {"message": "private upstream explanation " + "x" * size, "metadata": {"raw": "tail"}}
    error = ProviderUpstreamError(explanation)
    if size == 405:
        assert json.loads(error.incident_details) == explanation
    else:
        assert len(error.incident_details) <= providers._PROVIDER_DIAGNOSTIC_BODY_LIMIT + 100
        assert "diagnostic characters omitted" in error.incident_details
        assert '"raw": "tail"' in error.incident_details
    assert "private upstream explanation" not in str(error) + repr(error)


@pytest.mark.parametrize("body, error_name", [
    (b"{malformed private JSON body " + b"x" * 405, "JSONDecodeError"),
    (b'{"invalid":"\xff"}', "UnicodeDecodeError"),
])
def test_malformed_json_preserves_body_and_underlying_decode_trace(body, error_name, captured, caplog):
    provider = provider_for([Response(body)], retry_attempts=1)
    with pytest.raises(ProviderResponseError, match="JSON decoding failed") as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert body.decode("utf-8", errors="replace") in caught.value.incident_details
    assert error_name in caught.value.incident_details
    assert "Traceback (most recent call last)" in caught.value.incident_details
    assert "private JSON" not in str(caught.value) + caplog.text
    assert len(captured) == 1


@pytest.mark.parametrize("body", [b"null", b'["private nonobject body"]', b'{"unexpected":"private shape"}'])
def test_http200_wrong_shape_is_captured_before_existing_retry(body, captured, retry_sleep):
    provider = provider_for([Response(body), success()], retry_attempts=2)
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert body.decode() in captured[0]["details"]
    assert len(captured) == 1
    assert len(provider._session.requests) == 2
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]


@pytest.mark.parametrize("tail", [b"data: {malformed private frame}\n\n", b"data: unterminated private tail"])
def test_malformed_sse_body_is_preserved_without_new_retries(tail, captured):
    provider = provider_for([
        Response(chunks=[tail], headers={"Content-Type": "text/event-stream"}),
    ], retry_attempts=1)
    with pytest.raises(ProviderResponseError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert tail.decode() in caught.value.incident_details
    assert "private" not in str(caught.value)
    assert len(captured) == len(provider._session.requests) == 1


def test_skipped_bad_sse_frame_records_recovered_incident_not_fabricated_error(captured):
    body = (
        b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        b'data: {malformed private frame}\n\n'
        b'data: [DONE]\n\n'
    )
    provider = provider_for([Response(chunks=[body], headers={"Content-Type": "text/event-stream"})])
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert len(captured) == len(provider._session.requests) == 1
    assert isinstance(captured[0]["exception"], json.JSONDecodeError)
    assert body.decode() in captured[0]["details"]
    assert "JSONDecodeError" in captured[0]["details"]


@pytest.mark.parametrize("error", [TimeoutError("private timeout detail"), aiohttp.ClientConnectionError("private network detail")])
def test_transport_failure_preserves_real_exception_trace_and_safe_wrapper(error, captured, caplog, retry_sleep):
    error.__cause__ = OSError("underlying synthetic OS detail")
    provider = provider_for([Response(error=error)], retry_attempts=1)
    turn = ForegroundTurn(8192, 12, time.monotonic() + 600)
    token = set_foreground_turn(turn)
    try:
        with pytest.raises(RuntimeError) as caught:
            asyncio.run(provider.generate_response(MESSAGES, timeout=17))
    finally:
        reset_foreground_turn(token)
    assert turn.attempts == 1
    assert turn.output_remaining == 8192
    assert caught.value.__cause__ is error
    assert str(error) in caught.value.incident_details
    assert "underlying synthetic OS detail" in caught.value.incident_details
    assert "__aenter__" in caught.value.incident_details
    assert "Traceback (most recent call last)" in caught.value.incident_details
    assert "private" not in str(caught.value) + repr(caught.value) + caplog.text
    assert len(captured) == len(provider._session.requests) == 1
    assert captured[0]["exception"] is caught.value
    retry_sleep.assert_not_awaited()


def test_timeout_then_network_recovery_keeps_all_traces_and_backoff(captured, retry_sleep):
    provider = provider_for([
        Response(error=TimeoutError("original timeout detail")),
        Response(error=aiohttp.ClientConnectionError("original network detail")),
        success(),
    ], retry_attempts=3)
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10, 20]
    assert len(captured) == 1
    assert "original timeout detail" in captured[0]["details"]
    assert "original network detail" in captured[0]["details"]


def test_empty_response_recovery_keeps_original_shape_and_nonstream_switch(captured, retry_sleep):
    body = json.dumps({
        "choices": [{"message": {
            "content": "",
            "reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque"}],
        }}],
    }).encode()
    provider = provider_for([Response(body), success()], retry_attempts=2, empty_response_retries=1)
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert len(captured) == 1
    assert body.decode() in captured[0]["details"]
    assert [request[1]["stream"] for request in provider._session.requests] == [True, False]
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]


def test_terminal_empty_response_uses_original_typed_error(captured):
    provider = provider_for([Response(b'{"choices":[{"message":{"content":""}}]}')], retry_attempts=1)
    with pytest.raises(ProviderEmptyResponseError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert captured[0]["exception"] is caught.value
    assert "Empty response from provider" == str(caught.value)


def test_healthy_json_and_sse_never_capture_incidents(captured):
    stream = Response(
        chunks=[b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'],
        headers={"Content-Type": "text/event-stream"},
    )
    provider = provider_for([success(), stream])
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert len(provider._session.requests) == 2

    usage_only_total = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 17, "total_tokens": 40},
        }).encode()
    )
    explicit_zero = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"completion_tokens": 0},
        }).encode()
    )
    ambiguous_gemini = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usageMetadata": {
                "promptTokenCount": 17,
                "candidatesTokenCount": 23,
                "totalTokenCount": 40,
            },
        }).encode()
    )
    fractional_usage = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"completion_tokens": 1.5, "total_tokens": 40},
        }).encode()
    )
    malformed_usage = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {
                "completion_tokens": True,
                "output_tokens": -1,
                "eval_count": "not-a-number",
                "total_tokens": 40,
            },
        }).encode()
    )
    conflicting_usage = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"completion_tokens": 0, "output_tokens": 23},
        }).encode()
    )
    malformed_alias_usage = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"completion_tokens": 23, "output_tokens": 1.5},
        }).encode()
    )
    complete_gemini = Response(
        json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usageMetadata": {
                "candidatesTokenCount": 23,
                "thoughtsTokenCount": 5,
            },
        }).encode()
    )
    budgeted_provider = provider_for(
        [
            usage_only_total,
            explicit_zero,
            ambiguous_gemini,
            fractional_usage,
            malformed_usage,
            conflicting_usage,
            malformed_alias_usage,
            complete_gemini,
        ]
    )
    turn = ForegroundTurn(65536, 12, time.monotonic() + 600)

    token = set_foreground_turn(turn)
    try:
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        reserved = budgeted_provider._session.requests[0][1]["max_tokens"]
        assert turn.output_remaining == 65536 - reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 2 * reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 3 * reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 4 * reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 5 * reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 6 * reserved
        assert asyncio.run(budgeted_provider.generate_response(MESSAGES)) == "ok"
        assert turn.output_remaining == 65536 - 6 * reserved - 28

        multi_choice = provider_for([], extra_body={"n": 2})
        with pytest.raises(
            ValueError, match="Foreground provider calls support only n=1"
        ):
            asyncio.run(multi_choice.generate_response(MESSAGES))
        assert multi_choice._session.requests == []
        assert turn.attempts == 8

        turn.output_remaining = 512
        for key, value in (
            ("max_completion_tokens", True),
            ("max_output_tokens", 0),
        ):
            invalid_caps = provider_for(
                [],
                extra_body={key: value},
                fallback_base_url="https://fallback.example.test/v1",
                fallback_model="synthetic-fallback",
                fallback_api_key="synthetic-fallback-key",
            )
            with pytest.raises(ValueError, match=key):
                asyncio.run(
                    invalid_caps.generate_response(MESSAGES, prefer_fallback=True)
                )
            assert invalid_caps._session.requests == []
            assert turn.output_remaining == 512
            assert turn.attempts == 8

        capped = provider_for(
            [success()],
            extra_body={
                "n": 1,
                "max_completion_tokens": 9000,
                "max_output_tokens": 128,
                "custom": {"labels": ["preserved"]},
            },
        )
        assert asyncio.run(capped.generate_response(MESSAGES)) == "ok"
        capped_payload = capped._session.requests[0][1]
        assert capped_payload["n"] == 1
        assert capped_payload["max_tokens"] == 512
        assert capped_payload["max_completion_tokens"] == 512
        assert capped_payload["max_output_tokens"] == 128
        assert capped_payload["custom"] == {"labels": ["preserved"]}
    finally:
        reset_foreground_turn(token)
    assert turn.attempts == 9

    nonforeground = provider_for(
        [success()],
        extra_body={
            "n": 2,
            "max_completion_tokens": 9000,
            "max_output_tokens": 1280,
        },
    )
    assert asyncio.run(nonforeground.generate_response(MESSAGES)) == "ok"
    nonforeground_payload = nonforeground._session.requests[0][1]
    assert nonforeground_payload["n"] == 2
    assert nonforeground_payload["max_completion_tokens"] == 9000
    assert nonforeground_payload["max_output_tokens"] == 1280
    assert captured == []


def test_provider_registers_all_configured_keys_without_capturing_request_headers(monkeypatch, captured):
    registered = []
    monkeypatch.setattr(providers, "register_secrets", lambda values: registered.extend(values))
    provider_for(
        [], api_key=" synthetic-primary-key ", fallback_api_key=" synthetic-fallback-key ",
        vision_api_key=" synthetic-vision-key ",
    )
    assert registered == ["synthetic-primary-key", "synthetic-fallback-key", "synthetic-vision-key"]
    assert captured == []


def test_concurrent_calls_on_shared_provider_keep_diagnostics_separate(captured):
    async def run():
        first_started = asyncio.Event()
        second_started = asyncio.Event()

        class FirstResponse(Response):
            async def __aenter__(self):
                first_started.set()
                await second_started.wait()
                return self

        class SecondResponse(Response):
            async def __aenter__(self):
                await first_started.wait()
                second_started.set()
                return self

        provider = provider_for([
            FirstResponse(b"request-A private body", 400, headers={"X-Request-ID": "request-A-id"}),
            SecondResponse(b"request-B private body", 400, headers={"X-Request-ID": "request-B-id"}),
        ], retry_attempts=1)
        return await asyncio.gather(
            provider.generate_response(MESSAGES, model="request-A-model"),
            provider.generate_response(MESSAGES, model="request-B-model"),
            return_exceptions=True,
        )

    results = asyncio.run(run())
    assert len(captured) == 2
    assert len({result.incident_id for result in results}) == 2
    for own, other, error in [("A", "B", results[0]), ("B", "A", results[1])]:
        assert isinstance(error, ProviderRequestError)
        assert f"request-{own} private body" in error.incident_details
        assert f"request-{own}-model" in error.incident_details
        assert f"request-{own}-id" in error.incident_details
        assert f"request-{other}" not in error.incident_details


def test_real_store_redacts_registered_key_and_common_credentials(private_store, caplog):
    key = "synthetic-private-provider-credential-12345"
    body = (
        f"upstream echoed {key}\nAuthorization: Bearer other-header-secret\n"
        "Cookie: private-session-cookie\n"
        "-----BEGIN PRIVATE KEY-----\nsynthetic-private-key-material\n-----END PRIVATE KEY-----\n"
        + "full useful explanation " + "x" * 405 + " EXACT FINAL UPSTREAM DETAIL"
    )
    provider = provider_for([Response(body.encode(), 400)], api_key=key, retry_attempts=1)
    with pytest.raises(ProviderRequestError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    incident = private_store.get(0)
    assert incident.incident_id == caught.value.incident_id
    assert private_store.get(1) is None
    report = incident.format_report()
    persisted = private_store.path.read_text()
    for secret in (key, "other-header-secret", "private-session-cookie", "synthetic-private-key-material"):
        assert secret not in report + persisted + str(caught.value) + repr(caught.value) + caplog.text
    assert "[REDACTED]" in report
    assert "x" * 405 + " EXACT FINAL UPSTREAM DETAIL" in report
    assert body in caught.value.incident_details


def test_outer_capture_enriches_same_exception_without_duplicate_store_entry(private_store):
    provider = provider_for([Response(b"complete upstream rejection " + b"x" * 405, 400)], retry_attempts=1)
    with pytest.raises(ProviderRequestError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    error = caught.value
    first = private_store.get(0)
    assert error.incident_id == first.incident_id
    assert error_reporting.capture_incident("bot", "outer command failure", exception=error) == first.incident_id
    enriched = private_store.get(0)
    assert private_store.get(1) is None
    assert "outer command failure" in enriched.details
    assert "test_outer_capture_enriches_same_exception_without_duplicate_store_entry" in enriched.traceback
    assert "complete upstream rejection " + "x" * 405 in enriched.details


def test_recovered_incident_is_redacted_and_not_coalesced_with_next_request(private_store):
    key = "synthetic-private-recovery-key-12345"
    provider = provider_for([
        Response(f"first failed request echoed {key}".encode(), 503), success(),
        Response(b"second unrelated request", 400),
    ], api_key=key, retry_attempts=2)
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    first = private_store.get(0)
    assert key not in first.format_report()
    with pytest.raises(ProviderRequestError):
        asyncio.run(provider.generate_response(MESSAGES))
    assert private_store.get(0).incident_id != first.incident_id
    assert private_store.get(1).incident_id == first.incident_id
    assert private_store.get(2) is None
    assert "first failed request" not in private_store.get(0).details


def test_midstream_network_error_retains_received_body_and_trace(captured):
    partial = (
        b'data: {"choices":[{"delta":{"content":"'
        + b"x" * 90_000
        + b"STREAM_CAPTURE_TAIL"
        + b'"}}]}\n\n'
    )

    class BrokenStream(Response):
        async def iter_any(self):
            yield partial
            raise aiohttp.ClientPayloadError("synthetic stream connection reset")

    provider = provider_for([BrokenStream(headers={"Content-Type": "text/event-stream"})], retry_attempts=1)
    turn = ForegroundTurn(8192, 12, time.monotonic() + 600)
    token = set_foreground_turn(turn)
    try:
        with pytest.raises(RuntimeError) as caught:
            asyncio.run(provider.generate_response(MESSAGES))
    finally:
        reset_foreground_turn(token)
    assert turn.attempts == 1
    assert turn.output_remaining == 0
    assert partial.decode() not in caught.value.incident_details
    assert "response bytes omitted from provider diagnostics" in caught.value.incident_details
    assert "STREAM_CAPTURE_TAIL" in caught.value.incident_details
    assert '"response_body_capture_truncated": true' in caught.value.incident_details
    assert "synthetic stream connection reset" in caught.value.incident_details
    assert "ClientPayloadError" in caught.value.incident_details
    assert "STREAM_CAPTURE_TAIL" not in str(caught.value)
    assert len(captured) == len(provider._session.requests) == 1


def test_unconfigured_capture_still_retains_private_exception_details():
    body = b"unconfigured private upstream body " + b"x" * 405
    provider = provider_for([Response(body, 400)], retry_attempts=1)
    with pytest.raises(ProviderRequestError) as caught:
        asyncio.run(provider.generate_response(MESSAGES))
    assert body.decode() in caught.value.incident_details
    assert not hasattr(caught.value, "incident_id")
    assert error_reporting.get_incident_store() is None


@pytest.mark.parametrize("error_type", [TimeoutError, aiohttp.ClientConnectionError])
@pytest.mark.parametrize("recovered", [True, False])
def test_production_warning_handler_groups_retries_and_terminal_wrapper(error_type, recovered, production_handler):
    errors = [error_type("first private transport cause"), error_type("second private transport cause")]
    responses = [Response(error=error) for error in errors]
    if recovered:
        responses.append(success())
    provider = provider_for(responses, retry_attempts=len(responses))
    if recovered:
        assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    else:
        with pytest.raises(RuntimeError) as caught:
            asyncio.run(provider.generate_response(MESSAGES))
        assert caught.value.__cause__ is errors[-1]
        logging.getLogger("synthetic.outer").error(
            "Outer provider handler", exc_info=(type(caught.value), caught.value, caught.value.__traceback__),
        )
        assert caught.value.incident_id == errors[0].incident_id
    store = production_handler
    incident = store.get(0)
    assert store.get(1) is None
    assert incident.incident_id == errors[0].incident_id == errors[1].incident_id
    assert "first private transport cause" in incident.format_report()
    assert "second private transport cause" in incident.format_report()
    assert "https://primary.example.test/v1/chat/completions" in incident.details
    assert len(provider._session.requests) == len(responses)


def test_production_handler_honors_existing_exception_incident(production_handler):
    error = aiohttp.ClientConnectionError("already captured underlying transport")
    previous_id = error_reporting.capture_incident("transport", "lower level failure", exception=error)
    provider = provider_for([Response(error=error), success()], retry_attempts=2)
    assert asyncio.run(provider.generate_response(MESSAGES)) == "ok"
    assert production_handler.get(0).incident_id == previous_id
    assert production_handler.get(1) is None
    assert "recovered" in production_handler.get(0).details


def test_production_handler_keeps_concurrent_retry_groups_separate(production_handler):
    async def run():
        first_started = asyncio.Event()
        second_started = asyncio.Event()

        class PausedFailure(Response):
            async def __aenter__(self):
                first_started.set()
                await second_started.wait()
                raise self.error

        class SecondFailure(Response):
            async def __aenter__(self):
                await first_started.wait()
                second_started.set()
                raise self.error

        first = provider_for([
            PausedFailure(error=TimeoutError("request A first failure")),
            Response(error=TimeoutError("request A second failure")), success(),
        ], retry_attempts=3)
        second = provider_for([
            SecondFailure(error=aiohttp.ClientConnectionError("request B first failure")), success(),
        ], retry_attempts=2)
        return await asyncio.gather(first.generate_response(MESSAGES), second.generate_response(MESSAGES))

    assert asyncio.run(run()) == ["ok", "ok"]
    records = [production_handler.get(index) for index in range(2)]
    assert all(records)
    assert records[0].incident_id != records[1].incident_id
    assert production_handler.get(2) is None
    first = next(record for record in records if "request A first failure" in record.format_report())
    second = next(record for record in records if "request B first failure" in record.format_report())
    assert "request A second failure" in first.format_report()
    assert "request B" not in first.format_report()
    assert "request A" not in second.format_report()


def test_cancelled_http_backoff_retains_complete_prior_failure(production_handler, monkeypatch):
    body = "complete 503 explanation " + "x" * 3000 + " CANCELLATION BODY TAIL"
    response = Response(body.encode(), 503, headers={"X-Request-ID": "cancelled-http-request"})
    provider = provider_for([response], retry_attempts=3)

    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()
        waits = []

        async def pause_backoff(delay):
            waits.append(delay)
            blocked.set()
            await release.wait()

        monkeypatch.setattr(providers.asyncio, "sleep", pause_backoff)
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        task.cancel("synthetic cancellation")
        with pytest.raises(asyncio.CancelledError, match="synthetic cancellation"):
            await task
        assert waits == [10]

    asyncio.run(run())
    incident = production_handler.get(0)
    assert production_handler.get(1) is None
    assert body in incident.details
    assert '"status": 503' in incident.details
    assert '"attempt": "1/3"' in incident.details
    assert '"response_body_complete": true' in incident.details
    assert "cancelled-http-request" in incident.details
    assert "https://primary.example.test/v1/chat/completions" in incident.details
    assert "CancelledError" not in incident.format_report()
    assert len(provider._session.requests) == response.text_calls == 1


@pytest.mark.parametrize("error_type", [TimeoutError, RuntimeError, aiohttp.ClientConnectionError])
def test_cancellation_inside_exception_handler_retry_keeps_existing_group(error_type, production_handler, monkeypatch):
    errors = [error_type("first real failure"), error_type("second real failure " + "x" * 3000 + " PRIOR EXCEPTION TAIL")]
    provider = provider_for([Response(error=error) for error in errors], retry_attempts=3)

    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()
        waits = []

        async def pause_second_backoff(delay):
            waits.append(delay)
            if len(waits) == 2:
                blocked.set()
                await release.wait()

        monkeypatch.setattr(providers.asyncio, "sleep", pause_second_backoff)
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        existing_id = production_handler.get(0).incident_id
        assert errors[0].incident_id == errors[1].incident_id == existing_id
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert waits == [10, 20]
        return existing_id

    incident_id = asyncio.run(run())
    incident = production_handler.get(0)
    assert incident.incident_id == incident_id
    assert production_handler.get(1) is None
    assert "first real failure" in incident.format_report()
    assert "PRIOR EXCEPTION TAIL" in incident.format_report()
    assert '"attempt": "2/3"' in incident.details
    assert "CancelledError" not in incident.format_report()
    assert len(provider._session.requests) == 2


def test_cancellation_in_next_attempt_preserves_prior_http_failure(production_handler):
    body = b"prior complete HTTP failure " + b"x" * 3000 + b" PRIOR HTTP TAIL"

    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        class PendingStream(Response):
            async def iter_any(self):
                yield b'data: {"choices":[{"delta":{"content":"healthy partial content"},"finish_reason":"length"}]}\n\n'
                blocked.set()
                await release.wait()

        provider = provider_for([
            Response(body, 503), PendingStream(headers={"Content-Type": "text/event-stream"}),
        ], retry_attempts=3)
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(provider._session.requests) == 2

    asyncio.run(run())
    report = production_handler.get(0)
    assert body.decode() in report.details
    assert '"attempt": "2/3"' in report.details
    assert "healthy partial content" not in report.details
    assert "CancelledError" not in report.format_report()
    assert production_handler.get(1) is None


def test_cancellation_after_malformed_sse_preserves_received_frame(production_handler):
    body = b"data: {malformed private stream " + b"x" * 3000 + b" STREAM TAIL}\n\n"

    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        class PendingMalformedStream(Response):
            async def iter_any(self):
                yield body
                blocked.set()
                await release.wait()

        response = PendingMalformedStream(headers={"Content-Type": "text/event-stream"})
        provider = provider_for([response], retry_attempts=3)
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(provider._session.requests) == 1
        assert response.text_calls == 0

    asyncio.run(run())
    incident = production_handler.get(0)
    assert body.decode() in incident.details
    assert "JSONDecodeError" in incident.format_report()
    assert "CancelledError" not in incident.format_report()
    assert production_handler.get(1) is None


@pytest.mark.parametrize("endpoint", ["chat", "models"])
def test_cancelled_non200_body_read_retains_status_without_unread_body(endpoint, production_handler):
    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        class PendingBody(Response):
            async def text(self):
                self.text_calls += 1
                blocked.set()
                await release.wait()
                return self.raw_body.decode()

        response = PendingBody(b"unread upstream body must not be claimed", 503)
        provider = provider_for([response], retry_attempts=3)
        request = provider.initialize() if endpoint == "models" else provider.generate_response(MESSAGES)
        task = asyncio.create_task(request)
        await blocked.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert response.text_calls == len(provider._session.requests) == 1

    asyncio.run(run())
    incident = production_handler.get(0)
    assert '"status": 503' in incident.details
    assert '"response_body_complete": false' in incident.details
    assert "unread upstream body" not in incident.format_report()
    assert "CancelledError" not in incident.format_report()
    assert production_handler.get(1) is None


@pytest.mark.parametrize("phase", ["headers", "sse"])
def test_pristine_cancellation_does_not_create_incident(phase, production_handler):
    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        class PristineResponse(Response):
            async def __aenter__(self):
                if phase == "headers":
                    blocked.set()
                    await release.wait()
                return self

            async def iter_any(self):
                yield b'data: {"choices":[{"delta":{"content":"healthy partial"}}]}\n\n'
                blocked.set()
                await release.wait()

        provider = provider_for([PristineResponse(headers={"Content-Type": "text/event-stream"})])
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert len(provider._session.requests) == 1
        logging.getLogger("synthetic.outer").error(
            "Pristine cancellation propagated", exc_info=(type(caught.value), caught.value, caught.value.__traceback__),
        )

    asyncio.run(run())
    assert production_handler.get(0) is None


def test_cancellation_during_context_exit_does_not_duplicate_completed_capture(production_handler):
    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        class PendingExit(Response):
            async def __aexit__(self, exc_type, exc, tb):
                blocked.set()
                await release.wait()
                return False

        provider = provider_for([
            Response(b"real prior failure", 503), PendingExit(success().raw_body),
        ], retry_attempts=2)
        task = asyncio.create_task(provider.generate_response(MESSAGES))
        await blocked.wait()
        recorded_id = production_handler.get(0).incident_id
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(provider._session.requests) == 2
        return recorded_id

    recorded_id = asyncio.run(run())
    assert production_handler.get(0).incident_id == recorded_id
    assert production_handler.get(1) is None
    assert "real prior failure" in production_handler.get(0).details


@pytest.mark.parametrize("recovered", [False, True])
def test_handled_caller_cancellation_does_not_flush_normal_provider_attempts(recovered, production_handler, monkeypatch):
    responses = [Response(b"first real HTTP failure", 503), Response(b"second real HTTP failure", 503), success()] if recovered else [success()]
    provider = provider_for(responses, retry_attempts=len(responses))
    waits = []

    async def verify_backoff(delay):
        waits.append(delay)
        assert production_handler.get(0) is None

    async def run():
        try:
            raise asyncio.CancelledError("already handled caller cancellation")
        except asyncio.CancelledError:
            return await provider.generate_response(MESSAGES)

    monkeypatch.setattr(providers.asyncio, "sleep", verify_backoff)
    assert asyncio.run(run()) == "ok"
    assert len(provider._session.requests) == len(responses)
    if recovered:
        assert waits == [10, 20]
        incident = production_handler.get(0)
        assert incident.summary == "Provider request recovered after upstream failures"
        assert "first real HTTP failure" in incident.details
        assert "second real HTTP failure" in incident.details
        assert '"attempt": "3/3"' in incident.details
        assert production_handler.get(1) is None
    else:
        assert waits == []
        assert production_handler.get(0) is None


def test_new_cancellation_inside_handled_caller_cancellation_flushes_prior_failure(production_handler, monkeypatch):
    provider = provider_for([Response(b"prior real HTTP failure", 503)], retry_attempts=3)

    async def run():
        blocked = asyncio.Event()
        release = asyncio.Event()

        async def pause_backoff(delay):
            blocked.set()
            await release.wait()

        async def caller():
            try:
                raise asyncio.CancelledError("already handled cancellation")
            except asyncio.CancelledError:
                return await provider.generate_response(MESSAGES)

        monkeypatch.setattr(providers.asyncio, "sleep", pause_backoff)
        task = asyncio.create_task(caller())
        await blocked.wait()
        task.cancel("new actual cancellation")
        with pytest.raises(asyncio.CancelledError, match="new actual cancellation"):
            await task

    asyncio.run(run())
    assert len(provider._session.requests) == 1
    assert "prior real HTTP failure" in production_handler.get(0).details
    assert production_handler.get(1) is None


def test_failed_models_probe_captures_body_without_new_requests(captured):
    body = b"synthetic initialization rejection " + b"x" * 405
    provider = provider_for([Response(body, 401)])
    assert asyncio.run(provider.initialize()) is False
    assert len(captured) == len(provider._session.requests) == 1
    assert body.decode() in captured[0]["details"]
    assert "https://primary.example.test/v1/models" in captured[0]["details"]
