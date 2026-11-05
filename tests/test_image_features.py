"""GPT Image 2.6 features stay parked until IMAGE_GEN_FEATURES names them."""

import asyncio
import base64
import json
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import config as config_module
from bot_tools import ImageGeneratorTool, _decode_image_response
from tool_schemas import TOOL_PARAMETERS, build_openai_tools


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
GIF = b"GIF89a" + b"\x00" * 16
SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
NEW = "synthetic/gpt-image-2.6-sunburst"
OLD = "synthetic/gpt-image-2.5-sunburst"
MODELS = {OLD: "Current default", NEW: "Parked"}
OVERLAY_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()


@pytest.fixture
def image_tool(monkeypatch):
    config = SimpleNamespace(
        IMAGE_GEN_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        IMAGE_GEN_API_KEY="synthetic-image-key",
        IMAGE_GEN_MODELS=MODELS.copy(),
        IMAGE_GEN_MODEL=NEW,
        IMAGE_GEN_FEATURES={NEW: ["gif", "svg", "markup"]},
        IMAGE_GEN_QUALITY="low",
        IMAGE_GEN_TIMEOUT=300,
    )
    tool = ImageGeneratorTool(
        SimpleNamespace(
            config=config,
            memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
            _current_progress_by_channel={},
        )
    )
    message = SimpleNamespace(
        attachments=[],
        channel=SimpleNamespace(
            id=42, send=AsyncMock(return_value=SimpleNamespace(attachments=[]))
        ),
    )
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.post.return_value = response
    monkeypatch.setattr(
        "bot_tools._get_shared_session", AsyncMock(return_value=session)
    )
    persist = MagicMock(
        return_value=(
            "/synthetic/image.bin",
            "https://images.example.invalid/image.bin",
        )
    )
    monkeypatch.setattr("bot_tools._persist_public_image", persist)

    def respond(raw: bytes) -> None:
        response.text = AsyncMock(
            return_value=json.dumps(
                {
                    "data": [{"b64_json": base64.b64encode(raw).decode()}],
                }
            )
        )

    respond(GIF)
    return SimpleNamespace(
        tool=tool, message=message, session=session, persist=persist, respond=respond
    )


def _call(env, **arguments):
    return asyncio.run(
        env.tool.execute(env.message, prompt="a lantern", image="", **arguments)
    )


def _sent(env):
    return env.session.post.call_args.kwargs["json"]


def test_parked_schema_is_unchanged(image_tool):
    image_tool.tool.bot.config.IMAGE_GEN_MODEL = OLD
    function = build_openai_tools({"image_generator": image_tool.tool})[0]["function"]
    assert set(function["parameters"]["properties"]) == {
        "explanation",
        *TOOL_PARAMETERS["image_generator"]["properties"],
    }


def test_enabled_features_extend_a_copy_of_the_schema(image_tool):
    image_tool.tool.bot.config.IMAGE_GEN_FEATURES = {NEW: ["svg"]}
    properties = build_openai_tools({"image_generator": image_tool.tool})[0][
        "function"
    ]["parameters"]["properties"]
    assert properties["output_format"]["enum"] == ["svg"]
    assert not {"frame_count", "frame_duration_ms", "markup"} & properties.keys()
    assert "output_format" not in TOOL_PARAMETERS["image_generator"]["properties"]

    image_tool.tool.bot.config.IMAGE_GEN_FEATURES = {NEW: ["gif", "svg", "markup"]}
    properties = build_openai_tools({"image_generator": image_tool.tool})[0][
        "function"
    ]["parameters"]["properties"]
    assert properties["output_format"]["enum"] == ["gif", "svg"]
    assert {"frame_count", "frame_duration_ms", "markup"} <= properties.keys()


def test_no_feature_argument_sends_the_same_payload_as_before(image_tool):
    image_tool.respond(PNG)
    assert not _call(image_tool).startswith("Error")
    assert _sent(image_tool) == {"model": NEW, "prompt": "a lantern", "quality": "low"}


