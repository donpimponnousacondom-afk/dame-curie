import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bot_tools import (
    ImageGeneratorTool,
    _get_shared_session,
    close_shared_session,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
IMAGE_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
CDN = "https://cdn.discordapp.com/attachments/10/20/image.png"
PERMANENT = "https://images.example.invalid/bot/_images/image.png"


@pytest.fixture
def native_image(monkeypatch):
    config = SimpleNamespace(
        OPENAI_BASE_URL="https://chat.example.invalid/v1",
        OPENAI_API_KEY="synthetic-chat-key",
        OPENAI_MODEL="synthetic-chat-model",
        OPENAI_EXTRA_HEADERS={"X-Chat-Secret": "synthetic-chat-only"},
        OPENAI_EXTRA_BODY={"provider": {"only": ["synthetic-chat-provider"]}},
        IMAGE_GEN_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="http://127.0.0.1:8317/v1",
        IMAGE_GEN_API_KEY="synthetic-native-key",
        IMAGE_GEN_MODELS={"synthetic-image-a": "Illustration", "synthetic-image-b": "Editing"},
        IMAGE_GEN_MODEL="synthetic-image-a",
        IMAGE_GEN_QUALITY="low",
        IMAGE_GEN_TIMEOUT=300,
    )
    tool = ImageGeneratorTool(SimpleNamespace(
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
        persist=persist,
    )


@pytest.mark.parametrize("suffix", ["", "/", "/images/generations"])
@pytest.mark.parametrize("model", ["synthetic-image-a", "synthetic-image-b"])
def test_native_generation_ignores_extra_overrides_and_delivers(native_image, suffix, model):
    case = native_image
    case.tool.bot.config.IMAGE_GEN_BASE_URL = "http://127.0.0.1:8317/v1" + suffix
    result = asyncio.run(case.tool.execute(
        case.message, auto_send=True, prompt="a red fox", model=model,
        size="1024x1024", base_url="https://untrusted.example.invalid/v1",
        api_key="untrusted-credential",
    ))

    case.session.post.assert_called_once()
    args, kwargs = case.session.post.call_args
    assert args == ("http://127.0.0.1:8317/v1/images/generations",)
    assert kwargs["json"] == {
        "model": model, "prompt": "a red fox", "quality": "low",
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
    assert result.startswith("__IMAGE_SENT__ ")
    assert f"Permanent URL: {PERMANENT}" in result
    assert "Local path: /synthetic/image.png" in result
    assert f"Image URL: {CDN}" in result
    assert "do not resend" in result


@pytest.mark.parametrize("quality", ["low", "high", "xhigh", "max", "auto"])
def test_native_profile_settings_are_sent_without_claiming_response_quality(native_image, quality):
    case = native_image
    case.tool.bot.config.IMAGE_GEN_QUALITY = quality
    case.tool.bot.config.IMAGE_GEN_TIMEOUT = 600
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert not result.startswith("Error")
    assert case.session.post.call_args.kwargs["json"]["quality"] == quality
    assert case.session.post.call_args.kwargs["timeout"].total == 600
    assert "unexpected-provider-size" not in result
    assert "low quality" not in result


@pytest.mark.parametrize("base", [None, "", "   ", "/"])
def test_native_missing_base_never_uses_chat_configuration(native_image, base):
    case = native_image
    if base is None:
        delattr(case.tool.bot.config, "IMAGE_GEN_BASE_URL")
    else:
        setattr(case.tool.bot.config, "IMAGE_GEN_BASE_URL", base)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "IMAGE_GEN_BASE_URL" in result
    case.get_session.assert_not_awaited()
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("key", [None, ""])
def test_native_keyless_endpoint_never_borrows_chat_or_other_image_key(native_image, key):
    case = native_image
    if key is None:
        delattr(case.tool.bot.config, "IMAGE_GEN_API_KEY")
    else:
        setattr(case.tool.bot.config, "IMAGE_GEN_API_KEY", key)
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert not result.startswith("Error")
    assert case.session.post.call_args.kwargs["headers"] == {"Content-Type": "application/json"}


def test_unknown_image_protocol_fails_before_requests(native_image):
    case = native_image
    setattr(case.tool.bot.config, "IMAGE_GEN_PROTOCOL", "typo")
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "IMAGE_GEN_PROTOCOL" in result
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


@pytest.mark.parametrize("image", [IMAGE_URI, [IMAGE_URI], json.dumps([IMAGE_URI])])
def test_native_edit_preserves_original_reference_bytes(native_image, image):
    case = native_image
    result = asyncio.run(case.tool.execute(
        case.message, auto_send=True, prompt="make it blue", image=image,
        model="synthetic-image-b", quality="max",
    ))

    case.session.post.assert_called_once()
    args, kwargs = case.session.post.call_args
    assert args == ("http://127.0.0.1:8317/v1/images/edits",)
    assert kwargs["json"] == {
        "model": "synthetic-image-b", "prompt": "make it blue", "quality": "max",
        "images": [{"image_url": IMAGE_URI}],
        "output_format": "png", "response_format": "b64_json", "n": 1,
    }
    assert result.startswith("__IMAGE_SENT__ ")
    assert "from 1 input image" in result
    assert "Edited image" in case.tool.bot.memory.add_to_channel_memory.await_args.args[1]["content"]


def test_native_auto_attachments_keep_four_reference_limit(native_image, monkeypatch):
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


def test_native_reference_failure_does_not_submit_generation(native_image, monkeypatch):
    case = native_image
    monkeypatch.setattr(case.tool, "_load_one", AsyncMock(return_value=(None, "unavailable reference")))
    result = asyncio.run(case.tool.execute(
        case.message, prompt="change it", image="https://example.invalid/input.png",
    ))
    assert result == "Error: unavailable reference"
    case.get_session.assert_not_awaited()
    case.session.post.assert_not_called()


def test_native_failed_edit_never_falls_back_to_generation(native_image):
    case = native_image
    case.session.post.return_value.text.return_value = "{}"
    result = asyncio.run(case.tool.execute(case.message, auto_send=True, prompt="change it", image=IMAGE_URI))
    assert result.startswith("Error:")
    assert "may have been billed" not in result
    case.session.post.assert_called_once()
    assert case.session.post.call_args.args == ("http://127.0.0.1:8317/v1/images/edits",)
    case.message.channel.send.assert_not_awaited()


def test_native_private_http_reference_uses_existing_fetch_rules(native_image, monkeypatch):
    case = native_image
    reference = "http://127.0.0.1:8317/private.png"
    case.session.get.return_value = case.session.post.return_value
    monkeypatch.setattr("bot_tools._read_response_limited", AsyncMock(return_value=PNG))
    result = asyncio.run(case.tool.execute(case.message, prompt="change it", image=reference))
    assert not result.startswith("Error")
    case.session.get.assert_called_once()
    assert case.session.get.call_args.args == (reference,)
    assert case.session.get.call_args.kwargs["allow_redirects"] is False
    assert case.session.post.call_args.args == ("http://127.0.0.1:8317/v1/images/edits",)
    assert case.session.post.call_args.kwargs["json"]["images"] == [{"image_url": IMAGE_URI}]


@pytest.mark.parametrize("allowed", [False, True])
def test_native_local_reference_uses_existing_allowed_image_paths(native_image, tmp_path, allowed):
    case = native_image
    case.tool.bot.config.DAME_CURIE_SITE_DIR = str(tmp_path / "site")
    directory = tmp_path / "site" / "_images" if allowed else tmp_path / "outside"
    directory.mkdir(parents=True)
    reference = directory / "reference.png"
    reference.write_bytes(PNG)
    result = asyncio.run(case.tool.execute(case.message, prompt="edit", image=str(reference)))
    if allowed:
        assert not result.startswith("Error")
        assert case.session.post.call_args.kwargs["json"]["images"] == [{"image_url": IMAGE_URI}]
    else:
        assert "outside the allowed image dirs" in result
        case.get_session.assert_not_awaited()
        case.session.post.assert_not_called()


def test_native_local_reference_retains_file_size_limit(native_image, tmp_path, monkeypatch):
    case = native_image
    case.tool.bot.config.DAME_CURIE_SITE_DIR = str(tmp_path)
    directory = tmp_path / "_images"
    directory.mkdir()
    reference = directory / "reference.png"
    reference.write_bytes(PNG)
    monkeypatch.setattr("bot_tools.os.path.getsize", lambda path: case.tool.MAX_INPUT_BYTES + 1)
    result = asyncio.run(case.tool.execute(case.message, prompt="edit", image=str(reference)))
    assert "file too large" in result
    case.session.post.assert_not_called()


def test_native_remote_reference_refuses_redirect(native_image):
    case = native_image
    case.session.get.return_value = case.session.post.return_value
    case.session.get.return_value.status = 302
    result = asyncio.run(case.tool.execute(case.message, prompt="edit", image="https://images.example.invalid/ref.png"))
    assert "redirects; pass the direct image URL" in result
    assert case.session.get.call_args.kwargs["allow_redirects"] is False
    case.session.post.assert_not_called()


def test_native_remote_reference_retains_byte_limit(native_image, monkeypatch):
    case = native_image
    case.session.get.return_value = case.session.post.return_value
    read_image = AsyncMock(return_value=PNG)
    monkeypatch.setattr("bot_tools._read_response_limited", read_image)
    result = asyncio.run(case.tool.execute(case.message, prompt="edit", image="https://images.example.invalid/ref.png"))
    assert not result.startswith("Error")
    read_image.assert_awaited_once_with(case.session.get.return_value, case.tool.MAX_INPUT_BYTES)
    assert case.session.post.call_args.kwargs["json"]["images"] == [{"image_url": IMAGE_URI}]


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
        await close_shared_session()
        server = await asyncio.start_server(respond, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            setattr(case.tool.bot.config, "IMAGE_GEN_BASE_URL", f"http://127.0.0.1:{port}/v1")
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
    assert payload["model"] == "synthetic-image-a"
    case.message.channel.send.assert_awaited_once()
