import asyncio
import base64
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import aiohttp
import pytest

import error_reporting
from bot_tools import ImageGeneratorTool


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
REFERENCE = b"\x89PNG\r\n\x1a\nsynthetic-edit-reference-not-for-console"
REFERENCE_URI = "data:image/png;base64," + base64.b64encode(REFERENCE).decode()
LONG_PROMPT = '夜空の竜 🐉 — café e\u0301 "glass" \\ moon\n' * 180 + "EXACT PROMPT TAIL\n"
START = "Image request start "
DONE = "Image request done "


@pytest.fixture
def image_request(monkeypatch, tmp_path, caplog):
    config = SimpleNamespace(
        IMAGE_GEN_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        IMAGE_GEN_API_KEY="synthetic-image-credential",
        IMAGE_GEN_MODELS={
            "synthetic-image-a": "Illustrations",
            "synthetic-image-b": "Reference edits",
        },
        IMAGE_GEN_MODEL="synthetic-image-a",
        IMAGE_GEN_QUALITY="low",
        IMAGE_GEN_TIMEOUT=321,
    )
    tool = ImageGeneratorTool(SimpleNamespace(
        config=config, memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    ))
    message = SimpleNamespace(
        attachments=[],
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=SimpleNamespace(attachments=[]))),
    )
    response = MagicMock(status=200, headers={"Content-Type": "image/png"})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({
        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
    }))
    session = MagicMock()
    session.post.return_value = response
    monkeypatch.setattr("bot_tools._get_shared_session", AsyncMock(return_value=session))
    persist = MagicMock(return_value=("/synthetic/image.png", "https://images.example.invalid/image.png"))
    monkeypatch.setattr("bot_tools._persist_public_image", persist)
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    store = error_reporting.configure_incident_store(tmp_path / "incidents.json")
    caplog.set_level(logging.INFO, logger="bot_tools")
    return SimpleNamespace(
        tool=tool, message=message, session=session, response=response,
        persist=persist, store=store,
    )


def request_events(caplog):
    events = []
    for record in caplog.records:
        message = record.getMessage()
        if record.name == "bot_tools" and message.startswith((START, DONE)):
            assert record.levelno == logging.INFO
            assert "\n" not in message
            prefix = START if message.startswith(START) else DONE
            events.append((prefix, json.loads(message.removeprefix(prefix))))
    return events


def assert_request_pair(caplog, *, status=200, outcome="success"):
    events = request_events(caplog)
    assert [prefix for prefix, _ in events] == [START, DONE]
    start, done = [event for _, event in events]
    assert isinstance(start["request_id"], str) and start["request_id"]
    for field in ("request_id", "tool", "model", "endpoint"):
        assert done[field] == start[field]
    assert done["status"] == status
    assert type(done["status"]) is (int if status is not None else type(None))
    assert done["outcome"] == outcome
    assert isinstance(done["elapsed_ms"], (int, float)) and done["elapsed_ms"] >= 0
    if outcome == "success":
        assert done["image_bytes"] == len(PNG)
        assert done["format"] == "png"
        assert not done.get("incident_id")
    return start, done


