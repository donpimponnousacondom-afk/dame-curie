import ast
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from providers import (
    OllamaProvider,
    ProviderResponseError,
    ProviderUpstreamError,
    _read_sse_response,
)
from test_providers import (
    FakeEmptyResponse,
    FakeErrorResponse,
    FakeResponse,
    FakeSequenceSession,
    FakeSession,
)


class StreamResponse(FakeResponse):
    def __init__(self, chunks, content_type="text/event-stream"):
        self.chunks = chunks
        self.headers = {"Content-Type": content_type}
        self.content = self
        self.json_calls = 0

    async def iter_any(self):
        for chunk in self.chunks:
            yield chunk

    async def json(self, *, content_type="application/json"):
        assert content_type is None
        self.json_calls += 1
        return json.loads(b"".join(self.chunks))


@pytest.fixture
def retry_sleep(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("providers.asyncio.sleep", sleep)
    return sleep


CONTENT = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
DONE = b"data: [DONE]\n\n"
ERROR = {
    "error": {"code": 503, "type": "overloaded_error", "message": "Capacity exceeded"}
}
ERROR_FRAME = b"data: " + json.dumps(ERROR).encode() + b"\n\n"


@pytest.mark.parametrize(
    "chunks",
    [
        [CONTENT, DONE],
        [CONTENT.replace(b"data: ", b"data:")],
        [CONTENT[:3], CONTENT[3:17], CONTENT[17:]],
        [CONTENT.replace(b"\n", b"\r\n")],
        [CONTENT.rstrip(b"\n") + b"\n"],
        [CONTENT],
    ],
)
def test_supported_sse_framing(chunks):
    result = asyncio.run(_read_sse_response(StreamResponse(chunks)))
    assert result["choices"][0]["message"]["content"] == "hello"


@pytest.mark.parametrize("prefix", [[], [CONTENT]])
@pytest.mark.parametrize(
    "failure",
    [
        ERROR_FRAME,
        b"event: error\n" + ERROR_FRAME,
        b'event: error\ndata: {"code":503,"message":"Capacity exceeded"}\n\n',
        b"event: error\ndata: Capacity exceeded\n\n",
        b"event: error\n\n",
        b"event: error\ndata: [DONE]\n\n",
    ],
)
def test_explicit_sse_errors_never_return_partial_success(prefix, failure):
    with pytest.raises(ProviderUpstreamError):
        asyncio.run(_read_sse_response(StreamResponse(prefix + [failure, DONE])))


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (
            [],
            "bytes=0 data_frames=0 choices=0 malformed_frames=0 done=False trailing_bytes=0",
        ),
        ([DONE], "data_frames=0 choices=0 malformed_frames=0 done=True"),
        ([b": keepalive\n\n"], "data_frames=0 choices=0 malformed_frames=0"),
        ([b'data: {"choices":[]}\n\n'], "data_frames=1 choices=0 malformed_frames=0"),
        (
            [b'data: {"usage":{"total_tokens":1}}\n\n'],
            "data_frames=1 choices=0 malformed_frames=0",
        ),
        ([b"data: {broken}\n\n"], "data_frames=1 choices=0 malformed_frames=1"),
    ],
)
def test_empty_stream_failure_reports_framing_counts(chunks, expected):
    with pytest.raises(ProviderResponseError, match="produced no choices") as exc:
        asyncio.run(_read_sse_response(StreamResponse(chunks)))
    assert expected in str(exc.value)


@pytest.mark.parametrize("prefix", [[], [CONTENT]])
def test_unterminated_tail_is_not_silently_discarded(prefix):
    tail = ERROR_FRAME.rstrip(b"\n")
    with pytest.raises(ProviderResponseError, match="unterminated tail") as exc:
        asyncio.run(_read_sse_response(StreamResponse(prefix + [tail])))
    assert f"trailing_bytes={len(tail)}" in str(exc.value)
    assert "Capacity exceeded" not in str(exc.value)


def test_malformed_frame_after_content_has_content_free_diagnostics(caplog):
    frame = b"data: {private-prompt-secret}\n\n"
    result = asyncio.run(_read_sse_response(StreamResponse([CONTENT, frame, DONE])))
    assert result["choices"][0]["message"]["content"] == "hello"
    assert "malformed_frames=1" in caplog.text
    assert "private-prompt-secret" not in caplog.text


@pytest.mark.parametrize("payload", [b"null", b"[]", b'"private-prompt-secret"'])
def test_non_object_sse_json_has_typed_safe_failure(payload):
    with pytest.raises(ProviderResponseError, match="non-object JSON") as exc:
        asyncio.run(_read_sse_response(StreamResponse([b"data: " + payload + b"\n\n"])))
    assert "private-prompt-secret" not in str(exc.value)


