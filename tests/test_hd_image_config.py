import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot_tools import HDImageGeneratorTool


@pytest.fixture
def hd_image(monkeypatch):
    config = SimpleNamespace(
        OLLAMA_BASE_URL="https://openrouter.ai/api/v1",
        OLLAMA_API_KEY="synthetic-chat-key",
        OLLAMA_MODEL="synthetic-chat-model",
        OLLAMA_EXTRA_BODY={"provider": {"only": ["synthetic-chat-provider"]}},
        GEMINI_IMAGE_BASE_URL="",
        GEMINI_IMAGE_API_KEY="",
    )
    tool = HDImageGeneratorTool(
        SimpleNamespace(
            config=config,
            memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
            _current_progress_by_channel={},
        )
    )
    message = SimpleNamespace(
        attachments=[],
        channel=SimpleNamespace(
            id=42,
            send=AsyncMock(return_value=SimpleNamespace(attachments=[])),
        ),
    )
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(
        return_value=json.dumps(
            {"choices": [{"message": {"content": "data:image/png;base64,aW1hZ2U="}}]}
        )
    )
    session = MagicMock()
    session.post.return_value = response
    get_session = AsyncMock(return_value=session)
    monkeypatch.setattr("bot_tools._get_shared_session", get_session)
    monkeypatch.setattr("bot_tools._persist_public_image", MagicMock(return_value=("", "")))
    return tool, message, session, get_session


@pytest.mark.parametrize("base", [None, "", "   ", "/"])
@pytest.mark.parametrize("image", [None, "https://example.invalid/input.png"])
def test_chat_openrouter_settings_cannot_enable_hd_image(hd_image, monkeypatch, base, image):
    tool, message, session, get_session = hd_image
    if base is None:
        del tool.bot.config.GEMINI_IMAGE_BASE_URL
    else:
        tool.bot.config.GEMINI_IMAGE_BASE_URL = base
    message.attachments = [
        SimpleNamespace(
            url="https://example.invalid/attachment.png",
            content_type="image/png",
            filename="attachment.png",
        )
    ]
    load_image = AsyncMock(return_value=(b"image", ""))
    monkeypatch.setattr(tool, "_load_one", load_image)

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox", image=image))

    assert result == (
        "Error: HD image generation is not configured "
        "(set GEMINI_IMAGE_BASE_URL explicitly; chat settings are not used)"
    )
    load_image.assert_not_awaited()
    get_session.assert_not_awaited()
    session.get.assert_not_called()
    session.post.assert_not_called()
    message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("suffix", ["", "/", "/chat/completions"])
@pytest.mark.parametrize("model", ["", "dedicated-image-model"])
def test_hd_image_uses_explicit_endpoint_and_key(hd_image, suffix, model):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1" + suffix
    tool.bot.config.GEMINI_IMAGE_API_KEY = "synthetic-image-key"
    tool.bot.config.GEMINI_IMAGE_MODEL = model

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    assert result.startswith("__IMAGE_SENT__ HD image generated successfully")
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args == ("https://images.example.invalid/v1/chat/completions",)
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer synthetic-image-key",
    }
    assert kwargs["json"] == {
        "model": model or "gemini-3.1-flash-image",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "a red fox"}]}],
    }
    message.channel.send.assert_awaited_once()


@pytest.mark.parametrize("key_present", [True, False])
def test_explicit_keyless_image_endpoint_never_borrows_chat_key(hd_image, key_present):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "http://127.0.0.1:1234/v1"
    if not key_present:
        del tool.bot.config.GEMINI_IMAGE_API_KEY

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    assert result.startswith("__IMAGE_SENT__ HD image generated successfully")
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args == ("http://127.0.0.1:1234/v1/chat/completions",)
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    message.channel.send.assert_awaited_once()


IMAGE_URI = "data:image/png;base64,aW1hZ2U="
IMAGE_PART = {"type": "image_url", "image_url": {"url": IMAGE_URI}}


