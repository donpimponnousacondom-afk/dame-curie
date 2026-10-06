import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot_tools
from bot_tools import ImageGeneratorTool


LOCAL = "http://127.0.0.1:8081"
LOCAL_SITE = LOCAL + "/bot"
PUBLIC = "https://redroom.zombiedawn.net/dame"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
URL_CASES = [
    pytest.param((None, LOCAL_SITE), id="unset"),
    pytest.param(("", LOCAL_SITE), id="empty"),
    pytest.param((" \t", LOCAL_SITE), id="whitespace"),
    pytest.param((PUBLIC, PUBLIC), id="explicit"),
    pytest.param((PUBLIC + "/", PUBLIC), id="trailing-slash"),
    pytest.param((" " + PUBLIC + "/// ", PUBLIC), id="surrounding-space-and-slashes"),
]


@pytest.fixture(params=URL_CASES)
def site_case(request, tmp_path, monkeypatch):
    override, expected = request.param
    monkeypatch.setenv("DAME_CURIE_CONTAINER_MODE", "false")
    root = tmp_path / "public"
    data = tmp_path / "data"
    root.mkdir()
    data.mkdir()
    config = SimpleNamespace(
        DAME_CURIE_SITE_DIR=str(root), DAME_CURIE_PUBLIC_BASE_URL=LOCAL + "///",
        DATA_DIR=str(data), IMAGE_GEN_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        IMAGE_GEN_MODELS={"synthetic-image-a": "Illustrations"},
        IMAGE_GEN_MODEL="synthetic-image-a", IMAGE_GEN_QUALITY="low", IMAGE_GEN_TIMEOUT=300,
    )
    if override is not None:
        config.DAME_CURIE_SITE_PUBLIC_BASE_URL = override
    bot = SimpleNamespace(
        config=config, _control={}, control={}, tools={},
        memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    )
    message = SimpleNamespace(
        author=SimpleNamespace(id=42, display_name="synthetic"), attachments=[],
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=SimpleNamespace(
            attachments=[SimpleNamespace(url="https://cdn.example.invalid/image.png")],
        ))),
    )
    return SimpleNamespace(
        bot=bot, message=message, root=root, expected=expected, override=override,
    )


@pytest.mark.parametrize("auto_send", [False, True], ids=["saved", "sent"])
def test_website_override_leaves_image_delivery_urls_and_bytes_unchanged(site_case, monkeypatch, auto_send):
    case = site_case
    request = AsyncMock(return_value=(PNG, "png", ""))
    monkeypatch.setattr(bot_tools, "_native_image_request", request)
    result = asyncio.run(ImageGeneratorTool(case.bot).execute(case.message, prompt="synthetic image", auto_send=auto_send))
    request.assert_awaited_once()
    files = list((case.root / "_images").glob("*.png"))
    assert len(files) == 1
    assert files[0].read_bytes() == PNG
    assert files[0].with_suffix(".txt").read_bytes() == b"synthetic image"
    assert files[0].with_suffix(".txt").name not in result
    assert f"Permanent URL: {LOCAL_SITE}/_images/{files[0].name} " in result
    assert "redroom.zombiedawn.net" not in result
    assert f"Local path: {files[0]} " in result
    if auto_send:
        case.message.channel.send.assert_awaited_once()
        assert "Image URL: https://cdn.example.invalid/image.png" in result
    else:
        case.message.channel.send.assert_not_awaited()
        assert "NOT sent" in result
    assert case.bot.config.DAME_CURIE_SITE_DIR == str(case.root)
    assert case.bot.config.DAME_CURIE_PUBLIC_BASE_URL == LOCAL + "///"
