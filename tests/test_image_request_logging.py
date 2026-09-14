import asyncio
import base64
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, quote, unquote, urlsplit

import aiohttp
import pytest

import error_reporting
from bot_tools import HDImageGeneratorTool, ImageGeneratorTool


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
REFERENCE = b"\x89PNG\r\n\x1a\nsynthetic-edit-reference-not-for-console"
REFERENCE_URI = "data:image/png;base64," + base64.b64encode(REFERENCE).decode()
LONG_PROMPT = '夜空の竜 🐉 — café e\u0301 "glass" \\ moon\n' * 180 + "EXACT PROMPT TAIL\n"
START = "Image request start "
DONE = "Image request done "


@pytest.fixture
def image_response():
    response = MagicMock(status=200, headers={"Content-Type": "image/png"})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({
        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
    }))
    return response


@pytest.fixture
def image_request(request, monkeypatch, tmp_path, caplog, image_response):
    profile = request.param
    config = SimpleNamespace(
        IMAGE_GEN_PROTOCOL="pollinations" if profile == "pollinations" else "images",
        IMAGE_GEN_BASE_URL="https://normal.example.invalid/v1",
        IMAGE_GEN_API_KEY="synthetic-normal-image-credential",
        IMAGE_GEN_MODEL="gpt-image-2.5-flare",
        IMAGE_GEN_QUALITY="low",
        IMAGE_GEN_TIMEOUT=321,
        GEMINI_IMAGE_PROTOCOL="chat_completions" if profile == "hd-chat" else "images",
        GEMINI_IMAGE_BASE_URL="https://hd.example.invalid/v1",
        GEMINI_IMAGE_API_KEY="synthetic-hd-image-credential",
        GEMINI_IMAGE_MODEL="gemini-synthetic-image" if profile == "hd-chat" else "gpt-image-2.5-sunburst",
        GEMINI_IMAGE_QUALITY="max",
        GEMINI_IMAGE_TIMEOUT=654,
        POLLINATIONS_MODEL="synthetic flux/雪",
    )
    bot = SimpleNamespace(
        config=config, memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    )
    tool = HDImageGeneratorTool(bot) if profile.startswith("hd-") else ImageGeneratorTool(bot)
    message = SimpleNamespace(
        attachments=[],
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=SimpleNamespace(attachments=[]))),
    )
    if profile == "hd-chat":
        image_response.text.return_value = json.dumps({"choices": [{"message": {"images": [
            {"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(PNG).decode(),
            }},
        ]}}]})
        monkeypatch.setattr(tool, "_shrink", MagicMock(return_value=(REFERENCE, "image/png")))
    session = MagicMock()
    session.post.return_value = image_response
    session.get.return_value = image_response
    monkeypatch.setattr("bot_tools._get_shared_session", AsyncMock(return_value=session))
    read_image = AsyncMock(return_value=PNG)
    monkeypatch.setattr("bot_tools._read_response_limited", read_image)
    persist = MagicMock(return_value=("/synthetic/image.png", "https://images.example.invalid/image.png"))
    monkeypatch.setattr("bot_tools._persist_public_image", persist)
    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    store = error_reporting.configure_incident_store(tmp_path / "incidents.json")
    caplog.set_level(logging.INFO, logger="bot_tools")
    return SimpleNamespace(
        tool=tool, message=message, session=session, response=image_response,
        read_image=read_image, persist=persist, store=store, profile=profile,
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


@pytest.mark.parametrize("image_request,model,inputs,auto_send", [
    ("normal-native", "gpt-image-2", 0, False),
    ("normal-native", "gpt-image-2.5", 0, True),
    ("normal-native", "gpt-image-2.5-flare", 0, False),
    ("hd-native", "gpt-image-2.5-sunburst", 0, True),
    ("hd-native", "gpt-image-2.5-sunburst", 2, False),
], indirect=["image_request"])
def test_native_logs_exact_transmitted_request(image_request, caplog, model, inputs, auto_send):
    case = image_request
    prefix = "GEMINI_IMAGE" if case.profile == "hd-native" else "IMAGE_GEN"
    setattr(case.tool.bot.config, prefix + "_MODEL", model)
    arguments = {"image": [REFERENCE_URI] * inputs} if inputs else {}
    result = asyncio.run(case.tool.execute(case.message, prompt=LONG_PROMPT, auto_send=auto_send, **arguments))

    start, _ = assert_request_pair(caplog)
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    call = case.session.post.call_args
    payload = call.kwargs["json"]
    assert start["tool"] == ("hd_image" if case.profile == "hd-native" else "image_generator")
    assert start["protocol"] == "images"
    assert start["operation"] == ("edits" if inputs else "generations")
    assert start["endpoint"] == call.args[0]
    assert start["model"] == payload["model"] == model
    assert start["prompt"] == payload["prompt"] == LONG_PROMPT
    assert start["quality"] == payload["quality"] == ("max" if case.profile == "hd-native" else "low")
    assert start["input_images"] == len(payload.get("images", [])) == inputs
    assert start["auto_send"] is auto_send
    assert start["timeout_s"] == call.kwargs["timeout"].total == (654 if prefix == "GEMINI_IMAGE" else 321)
    assert "requested_prompt" not in start
    assert case.message.channel.send.await_count == int(auto_send)
    assert "__IMAGE_SENT__" in result if auto_send else "generated, NOT sent" in result
    assert start["request_id"] not in result
    assert START not in result and DONE not in result
    assert case.store.get(0) is None
    for encoded in (base64.b64encode(REFERENCE).decode(), base64.b64encode(PNG).decode()):
        assert encoded not in "\n".join(record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("image_request", ["hd-chat"], indirect=True)
@pytest.mark.parametrize("inputs,auto_send", [(0, False), (2, True)])
def test_hd_chat_logs_exact_text_and_reference_count(image_request, caplog, inputs, auto_send):
    case = image_request
    arguments = {"image": [REFERENCE_URI] * inputs} if inputs else {}
    result = asyncio.run(case.tool.execute(case.message, prompt=LONG_PROMPT, auto_send=auto_send, **arguments))

    start, _ = assert_request_pair(caplog)
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    call = case.session.post.call_args
    payload = call.kwargs["json"]
    parts = payload["messages"][0]["content"]
    assert start["tool"] == "hd_image"
    assert start["protocol"] == "chat_completions"
    assert start["operation"] == ("edits" if inputs else "generations")
    assert start["endpoint"] == call.args[0] == "https://hd.example.invalid/v1/chat/completions"
    assert start["model"] == payload["model"] == "gemini-synthetic-image"
    assert start["prompt"] == parts[0]["text"] == LONG_PROMPT
    assert start["input_images"] == sum(part["type"] == "image_url" for part in parts) == inputs
    assert start["auto_send"] is auto_send
    assert start["timeout_s"] == call.kwargs["timeout"].total == 654
    assert start.get("quality") is None and "requested_prompt" not in start
    assert case.message.channel.send.await_count == int(auto_send)
    assert start["request_id"] not in result
    assert case.store.get(0) is None
    assert base64.b64encode(REFERENCE).decode() not in caplog.text
    assert base64.b64encode(PNG).decode() not in caplog.text


@pytest.mark.parametrize("image_request", ["pollinations"], indirect=True)
@pytest.mark.parametrize("prompt", ["雪の城\nsecond line", LONG_PROMPT], ids=["short", "truncated"])
def test_pollinations_logs_actual_limited_prompt_and_original(image_request, caplog, prompt):
    case = image_request
    result = asyncio.run(case.tool.execute(case.message, prompt=prompt))

    start, _ = assert_request_pair(caplog)
    case.session.get.assert_called_once()
    case.session.post.assert_not_called()
    call = case.session.get.call_args
    url = urlsplit(call.args[0])
    query = parse_qs(url.query)
    assert start["tool"] == "image_generator"
    assert start["protocol"] == "pollinations"
    assert start["operation"] == "generations"
    assert start["endpoint"] == "https://image.pollinations.ai/prompt/"
    assert start["prompt"] == unquote(url.path.removeprefix("/prompt/")) == prompt[:1500]
    assert start["model"] == query["model"][0] == "synthetic flux/雪"
    assert query["width"] == query["height"] == ["1024"]
    assert query["nologo"] == ["true"] and len(query["seed"]) == 1
    assert call.kwargs["allow_redirects"] is True
    assert start["input_images"] == 0
    assert start["auto_send"] is False
    assert start["timeout_s"] == call.kwargs["timeout"].total == 90
    assert start.get("quality") is None
    if len(prompt) > 1500:
        assert start["requested_prompt"] == prompt
    else:
        assert "requested_prompt" not in start
    assert "generated, NOT sent" in result
    case.message.channel.send.assert_not_awaited()
    assert case.store.get(0) is None


@pytest.mark.parametrize("image_request", ["normal-native"], indirect=True)
def test_overlapping_requests_keep_ids_and_completions_associated(image_request, caplog):
    case = image_request
    second = HDImageGeneratorTool(case.tool.bot)
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
        second_result = await second.execute(case.message, prompt="second 火\nHD")
        second_finished.set()
        return await first, second_result

    async def bounded_overlap():
        return await asyncio.wait_for(overlap(), timeout=2)

    results = asyncio.run(bounded_overlap())
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
        assert start["tool"] == done["tool"] == ("image_generator" if start["prompt"].startswith("first") else "hd_image")
        assert done["status"] == 200 and done["outcome"] == "success"
        assert done["image_bytes"] == len(PNG) + (len(b"second-image") if start["tool"] == "hd_image" else 0)
    assert all("generated, NOT sent" in result for result in results)
    assert case.store.get(0) is None


@pytest.mark.parametrize("image_request", ["normal-native", "hd-native", "hd-chat"], indirect=True)
def test_credentials_and_image_payloads_are_redacted_without_changing_http(image_request, caplog):
    case = image_request
    key = "synthetic-request-credential-843be"
    prefix = "IMAGE_GEN" if case.profile == "normal-native" else "GEMINI_IMAGE"
    base = f"https://url-user:url-password@images.example.invalid/v1/{key}?access_token=query-secret#fragment-secret"
    setattr(case.tool.bot.config, prefix + "_API_KEY", key)
    setattr(case.tool.bot.config, prefix + "_MODEL", "synthetic-model-" + key)
    setattr(case.tool.bot.config, prefix + "_BASE_URL", base)
    prompt = (
        f"paint 火 with {key}\nAuthorization: Bearer fake-authorization-secret\n"
        "Cookie: session=fake-cookie-secret\nKeep this final line intact."
    )
    arguments = {"image": REFERENCE_URI} if case.profile.startswith("hd-") else {}
    asyncio.run(case.tool.execute(case.message, prompt=prompt, **arguments))

    start, done = assert_request_pair(caplog)
    case.session.post.assert_called_once()
    call = case.session.post.call_args
    payload = call.kwargs["json"]
    sent_prompt = payload["messages"][0]["content"][0]["text"] if case.profile == "hd-chat" else payload["prompt"]
    assert sent_prompt == prompt
    assert payload["model"] == "synthetic-model-" + key
    assert call.kwargs["headers"]["Authorization"] == "Bearer " + key
    assert call.args[0].startswith(base)
    assert start["prompt"] == (
        "paint 火 with [REDACTED]\nAuthorization: [REDACTED]\n"
        "Cookie: [REDACTED]\nKeep this final line intact."
    )
    assert start["model"] == "synthetic-model-[REDACTED]"
    assert start["endpoint"] == "https://images.example.invalid/v1/[REDACTED]"
    assert start["input_images"] == int(case.profile.startswith("hd-"))
    messages = "\n".join(record.getMessage() for record in caplog.records)
    for secret in (key, "url-user", "url-password", "query-secret", "fragment-secret", "fake-authorization-secret", "fake-cookie-secret"):
        assert secret not in messages
    for encoded in (base64.b64encode(REFERENCE).decode(), base64.b64encode(PNG).decode()):
        assert encoded not in messages
    assert not {"headers", "authorization", "cookie", "api_key", "images", "messages", "b64_json"} & (start.keys() | done.keys())
    assert case.store.get(0) is None


@pytest.mark.parametrize("image_request", ["pollinations"], indirect=True)
def test_pollinations_redacts_secrets_in_sent_and_requested_prompts(image_request, caplog):
    case = image_request
    key = "synthetic-registered/credential+雪"
    error_reporting.register_secrets([key])
    prompt = f"draw 火 with {key}\n" + "x" * 1500 + f"\nrequested tail {key}"
    case.tool.bot.config.POLLINATIONS_MODEL = "flux-" + key
    asyncio.run(case.tool.execute(case.message, prompt=prompt))

    start, _ = assert_request_pair(caplog)
    case.session.get.assert_called_once()
    call = case.session.get.call_args
    url = urlsplit(call.args[0])
    assert unquote(url.path.removeprefix("/prompt/")) == prompt[:1500]
    assert parse_qs(url.query)["model"] == ["flux-" + key]
    assert start["prompt"] == prompt[:1500].replace(key, "[REDACTED]")
    assert start["requested_prompt"] == prompt.replace(key, "[REDACTED]")
    assert start["model"] == "flux-[REDACTED]"
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert key not in messages
    assert quote(key, safe="") not in messages
    assert case.store.get(0) is None


@pytest.mark.parametrize("image_request", ["normal-native", "hd-native", "hd-chat"], indirect=True)
@pytest.mark.parametrize("status,body,outcome,error_type", [
    (503, "synthetic upstream unavailable", "http_error", None),
    (200, "<html>synthetic non-JSON response</html>", "non_json", "JSONDecodeError"),
    (200, "{}", "decode_error", "KeyError"),
], ids=["http-error", "non-json", "bad-shape"])
def test_unusable_response_logs_failure_status_and_incident_once(image_request, caplog, status, body, outcome, error_type):
    case = image_request
    case.response.status = status
    case.response.text.return_value = body
    result = asyncio.run(case.tool.execute(case.message, prompt=LONG_PROMPT, auto_send=True))

    start, done = assert_request_pair(caplog, status=status, outcome=outcome)
    payload = case.session.post.call_args.kwargs["json"]
    sent_prompt = payload["messages"][0]["content"][0]["text"] if case.profile == "hd-chat" else payload["prompt"]
    assert start["prompt"] == sent_prompt == LONG_PROMPT
    assert result.startswith("Error:") and "not retried" in result
    assert done["incident_id"] == result.incident_id == case.store.get(0).incident_id
    assert case.store.get(0).context["image_request_id"] == done["request_id"]
    assert done.get("error_type") == error_type
    assert case.store.get(1) is None
    assert "prompt" not in case.store.get(0).context
    assert LONG_PROMPT not in case.store.get(0).format_report()
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()
    assert start["request_id"] not in result
    assert not done.get("image_bytes")


@pytest.mark.parametrize("image_request", ["pollinations"], indirect=True)
@pytest.mark.parametrize("status,outcome", [(503, "http_error"), (200, "decode_error")])
def test_pollinations_http_and_non_image_failures_log_completion(image_request, caplog, status, outcome):
    case = image_request
    case.response.status = status
    case.response.headers = {"Content-Type": "text/html"}
    case.response.text.return_value = "synthetic upstream error body"
    case.read_image.return_value = b"<html>synthetic non-image body</html>"
    result = asyncio.run(case.tool.execute(case.message, prompt="synthetic Pollinations failure", auto_send=True))

    _, done = assert_request_pair(caplog, status=status, outcome=outcome)
    assert result.startswith("Error")
    assert done["incident_id"] == result.incident_id == case.store.get(0).incident_id
    assert case.store.get(0).context["image_request_id"] == done["request_id"]
    assert not done.get("error_type")
    assert case.store.get(1) is None
    case.session.get.assert_called_once()
    case.session.post.assert_not_called()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("image_request", ["normal-native", "hd-native", "hd-chat", "pollinations"], indirect=True)
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
    body_reader = case.read_image if case.profile == "pollinations" else case.response.text
    target = case.response.__aenter__ if stage == "enter" else body_reader
    target.side_effect = exception
    result = asyncio.run(case.tool.execute(case.message, prompt="synthetic failure prompt", auto_send=True))

    _, done = assert_request_pair(caplog, status=status, outcome=outcome)
    assert result.startswith("Error")
    assert done["error_type"] == error_type
    assert done["incident_id"] == result.incident_id == case.store.get(0).incident_id
    assert case.store.get(0).context["image_request_id"] == done["request_id"]
    assert case.store.get(1) is None
    assert case.session.post.call_count + case.session.get.call_count == 1
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()
    assert not done.get("image_bytes")


@pytest.mark.parametrize("image_request", ["normal-native", "hd-native", "hd-chat", "pollinations"], indirect=True)
@pytest.mark.parametrize("stage,status", [("enter", None), ("body", 200)])
def test_cancellation_logs_completion_and_propagates_without_incident(image_request, caplog, stage, status):
    case = image_request
    body_reader = case.read_image if case.profile == "pollinations" else case.response.text
    target = case.response.__aenter__ if stage == "enter" else body_reader
    target.side_effect = asyncio.CancelledError("synthetic caller cancellation")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(case.tool.execute(case.message, prompt="cancelled 雪\nrequest", auto_send=True))

    _, done = assert_request_pair(caplog, status=status, outcome="cancelled")
    assert done["error_type"] == "CancelledError"
    assert done["incident_id"] is None
    assert case.store.get(0) is None
    assert case.session.post.call_count + case.session.get.call_count == 1
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("name,encoded", [
    ("image_generator", False), ("hd_image", False), ("hd_image", True),
], ids=["normal-raw", "hd-raw", "hd-percent-encoded"])
def test_dispatcher_redacts_image_result_before_console_clipping(name, encoded, monkeypatch, caplog):
    import bot as bot_module

    monkeypatch.setattr(error_reporting, "_store", None)
    monkeypatch.setattr(error_reporting, "_secrets", ())
    secret = "s/雪+synthetic-boundary-credential"
    error_reporting.register_secrets([secret])
    rendered_secret = quote(secret, safe="") if encoded else secret
    leading = "Generated image: "
    leading += "x" * (190 - len(leading))
    raw_result = leading + rendered_secret + "\nVerbatim model-facing tail 火"
    tool = SimpleNamespace(execute=AsyncMock(return_value=raw_result))
    breaker = SimpleNamespace(
        is_open=lambda tool_name: False, record_success=MagicMock(), record_failure=MagicMock(),
    )
    bot = SimpleNamespace(tools={name: tool}, _tool_breaker=breaker)
    message = SimpleNamespace(guild=None, channel=SimpleNamespace(id=42))
    trace = AsyncMock()
    monkeypatch.setattr(bot_module, "record_reasoning", trace)
    caplog.set_level(logging.INFO, logger="bot")

    result = asyncio.run(bot_module.MaxwellBot._execute_tool_by_name(
        bot, message, name, {"prompt": "synthetic dispatcher prompt"},
        disabled=set(), compatible={name},
    ))

    prefix = f"Tool {name} finished: "
    records = [record for record in caplog.records if record.name == "bot" and record.getMessage().startswith(prefix)]
    assert len(records) == 1 and records[0].levelno == logging.INFO
    assert records[0].getMessage() == prefix + leading + "[REDACTED]"
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert rendered_secret[:10] not in messages
    assert secret not in messages and quote(secret, safe="") not in messages
    assert result == f"Tool {name}: {raw_result}"
    trace.assert_awaited_once()
    assert trace.await_args.kwargs["result"] == raw_result
    tool.execute.assert_awaited_once_with(message, prompt="synthetic dispatcher prompt")
    breaker.record_success.assert_called_once_with(name)
    breaker.record_failure.assert_not_called()
