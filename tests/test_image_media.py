import asyncio
import base64
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import quote

import pytest

from image_media import ImageMediaError, image_mime, normalize_image, normalize_image_part


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10" fill="red"/></svg>'
PNG = b"\x89PNG\r\n\x1a\nsynthetic-raster"


@pytest.mark.parametrize("blob,mime", [
    (PNG, "image/png"),
    (b"\xff\xd8\xfffake", "image/jpeg"),
    (b"GIF89afake", "image/gif"),
    (b"RIFF1234WEBPfake", "image/webp"),
])
def test_raster_mime_follows_bytes_without_changing_them(blob, mime):
    assert asyncio.run(normalize_image(blob, "image/png")) == (blob, mime)


def test_comment_and_pi_prefixes_do_not_cause_backtracking():
    source = (
        "from image_media import image_mime; "
        "prefix = b'<!--note--><?metadata value?>' * 1000; "
        "assert image_mime(prefix + b'<html/>', 'text/html') == 'text/html'; "
        "assert image_mime(prefix + b'<svg/>', 'text/plain') == 'image/svg+xml'"
    )
    subprocess.run([sys.executable, "-B", "-c", source], check=True, timeout=2)


def test_nonimage_html_xml_and_audio_are_not_misclassified():
    assert image_mime(b"<html><svg/></html>", "text/html") == "text/html"
    assert image_mime(b"<?xml version='1.0'?><document/>", "application/xml") == "application/xml"
    assert image_mime(b"\xff\xfe\x00\x01", "audio/mpeg") == "audio/mpeg"


@pytest.mark.parametrize("svg", [
    b'<svg><image href="file:///synthetic-secret"/></svg>',
    b'<svg><image href="https://example.test/private.png"/></svg>',
    b'<svg><image href="../private.png"/></svg>',
    b'<svg style="fill:url(file:///synthetic-secret)"/>',
    b'<svg><style>@import "https://example.test/a.css";</style></svg>',
    b'<svg style="fill:u\\72l(file:///synthetic-secret)"/>',
    b'<svg><image href="data:image/svg+xml;base64,PHN2Zy8+"/></svg>',
    b'<svg><image href="data:image/png;base64,PHN2Zy8+"/></svg>',
    b'<!DOCTYPE svg [<!ENTITY x "expanded">]><svg>&x;</svg>',
    b'<?xml-stylesheet href="file:///synthetic-secret"?><svg/>',
    b'<svg xml:base="file:///synthetic/"><image href="a.png"/></svg>',
    b'<svg><unclosed>',
])
def test_unsafe_or_malformed_svg_is_rejected_before_renderer(monkeypatch, svg):
    spawn = AsyncMock()
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", spawn)
    with pytest.raises(ImageMediaError):
        asyncio.run(normalize_image(svg, "image/svg+xml"))
    spawn.assert_not_called()


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be", "utf-16", "utf-32"])
def test_encoded_doctype_cannot_bypass_resource_restrictions(monkeypatch, encoding):
    spawn = AsyncMock()
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", spawn)
    svg = '<!DOCTYPE svg [<!ENTITY x "expanded">]><svg>&x;</svg>'.encode(encoding)
    with pytest.raises(ImageMediaError):
        asyncio.run(normalize_image(svg, "image/svg+xml"))
    spawn.assert_not_called()


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be", "utf-32"])
def test_unsupported_xml_encoding_cannot_leak_as_legacy_png(encoding):
    blob = SVG.decode().encode(encoding)
    part = {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(blob).decode()}}
    result = asyncio.run(normalize_image_part(part))
    assert result["type"] == "text" and result["text"].startswith("Error:")


def test_svg_renderer_uses_bounded_stdin_and_handles_utf16(monkeypatch):
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(PNG, None)))
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", spawn)
    svg = ('<?xml version="1.0" encoding="UTF-16"?>' + SVG.decode()).encode("utf-16")
    assert asyncio.run(normalize_image(svg, "image/png")) == (PNG, "image/png")
    args = spawn.call_args.args
    assert args[args.index("-protocol_whitelist") + 1] == "pipe"
    assert args[args.index("-i") + 1] == "pipe:0"
    assert args[args.index("-width") + 1] == "1536"
    assert args[args.index("-height") + 1] == "1536"
    assert "resource.RLIMIT_AS" in args[4] and "resource.RLIMIT_CPU" in args[4]
    sent = process.communicate.call_args.args[0]
    assert b"UTF-16" not in sent and b"<svg" in sent
    assert args[args.index("-frame_size") + 1] == str(len(sent))


@pytest.mark.parametrize("failure", [TimeoutError, asyncio.CancelledError])
def test_svg_timeout_and_cancellation_kill_and_reap(monkeypatch, failure):
    process = SimpleNamespace(
        returncode=None, communicate=AsyncMock(side_effect=failure()), kill=Mock(), wait=AsyncMock(),
    )
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", AsyncMock(return_value=process))
    expected = ImageMediaError if failure is TimeoutError else asyncio.CancelledError
    with pytest.raises(expected):
        asyncio.run(normalize_image(SVG, "image/svg+xml"))
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()


def test_renderer_failure_is_an_explicit_media_error(monkeypatch):
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(b"", None)))
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(ImageMediaError, match="could not be rendered"):
        asyncio.run(normalize_image(SVG))


def test_svg_fragments_and_inline_raster_references_are_allowed(monkeypatch):
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(PNG, None)))
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", AsyncMock(return_value=process))
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="a"/></defs><use href="#a"/><image href="data:image/png;base64,iVBORw0KGgo="/></svg>'
    assert asyncio.run(normalize_image(svg))[1] == "image/png"


@pytest.mark.parametrize("header", ["data:image/svg+xml;base64,", "DATA:IMAGE/PNG;BASE64,"])
def test_data_uri_svg_normalization_preserves_options_and_input(monkeypatch, header):
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(PNG, None)))
    monkeypatch.setattr("image_media.asyncio.create_subprocess_exec", AsyncMock(return_value=process))
    part = {"type": "image_url", "image_url": {"url": header + quote(base64.b64encode(SVG).decode(), safe=""), "detail": "low"}}
    result = asyncio.run(normalize_image_part(part))
    assert result["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert result["image_url"]["detail"] == "low"
    assert part["image_url"]["url"].startswith(header)


def test_invalid_svg_part_becomes_visible_error_not_paid_image():
    part = {"type": "image_url", "image_url": {"url": "data:image/svg+xml;base64," + base64.b64encode(b"<svg>").decode()}}
    result = asyncio.run(normalize_image_part(part))
    assert result["type"] == "text" and result["text"].startswith("Error:")
    assert "image_url" not in result


def test_raw_svg_data_uri_and_remote_svg_fail_explicitly():
    for url in ("data:image/svg+xml,%3Csvg%3E", "https://example.test/original.svg"):
        result = asyncio.run(normalize_image_part({"type": "image_url", "image_url": {"url": url}}))
        assert result["type"] == "text" and result["text"].startswith("Error:")
