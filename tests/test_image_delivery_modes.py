import asyncio
import base64
import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot_tools import HDImageGeneratorTool, ImageGeneratorTool, SendFileTool, SendMediaTool
from tool_schemas import TOOL_PARAMETERS, result_contract


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
CDN = "https://cdn.discordapp.com/attachments/10/20/image.png"


@pytest.fixture(params=["pollinations", "normal-native", "hd-native", "hd-chat"])
def image_delivery(request, monkeypatch, tmp_path):
    profile = request.param
    config = SimpleNamespace(
        MAXWELL_SITE_DIR=str(tmp_path / "site"),
        MAXWELL_PUBLIC_BASE_URL="https://images.example.invalid",
        IMAGE_GEN_PROTOCOL="pollinations" if profile == "pollinations" else "images",
        IMAGE_GEN_BASE_URL="https://normal.example.invalid/v1",
        POLLINATIONS_MODEL="flux",
        GEMINI_IMAGE_PROTOCOL="images" if profile == "hd-native" else "chat_completions",
        GEMINI_IMAGE_BASE_URL="https://hd.example.invalid/v1",
    )
    bot = SimpleNamespace(
        config=config,
        memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    )
    tool = HDImageGeneratorTool(bot) if profile.startswith("hd-") else ImageGeneratorTool(bot)
    posted = SimpleNamespace(attachments=[SimpleNamespace(url=CDN)])
    message = SimpleNamespace(
        attachments=[], reply=AsyncMock(return_value=posted),
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=posted)),
    )
    response = MagicMock(status=200, headers={"Content-Type": "image/png"})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    encoded = base64.b64encode(PNG).decode()
    payload = (
        {"choices": [{"message": {"images": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}},
        ]}}]}
        if profile == "hd-chat" else {"data": [{"b64_json": encoded}]}
    )
    response.text = AsyncMock(return_value=json.dumps(payload))
    session = MagicMock()
    session.get.return_value = response
    session.post.return_value = response
    monkeypatch.setattr("bot_tools._get_shared_session", AsyncMock(return_value=session))
    monkeypatch.setattr("bot_tools._read_response_limited", AsyncMock(return_value=PNG))
    signal = MagicMock()
    monkeypatch.setattr(tool, "_signal_streaming", signal)
    return SimpleNamespace(
        tool=tool, message=message, session=session, response=response,
        signal=signal, site=tmp_path / "site", profile=profile,
    )


@pytest.mark.parametrize("arguments", [{}, {"auto_send": False}])
def test_default_image_generation_persists_without_delivery(image_delivery, arguments):
    case = image_delivery
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox", **arguments))
    paths = list(case.site.glob("_images/*.png"))
    assert len(paths) == 1
    assert paths[0].read_bytes() == PNG
    assert paths[0].with_suffix(".txt").read_bytes() == b"a red fox"
    assert set(case.site.glob("_images/*")) == {paths[0], paths[0].with_suffix(".txt")}
    assert "generated, NOT sent" in result
    assert f"Local path: {paths[0]}" in result
    assert f"Permanent URL: https://images.example.invalid/bot/_images/{paths[0].name}" in result
    assert f'send_file(path="{paths[0]}", caption="...")' in result
    assert "normal image-preview link" in result
    assert "__IMAGE_SENT__" not in result
    assert "Image URL:" not in result
    case.message.channel.send.assert_not_awaited()
    case.message.reply.assert_not_awaited()
    case.signal.assert_not_called()
    case.tool.bot.memory.add_to_channel_memory.assert_awaited_once()
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_auto_send_uploads_exactly_once_with_terminal_marker(image_delivery):
    case = image_delivery
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox", auto_send=True))
    assert result.startswith("__IMAGE_SENT__ ")
    assert "sent to chat:" in result
    assert "do not resend the image or its URL" in result
    assert "No commentary needed" in result
    assert f"Image URL: {CDN}" in result
    paths = list(case.site.glob("_images/*.png"))
    assert len(paths) == 1
    assert paths[0].read_bytes() == PNG
    assert paths[0].with_suffix(".txt").read_bytes() == b"a red fox"
    assert set(case.site.glob("_images/*")) == {paths[0], paths[0].with_suffix(".txt")}
    case.message.channel.send.assert_awaited_once()
    assert case.message.channel.send.await_args.kwargs["file"].fp.getvalue() == PNG
    case.message.reply.assert_not_awaited()
    case.signal.assert_called_once_with(case.message)
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_default_persistence_failure_is_not_delivery_or_regeneration(image_delivery, tmp_path):
    case = image_delivery
    blocked = tmp_path / "not-a-directory"
    blocked.write_bytes(b"synthetic blocker")
    case.tool.bot.config.MAXWELL_SITE_DIR = str(blocked)
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "saving the local/public copy failed" in result
    assert "NOT sent" in result
    assert "not retried" in result
    assert "do not automatically repeat image generation" in result
    assert "__IMAGE_SENT__" not in result
    case.message.channel.send.assert_not_awaited()
    case.message.reply.assert_not_awaited()
    case.tool.bot.memory.add_to_channel_memory.assert_not_awaited()
    assert case.session.get.call_count + case.session.post.call_count == 1


