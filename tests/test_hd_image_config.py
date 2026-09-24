import asyncio
import base64
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import MaxwellBot
from bot_tools import ImageGeneratorTool
from config import Config, _json_env
from tool_schemas import TOOL_PARAMETERS, build_openai_tools


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
MODELS = {"synthetic-image-a": "Illustrations", "synthetic-image-b": "Reference edits"}


@pytest.fixture
def image_tool(monkeypatch):
    config = SimpleNamespace(
        OPENAI_BASE_URL="https://chat.example.invalid/v1",
        OPENAI_API_KEY="synthetic-chat-key",
        IMAGE_GEN_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        IMAGE_GEN_API_KEY="synthetic-image-key",
        IMAGE_GEN_MODELS=MODELS.copy(),
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
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=SimpleNamespace(attachments=[]))),
    )
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({
        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
    }))
    session = MagicMock()
    session.post.return_value = response
    get_session = AsyncMock(return_value=session)
    monkeypatch.setattr("bot_tools._get_shared_session", get_session)
    monkeypatch.setattr("bot_tools._persist_public_image", MagicMock(return_value=("/synthetic/image.png", "")))
    return tool, message, session, get_session


@pytest.mark.parametrize("base", [None, "", "   ", "/"])
@pytest.mark.parametrize("image", [None, "data:image/png;base64,aW1hZ2U="])
def test_chat_settings_cannot_enable_unconfigured_images(image_tool, base, image):
    tool, message, session, get_session = image_tool
    if base is None:
        del tool.bot.config.IMAGE_GEN_BASE_URL
    else:
        tool.bot.config.IMAGE_GEN_BASE_URL = base
    result = asyncio.run(tool.execute(message, prompt="a red fox", image=image))
    assert result.startswith("Error:")
    assert "IMAGE_GEN_BASE_URL" in result
    get_session.assert_not_awaited()
    session.post.assert_not_called()
    message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("model", [None, "synthetic-image-a", "synthetic-image-b"])
def test_native_model_default_and_exact_override(image_tool, model):
    tool, message, session, _ = image_tool
    arguments = {} if model is None else {"model": model}
    result = asyncio.run(tool.execute(message, prompt="a red fox", **arguments))
    assert "generated, NOT sent" in result
    assert session.post.call_args.args == ("https://images.example.invalid/v1/images/generations",)
    assert session.post.call_args.kwargs["json"]["model"] == (model or "synthetic-image-a")
    assert session.post.call_args.kwargs["json"]["prompt"] == "a red fox"
    assert session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer synthetic-image-key"
    message.channel.send.assert_not_awaited()


@pytest.mark.parametrize("model", ["synthetic-image-A", "synthetic-image-a ", "unknown-image"])
def test_unlisted_model_rejected_before_http(image_tool, model):
    tool, message, session, get_session = image_tool
    result = asyncio.run(tool.execute(message, prompt="a red fox", model=model))
    assert result.startswith("Error:")
    assert "model" in result.lower()
    get_session.assert_not_awaited()
    session.post.assert_not_called()


@pytest.mark.parametrize("models,default", [
    ({}, ""),
    ({"synthetic-image-a": "Illustrations"}, ""),
    ({"synthetic-image-a": "Illustrations"}, "unlisted-image"),
])
def test_missing_or_invalid_image_configuration_errors_before_http(image_tool, models, default):
    tool, message, session, get_session = image_tool
    tool.bot.config.IMAGE_GEN_MODELS = models
    tool.bot.config.IMAGE_GEN_MODEL = default
    result = asyncio.run(tool.execute(message, prompt="a red fox"))
    assert result.startswith("Error:")
    get_session.assert_not_awaited()
    session.post.assert_not_called()


@pytest.fixture
def isolated_config(monkeypatch):
    monkeypatch.setattr(Config, "DISCORD_TOKEN", "synthetic-token")
    monkeypatch.setattr(Config, "OPENAI_BASE_URL", "https://chat.example.invalid/v1")
    monkeypatch.setattr(Config, "OPENAI_MODEL", "synthetic-chat-model")
    monkeypatch.setattr(Config, "OPENAI_MAX_TOKENS", 4096)
    monkeypatch.setattr(Config, "IMAGE_GEN_PROTOCOL", "images")
    monkeypatch.setattr(Config, "IMAGE_GEN_MODELS", {})
    monkeypatch.setattr(Config, "IMAGE_GEN_MODEL", "")
    monkeypatch.setattr(Config, "ENABLE_SHELL", False)
    monkeypatch.setattr(Config, "feature_report", classmethod(lambda cls: []))
    return Config