@pytest.mark.parametrize(
    "response_message",
    [
        {"content": None, "images": [IMAGE_PART]},
        {"content": "", "images": [IMAGE_PART]},
        {"content": "Here is the image.", "images": [IMAGE_PART]},
        {"content": [{"type": "text", "text": "Here it is."}], "images": [IMAGE_PART]},
        {"content": [IMAGE_PART]},
        {"content": [{"type": "text", "text": "Here it is."}, IMAGE_PART]},
        {"content": IMAGE_URI, "images": [IMAGE_PART]},
        {"content": [{"type": "text", "text": f"![image]({IMAGE_URI})"}]},
    ],
)
def test_supported_image_responses_generate_and_upload_once(hd_image, response_message):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1"
    session.post.return_value.text.return_value = json.dumps(
        {"choices": [{"message": response_message, "finish_reason": "stop"}]}
    )

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    session.post.assert_called_once()
    assert result.startswith("__IMAGE_SENT__ HD image generated successfully")
    message.channel.send.assert_awaited_once()
    assert message.channel.send.await_args.kwargs["file"].fp.getvalue() == b"image"
    tool.bot.memory.add_to_channel_memory.assert_awaited_once()


@pytest.mark.parametrize(
    "response_body",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]},
        {"choices": [{"message": {"content": None, "refusal": "Request refused."}}]},
        {"choices": [{"message": {"content": "I cannot generate this image."}}]},
        {"choices": [{"message": {"content": "data:image/png;base64,a"}}]},
    ],
)
@pytest.mark.parametrize("editing", [False, True])
def test_unusable_response_does_not_repeat_billable_generation(
    hd_image, monkeypatch, response_body, editing
):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1"
    session.post.return_value.text.return_value = json.dumps(response_body)
    monkeypatch.setattr(tool, "_shrink", lambda raw: (raw, "image/png"))

    result = asyncio.run(
        tool.execute(message, auto_send=True, prompt="a red fox", image=IMAGE_URI if editing else None)
    )

    session.post.assert_called_once()
    message.channel.send.assert_not_awaited()
    assert result.startswith("Error:")
    assert "may have been billed" not in result
    assert "not retried" in result
    assert "do not automatically repeat" in result
    assert "reword" not in result.lower()
    assert "real people" not in result
    assert "image_generator" not in result


@pytest.mark.parametrize("status", [400, 429, 500, 502, 503])
@pytest.mark.parametrize("body", [
    "upstream unavailable",
    '{"error":{"message":"Safety rejection; request ID synthetic-hd-id.","type":"image_generation_user_error","code":"moderation_blocked"}}',
])
def test_http_error_does_not_repeat_billable_generation(hd_image, status, body):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1"
    session.post.return_value.status = status
    session.post.return_value.text.return_value = body

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    session.post.assert_called_once()
    message.channel.send.assert_not_awaited()
    assert f"API returned status {status}" in result
    assert body in result
    assert "may have been billed" not in result
    assert "not retried" in result


@pytest.mark.parametrize("error", [asyncio.TimeoutError, ConnectionError])
@pytest.mark.parametrize("stage", ["__aenter__", "text"])
def test_transport_failure_does_not_repeat_billable_generation(hd_image, error, stage):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1"
    getattr(session.post.return_value, stage).side_effect = error("response lost")

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    session.post.assert_called_once()
    message.channel.send.assert_not_awaited()
    assert result.startswith("Error")
    assert "may have been billed" not in result
    assert "not retried" in result


def test_non_json_response_does_not_repeat_billable_generation(hd_image):
    tool, message, session, _ = hd_image
    tool.bot.config.GEMINI_IMAGE_BASE_URL = "https://images.example.invalid/v1"
    session.post.return_value.text.return_value = "<html>upstream response lost</html>"

    result = asyncio.run(tool.execute(message, auto_send=True, prompt="a red fox"))

    session.post.assert_called_once()
    message.channel.send.assert_not_awaited()
    assert "non-JSON response" in result
    assert "may have been billed" not in result
    assert "not retried" in result