@pytest.mark.parametrize("model,inputs,auto_send,quality", [
    (None, 0, False, None),
    ("synthetic-image-b", 0, True, "max"),
    ("synthetic-image-b", 2, False, "high"),
])
def test_native_logs_exact_transmitted_request(image_request, caplog, model, inputs, auto_send, quality):
    case = image_request
    arguments = {"image": [REFERENCE_URI] * inputs} if inputs else {}
    if model is not None:
        arguments["model"] = model
    if quality is not None:
        arguments["quality"] = quality
    result = asyncio.run(case.tool.execute(case.message, prompt=LONG_PROMPT, auto_send=auto_send, **arguments))

    start, _ = assert_request_pair(caplog)
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    call = case.session.post.call_args
    payload = call.kwargs["json"]
    assert start["tool"] == "image_generator"
    assert start["protocol"] == "images"
    assert start["operation"] == ("edits" if inputs else "generations")
    assert start["endpoint"] == call.args[0]
    assert start["model"] == payload["model"] == (model or "synthetic-image-a")
    assert start["prompt"] == payload["prompt"] == LONG_PROMPT
    assert start["quality"] == payload["quality"] == (quality or "low")
    assert start["input_images"] == len(payload.get("images", [])) == inputs
    assert start["auto_send"] is auto_send
    assert start["timeout_s"] == call.kwargs["timeout"].total == 321
    assert "requested_prompt" not in start
    assert case.message.channel.send.await_count == int(auto_send)
    assert "__IMAGE_SENT__" in result if auto_send else "NOT sent" in result
    assert start["request_id"] not in result
    assert START not in result and DONE not in result
    assert case.store.get(0) is None
    for encoded in (base64.b64encode(REFERENCE).decode(), base64.b64encode(PNG).decode()):
        assert encoded not in "\n".join(record.getMessage() for record in caplog.records)


def test_overlapping_requests_keep_ids_and_completions_associated(image_request, caplog):
    case = image_request
    second_response = MagicMock(status=200)
    second_response.__aenter__ = AsyncMock(return_value=second_response)
    second_response.__aexit__ = AsyncMock(return_value=None)
    second_response.text = AsyncMock(return_value=json.dumps({
        "data": [{"b64_json": base64.b64encode(PNG + b"second-image").decode()}],
    }))
    case.session.post.side_effect = [case.response, second_response]
    first_body = case.response.text.return_value

    async def overlap():
        first_reading = asyncio.Event()
        second_finished = asyncio.Event()

        async def first_text():
            first_reading.set()
            await second_finished.wait()
            return first_body

        case.response.text.side_effect = first_text
        first = asyncio.create_task(case.tool.execute(case.message, prompt="first 雪\nnormal"))
        await first_reading.wait()
        second_result = await case.tool.execute(
            case.message, prompt="second 火\nedit", image=REFERENCE_URI, model="synthetic-image-b",
        )
        second_finished.set()
        return await first, second_result

    results = asyncio.run(asyncio.wait_for(overlap(), timeout=2))
    events = request_events(caplog)
    assert [prefix for prefix, _ in events] == [START, START, DONE, DONE]
    starts = {event["request_id"]: event for prefix, event in events if prefix == START}
    dones = {event["request_id"]: event for prefix, event in events if prefix == DONE}
    assert len(starts) == len(dones) == 2 and starts.keys() == dones.keys()
    assert events[2][1]["request_id"] == events[1][1]["request_id"]
    assert case.session.post.call_count == 2
    for (_, start), call in zip(events[:2], case.session.post.call_args_list, strict=True):
        done = dones[start["request_id"]]
        assert start["prompt"] == call.kwargs["json"]["prompt"]
        assert start["model"] == done["model"] == call.kwargs["json"]["model"]
        assert start["endpoint"] == done["endpoint"] == call.args[0]
        assert start["tool"] == done["tool"] == "image_generator"
        assert start["operation"] == ("edits" if start["prompt"].startswith("second") else "generations")
        assert done["status"] == 200 and done["outcome"] == "success"
        assert done["image_bytes"] == len(PNG) + (len(b"second-image") if start["operation"] == "edits" else 0)
    assert all("NOT sent" in result for result in results)
    assert case.store.get(0) is None


