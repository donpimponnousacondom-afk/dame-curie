import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bot_tools import (
    HDImageGeneratorTool,
    ImageGeneratorTool,
    _get_shared_session,
    close_shared_session,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
IMAGE_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
CDN = "https://cdn.discordapp.com/attachments/10/20/image.png"
PERMANENT = "https://images.example.invalid/bot/_images/image.png"


@pytest.fixture(params=[ImageGeneratorTool, HDImageGeneratorTool], ids=["normal", "hd"])
def native_image(request, monkeypatch):
    hd = request.param is HDImageGeneratorTool
    prefix = "GEMINI_IMAGE" if hd else "IMAGE_GEN"
    config = SimpleNamespace(
        OLLAMA_BASE_URL="https://chat.example.invalid/v1",
        OLLAMA_API_KEY="synthetic-chat-key",
        OLLAMA_MODEL="synthetic-chat-model",
        OLLAMA_EXTRA_HEADERS={"X-Chat-Secret": "synthetic-chat-only"},
        OLLAMA_EXTRA_BODY={"provider": {"only": ["synthetic-chat-provider"]}},
        GEMINI_IMAGE_BASE_URL="https://hd.example.invalid/v1",
        GEMINI_IMAGE_API_KEY="synthetic-hd-key",
        IMAGE_GEN_BASE_URL="https://normal.example.invalid/v1",
        IMAGE_GEN_API_KEY="synthetic-normal-key",
    )
    setattr(config, prefix + "_PROTOCOL", "images")
    setattr(config, prefix + "_BASE_URL", "http://127.0.0.1:8317/v1")
    setattr(config, prefix + "_API_KEY", "synthetic-native-key")
    setattr(config, prefix + "_MODEL", "gpt-image-2.5")
    tool = request.param(SimpleNamespace(
        config=config,
        memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    ))
    message = SimpleNamespace(
        attachments=[],
        channel=SimpleNamespace(
            id=42,
            send=AsyncMock(return_value=SimpleNamespace(
                attachments=[SimpleNamespace(url=CDN + "?ex=abc&hm=123")],
            )),
        ),
    )
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({
        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
        "quality": "low",
        "size": "unexpected-provider-size",
    }))
    session = MagicMock()
    session.post.return_value = response
    get_session = AsyncMock(return_value=session)
    monkeypatch.setattr("bot_tools._get_shared_session", get_session)
    persist = MagicMock(return_value=("/synthetic/image.png", PERMANENT))
    monkeypatch.setattr("bot_tools._persist_public_image", persist)
    return SimpleNamespace(
        tool=tool, message=message, session=session, get_session=get_session,
        persist=persist, prefix=prefix, hd=hd,
    )


@pytest.mark.parametrize("suffix", ["", "/", "/images/generations"])
@pytest.mark.parametrize("model", [
    "gpt-image-2", "gpt-image-2.5", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
])
def test_native_generation_preserves_profile_and_explicit_delivery(native_image, suffix, model):
    case = native_image
    setattr(case.tool.bot.config, case.prefix + "_BASE_URL", "http://127.0.0.1:8317/v1" + suffix)
    setattr(case.tool.bot.config, case.prefix + "_MODEL", model)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))

    case.session.post.assert_called_once()
    args, kwargs = case.session.post.call_args
    assert args == ("http://127.0.0.1:8317/v1/images/generations",)
    assert kwargs["json"] == {
        "model": model, "prompt": "a red fox", "quality": "high" if case.hd else "low",
        "output_format": "png", "response_format": "b64_json", "n": 1,
    }
    assert kwargs["headers"] == {
        "Content-Type": "application/json", "Authorization": "Bearer synthetic-native-key",
    }
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"].total == 300
    case.session.get.assert_not_called()
    case.message.channel.send.assert_awaited_once()
    assert case.message.channel.send.await_args.kwargs["file"].fp.getvalue() == PNG
    case.persist.assert_called_once()
    assert case.persist.call_args.args[1] == PNG
    case.tool.bot.memory.add_to_channel_memory.assert_awaited_once()
    expected = "__IMAGE_SENT__ HD image generated successfully, sent to chat:" if case.hd else "__IMAGE_SENT__ Image sent to chat:"
    assert result.startswith(expected)
    assert f"Permanent URL: {PERMANENT}" in result
    assert "Local path: /synthetic/image.png" in result
    assert f"Image URL: {CDN}" in result
    assert "do not resend" in result


