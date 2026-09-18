import asyncio
import base64
import json
import logging
from datetime import datetime
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, quote, unquote, urlsplit

import discord
import pytest

import bot_tools
import error_reporting
from bot_tools import HDImageGeneratorTool, ImageGeneratorTool


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
LOCAL = "https://images.example.invalid"
CDN = "https://cdn.example.invalid/image.png"
KEY = "synthetic/key+credential"
PROMPT = " \n\t" + '火 dragon 🐉 — café e\u0301 "glass" \\ moon\n' * 100 + "FULL PROMPT TAIL \t\n"
REVISION = "Provider revision is not the submitted prompt."
PROFILES = ["normal-native", "hd-native", "hd-chat", "pollinations"]


def response_for(profile, image_bytes, ext="png"):
    encoded = base64.b64encode(image_bytes).decode()
    payload = (
        {"choices": [{"message": {"content": REVISION, "images": [
            {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{encoded}"}},
        ]}}]}
        if profile == "hd-chat" else {"data": [{"b64_json": encoded, "revised_prompt": REVISION}]}
    )
    response = MagicMock(status=200, headers={"Content-Type": f"image/{ext}"})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps(payload))

    async def chunks(size):
        yield image_bytes

    response.content.iter_chunked = chunks
    return response


@pytest.fixture(params=PROFILES)
def image_case(request, monkeypatch, tmp_path, caplog):
    profile = request.param
    root = tmp_path / "site"
    config = SimpleNamespace(
        MAXWELL_SITE_DIR=str(root), MAXWELL_PUBLIC_BASE_URL=LOCAL,
        MAXWELL_SITE_PUBLIC_BASE_URL="https://redroom.zombiedawn.net/dame",
        IMAGE_GEN_PROTOCOL="pollinations" if profile == "pollinations" else "images",
        IMAGE_GEN_BASE_URL="https://normal.example.invalid/v1", IMAGE_GEN_API_KEY=KEY,
        IMAGE_GEN_MODEL="normal-model", IMAGE_GEN_QUALITY="low", IMAGE_GEN_TIMEOUT=90,
        GEMINI_IMAGE_PROTOCOL="chat_completions" if profile == "hd-chat" else "images",
        GEMINI_IMAGE_BASE_URL="https://hd.example.invalid/v1", GEMINI_IMAGE_API_KEY=KEY,
        GEMINI_IMAGE_MODEL="hd-model", GEMINI_IMAGE_QUALITY="high", GEMINI_IMAGE_TIMEOUT=90,
        POLLINATIONS_MODEL="flux",
    )
    bot = SimpleNamespace(
        config=config, memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    )
    tool = HDImageGeneratorTool(bot) if profile.startswith("hd-") else ImageGeneratorTool(bot)
    message = SimpleNamespace(
        attachments=[], channel=SimpleNamespace(id=42, send=AsyncMock(
            return_value=SimpleNamespace(attachments=[SimpleNamespace(url=CDN)]),
        )),
    )
    response = response_for(profile, PNG)
    session = MagicMock()
    session.post.return_value = response
    session.get.return_value = response
    monkeypatch.setattr(bot_tools, "_get_shared_session", AsyncMock(return_value=session))
    monkeypatch.setattr(error_reporting, "_secrets", ())
    monkeypatch.setattr(error_reporting, "_store", None)
    error_reporting.configure_incident_store(tmp_path / "incidents.json")
    caplog.set_level(logging.INFO, logger="bot_tools")
    return SimpleNamespace(
        bot=bot, tool=tool, message=message, profile=profile, root=root,
        session=session, response=response,
    )


def generate(case, prompt=PROMPT, auto_send=False):
    return asyncio.run(case.tool.execute(case.message, prompt=prompt, auto_send=auto_send))


def sent_prompt(case):
    if case.profile == "pollinations":
        return unquote(urlsplit(case.session.get.call_args.args[0]).path.removeprefix("/prompt/"))
    payload = case.session.post.call_args.kwargs["json"]
    if case.profile == "hd-chat":
        return payload["messages"][0]["content"][0]["text"]
    return payload["prompt"]