@pytest.mark.parametrize(
    "message, category",
    [
        ("Too many concurrent requests", "concurrency_limit"),
        ("Rate limit exceeded", "rate_limit"),
        ("Insufficient credits", "quota"),
        ("Maximum context length exceeded", "context_limit"),
        ("Invalid tool function arguments", "tool_input"),
        ("Invalid input parameter", "invalid_input"),
        ("Model not found", "model_unavailable"),
        ("Server overloaded", "overload"),
        ("Unrecognized failure", "unknown"),
    ],
)
def test_upstream_error_categories_do_not_echo_free_text(message, category):
    error = ProviderUpstreamError(
        {"message": message + " Bearer private-secret", "metadata": "private-prompt"}
    )
    assert f"category={category}" in str(error)
    assert "private-secret" not in str(error)
    assert "private-prompt" not in str(error)
    assert "Bearer" not in str(error)
    assert len(str(error)) < 200


def test_upstream_error_labels_are_allowlisted_and_bounded():
    error = ProviderUpstreamError(
        {"code": 503, "type": "overloaded_error", "message": "secret" * 10000}
    )
    assert "code=503 type=overloaded_error message_chars=60000" in str(error)
    assert "secret" not in str(error)
    unknown = ProviderUpstreamError({"code": "private-token", "type": "private-prompt"})
    assert "code=unknown type=unknown" in str(unknown)
    assert "private" not in str(unknown)


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "Application/JSON; charset=utf-8", "application/problem+json"],
)
def test_http200_json_response_overrides_stream_request(content_type):
    provider = OllamaProvider("http://example.test", "model", 8192, 0.6)
    provider.available = True
    body = {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
    response = StreamResponse([json.dumps(body).encode()], content_type)
    provider._session = FakeSession(response)
    result = asyncio.run(
        provider.generate_response([{"role": "user", "content": "synthetic"}])
    )
    assert result == "hello"
    assert response.json_calls == 1
    assert provider._session.payloads[0]["stream"] is True


@pytest.mark.parametrize("prefix", [[], [CONTENT]])
@pytest.mark.parametrize("response_format", ["sse", "json"])
def test_explicit_upstream_error_preserved_without_native_tool_retry(
    prefix, response_format, retry_sleep, caplog
):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=2
    )
    provider.available = True
    body = {"error": {"code": 400, "message": "Invalid tool function private-secret"}}
    if response_format == "sse":
        response = StreamResponse(
            prefix + [b"data: " + json.dumps(body).encode() + b"\n\n"]
        )
    else:
        body["choices"] = [{"message": {"content": "partial"}}]
        response = StreamResponse([json.dumps(body).encode()], "application/json")
    session = FakeSession(response)
    provider._session = session
    tools = [{"type": "function", "function": {"name": "synthetic"}}]
    with pytest.raises(ProviderUpstreamError, match="category=tool_input"):
        asyncio.run(
            provider.generate_response(
                [{"role": "user", "content": "private-prompt"}], tools=tools
            )
        )
    assert len(session.payloads) == 2
    assert all(payload["tools"] == tools for payload in session.payloads)
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]
    assert "status=200" in caplog.text
    assert f"format={response_format}" in caplog.text
    assert "private-secret" not in caplog.text
    assert "private-prompt" not in caplog.text


def test_http200_unsupported_content_type_does_not_dump_body(caplog):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=1
    )
    provider.available = True
    provider._session = FakeSession(StreamResponse([b"private-secret"], "text/html"))
    with pytest.raises(ProviderResponseError, match="unterminated tail"):
        asyncio.run(provider.generate_response([]))
    assert "private-secret" not in caplog.text


def test_retry_defaults_match_config_and_template():
    assert OllamaProvider("http://example.test", "model", 8192, 0.6).retry_attempts == 5
    root = Path(__file__).resolve().parents[1]
    config = ast.parse((root / "config.py").read_text())
    call = next(
        node
        for node in ast.walk(config)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "OLLAMA_RETRY_ATTEMPTS"
    )
    assert call.args[1].value == 5
    assert "OLLAMA_RETRY_ATTEMPTS=5\n" in (root / ".env.example").read_text()
    readme = (root / "README.md").read_text()
    retry_row = next(
        line
        for line in readme.splitlines()
        if line.startswith("| `OLLAMA_RETRY_ATTEMPTS` |")
    )
    assert "(default: `5`)" in retry_row
    assert "Extra recovery attempts after an HTTP 200" not in readme
    assert (
        "defaults to **5 total attempts**"
        in (root / "docs/CONFIGURATION.md").read_text()
    )
    audit = (root / "doc/html/maxwell-tool-budgets.html").read_text()
    assert (
        "</code> / <code>OLLAMA_EMPTY_RESPONSE_RETRIES</code></td><td>5 / 2;" in audit
    )
    assert (
        "tool-protocol fallback can start a second completion attempt budget"
        not in audit
    )
    assert (
        "configured attempts are intentionally not the only HTTP-attempt allowance"
        not in audit
    )