@pytest.mark.parametrize("editing", [False, True])
def test_credentials_and_image_payloads_are_redacted_without_changing_http(image_request, caplog, editing):
    case = image_request
    key = "synthetic-request-credential-843be"
    base = f"https://url-user:url-password@images.example.invalid/v1/{key}?access_token=query-secret#fragment-secret"
    case.tool.bot.config.IMAGE_GEN_API_KEY = key
    selected = "synthetic-model-" + key
    case.tool.bot.config.IMAGE_GEN_MODELS[selected] = "Synthetic private model"
    case.tool.bot.config.IMAGE_GEN_BASE_URL = base
    prompt = (
        f"paint 火 with {key}\nAuthorization: Bearer fake-authorization-secret\n"
        "Cookie: session=fake-cookie-secret\nKeep this final line intact."
    )
    arguments = {"image": REFERENCE_URI} if editing else {}
    asyncio.run(case.tool.execute(case.message, prompt=prompt, model=selected, **arguments))

    start, done = assert_request_pair(caplog)
    call = case.session.post.call_args
    payload = call.kwargs["json"]
    assert payload["prompt"] == prompt and payload["model"] == selected
    assert call.kwargs["headers"]["Authorization"] == "Bearer " + key
    assert call.args[0].startswith(base)
    assert start["prompt"] == (
        "paint 火 with [REDACTED]\nAuthorization: [REDACTED]\n"
        "Cookie: [REDACTED]\nKeep this final line intact."
    )
    assert start["model"] == "synthetic-model-[REDACTED]"
    assert start["endpoint"] == "https://images.example.invalid/v1/[REDACTED]"
    assert start["input_images"] == int(editing)
    messages = "\n".join(record.getMessage() for record in caplog.records)
    for secret in (key, "url-user", "url-password", "query-secret", "fragment-secret", "fake-authorization-secret", "fake-cookie-secret"):
        assert secret not in messages
    for encoded in (base64.b64encode(REFERENCE).decode(), base64.b64encode(PNG).decode()):
        assert encoded not in messages
    assert not {"headers", "authorization", "cookie", "api_key", "images", "messages", "b64_json"} & (start.keys() | done.keys())
    assert case.store.get(0) is None


@pytest.mark.parametrize("status,body,outcome,error_type", [
    (503, "synthetic upstream unavailable", "http_error", None),
    (200, "<html>synthetic non-JSON response</html>", "non_json", "JSONDecodeError"),
    (200, "{}", "decode_error", "KeyError"),
], ids=["http-error", "non-json", "bad-shape"])
@pytest.mark.parametrize("editing", [False, True])
def test_unusable_response_logs_failure_status_and_incident_once(image_request, caplog, status, body, outcome, error_type, editing):
    case = image_request
    case.response.status = status
    case.response.text.return_value = body
    result = asyncio.run(case.tool.execute(
        case.message, prompt=LONG_PROMPT, auto_send=True, image=REFERENCE_URI if editing else None,
    ))

    start, done = assert_request_pair(caplog, status=status, outcome=outcome)
    assert start["prompt"] == case.session.post.call_args.kwargs["json"]["prompt"] == LONG_PROMPT
    assert result.startswith("Error:") and "not retried" in result
    assert done["incident_id"] == result.incident_id == case.store.get(0).incident_id
    assert case.store.get(0).context["image_request_id"] == done["request_id"]
    assert done.get("error_type") == error_type
    assert case.store.get(1) is None
    assert "prompt" not in case.store.get(0).context
    assert LONG_PROMPT not in case.store.get(0).format_report()
    case.session.post.assert_called_once()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()
    assert start["request_id"] not in result
    assert not done.get("image_bytes")