def saved_pair(case, prompt=PROMPT):
    images = list(case.root.glob("_images/*.png"))
    assert len(images) == 1
    image = images[0]
    sidecar = image.with_suffix(".txt")
    expected = prompt[:1500] if case.profile == "pollinations" else prompt
    assert image.read_bytes() == PNG
    assert sidecar.read_bytes() == expected.encode("utf-8")
    assert set(image.parent.iterdir()) == {image, sidecar}
    return image, sidecar


@pytest.mark.parametrize("auto_send", [False, True], ids=["saved", "sent"])
def test_real_requests_save_exact_submitted_text_without_changing_delivery(image_case, auto_send):
    case = image_case
    result = generate(case, auto_send=auto_send)
    image, sidecar = saved_pair(case)
    expected = PROMPT[:1500] if case.profile == "pollinations" else PROMPT
    assert sent_prompt(case) == expected
    assert REVISION not in sidecar.read_text(encoding="utf-8")
    assert case.session.get.call_count + case.session.post.call_count == 1
    assert f"Permanent URL: {LOCAL}/bot/_images/{image.name} " in result
    assert f"Local path: {image} " in result
    assert sidecar.name not in result and "https://redroom.zombiedawn.net" not in result
    assert PROMPT[:100] in result
    memory = case.bot.memory.add_to_channel_memory.await_args.args[1]
    label = "Generated HD image" if case.profile.startswith("hd-") else "Generated image"
    assert memory["content"] == f"{label}: {PROMPT[:200]}"
    if auto_send:
        case.message.channel.send.assert_awaited_once()
        upload = case.message.channel.send.await_args.kwargs["file"]
        assert upload.fp.getvalue() == PNG
        expected_name = "hd_generated_image.png" if case.profile.startswith("hd-") else "generated_image.png"
        assert upload.filename == expected_name
        assert result.startswith("__IMAGE_SENT__ ") and f"Image URL: {CDN}" in result
    else:
        case.message.channel.send.assert_not_awaited()
        assert "generated, NOT sent:" in result and "__IMAGE_SENT__" not in result
    if case.profile == "pollinations":
        query = parse_qs(urlsplit(case.session.get.call_args.args[0]).query)
        assert query == {"width": ["1024"], "height": ["1024"], "nologo": ["true"], "model": ["flux"], "seed": query["seed"]}
    elif case.profile == "hd-chat":
        assert case.session.post.call_args.kwargs["json"] == {
            "model": "hd-model", "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT}]}],
        }
    else:
        assert case.session.post.call_args.kwargs["json"] == {
            "model": "hd-model" if case.profile == "hd-native" else "normal-model",
            "prompt": PROMPT, "quality": "high" if case.profile == "hd-native" else "low",
            "output_format": "png", "response_format": "b64_json", "n": 1,
        }