def test_model_without_an_entry_sends_the_same_payload_as_before(image_tool):
    image_tool.respond(PNG)
    image_tool.tool.bot.config.IMAGE_GEN_MODEL = OLD
    assert not _call(image_tool).startswith("Error")
    assert _sent(image_tool) == {"model": OLD, "prompt": "a lantern", "quality": "low"}


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"frame_count": 9}, "frame_count"),
        ({"output_format": "svg", "frame_duration_ms": 200}, "frame_duration_ms"),
    ],
)
def test_disabled_frame_fields_name_the_setting(image_tool, arguments, field):
    image_tool.tool.bot.config.IMAGE_GEN_FEATURES = {NEW: ["svg"]}
    result = _call(image_tool, **arguments)
    assert f"{field} is not enabled" in result and "IMAGE_GEN_FEATURES" in result
    image_tool.session.post.assert_not_called()


def test_disabled_markup_stops_before_the_input_image_is_fetched(image_tool):
    image_tool.tool.bot.config.IMAGE_GEN_FEATURES = {NEW: ["gif"]}
    result = _edit(
        image_tool, image="https://images.example.invalid/in.png", markup=OVERLAY_URI
    )
    assert "markup is not enabled" in result and "IMAGE_GEN_FEATURES" in result
    image_tool.session.get.assert_not_called()
    image_tool.session.post.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"output_format": "gif"}, "output_format gif"),
        ({"output_format": "svg"}, "output_format svg"),
        ({"output_format": "bmp"}, "output_format bmp"),
    ],
)
def test_disabled_format_is_refused_before_http_and_names_the_setting(
    image_tool, arguments, field
):
    image_tool.tool.bot.config.IMAGE_GEN_MODEL = OLD
    result = _call(image_tool, **arguments)
    assert field in result and OLD in result and "IMAGE_GEN_FEATURES" in result
    image_tool.session.post.assert_not_called()


@pytest.mark.parametrize("arguments", [{"frame_count": 9}, {"frame_duration_ms": 200}])
def test_frame_fields_need_gif(image_tool, arguments):
    assert "needs output_format gif" in _call(image_tool, **arguments)
    assert "needs output_format gif" in _call(
        image_tool, output_format="svg", **arguments
    )
    image_tool.session.post.assert_not_called()


def test_gif_request_sends_exact_fields_and_saves_gif(image_tool):
    result = _call(
        image_tool, output_format="gif", frame_count=9, frame_duration_ms=200
    )
    assert not result.startswith("Error")
    assert image_tool.session.post.call_args.args[0].endswith("/images/generations")
    assert _sent(image_tool) == {
        "model": NEW,
        "prompt": "a lantern",
        "quality": "low",
        "output_format": "gif",
        "frame_count": 9,
        "frame_duration_ms": 200,
    }
    assert image_tool.persist.call_args.kwargs["ext"] == ".gif"
    assert "Permanent URL" in result


def test_svg_request_saves_svg_with_the_same_public_url_as_any_image(image_tool):
    image_tool.respond(SVG)
    result = _call(image_tool, output_format="svg")
    assert _sent(image_tool)["output_format"] == "svg"
    assert image_tool.persist.call_args.kwargs["ext"] == ".svg"
    assert "Permanent URL" in result
    assert "Local path: /synthetic/image.bin" in result


def test_svg_response_is_not_saved_as_png():
    data = {"data": [{"b64_json": base64.b64encode(SVG).decode()}]}
    assert _decode_image_response(data) == (SVG, "svg")


def test_svg_with_a_doctype_is_not_saved_as_png():
    raw = b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "x.dtd"><svg></svg>'
    data = {"data": [{"b64_json": base64.b64encode(raw).decode()}]}
    assert _decode_image_response(data) == (raw, "svg")


@pytest.mark.parametrize(
    "raw", [b"<!DOCTYPE html><html></html>", b"<html><body>error</body></html>"]
)
def test_html_body_is_not_accepted_as_a_requested_svg(image_tool, raw):
    image_tool.respond(raw)
    result = _call(image_tool, output_format="svg")
    assert "asked for svg" in result
    image_tool.persist.assert_not_called()


@pytest.mark.parametrize(
    ("requested", "raw", "returned"),
    [("gif", PNG, "png"), ("svg", PNG, "png"), ("gif", SVG, "svg")],
)
def test_wrong_returned_format_is_a_visible_error_and_saves_nothing(
    image_tool, requested, raw, returned
):
    image_tool.respond(raw)
    result = _call(image_tool, output_format=requested)
    assert f"asked for {requested}" in result and f"returned {returned}" in result
    image_tool.persist.assert_not_called()
    assert image_tool.session.post.call_count == 1