@pytest.mark.parametrize("raw", ["{not json", "[]", "null", '"synthetic-image-a"'])
def test_config_image_model_map_requires_strict_json_object(monkeypatch, raw):
    monkeypatch.setenv("IMAGE_GEN_MODELS", raw)
    with pytest.raises(ValueError, match="IMAGE_GEN_MODELS.*JSON object"):
        _json_env("IMAGE_GEN_MODELS", strict=True)


def test_config_accepts_valid_operator_model_map(isolated_config, monkeypatch):
    monkeypatch.setenv("IMAGE_GEN_MODELS", json.dumps(MODELS))
    monkeypatch.setattr(isolated_config, "IMAGE_GEN_MODELS", _json_env("IMAGE_GEN_MODELS", strict=True))
    monkeypatch.setattr(isolated_config, "IMAGE_GEN_MODEL", "synthetic-image-b")
    isolated_config.validate()
    assert isolated_config.IMAGE_GEN_MODELS == MODELS


@pytest.mark.parametrize("models,default,diagnostic", [
    ({"synthetic-image-a": ""}, "synthetic-image-a", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": "   "}, "synthetic-image-a", "IMAGE_GEN_MODELS"),
    ({" synthetic-image-a": "Illustrations"}, " synthetic-image-a", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": 123}, "synthetic-image-a", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": "Illustrations"}, "", "IMAGE_GEN_MODEL"),
    ({"synthetic-image-a": "Illustrations"}, "unknown-image", "IMAGE_GEN_MODEL"),
])
def test_config_rejects_invalid_image_map_or_default(isolated_config, monkeypatch, models, default, diagnostic):
    monkeypatch.setattr(isolated_config, "IMAGE_GEN_MODELS", models)
    monkeypatch.setattr(isolated_config, "IMAGE_GEN_MODEL", default)
    with pytest.raises(ValueError, match=diagnostic):
        isolated_config.validate()


def test_unconfigured_image_profile_can_boot_but_cannot_generate(isolated_config, image_tool):
    isolated_config.validate()
    tool, message, session, get_session = image_tool
    tool.bot.config.IMAGE_GEN_MODELS = isolated_config.IMAGE_GEN_MODELS
    tool.bot.config.IMAGE_GEN_MODEL = isolated_config.IMAGE_GEN_MODEL
    result = asyncio.run(tool.execute(message, prompt="a red fox"))
    assert result.startswith("Error:")
    assert "IMAGE_GEN_MODELS" in result
    get_session.assert_not_awaited()
    session.post.assert_not_called()


def test_dynamic_schema_exposes_every_configured_model_without_mutating_shared_schema(image_tool):
    tool, _, _, _ = image_tool
    tool.bot.config.IMAGE_GEN_MODELS = {
        f"synthetic-image-{index}": f"Operator description {index} " + "details " * 30
        for index in range(8)
    }
    tool.bot.config.IMAGE_GEN_MODEL = "synthetic-image-0"
    original = deepcopy(TOOL_PARAMETERS["image_generator"]["properties"])
    first = build_openai_tools({"image_generator": tool}, max_description_chars=64)[0]["function"]
    second = build_openai_tools({"image_generator": tool}, max_description_chars=64)[0]["function"]
    model_property = first["parameters"]["properties"]["model"]
    assert model_property["enum"] == list(tool.bot.config.IMAGE_GEN_MODELS)
    for model, description in tool.bot.config.IMAGE_GEN_MODELS.items():
        assert model in model_property["description"]
        assert description in model_property["description"]
    assert second["parameters"]["properties"]["model"] == model_property
    assert TOOL_PARAMETERS["image_generator"]["properties"] == original

    bot = SimpleNamespace(
        tools={"image_generator": tool},
        _control={"tools_enabled": True, "native_tool_calls": False, "disabled_tools": []},
    )
    bot._compatible_tool_names = MaxwellBot._compatible_tool_names.__get__(bot)
    guidance = MaxwellBot._tool_system_prompt(bot)
    assert "image_generator" in guidance
    assert "default is synthetic-image-0:" in guidance
    for model, description in tool.bot.config.IMAGE_GEN_MODELS.items():
        assert model in guidance
        assert description in guidance