@pytest.mark.parametrize("image_case", ["hd-native", "hd-chat"], indirect=True)
def test_hd_edit_sidecar_contains_only_submitted_text(image_case):
    case = image_case
    reference = "data:image/png;base64," + base64.b64encode(PNG).decode()
    result = asyncio.run(case.tool.execute(case.message, prompt=PROMPT, image=reference))
    image, sidecar = saved_pair(case)
    assert sent_prompt(case) == PROMPT
    payload = case.session.post.call_args.kwargs["json"]
    if case.profile == "hd-native":
        assert payload["images"] == [{"image_url": reference}]
        assert case.session.post.call_args.args[0].endswith("/images/edits")
    else:
        assert len(payload["messages"][0]["content"]) == 2
    assert "data:image" not in sidecar.read_text(encoding="utf-8")
    assert str(image) in result and sidecar.name not in result
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_sidecar_preserves_original_non_png_bytes_and_filename_extension(image_case):
    case = image_case
    raw = b"\xff\xd8\xffsynthetic original JPEG bytes"
    response = response_for(case.profile, raw, ext="jpeg")
    case.session.post.return_value = response
    case.session.get.return_value = response
    result = generate(case)
    ext = "png" if case.profile == "pollinations" else "jpg"
    images = list(case.root.glob(f"_images/*.{ext}"))
    assert len(images) == 1
    assert images[0].read_bytes() == raw
    expected = PROMPT[:1500] if case.profile == "pollinations" else PROMPT
    assert images[0].with_suffix(".txt").read_bytes() == expected.encode("utf-8")
    assert f"Permanent URL: {LOCAL}/bot/_images/{images[0].name} " in result
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_sidecar_redacts_known_credentials_without_changing_submitted_prompt(image_case, caplog):
    case = image_case
    error_reporting.register_secrets([KEY])
    prompt = f" \n{KEY}\n{quote(KEY, safe='')}\nAuthorization: Bearer fake-auth\nCookie: fake-cookie\n" + PROMPT
    result = generate(case, prompt)
    submitted = prompt[:1500] if case.profile == "pollinations" else prompt
    assert sent_prompt(case) == submitted
    expected = submitted.replace(KEY, "[REDACTED]").replace(quote(KEY, safe=""), "[REDACTED]")
    expected = expected.replace("Authorization: Bearer fake-auth", "Authorization: [REDACTED]")
    expected = expected.replace("Cookie: fake-cookie", "Cookie: [REDACTED]")
    image = next(case.root.glob("_images/*.png"))
    sidecar = image.with_suffix(".txt")
    assert sidecar.read_bytes() == expected.encode("utf-8")
    assert image.read_bytes() == PNG
    assert prompt[:100] in result and sidecar.name not in result
    for secret in (KEY, quote(KEY, safe=""), "fake-auth", "fake-cookie"):
        assert secret not in caplog.text and secret not in sidecar.read_text(encoding="utf-8")
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_sidecar_atomically_replaces_a_same_directory_temporary(image_case, monkeypatch):
    case = image_case
    expected = (PROMPT[:1500] if case.profile == "pollinations" else PROMPT).encode("utf-8")
    replace = bot_tools.os.replace
    observed = []

    def inspect_replace(source, target):
        source, target = Path(source), Path(target)
        assert source.parent == target.parent == case.root / "_images"
        assert source.name.startswith(f".{target.stem}.") and source.name.endswith(".txt.tmp")
        assert target.suffix == ".txt" and target.with_suffix(".png").read_bytes() == PNG
        assert source.read_bytes() == expected
        target.write_bytes(b"previous prompt")
        observed.append((source, target))
        return replace(source, target)

    monkeypatch.setattr(bot_tools.os, "replace", inspect_replace)
    generate(case)
    image, sidecar = saved_pair(case)
    assert len(observed) == 1 and observed[0][1] == sidecar
    assert not observed[0][0].exists() and image.exists()


class UnencodablePrompt(str):
    def encode(self, *args, **kwargs):
        raise UnicodeEncodeError("utf-8", self, 0, len(self), "synthetic metadata encoding failure")


def fail_sidecar_at(monkeypatch, stage):
    diagnostic = "must-not-appear-in-metadata-diagnostics: " + PROMPT
    if stage == "open":
        monkeypatch.setattr(bot_tools.tempfile, "NamedTemporaryFile", MagicMock(side_effect=OSError(diagnostic)))
    elif stage == "write":
        create = bot_tools.tempfile.NamedTemporaryFile

        def failing_file(*args, **kwargs):
            temporary = create(*args, **kwargs)
            temporary.write = MagicMock(side_effect=OSError(diagnostic))
            return temporary

        monkeypatch.setattr(bot_tools.tempfile, "NamedTemporaryFile", failing_file)
    elif stage == "replace":
        monkeypatch.setattr(bot_tools.os, "replace", MagicMock(side_effect=OSError(diagnostic)))
    else:
        redact = bot_tools.redact_sensitive_text
        monkeypatch.setattr(bot_tools, "redact_sensitive_text", lambda text: UnencodablePrompt(redact(text)))