def test_configured_output_format_conflict_stops_before_http(image_tool):
    image_tool.tool.bot.config.IMAGE_GEN_EXTRA_BODY = {"output_format": "png"}
    result = _call(image_tool, output_format="gif")
    assert "conflicts" in result and "output_format" in result
    image_tool.session.post.assert_not_called()


def test_complexity_travels_through_the_operator_body_only(image_tool):
    image_tool.respond(PNG)
    image_tool.tool.bot.config.IMAGE_GEN_EXTRA_BODY = {"complexity": "medium"}
    _call(image_tool)
    assert _sent(image_tool)["complexity"] == "medium"


def _edit(env, **arguments):
    return asyncio.run(env.tool.execute(env.message, prompt="recolor", **arguments))


def test_markup_request_sends_the_documented_object(image_tool):
    image_tool.respond(PNG)
    result = _edit(image_tool, image=OVERLAY_URI, markup=OVERLAY_URI)
    assert not result.startswith("Error")
    assert image_tool.session.post.call_args.args[0].endswith("/images/edits")
    assert _sent(image_tool)["markup"] == {"image_url": OVERLAY_URI}
    assert _sent(image_tool)["images"] == [{"image_url": OVERLAY_URI}]


def test_markup_refusals_stop_before_http(image_tool):
    assert "needs an input image" in _edit(image_tool, image="", markup=OVERLAY_URI)
    gif_uri = "data:image/gif;base64," + base64.b64encode(GIF).decode()
    assert "must be a PNG" in _edit(image_tool, image=OVERLAY_URI, markup=gif_uri)
    image_tool.tool.bot.config.IMAGE_GEN_FEATURES = {NEW: ["gif"]}
    result = _edit(image_tool, image=OVERLAY_URI, markup=OVERLAY_URI)
    assert (
        "markup is not enabled" in result
        and NEW in result
        and "IMAGE_GEN_FEATURES" in result
    )
    image_tool.session.post.assert_not_called()


@pytest.fixture
def isolated_config(monkeypatch):
    for name in (
        "IMAGE_GEN_MODELS",
        "IMAGE_GEN_MODEL",
        "IMAGE_GEN_BASE_URL",
        "IMAGE_GEN_FEATURES",
        "IMAGE_GEN_PROTOCOL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("IMAGE_GEN_BASE_URL", "https://images.example.invalid/v1")
    monkeypatch.setenv("IMAGE_GEN_MODELS", json.dumps(MODELS))
    monkeypatch.setenv("IMAGE_GEN_MODEL", OLD)
    monkeypatch.setenv("ENABLE_IMAGE_GEN", "auto")
    return config_module.__file__


def test_config_without_features_keeps_images_enabled(isolated_config):
    loaded = runpy.run_path(isolated_config)["Config"]
    assert loaded.IMAGE_GEN_FEATURES == {}
    assert loaded.IMAGE_GEN_CONFIG_ERROR == ""
    assert loaded.ENABLE_IMAGE_GEN is True


def test_config_accepts_a_parked_model_while_the_default_stays(
    isolated_config, monkeypatch
):
    monkeypatch.setenv(
        "IMAGE_GEN_FEATURES", json.dumps({NEW: ["gif", "svg", "markup"]})
    )
    loaded = runpy.run_path(isolated_config)["Config"]
    assert loaded.IMAGE_GEN_CONFIG_ERROR == ""
    assert loaded.IMAGE_GEN_MODEL == OLD


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        "[]",
        json.dumps({"synthetic/unlisted": ["gif"]}),
        json.dumps({NEW: "gif"}),
        json.dumps({NEW: ["apng"]}),
        json.dumps({NEW: [["gif"]]}),
    ],
)
def test_config_invalid_features_disable_only_images_and_name_the_setting(
    isolated_config, monkeypatch, raw
):
    monkeypatch.setenv("IMAGE_GEN_FEATURES", raw)
    loaded = runpy.run_path(isolated_config)["Config"]
    assert "IMAGE_GEN_FEATURES" in loaded.IMAGE_GEN_CONFIG_ERROR
    assert loaded.ENABLE_IMAGE_GEN is False