@pytest.mark.parametrize("quality", ["low", "high", "xhigh", "max", "auto"])
def test_native_profile_settings_are_sent_without_claiming_response_quality(native_image, quality):
    case = native_image
    setattr(case.tool.bot.config, case.prefix + "_QUALITY", quality)
    setattr(case.tool.bot.config, case.prefix + "_TIMEOUT", 600)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert not result.startswith("Error")
    assert case.session.post.call_args.kwargs["json"]["quality"] == quality
    assert case.session.post.call_args.kwargs["timeout"].total == 600
    assert "unexpected-provider-size" not in result
    assert "low quality" not in result


@pytest.mark.parametrize("base", [None, "", "   ", "/"])
def test_native_missing_base_never_uses_chat_other_image_profile_or_pollinations(native_image, base):
    case = native_image
    if base is None:
        delattr(case.tool.bot.config, case.prefix + "_BASE_URL")
    else:
        setattr(case.tool.bot.config, case.prefix + "_BASE_URL", base)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert case.prefix + "_BASE_URL" in result
    assert "chat settings are not used" in result
    case.get_session.assert_not_awaited()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("key", [None, ""])
def test_native_keyless_endpoint_never_borrows_chat_or_other_image_key(native_image, key):
    case = native_image
    if key is None:
        delattr(case.tool.bot.config, case.prefix + "_API_KEY")
    else:
        setattr(case.tool.bot.config, case.prefix + "_API_KEY", key)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert not result.startswith("Error")
    assert case.session.post.call_args.kwargs["headers"] == {"Content-Type": "application/json"}


def test_unknown_image_protocol_fails_before_requests(native_image):
    case = native_image
    setattr(case.tool.bot.config, case.prefix + "_PROTOCOL", "typo")
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert case.prefix + "_PROTOCOL" in result
    case.get_session.assert_not_awaited()


@pytest.mark.parametrize("body", [
    "<html>lost response</html>", "null", "[]", "{}",
    '{"data":[]}', '{"data":[{}]}', '{"data":[{"b64_json":""}]}',
    '{"data":[{"b64_json":"!invalid!"}]}', '{"data":[{"b64_json":null}]}',
    '{"data":[{"url":"https://example.invalid/image.png"}]}',
    '{"choices":[{"message":{"content":"not an image"}}]}',
])
def test_unusable_native_response_is_not_retried_or_sent_to_chat(native_image, body):
    case = native_image
    case.session.post.return_value.text.return_value = body
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "may have been billed" not in result
    assert "not retried" in result
    assert "do not automatically repeat" in result
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    case.message.channel.send.assert_not_awaited()
    case.persist.assert_not_called()


@pytest.mark.parametrize("status", [301, 307, 400, 401, 429, 500, 502, 503])
def test_native_http_error_is_not_retried_or_redirected(native_image, status):
    case = native_image
    case.session.post.return_value.status = status
    case.session.post.return_value.text.return_value = "upstream rejection; diagnostic_key=synthetic-native-key"
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert str(status) in result
    assert "may have been billed" not in result
    assert "upstream rejection" in result
    assert "synthetic-native-key" not in result
    case.session.post.assert_called_once()
    assert case.session.post.call_args.kwargs["allow_redirects"] is False
    case.session.get.assert_not_called()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("body", [
    json.dumps({"error": {
        "message": "Your request was rejected by the safety system. Request ID synthetic-moderation-id.",
        "type": "image_generation_user_error", "param": None, "code": "moderation_blocked",
        "moderation_details": {"moderation_stage": "output", "categories": ["other"]},
    }}, indent=2),
    "This rejection mentions quota but does not say the model has none.",
])
def test_native_rejection_returns_exact_upstream_reason_without_diagnosis(native_image, body):
    case = native_image
    case.session.post.return_value.status = 400
    case.session.post.return_value.text.return_value = body
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox"))
    assert body in result
    assert "status 400" in result
    assert "may have been billed" not in result
    assert "has no quota right now" not in result
    assert "not retried" in result
    case.session.post.assert_called_once()
    case.persist.assert_not_called()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("error", [TimeoutError, ConnectionError, aiohttp.ClientPayloadError])
@pytest.mark.parametrize("stage", ["__aenter__", "text"])
def test_native_transport_failure_is_not_retried(native_image, error, stage):
    case = native_image
    getattr(case.session.post.return_value, stage).side_effect = error("private transport detail")
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "may have been billed" not in result
    assert "not retried" in result
    assert "private transport" not in result
    case.session.post.assert_called_once()
    case.session.get.assert_not_called()
    case.message.channel.send.assert_not_awaited()


def test_native_cancellation_never_retries(native_image):
    case = native_image
    case.session.post.return_value.__aenter__.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    case.session.post.assert_called_once()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("native_image", [HDImageGeneratorTool], indirect=True)