@pytest.mark.parametrize(
    "retry_attempts, expected", [(None, [10, 20, 30, 40]), (1, []), (3, [10, 20])]
)
def test_transient_attempt_budget_and_exact_linear_delays(
    retry_attempts, expected, retry_sleep
):
    options = {} if retry_attempts is None else {"retry_attempts": retry_attempts}
    provider = OllamaProvider("http://example.test", "model", 8192, 0.6, **options)
    provider.available = True
    session = FakeSession(StreamResponse([]))
    provider._session = session
    with pytest.raises(ProviderResponseError, match="produced no choices"):
        asyncio.run(provider.generate_response([]))
    assert len(session.payloads) == len(expected) + 1
    assert [call.args[0] for call in retry_sleep.await_args_list] == expected


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_failover_also_uses_linear_backoff(status, retry_sleep):
    provider = OllamaProvider(
        "http://primary.test",
        "model",
        8192,
        0.6,
        fallback_base_url="http://fallback.test",
        fallback_model="fallback",
    )
    provider.available = True
    session = FakeSequenceSession(
        [FakeErrorResponse(status, "temporarily busy"), FakeResponse()]
    )
    provider._session = session
    assert asyncio.run(provider.generate_response([], fast_fallback=True)) == "ok"
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]
    assert "primary.test" in session.urls[0]
    assert "fallback.test" in session.urls[1]


@pytest.mark.parametrize("status", [400, 403, 404])
def test_deterministic_failover_remains_immediate(status, retry_sleep):
    provider = OllamaProvider(
        "http://primary.test",
        "model",
        8192,
        0.6,
        fallback_base_url="http://fallback.test",
        fallback_model="fallback",
    )
    provider.available = True
    session = FakeSequenceSession(
        [FakeErrorResponse(status, "invalid request"), FakeResponse()]
    )
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "ok"
    retry_sleep.assert_not_awaited()
    assert "fallback.test" in session.urls[1]


def test_sse_content_type_overrides_nonstreaming_recovery(retry_sleep):
    provider = OllamaProvider(
        "http://example.test",
        "model",
        8192,
        0.6,
        retry_attempts=2,
        empty_response_retries=1,
    )
    provider.available = True
    empty = StreamResponse(
        [b'{"choices":[{"message":{"content":""}}]}'], "application/json"
    )
    streamed = StreamResponse([CONTENT, DONE])
    session = FakeSequenceSession([empty, streamed])
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "hello"
    assert session.payloads[1]["stream"] is False
    assert streamed.json_calls == 0
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10]


@pytest.mark.parametrize("content_type", ["text/plain", "", "private-header-secret"])
def test_unrecognized_content_type_preserves_valid_sse(content_type):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=1
    )
    provider.available = True
    provider._session = FakeSession(StreamResponse([CONTENT, DONE], content_type))
    assert asyncio.run(provider.generate_response([])) == "hello"


@pytest.mark.parametrize("attempts", [1, 3, 5])
def test_empty_content_recovery_never_extends_attempt_budget(attempts, retry_sleep):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=attempts
    )
    provider.available = True
    session = FakeSession(FakeEmptyResponse())
    provider._session = session
    with pytest.raises(RuntimeError, match="Empty response from provider"):
        asyncio.run(provider.generate_response([]))
    assert len(session.payloads) == attempts
    assert [call.args[0] for call in retry_sleep.await_args_list] == list(
        range(10, attempts * 10, 10)
    )
    if attempts > 1:
        assert session.payloads[-1]["stream"] is False


@pytest.mark.parametrize("attempts", [1, 2, 5])
def test_native_tool_correction_uses_remaining_attempts(attempts, retry_sleep, caplog):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=attempts
    )
    provider.available = True
    session = FakeSequenceSession(
        [
            FakeErrorResponse(400, "Tools are not supported: private-secret"),
            FakeResponse(),
        ]
    )
    provider._session = session
    tokens = []
    tools = [{"type": "function", "function": {"name": "synthetic"}}]
    request = provider.generate_response([], tools=tools, on_token=tokens.append)
    if attempts == 1:
        with pytest.raises(RuntimeError, match="Provider API error: 400"):
            asyncio.run(request)
    else:
        assert asyncio.run(request) == "ok"
        assert "tools" not in session.payloads[1]
        assert tokens
    assert len(session.payloads) == min(attempts, 2)
    assert session.payloads[0]["tools"] == tools
    assert "private-secret" not in caplog.text
    retry_sleep.assert_not_awaited()


