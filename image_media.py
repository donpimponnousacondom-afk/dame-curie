import asyncio
import base64
import binascii
import contextlib
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote_to_bytes, urlsplit


SVG_MAX_BYTES = 10 * 1024 * 1024
SVG_MAX_DIMENSION = 1536
SVG_TIMEOUT_SECONDS = 12
SVG_RENDER_LIMITS = (
    "import os,resource,sys; "
    "resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912)); "
    "resource.setrlimit(resource.RLIMIT_CPU,(10,10)); "
    "os.execvp(sys.argv[1],sys.argv[1:])"
)


class ImageMediaError(ValueError):
    pass


def image_mime(blob: bytes, declared: str = "") -> str:
    mime = declared.split(";", 1)[0].strip().lower()
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif blob.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif blob.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        prefix = blob.lstrip(b"\xef\xbb\xbf \t\r\n")
        if blob.startswith((b"\xff\xfe", b"\xfe\xff")):
            prefix = blob.decode("utf-16", errors="replace").lstrip().encode("utf-8")
        svg_root = re.match(rb"(?:<\?.*?\?>\s*|<!--.*?-->\s*)*+<(?:[\w.-]+:)?svg(?:\s|/?>)", prefix, re.S)
        encoded_xml = blob.startswith((b"<\x00", b"\x00<", b"\x00\x00\x00<", b"\xff\xfe", b"\xfe\xff", b"\x00\x00\xfe\xff"))
        if svg_root or (mime.startswith("image/") and (prefix.startswith(b"<") or encoded_xml)):
            mime = "image/svg+xml"
    return mime or "image/png"


def svg_source(blob: bytes) -> str:
    if len(blob) > SVG_MAX_BYTES:
        raise ImageMediaError("SVG exceeds the 10 MiB rendering limit")
    try:
        text = blob.decode("utf-16" if blob.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        if "\x00" in text:
            raise ImageMediaError("SVG must use UTF-8 or BOM-marked UTF-16 encoding")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b|<\?(?!xml\s)", text, re.I):
            raise ImageMediaError("SVG entities, doctypes and external stylesheets are not supported")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise ImageMediaError("SVG is not valid XML") from exc
    if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
        raise ImageMediaError("Image XML does not contain an SVG root")
    for element in root.iter():
        values = list(element.attrib.values())
        if element.tag.rsplit("}", 1)[-1] == "style":
            values.append(element.text or "")
        for name, value in element.attrib.items():
            if name.rsplit("}", 1)[-1] in {"href", "src", "base"}:
                svg_reference(value)
        for value in values:
            css = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
            if "\\" in css or re.search(r"@import\b", css, re.I):
                raise ImageMediaError("SVG external or escaped resource references are not supported")
            for match in re.finditer(r"url\s*\((.*?)\)", css, re.I | re.S):
                svg_reference(match[1].strip().strip("\"'"))
    return re.sub(r"^\s*<\?xml\b.*?\?>", "", text, count=1, flags=re.S)


def svg_reference(value: str) -> None:
    value = value.strip()
    if not value or value.startswith("#"):
        return
    inline = re.fullmatch(r"data:(image/(?:png|jpeg|gif|webp));base64,([A-Za-z0-9+/=\s]+)", value, re.I)
    if not inline:
        raise ImageMediaError("SVG external resources are not supported; use inline raster data or fragment references")
    try:
        raster = base64.b64decode(inline[2])
    except binascii.Error as exc:
        raise ImageMediaError("SVG inline raster data is invalid") from exc
    if image_mime(raster, "application/octet-stream") != inline[1].lower():
        raise ImageMediaError("SVG inline images must contain the declared raster format, not nested SVG or other data")


async def normalize_image(blob: bytes, declared: str = "") -> tuple[bytes, str]:
    mime = image_mime(blob, declared)
    if mime != "image/svg+xml":
        return blob, mime
    svg = svg_source(blob).encode("utf-8")
    command = (
        sys.executable, "-I", "-S", "-c", SVG_RENDER_LIMITS, "ffmpeg",
        "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "pipe",
        "-f", "svg_pipe", "-frame_size", str(len(svg)), "-c:v", "librsvg",
        "-width", str(SVG_MAX_DIMENSION), "-height", str(SVG_MAX_DIMENSION), "-keep_ar", "1",
        "-i", "pipe:0", "-frames:v", "1", "-c:v", "png", "-threads", "1", "-f", "image2pipe", "pipe:1",
    )
    try:
        process = await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        raise ImageMediaError("SVG renderer could not be started") from exc
    try:
        async with asyncio.timeout(SVG_TIMEOUT_SECONDS):
            output, _ = await process.communicate(svg)
    except TimeoutError as exc:
        raise ImageMediaError("SVG rendering timed out") from exc
    finally:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
    if process.returncode != 0 or not output.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ImageMediaError("SVG could not be rendered; it may be malformed, unsupported or exceed rendering limits")
    return output, "image/png"


async def normalize_image_part(part: dict) -> dict:
    image = part.get("image_url", {})
    url = image.get("url", "")
    mime = ""
    result = part
    try:
        if url[:5].lower() == "data:":
            header, _, data = url.partition(",")
            mime = header[5:].split(";", 1)[0].lower()
            encoded = ";base64" in header.lower()
            if encoded or mime == "image/svg+xml":
                blob = base64.b64decode(unquote_to_bytes(data)) if encoded else unquote_to_bytes(data)
                normalized, mime = await normalize_image(blob, mime)
                result = {
                    **part,
                    "image_url": {**image, "url": f"data:{mime};base64,{base64.b64encode(normalized).decode('ascii')}"},
                }
        elif urlsplit(url).path.lower().endswith(".svg"):
            raise ImageMediaError("Load SVG URLs with see_image before visual inspection")
    except (ImageMediaError, binascii.Error) as exc:
        if isinstance(exc, ImageMediaError) or mime == "image/svg+xml":
            result = {"type": "text", "text": f"Error: image could not be attached for visual inspection: {exc}"}
    return result