@pytest.mark.parametrize("image", [IMAGE_URI, [IMAGE_URI], json.dumps([IMAGE_URI])])
def test_native_hd_edit_preserves_original_reference_bytes(native_image, monkeypatch, image):
    case = native_image
    shrink = MagicMock(side_effect=AssertionError("native HD must retain reference detail"))
    monkeypatch.setattr(case.tool, "_shrink", shrink)
    case.tool.bot.config.GEMINI_IMAGE_MODEL = "gpt-image-2.5-sunburst"
    case.tool.bot.config.GEMINI_IMAGE_QUALITY = "max"
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="make it blue", image=image))

    shrink.assert_not_called()
    case.session.post.assert_called_once()
    args, kwargs = case.session.post.call_args
    assert args == ("http://127.0.0.1:8317/v1/images/edits",)
    assert kwargs["json"] == {
        "model": "gpt-image-2.5-sunburst", "prompt": "make it blue", "quality": "max",
        "images": [{"image_url": IMAGE_URI}],
        "output_format": "png", "response_format": "b64_json", "n": 1,
    }
    assert result.startswith("__IMAGE_SENT__ HD image edited successfully, sent to chat:")
    assert "from 1 input image" in result
    assert "Edited HD image" in case.tool.bot.memory.add_to_channel_memory.await_args.args[1]["content"]


@pytest.mark.parametrize("native_image", [HDImageGeneratorTool], indirect=True)
def test_native_hd_auto_attachments_keep_four_reference_limit(native_image, monkeypatch):
    case = native_image
    case.message.attachments = [SimpleNamespace(
        url=f"https://example.invalid/{index}.png", content_type="image/png", filename="input.png",
    ) for index in range(6)]
    load = AsyncMock(return_value=(PNG, ""))
    monkeypatch.setattr(case.tool, "_load_one", load)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="combine these"))
    assert load.await_count == 4
    assert case.session.post.call_args.kwargs["json"]["images"] == [{"image_url": IMAGE_URI}] * 4
    assert "from 4 input images" in result
    case.session.post.assert_called_once()


@pytest.mark.parametrize("native_image", [HDImageGeneratorTool], indirect=True)
def test_native_hd_reference_failure_does_not_submit_generation(native_image, monkeypatch):
    case = native_image
    monkeypatch.setattr(case.tool, "_load_one", AsyncMock(return_value=(None, "unavailable reference")))
    result = asyncio.run(case.tool.execute(
        case.message, prompt="change it", image="https://example.invalid/input.png",
    ))
    assert result == "Error: unavailable reference"
    case.get_session.assert_not_awaited()
    case.session.post.assert_not_called()


@pytest.mark.parametrize("native_image", [HDImageGeneratorTool], indirect=True)
def test_native_hd_failed_edit_never_falls_back_to_generation(native_image):
    case = native_image
    case.session.post.return_value.text.return_value = "{}"
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="change it", image=IMAGE_URI))
    assert result.startswith("Error:")
    assert "may have been billed" not in result
    case.session.post.assert_called_once()
    assert case.session.post.call_args.args == ("http://127.0.0.1:8317/v1/images/edits",)
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("native_image", [HDImageGeneratorTool], indirect=True)
def test_native_hd_private_reference_remains_forbidden(native_image):
    case = native_image
    result = asyncio.run(case.tool.execute(
        case.message, prompt="change it", image="http://127.0.0.1:8317/private.png",
    ))
    assert "refusing to fetch private/internal URL" in result
    case.get_session.assert_not_awaited()
    case.session.post.assert_not_called()


def test_real_native_transport_accepts_configured_loopback_endpoint(native_image, monkeypatch):
    case = native_image
    received = []
    monkeypatch.setattr("bot_tools._get_shared_session", _get_shared_session)

    async def respond(reader, writer):
        headers = await reader.readuntil(b"\r\n\r\n")
        length = next(int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n")
                      if line.lower().startswith(b"content-length:"))
        received.append((headers, json.loads(await reader.readexactly(length))))
        body = json.dumps({"data": [{"b64_json": base64.b64encode(PNG).decode()}]}).encode()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                     + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def generate():
        server = await asyncio.start_server(respond, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            setattr(case.tool.bot.config, case.prefix + "_BASE_URL", f"http://127.0.0.1:{port}/v1")
            result = await case.tool.execute(case.message, auto_send=True, prompt="synthetic local image")
        await close_shared_session()
        return result

    result = asyncio.run(generate())
    assert not result.startswith("Error")
    assert len(received) == 1
    headers, payload = received[0]
    assert headers.startswith(b"POST /v1/images/generations HTTP/1.1\r\n")
    assert b"Authorization: Bearer synthetic-native-key\r\n" in headers
    assert b"synthetic-chat" not in headers
    assert payload["model"] == "gpt-image-2.5"
    case.message.channel.send.assert_awaited_once()
