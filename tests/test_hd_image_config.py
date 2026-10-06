import asyncio
import base64
import json
import runpy
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import config as config_module
from bot import MaxwellBot
from bot_tools import ImageGeneratorTool
from config import _json_env
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


@pytest.mark.parametrize("model", [None, "", "synthetic-image-a"])
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


@pytest.mark.parametrize("model", ["synthetic-image-A", "synthetic-image-a ", "unknown-image", "synthetic-image-b"])
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
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DAME_CURIE_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("DISCORD_TOKEN", "synthetic-token")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://chat.example.invalid/v1")
    monkeypatch.setenv("OPENAI_MODEL", "synthetic-chat-model")
    monkeypatch.setenv("OPENAI_EXTRA_BODY", "{}")
    monkeypatch.setenv("OPENAI_EXTRA_HEADERS", "{}")
    monkeypatch.setenv("ENABLE_SHELL", "false")
    for name in ("IMAGE_GEN_BASE_URL", "IMAGE_GEN_API_KEY", "IMAGE_GEN_MODELS", "IMAGE_GEN_MODEL", "IMAGE_GEN_EXTRA_BODY", "IMAGE_GEN_QUALITY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("IMAGE_GEN_PROTOCOL", "images")
    monkeypatch.setenv("ENABLE_IMAGE_GEN", "auto")
    return config_module.__file__


@pytest.mark.parametrize("raw", ["{not json", "[]", "null", '"synthetic-image-a"'])
@pytest.mark.parametrize("setting", ["IMAGE_GEN_MODELS", "IMAGE_GEN_EXTRA_BODY"])
def test_config_image_model_map_requires_strict_json_object(isolated_config, image_tool, monkeypatch, raw, setting):
    monkeypatch.setenv("IMAGE_GEN_MODELS", json.dumps(MODELS))
    monkeypatch.setenv(setting, raw)
    monkeypatch.setenv("IMAGE_GEN_BASE_URL", "https://images.example.invalid/v1")
    monkeypatch.setenv("IMAGE_GEN_MODEL", "synthetic-image-a")
    monkeypatch.setenv("ENABLE_IMAGE_GEN", "true")
    with pytest.raises(ValueError, match=f"{setting}.*JSON object"):
        _json_env(setting, strict=True)
    loaded = runpy.run_path(isolated_config)["Config"]
    loaded.validate()
    assert loaded.ENABLE_IMAGE_GEN is False
    assert setting in loaded.IMAGE_GEN_CONFIG_ERROR
    assert raw not in loaded.IMAGE_GEN_CONFIG_ERROR
    assert any(
        name == "ENABLE_IMAGE_GEN" and not enabled and loaded.IMAGE_GEN_CONFIG_ERROR in reason
        for name, _, enabled, reason in loaded.feature_report()
    )
    tool, message, session, get_session = image_tool
    tool.bot.config = loaded
    result = asyncio.run(tool.execute(message, prompt="a red fox"))
    assert loaded.IMAGE_GEN_CONFIG_ERROR in result
    get_session.assert_not_awaited()
    session.post.assert_not_called()


@pytest.mark.parametrize("switch,enabled", [("auto", True), ("true", True), ("false", False)])
@pytest.mark.parametrize("quality", [None, "", "high"])
def test_config_accepts_valid_operator_model_map(isolated_config, image_tool, monkeypatch, switch, enabled, quality):
    monkeypatch.setenv("IMAGE_GEN_BASE_URL", "https://images.example.invalid/v1")
    monkeypatch.setenv("IMAGE_GEN_MODELS", json.dumps(MODELS))
    monkeypatch.setenv("IMAGE_GEN_MODEL", "synthetic-image-b")
    monkeypatch.setenv("IMAGE_GEN_API_KEY", "")
    if quality is not None:
        monkeypatch.setenv("IMAGE_GEN_QUALITY", quality)
    monkeypatch.setenv("IMAGE_GEN_EXTRA_BODY", '{"response_format":"b64_json","seed":0}')
    monkeypatch.setenv("ENABLE_IMAGE_GEN", switch)
    loaded = runpy.run_path(isolated_config)["Config"]
    loaded.validate()
    assert loaded.IMAGE_GEN_MODELS == MODELS
    assert loaded.IMAGE_GEN_CONFIG_ERROR == ""
    assert loaded.ENABLE_IMAGE_GEN is enabled
    assert loaded.IMAGE_GEN_API_KEY == ""
    assert loaded.IMAGE_GEN_QUALITY == quality
    assert loaded.IMAGE_GEN_EXTRA_BODY == {"response_format": "b64_json", "seed": 0}
    assert next(row[2] for row in loaded.feature_report() if row[0] == "ENABLE_IMAGE_GEN") is enabled
    tool, message, session, get_session = image_tool
    tool.bot.config = loaded
    result = asyncio.run(tool.execute(message, prompt="a red fox"))
    if not enabled:
        assert "ENABLE_IMAGE_GEN=false" in result
        get_session.assert_not_awaited()
        session.post.assert_not_called()
    else:
        expected = {"model": "synthetic-image-b", "prompt": "a red fox", "response_format": "b64_json", "seed": 0}
        if quality is not None:
            expected["quality"] = quality
        assert session.post.call_args.kwargs["json"] == expected
        assert loaded.IMAGE_GEN_EXTRA_BODY == {"response_format": "b64_json", "seed": 0}


@pytest.mark.parametrize("models,default,protocol,diagnostic", [
    ({"synthetic-image-a": ""}, "synthetic-image-a", "images", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": "   "}, "synthetic-image-a", "images", "IMAGE_GEN_MODELS"),
    ({" synthetic-image-a": "Illustrations"}, " synthetic-image-a", "images", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": 123}, "synthetic-image-a", "images", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": "private-description", "synthetic-image-b": ""}, "synthetic-image-a", "images", "IMAGE_GEN_MODELS"),
    ({"synthetic-image-a": "Illustrations"}, "", "images", "IMAGE_GEN_MODEL"),
    ({"synthetic-image-a": "Illustrations"}, "unknown-image", "images", "IMAGE_GEN_MODEL"),
    ({"synthetic-image-a": "Illustrations"}, "synthetic-image-a", "pollinations", "IMAGE_GEN_PROTOCOL"),
])
def test_config_rejects_invalid_image_map_or_default(isolated_config, monkeypatch, models, default, protocol, diagnostic):
    monkeypatch.setenv("IMAGE_GEN_BASE_URL", "https://images.example.invalid/v1")
    monkeypatch.setenv("IMAGE_GEN_MODELS", json.dumps(models))
    monkeypatch.setenv("IMAGE_GEN_MODEL", default)
    monkeypatch.setenv("IMAGE_GEN_PROTOCOL", protocol)
    monkeypatch.setenv("ENABLE_IMAGE_GEN", "true")
    loaded = runpy.run_path(isolated_config)["Config"]
    loaded.validate()
    assert loaded.ENABLE_IMAGE_GEN is False
    assert diagnostic in loaded.IMAGE_GEN_CONFIG_ERROR
    assert "Illustrations" not in loaded.IMAGE_GEN_CONFIG_ERROR
    assert "private-description" not in loaded.IMAGE_GEN_CONFIG_ERROR
    assert any(
        name == "ENABLE_IMAGE_GEN" and not enabled and diagnostic in reason
        for name, _, enabled, reason in loaded.feature_report()
    )


@pytest.mark.parametrize("switch", ["auto", "false"])
def test_unconfigured_image_profile_can_boot_but_cannot_generate(isolated_config, image_tool, monkeypatch, switch):
    monkeypatch.setenv("ENABLE_IMAGE_GEN", switch)
    loaded = runpy.run_path(isolated_config)["Config"]
    loaded.validate()
    assert loaded.ENABLE_IMAGE_GEN is False
    assert "IMAGE_GEN_BASE_URL" in loaded.IMAGE_GEN_CONFIG_ERROR
    tool, message, session, get_session = image_tool
    tool.bot.config = loaded
    result = asyncio.run(tool.execute(message, prompt="a red fox"))
    assert result.startswith("Error:")
    assert loaded.IMAGE_GEN_CONFIG_ERROR in result
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
    assert not {"model", "quality"} & first["parameters"]["properties"].keys()
    assert second["parameters"]["properties"] == first["parameters"]["properties"]
    assert not {"voice", "language"} & TOOL_PARAMETERS["tts"]["properties"].keys()
    image_description = first["parameters"]["properties"]["image"]["description"]
    assert "empty string" in image_description and "empty JSON list" in image_description
    assert TOOL_PARAMETERS["image_generator"]["properties"] == original

    bot = SimpleNamespace(
        tools={"image_generator": tool},
        _control={"tools_enabled": True, "native_tool_calls": False, "disabled_tools": []},
    )
    bot._compatible_tool_names = MaxwellBot._compatible_tool_names.__get__(bot)
    guidance = MaxwellBot._tool_system_prompt(bot)
    assert "image_generator" in guidance
    for model in tool.bot.config.IMAGE_GEN_MODELS:
        if model != tool.bot.config.IMAGE_GEN_MODEL:
            assert model not in guidance