@pytest.mark.parametrize("auto_send", [False, True])
def test_generation_error_has_no_success_marker_or_retry(image_delivery, auto_send):
    case = image_delivery
    case.response.status = 503
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox", auto_send=auto_send))
    assert result.startswith("Error")
    assert "__IMAGE_SENT__" not in result
    assert list(case.site.glob("_images/*")) == []
    case.message.channel.send.assert_not_awaited()
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_upload_failure_has_no_success_marker_and_keeps_generated_file(image_delivery):
    case = image_delivery
    case.message.channel.send.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions",
    )
    result = asyncio.run(case.tool.execute(case.message, prompt="a red fox", auto_send=True))
    assert result.startswith("Error:")
    assert "__IMAGE_SENT__" not in result
    paths = list(case.site.glob("_images/*.png"))
    assert len(paths) == 1
    assert paths[0].read_bytes() == PNG
    assert paths[0].with_suffix(".txt").read_bytes() == b"a red fox"
    assert set(case.site.glob("_images/*")) == {paths[0], paths[0].with_suffix(".txt")}
    case.message.channel.send.assert_awaited_once()
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_generated_path_can_be_presented_once_with_caption(image_delivery):
    case = image_delivery
    asyncio.run(case.tool.execute(case.message, prompt="a red fox"))
    path = next(case.site.glob("_images/*.png"))
    assert path.with_suffix(".txt").read_bytes() == b"a red fox"
    result = asyncio.run(SendFileTool(case.tool.bot).execute(
        case.message, path=str(path), caption="Here is your fox.",
    ))
    assert result.startswith("__FILE_SENT__")
    assert result.endswith("\n__CAPTION_SENT__")
    case.message.reply.assert_awaited_once()
    assert case.message.reply.await_args.kwargs["content"] == "Here is your fox."
    assert case.message.reply.await_args.kwargs["file"].fp.getvalue() == PNG
    case.message.channel.send.assert_not_awaited()


@pytest.fixture(params=["inline", "path", "media"])
def caption_delivery(request, monkeypatch, tmp_path):
    config = SimpleNamespace(MAXWELL_SITE_DIR=str(tmp_path))
    bot = SimpleNamespace(config=config)
    posted = SimpleNamespace(attachments=[SimpleNamespace(url=CDN)])
    message = SimpleNamespace(
        reply=AsyncMock(return_value=posted),
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=posted)),
    )
    path = tmp_path / "image.png"
    path.write_bytes(PNG)
    tool = SendMediaTool(bot) if request.param == "media" else SendFileTool(bot)
    arguments = {
        "inline": {"filename": "image.png", "content": base64.b64encode(PNG).decode(), "encoding": "base64"},
        "path": {"path": str(path)},
        "media": {"url": "https://images.example.invalid/image.png"},
    }[request.param]
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get.return_value = response
    monkeypatch.setattr("bot_tools._is_safe_url", lambda url: True)
    monkeypatch.setattr("bot_tools._get_shared_session", AsyncMock(return_value=session))
    monkeypatch.setattr("bot_tools._read_response_limited", AsyncMock(return_value=PNG))
    return SimpleNamespace(tool=tool, message=message, arguments=arguments, session=session)