@pytest.mark.parametrize("failure,stage,status,outcome,error_type", [
    ("connector", "enter", None, "connection_error", "ClientConnectorError"),
    ("timeout", "enter", None, "timeout", "TimeoutError"),
    ("timeout", "body", 200, "timeout", "TimeoutError"),
    ("unexpected", "enter", None, "error", "RuntimeError"),
], ids=["connector", "connect-timeout", "body-timeout", "unexpected-error"])
def test_transport_failure_logs_received_status_without_retry(image_request, caplog, failure, stage, status, outcome, error_type):
    case = image_request
    exception = {
        "connector": aiohttp.ClientConnectorError(
            SimpleNamespace(host="images.example.invalid", port=443, ssl=True),
            ConnectionRefusedError(111, "synthetic connection refused"),
        ),
        "timeout": TimeoutError("synthetic timeout"),
        "unexpected": RuntimeError("synthetic unexpected request failure"),
    }[failure]
    target = case.response.__aenter__ if stage == "enter" else case.response.text
    target.side_effect = exception
    result = asyncio.run(case.tool.execute(case.message, prompt="synthetic failure prompt", auto_send=True))

    _, done = assert_request_pair(caplog, status=status, outcome=outcome)
    assert result.startswith("Error")
    assert done["error_type"] == error_type
    assert done["incident_id"] == result.incident_id == case.store.get(0).incident_id
    assert case.store.get(0).context["image_request_id"] == done["request_id"]
    assert case.store.get(1) is None
    case.session.post.assert_called_once()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()
    assert not done.get("image_bytes")


@pytest.mark.parametrize("stage,status", [("enter", None), ("body", 200)])
def test_cancellation_logs_completion_and_propagates_without_incident(image_request, caplog, stage, status):
    case = image_request
    target = case.response.__aenter__ if stage == "enter" else case.response.text
    target.side_effect = asyncio.CancelledError("synthetic caller cancellation")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(case.tool.execute(case.message, prompt="cancelled 雪\nrequest", auto_send=True))

    _, done = assert_request_pair(caplog, status=status, outcome="cancelled")
    assert done["error_type"] == "CancelledError"
    assert done["incident_id"] is None
    assert case.store.get(0) is None
    case.session.post.assert_called_once()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("encoded", [False, True], ids=["raw", "percent-encoded"])
@pytest.mark.parametrize("tool_name", ["image_generator", "shell"])
def test_dispatcher_redacts_image_result_without_changing_model_result(encoded, tool_name, monkeypatch, caplog):
    import bot as bot_module

    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    secret = "s/雪+synthetic-boundary-credential"
    error_reporting.register_secrets([secret])
    rendered_secret = quote(secret, safe="") if encoded else secret
    leading = "Synthetic tool result: " + "x" * 100_000
    raw_result = leading + rendered_secret + "\nVerbatim model-facing tail 火"
    tool = SimpleNamespace(execute=AsyncMock(return_value=raw_result))
    breaker = SimpleNamespace(
        is_open=lambda tool_name: False, record_success=MagicMock(), record_failure=MagicMock(),
    )
    bot = SimpleNamespace(tools={tool_name: tool}, _tool_breaker=breaker)
    message = SimpleNamespace(guild=None, channel=SimpleNamespace(id=42))
    trace = AsyncMock()
    monkeypatch.setattr(bot_module, "record_reasoning", trace)
    caplog.set_level(logging.INFO, logger="bot")

    params = {"prompt": "synthetic dispatcher prompt"} if tool_name == "image_generator" else {"command": "synthetic"}
    result = asyncio.run(bot_module.MaxwellBot._execute_tool_by_name(
        bot, message, tool_name, params,
        disabled=set(), compatible={tool_name},
    ))

    prefix = f"Tool {tool_name} finished: "
    records = [record for record in caplog.records if record.name == "bot" and record.getMessage().startswith(prefix)]
    assert len(records) == 1 and records[0].levelno == logging.INFO
    assert records[0].getMessage() == f"{prefix}{len(raw_result)} chars"
    assert len(records[0].getMessage().encode()) < 256
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert rendered_secret[:10] not in messages
    assert secret not in messages and quote(secret, safe="") not in messages
    assert result == f"Tool {tool_name}: {raw_result}"
    trace.assert_awaited_once()
    assert trace.await_args.kwargs["result"] == raw_result
    tool.execute.assert_awaited_once_with(message, **params)
    breaker.record_success.assert_called_once_with(tool_name)
    breaker.record_failure.assert_not_called()