def test_native_tool_correction_does_not_restart_default_budget(retry_sleep):
    provider = OllamaProvider("http://example.test", "model", 8192, 0.6)
    provider.available = True
    responses = [FakeErrorResponse(400, "This model does not support tools")]
    responses.extend(FakeErrorResponse(500, "busy") for _ in range(4))
    session = FakeSequenceSession(responses)
    provider._session = session
    with pytest.raises(RuntimeError, match="transient HTTP 500"):
        asyncio.run(provider.generate_response([], tools=[{"type": "function"}]))
    assert len(session.payloads) == 5
    assert [call.args[0] for call in retry_sleep.await_args_list] == [20, 30, 40]


@pytest.mark.parametrize("payload", [b'{"secret-prompt":broken}', b"\xff"])
def test_malformed_json_has_safe_typed_diagnostics(payload, caplog):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=1
    )
    provider.available = True
    provider._session = FakeSession(StreamResponse([payload], "application/json"))
    with pytest.raises(ProviderResponseError, match="JSON decoding failed") as exc:
        asyncio.run(provider.generate_response([]))
    assert exc.value.__suppress_context__
    assert "secret-prompt" not in caplog.text
    assert "content_type=application/json" in caplog.text


@pytest.mark.parametrize("content_type", ["text/plain", "", "private-header-secret"])
def test_requested_json_ignores_mismatched_mime_validation(content_type, retry_sleep):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=2
    )
    provider.available = True
    empty = StreamResponse(
        [b'{"choices":[{"message":{"content":""}}]}'], "application/json"
    )
    response = StreamResponse(
        [b'{"choices":[{"message":{"content":"hello"}}]}'], content_type
    )
    session = FakeSequenceSession([empty, response])
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "hello"
    assert session.payloads[1]["stream"] is False
    assert response.json_calls == 1


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_retryable_http_status_uses_five_attempts_without_body_dumps(
    status, retry_sleep, caplog
):
    provider = OllamaProvider("http://example.test", "model", 8192, 0.6)
    provider.available = True
    session = FakeSession(FakeErrorResponse(status, "private-response-secret"))
    provider._session = session
    with pytest.raises(RuntimeError, match=f"transient HTTP {status}") as exc:
        asyncio.run(provider.generate_response([]))
    assert len(session.payloads) == 5
    assert [call.args[0] for call in retry_sleep.await_args_list] == [10, 20, 30, 40]
    assert "private-response-secret" not in str(exc.value)
    assert "private-response-secret" not in caplog.text


@pytest.mark.parametrize("status", [501, 505])
def test_non_transient_http_status_does_not_retry_same_endpoint(status, retry_sleep):
    provider = OllamaProvider("http://example.test", "model", 8192, 0.6)
    provider.available = True
    session = FakeSession(FakeErrorResponse(status, "not supported"))
    provider._session = session
    with pytest.raises(RuntimeError, match=f"Provider API error: {status}"):
        asyncio.run(provider.generate_response([]))
    assert len(session.payloads) == 1
    retry_sleep.assert_not_awaited()


def test_empty_json_message_keys_are_not_logged(caplog):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=1
    )
    provider.available = True
    response = StreamResponse(
        [b'{"choices":[{"message":{"content":"","private-key-secret":1}}]}'],
        "application/json",
    )
    provider._session = FakeSession(response)
    with pytest.raises(RuntimeError, match="Empty response"):
        asyncio.run(provider.generate_response([]))
    assert "message_field_count=2" in caplog.text
    assert "private-key-secret" not in caplog.text


@pytest.mark.parametrize("response_format", ["sse", "json"])
@pytest.mark.parametrize("error", [None, {}])
def test_nullable_error_field_allows_success_but_empty_error_object_fails(
    response_format, error
):
    provider = OllamaProvider(
        "http://example.test", "model", 8192, 0.6, retry_attempts=1
    )
    provider.available = True
    field = "delta" if response_format == "sse" else "message"
    body = {"choices": [{field: {"content": "hello"}}], "error": error}
    if response_format == "sse":
        response = StreamResponse([b"data: " + json.dumps(body).encode() + b"\n\n"])
    else:
        response = StreamResponse([json.dumps(body).encode()], "application/json")
    provider._session = FakeSession(response)
    if error is None:
        assert asyncio.run(provider.generate_response([])) == "hello"
    else:
        with pytest.raises(ProviderUpstreamError):
            asyncio.run(provider.generate_response([]))


@pytest.mark.parametrize("prefix", [b"event: error\n", b""])
def test_explicit_error_marker_is_not_overridden_by_null_error(prefix):
    body = {"type": "error", "error": None, "choices": []}
    frame = prefix + b"data: " + json.dumps(body).encode() + b"\n\n"
    with pytest.raises(ProviderUpstreamError):
        asyncio.run(_read_sse_response(StreamResponse([CONTENT, frame])))
