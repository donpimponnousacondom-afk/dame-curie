"""image_generator routes generation and reference edits through native Images."""

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bot_tools import ImageGeneratorTool


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
REFERENCE = b"\xff\xd8\xfforiginal reference bytes"
REFERENCE_URI = "data:image/jpeg;base64," + base64.b64encode(REFERENCE).decode()


def test_native_generations_and_edits_use_one_configured_endpoint(monkeypatch):
    config = SimpleNamespace(
        IMAGE_GEN_PROTOCOL="images", IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        IMAGE_GEN_API_KEY="", IMAGE_GEN_MODELS={"synthetic-image-a": "Illustrations"},
        IMAGE_GEN_MODEL="synthetic-image-a", IMAGE_GEN_QUALITY="high", IMAGE_GEN_TIMEOUT=300,
    )
    tool = ImageGeneratorTool(SimpleNamespace(
        config=config, memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    ))
    message = SimpleNamespace(attachments=[], channel=SimpleNamespace(id=42, send=AsyncMock()))
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({"data": [{"b64_json": base64.b64encode(PNG).decode()}]}))
    session = MagicMock()
    session.post.return_value = response
    monkeypatch.setattr("bot_tools._get_shared_session", AsyncMock(return_value=session))
    monkeypatch.setattr("bot_tools._persist_public_image", MagicMock(return_value=("/synthetic/image.png", "")))

    generated = asyncio.run(tool.execute(message, prompt="a fox"))
    edited = asyncio.run(tool.execute(message, prompt="make it blue", image=REFERENCE_URI))

    assert "generated, NOT sent" in generated
    assert "edited, NOT sent" in edited
    assert [call.args[0] for call in session.post.call_args_list] == [
        "https://images.example.invalid/v1/images/generations",
        "https://images.example.invalid/v1/images/edits",
    ]
    assert [call.kwargs["json"]["prompt"] for call in session.post.call_args_list] == ["a fox", "make it blue"]
    assert session.post.call_args_list[1].kwargs["json"]["images"] == [{"image_url": REFERENCE_URI}]
    assert all(call.kwargs["headers"] == {"Content-Type": "application/json"} for call in session.post.call_args_list)
    session.get.assert_not_called()
    message.channel.send.assert_not_awaited()