@pytest.mark.parametrize("stage", ["open", "write", "replace", "encoding"])
@pytest.mark.parametrize("auto_send", [False, True], ids=["saved", "sent"])
def test_metadata_failure_preserves_exact_success_reply_delivery_and_one_request(image_case, monkeypatch, caplog, stage, auto_send):
    case = image_case
    monkeypatch.setattr(bot_tools, "datetime", SimpleNamespace(now=lambda zone: datetime(2026, 9, 13, tzinfo=zone)))
    monkeypatch.setattr(bot_tools.random, "randint", lambda low, high: low)
    expected_result = generate(case, auto_send=auto_send)
    image, sidecar = saved_pair(case)
    sidecar.unlink()
    image.unlink()
    case.session.reset_mock()
    case.message.channel.send.reset_mock()
    case.bot.memory.add_to_channel_memory.reset_mock()
    caplog.clear()
    fail_sidecar_at(monkeypatch, stage)
    result = generate(case, auto_send=auto_send)
    assert result == expected_result
    assert image.read_bytes() == PNG and set(image.parent.iterdir()) == {image}
    assert case.session.get.call_count + case.session.post.call_count == 1
    assert sent_prompt(case) == (PROMPT[:1500] if case.profile == "pollinations" else PROMPT)
    assert case.message.channel.send.await_count == int(auto_send)
    if auto_send:
        assert case.message.channel.send.await_args.kwargs["file"].fp.getvalue() == PNG
    case.bot.memory.add_to_channel_memory.assert_awaited_once()
    warnings = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    kind = "UnicodeEncodeError" if stage == "encoding" else "OSError"
    assert warnings == [f"Image prompt sidecar write failed ({kind})"]


def test_encoding_failure_retains_original_persistence_success_tuple(image_case, caplog):
    case = image_case
    path, url = bot_tools._persist_public_image(case.bot, PNG, submitted_prompt="private \ud800 prompt")
    image = next(case.root.glob("_images/*.png"))
    assert (path, url) == (str(image), f"{LOCAL}/bot/_images/{image.name}")
    assert image.read_bytes() == PNG and set(image.parent.iterdir()) == {image}
    warnings = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert warnings == ["Image prompt sidecar write failed (UnicodeEncodeError)"]
    case.session.get.assert_not_called()
    case.session.post.assert_not_called()


def test_cleanup_failure_is_private_and_does_not_abort_delivery(image_case, monkeypatch, caplog):
    case = image_case
    with monkeypatch.context() as patch:
        patch.setattr(bot_tools.os, "replace", MagicMock(side_effect=OSError(PROMPT)))
        patch.setattr(Path, "unlink", MagicMock(side_effect=PermissionError(PROMPT)))
        result = generate(case, auto_send=True)
    image = next(case.root.glob("_images/*.png"))
    assert image.read_bytes() == PNG and not image.with_suffix(".txt").exists()
    assert result.startswith("__IMAGE_SENT__ ") and f"Local path: {image} " in result
    assert "Image prompt sidecar" not in result and "https://redroom.zombiedawn.net" not in result
    case.message.channel.send.assert_awaited_once()
    assert case.message.channel.send.await_args.kwargs["file"].fp.getvalue() == PNG
    assert case.session.get.call_count + case.session.post.call_count == 1
    warnings = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert warnings == ["Image prompt sidecar write failed (OSError)", "Image prompt sidecar cleanup failed (PermissionError)"]
    leftovers = list(image.parent.glob(".*.txt.tmp"))
    assert len(leftovers) == 1
    leftovers[0].unlink()


