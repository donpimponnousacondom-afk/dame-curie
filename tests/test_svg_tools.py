import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import MaxwellBot
from bot_tools import FetchUrlTool, SeeImageTool
from image_media import ImageMediaError


SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/a.png"/></svg>'
PNG = b"\x89PNG\r\n\x1a\nsynthetic-raster"


@pytest.mark.parametrize("mime", ["image/svg+xml", "text/plain", "application/xml"])
def test_fetch_svg_returns_original_xml_even_with_external_refs(monkeypatch, mime):
    fetch = AsyncMock(return_value=("https://example.test/a.svg", mime, SVG))
    renderer = AsyncMock(side_effect=AssertionError("fetch_url must not render SVG"))
    monkeypatch.setattr("bot_tools._fetch_public_url", fetch)
    monkeypatch.setattr("bot_tools.normalize_image", renderer)
    bot = SimpleNamespace(_control={"process_images": False})
    result = asyncio.run(FetchUrlTool(bot).execute(SimpleNamespace(), url="https://example.test/a.svg"))
    assert result == SVG.decode()
    assert "__IMAGE_B64__" not in result
    renderer.assert_not_called()


def test_fetch_html_still_extracts_text_instead_of_returning_markup(monkeypatch):
    html = b'<html><head><script>hidden()</script></head><body><p>Hello</p><svg/></body></html>'
    monkeypatch.setattr("bot_tools._fetch_public_url", AsyncMock(return_value=("https://example.test/page", "text/html", html)))
    result = asyncio.run(FetchUrlTool(SimpleNamespace()).execute(SimpleNamespace(), url="https://example.test/page"))
    assert "Hello" in result
    assert "<html>" not in result and "hidden()" not in result


def test_see_image_rasterizes_before_cache_and_marker(monkeypatch):
    cached = []
    normalizer = AsyncMock(return_value=(PNG, "image/png"))
    monkeypatch.setattr("bot_tools.normalize_image", normalizer)
    bot = SimpleNamespace(
        _control={"process_images": True}, _media_item=lambda **kwargs: kwargs,
        _cache_media_context=lambda channel, items: cached.extend(items),
    )
    message = SimpleNamespace(id=1, channel=SimpleNamespace(id=2))
    result = asyncio.run(SeeImageTool(bot).result_from_blob(SVG, "image/svg+xml", "https://example.test/a.svg", message))
    normalizer.assert_awaited_once_with(SVG, "image/svg+xml")
    assert cached[0]["mime_type"] == "image/png"
    assert cached[0]["filename"] == "see-image.png"
    assert cached[0]["url"] == "https://example.test/a.svg"
    assert base64.b64encode(PNG).decode() in result
    assert base64.b64encode(SVG).decode() not in result


def test_see_image_download_path_normalizes_without_mutating_source_item(monkeypatch):
    source = {"b64": base64.b64encode(SVG).decode(), "mime_type": "image/svg+xml", "filename": "original.svg", "url": "https://example.test/a.svg"}
    cached = []
    monkeypatch.setattr("bot_tools.normalize_image", AsyncMock(return_value=(PNG, "image/png")))
    bot = SimpleNamespace(
        _control={"process_images": True}, _download_embed_media=AsyncMock(return_value=source),
        _cache_media_context=lambda channel, items: cached.extend(items),
    )
    result = asyncio.run(SeeImageTool(bot).execute(SimpleNamespace(id=1, channel=SimpleNamespace(id=2)), url=source["url"]))
    assert "__IMAGE_B64__" in result and "original.png" in result
    assert cached[0]["mime_type"] == "image/png"
    assert source["mime_type"] == "image/svg+xml" and source["filename"] == "original.svg"


def test_svg_disguised_as_gif_never_reaches_unbounded_gif_decoder(monkeypatch):
    gif = AsyncMock(side_effect=AssertionError("SVG must not enter the GIF decoder"))
    monkeypatch.setattr("bot_tools.normalize_image", AsyncMock(return_value=(PNG, "image/png")))
    result = asyncio.run(SeeImageTool(SimpleNamespace(_normalize_gif=gif)).result_from_blob(SVG, "image/gif", "https://example.test/a.gif"))
    assert "__IMAGE_B64__" in result and "image/png" in result
    gif.assert_not_called()


def test_see_image_conversion_failure_is_tool_error(monkeypatch):
    monkeypatch.setattr("bot_tools.normalize_image", AsyncMock(side_effect=ImageMediaError("SVG external resources are not supported")))
    result = asyncio.run(SeeImageTool(SimpleNamespace()).result_from_blob(SVG, "image/svg+xml", "https://example.test/a.svg"))
    assert result.startswith("Error:") and "__IMAGE_B64__" not in result


def test_bare_svg_link_is_admitted_for_visual_normalization():
    assert MaxwellBot._media_link_refs("https://example.test/a.svg") == [("https://example.test/a.svg", ".svg")]


def test_embed_svg_with_generic_mime_is_admitted_without_changing_original(monkeypatch):
    fake = SimpleNamespace(
        _fetch_public_payload=AsyncMock(return_value=("https://example.test/a.svg", "application/octet-stream", SVG)),
        _is_gif_page_url=lambda _: False, _media_item=lambda **kwargs: kwargs,
    )
    result = asyncio.run(MaxwellBot._download_embed_media(fake, "https://example.test/a.svg", "original.svg", 10000, 1))
    assert result["mime_type"] == "image/svg+xml" and result["is_image"]
    assert base64.b64decode(result["b64"]) == SVG
    assert result["url"] == "https://example.test/a.svg"