@pytest.mark.parametrize("caption", [None, "", "A fox, as requested."])
def test_caption_uses_same_attachment_message_without_changing_default(caption_delivery, caption):
    case = caption_delivery
    arguments = case.arguments | ({"caption": caption} if caption is not None else {})
    result = asyncio.run(case.tool.execute(case.message, **arguments))
    prefix = "__MEDIA_SENT__" if isinstance(case.tool, SendMediaTool) else "__FILE_SENT__"
    assert result.startswith(prefix)
    assert ("__CAPTION_SENT__" in result) is bool(caption)
    case.message.reply.assert_awaited_once()
    sent = case.message.reply.await_args.kwargs
    assert sent["file"].fp.getvalue() == PNG
    if caption:
        assert sent["content"] == caption
    else:
        assert "content" not in sent
    case.message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("extra", [0, 1])
def test_caption_limits_never_split_into_extra_messages(caption_delivery, extra):
    case = caption_delivery
    caption = "x" * (2000 + extra)
    result = asyncio.run(case.tool.execute(case.message, caption=caption, **case.arguments))
    if extra:
        assert result.startswith("Error:")
        assert "__CAPTION_SENT__" not in result
        case.message.reply.assert_not_awaited()
        case.session.get.assert_not_called()
    else:
        assert "__CAPTION_SENT__" in result
        case.message.reply.assert_awaited_once()
        assert case.message.reply.await_args.kwargs["content"] == caption
    case.message.channel.send.assert_not_awaited()


def test_caption_failure_has_no_delivery_markers(caption_delivery):
    case = caption_delivery
    case.message.reply.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "Missing Permissions",
    )
    result = asyncio.run(case.tool.execute(case.message, caption="A fox.", **case.arguments))
    assert result.startswith("Error")
    assert "__CAPTION_SENT__" not in result
    assert "__FILE_SENT__" not in result
    assert "__MEDIA_SENT__" not in result
    case.message.reply.assert_awaited_once()
    case.message.channel.send.assert_not_awaited()


def test_send_file_missing_reply_parent_keeps_caption_in_fallback_post():
    posted = SimpleNamespace(attachments=[SimpleNamespace(url=CDN)])
    message = SimpleNamespace(
        reply=AsyncMock(side_effect=discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found"), {"code": 10008, "message": "Unknown Message"},
        )),
        channel=SimpleNamespace(send=AsyncMock(return_value=posted)),
    )
    result = asyncio.run(SendFileTool(None).execute(
        message, filename="note.txt", content="note", caption="Your note.",
    ))
    assert result.startswith("__FILE_SENT__")
    assert result.endswith("\n__CAPTION_SENT__")
    message.channel.send.assert_awaited_once()
    assert message.channel.send.await_args.kwargs["content"] == "Your note."
    assert message.channel.send.await_args.kwargs["file"].fp.getvalue() == b"note"


@pytest.mark.parametrize("name,tool_class", [
    ("image_generator", ImageGeneratorTool), ("hd_image", HDImageGeneratorTool),
])
def test_image_schema_and_prompt_describe_conditional_delivery(name, tool_class):
    parameters = TOOL_PARAMETERS[name]
    auto_send = parameters["properties"]["auto_send"]
    assert auto_send["type"] == "boolean"
    assert auto_send["default"] is False
    assert "auto_send" not in parameters.get("required", [])
    assert inspect.signature(tool_class.execute).parameters["auto_send"].default is False
    description = tool_class(None).get_description()
    assert "default false" in description
    assert "send_file(path=..., caption=...)" in description
    assert "__IMAGE_SENT__" in description
    assert "auto_send=true" in result_contract(name)


@pytest.mark.parametrize("name", ["send_file", "send_media"])
def test_caption_schema_is_optional_string(name):
    parameters = TOOL_PARAMETERS[name]
    assert parameters["properties"]["caption"]["type"] == "string"
    assert "caption" not in parameters.get("required", [])