@pytest.mark.parametrize("failure", ["http", "decode"])
def test_failed_request_creates_neither_image_nor_prompt(image_case, failure):
    case = image_case
    if failure == "http":
        case.response.status = 503
        case.response.text.return_value = "synthetic upstream failure"
    else:
        response = response_for(case.profile, b"")
        response.text.return_value = "{}"
        case.session.post.return_value = response
        case.session.get.return_value = response
    result = generate(case, auto_send=True)
    prefix = "Error generating image:" if case.profile == "pollinations" and failure == "http" else "Error:"
    assert result.startswith(prefix)
    assert list(case.root.glob("_images/*")) == []
    case.message.channel.send.assert_not_awaited()
    case.bot.memory.add_to_channel_memory.assert_not_awaited()
    assert case.session.get.call_count + case.session.post.call_count == 1


def test_cancelled_request_creates_neither_artifact(image_case):
    case = image_case
    case.response.__aenter__.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        generate(case, auto_send=True)
    assert list(case.root.glob("_images/*")) == []
    case.message.channel.send.assert_not_awaited()
    assert case.session.get.call_count + case.session.post.call_count == 1


@pytest.mark.parametrize("failure", ["discord", "memory"])
def test_later_delivery_or_memory_failure_preserves_saved_pair(image_case, failure):
    case = image_case
    if failure == "discord":
        case.message.channel.send.side_effect = discord.Forbidden(
            SimpleNamespace(status=403, reason="Forbidden"), "synthetic denial",
        )
        assert generate(case, auto_send=True).startswith("Error:")
        case.bot.memory.add_to_channel_memory.assert_not_awaited()
    else:
        case.bot.memory.add_to_channel_memory.side_effect = RuntimeError("synthetic memory failure")
        with pytest.raises(RuntimeError, match="synthetic memory failure"):
            generate(case, auto_send=True)
    saved_pair(case)
    case.message.channel.send.assert_awaited_once()
    assert case.session.get.call_count + case.session.post.call_count == 1


def synchronized_response(profile, image_bytes, barrier):
    response = response_for(profile, image_bytes)
    body = response.text.return_value

    async def read_body():
        await barrier.wait()
        return body

    async def read_chunks(size):
        await barrier.wait()
        yield image_bytes

    response.text = read_body
    response.content.iter_chunked = read_chunks
    return response


def test_overlapping_requests_pair_their_own_submitted_prompts_and_bytes(image_case, monkeypatch):
    case = image_case
    prompts = ["FIRST\n" + PROMPT, "SECOND\n" + PROMPT]
    submitted = [text[:1500] if case.profile == "pollinations" else text for text in prompts]
    images = {submitted[0]: PNG + b"first", submitted[1]: PNG + b"second"}
    numbers = count(100000)
    monkeypatch.setattr(bot_tools.random, "randint", lambda low, high: next(numbers))

    async def concurrent():
        barrier = asyncio.Barrier(2)

        def request_response(url, **kwargs):
            payload = kwargs.get("json")
            text = unquote(urlsplit(url).path.removeprefix("/prompt/")) if payload is None else (
                payload["messages"][0]["content"][0]["text"] if case.profile == "hd-chat" else payload["prompt"]
            )
            return synchronized_response(case.profile, images[text], barrier)

        case.session.post.side_effect = request_response
        case.session.get.side_effect = request_response
        async with asyncio.timeout(5):
            return await asyncio.gather(*(case.tool.execute(case.message, prompt=text) for text in prompts))

    results = asyncio.run(concurrent())
    files = list(case.root.glob("_images/*.png"))
    assert len(files) == 2 and len(list(case.root.glob("_images/*"))) == 4
    paths = {}
    for image in files:
        text = image.with_suffix(".txt").read_text(encoding="utf-8")
        assert image.read_bytes() == images[text]
        paths[text] = image
    assert set(paths) == set(submitted)
    for text, result in zip(submitted, results, strict=True):
        assert f"Local path: {paths[text]} " in result
        assert paths[text].with_suffix(".txt").name not in result
    assert case.session.get.call_count + case.session.post.call_count == 2
