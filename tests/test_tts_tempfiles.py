import asyncio
import builtins
import errno
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot_tools import TtsTool


@pytest.fixture
def tts_runtime(monkeypatch, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    monkeypatch.setattr(TtsTool, "_last_tts", {})
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-riva")
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    for name in (
        "TTS_RIVA_VOICE",
        "TTS_RIVA_LANGUAGE",
        "TTS_RIVA_VOICE_ES",
        "TTS_RIVA_LANGUAGE_ES",
        "TTS_RIVA_FUNCTION_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    synthesize = Mock(return_value=SimpleNamespace(audio=b"\x01\x00" * 512))
    riva = ModuleType("riva")
    client = ModuleType("riva.client")
    proto = ModuleType("riva.client.proto")
    riva.client = client
    client.proto = proto
    client.Auth = Mock()
    client.SpeechSynthesisService = Mock(
        return_value=SimpleNamespace(synthesize=synthesize)
    )
    proto.riva_audio_pb2 = SimpleNamespace(AudioEncoding=SimpleNamespace(LINEAR_PCM=1))
    for name, module in (
        ("riva", riva),
        ("riva.client", client),
        ("riva.client.proto", proto),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    gtts = ModuleType("gtts")
    save = Mock(side_effect=lambda filename: Path(filename).write_bytes(b"gtts audio"))
    gtts.gTTS = Mock(return_value=SimpleNamespace(save=save))
    monkeypatch.setitem(sys.modules, "gtts", gtts)
    return SimpleNamespace(
        tool=TtsTool(
            SimpleNamespace(config=SimpleNamespace(NVIDIA_API_KEY="", FISH_API_KEY=""))
        ),
        scratch=scratch,
        cwd=cwd,
        riva=synthesize,
        gtts=gtts.gTTS,
        save=save,
    )


@pytest.fixture
def tts_media(monkeypatch):
    sources = []
    outputs = []

    async def subprocess_exec(*args, **kwargs):
        source = Path(args[-1] if args[0] == "ffprobe" else args[args.index("-i") + 1])
        assert source.is_absolute()
        assert source.is_file()
        sources.append(source)
        stdout = b"1.25"
        if args[0] == "ffmpeg" and args[-1] == "pipe:1":
            stdout = b"\x01\x00" * 512
        elif args[0] == "ffmpeg":
            output = Path(args[-1])
            assert output.parent == source.parent
            output.write_bytes(b"ogg audio")
            outputs.append(output)
            stdout = b""
        return SimpleNamespace(
            returncode=0, communicate=AsyncMock(return_value=(stdout, b""))
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", subprocess_exec)
    return SimpleNamespace(sources=sources, outputs=outputs)


@pytest.fixture
def tts_message():
    files = []

    async def send_message(channel_id, *, params):
        voice_file = params.files[0]
        path = Path(voice_file.fp.name)
        assert path.is_absolute()
        assert path.read_bytes() == b"ogg audio"
        assert voice_file.to_dict(0)["filename"] == "voice-message.ogg"
        assert voice_file.to_dict(0)["duration_secs"] == 1.25
        assert len(voice_file.to_dict(0)["waveform"]) > 0
        files.append(voice_file)

    send = AsyncMock(side_effect=send_message)
    message = SimpleNamespace(
        channel=SimpleNamespace(
            id=321, _state=SimpleNamespace(http=SimpleNamespace(send_message=send))
        )
    )
    return SimpleNamespace(message=message, send=send, files=files)


@pytest.mark.parametrize(
    "language, voice_name, language_code",
    [
        ("english", "Magpie-Multilingual.EN-US.Jason.Angry", "en-US"),
        ("spanish", "Magpie-Multilingual.ES-US.Jason.Angry", "es-US"),
    ],
)
def test_execute_riva_keeps_audio_until_discord_send_then_cleans(
    tts_runtime, tts_media, tts_message, language, voice_name, language_code
):
    result = asyncio.run(
        tts_runtime.tool.execute(
            tts_message.message, text="synthetic audio", language=language
        )
    )

    assert result == "__TTS_SENT__"
    tts_runtime.riva.assert_called_once_with(
        text="synthetic audio",
        voice_name=voice_name,
        language_code=language_code,
        sample_rate_hz=44100,
        encoding=1,
    )
    tts_runtime.gtts.assert_not_called()
    tts_message.send.assert_awaited_once()
    assert tts_message.files[0].fp.closed
    assert all(not path.exists() for path in tts_media.sources + tts_media.outputs)
    assert list(tts_runtime.scratch.iterdir()) == []
    assert list(tts_runtime.cwd.iterdir()) == []


def test_execute_riva_succeeds_with_read_only_cwd(
    monkeypatch, tts_runtime, tts_media, tts_message
):
    real_open = builtins.open

    def read_only_cwd_open(file, mode="r", *args, **kwargs):
        if (
            any(flag in mode for flag in "wax+")
            and Path(file).absolute().parent == tts_runtime.cwd
        ):
            raise OSError(errno.EROFS, "Read-only file system", str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_cwd_open)
    monkeypatch.setattr("io.open", read_only_cwd_open)
    with pytest.raises(OSError, match="Read-only file system"):
        open("tts_probe.wav", "wb")

    result = asyncio.run(
        tts_runtime.tool.execute(tts_message.message, text="synthetic")
    )

    assert result == "__TTS_SENT__"
    tts_runtime.gtts.assert_not_called()
    assert list(tts_runtime.scratch.iterdir()) == []
    assert list(tts_runtime.cwd.iterdir()) == []


def test_execute_gtts_fallback_uses_private_temp_path(
    tts_runtime, tts_media, tts_message
):
    tts_runtime.riva.side_effect = RuntimeError("synthetic Riva failure")

    result = asyncio.run(
        tts_runtime.tool.execute(
            tts_message.message, text="hola", lang="es", voice="mommy"
        )
    )

    assert result == "__TTS_SENT__"
    tts_runtime.riva.assert_called_once()
    tts_runtime.gtts.assert_called_once_with(text="hola", lang="es")
    path = Path(tts_runtime.save.call_args.args[0])
    assert path.is_absolute()
    assert path.parent.parent == tts_runtime.scratch
    assert not path.parent.exists()


def test_execute_fish_uses_real_helper_and_preserves_voice(
    monkeypatch, tts_runtime, tts_media, tts_message
):
    monkeypatch.setenv("FISH_API_KEY", "synthetic-fish")
    monkeypatch.setenv("TTS_FISH_MODEL", "synthetic-model")
    monkeypatch.setenv("TTS_FISH_FORMAT", "mp3")
    monkeypatch.setenv("TTS_FISH_REFERENCE_ID_MOMMY", "synthetic-mommy")
    response = SimpleNamespace(status=200, read=AsyncMock(return_value=b"fish" * 64))
    request = AsyncMock()
    request.__aenter__.return_value = response
    session = SimpleNamespace(post=Mock(return_value=request))
    monkeypatch.setattr(
        "bot_tools._get_shared_session", AsyncMock(return_value=session)
    )

    result = asyncio.run(
        tts_runtime.tool.execute(
            tts_message.message, text="[excited] synthetic", voice="mommy"
        )
    )

    assert result == "__TTS_SENT__"
    tts_runtime.riva.assert_not_called()
    tts_runtime.gtts.assert_not_called()
    assert session.post.call_args.kwargs["json"] == {
        "text": "[excited] synthetic",
        "format": "mp3",
        "reference_id": "synthetic-mommy",
    }
    assert session.post.call_args.kwargs["headers"]["model"] == "synthetic-model"
    assert list(tts_runtime.scratch.iterdir()) == []


def test_execute_failed_provider_cleans_partial_audio(
    tts_runtime, tts_media, tts_message
):
    tts_runtime.riva.side_effect = RuntimeError("synthetic Riva failure")

    def failed_save(filename):
        Path(filename).write_bytes(b"partial audio")
        raise RuntimeError("synthetic gTTS failure")

    tts_runtime.save.side_effect = failed_save
    result = asyncio.run(
        tts_runtime.tool.execute(tts_message.message, text="synthetic")
    )

    assert (
        result == "Error: all TTS providers failed (last error: synthetic gTTS failure)"
    )
    tts_message.send.assert_not_awaited()
    assert tts_media.sources == []
    assert list(tts_runtime.scratch.iterdir()) == []
    assert list(tts_runtime.cwd.iterdir()) == []


def test_execute_failed_send_cleans_audio_and_closes_file(
    tts_runtime, tts_media, tts_message
):
    files = []

    async def failed_send(channel_id, *, params):
        voice_file = params.files[0]
        assert Path(voice_file.fp.name).is_file()
        files.append(voice_file)
        raise RuntimeError("synthetic send failure")

    tts_message.send.side_effect = failed_send
    result = asyncio.run(
        tts_runtime.tool.execute(tts_message.message, text="synthetic")
    )

    assert (
        result == "Error sending TTS voice message to channel: synthetic send failure"
    )
    assert files[0].fp.closed
    assert list(tts_runtime.scratch.iterdir()) == []


@pytest.mark.parametrize("stage", ["provider", "conversion", "send"])
def test_execute_cancellation_cleans_temp_directory(
    monkeypatch, tts_runtime, tts_media, tts_message, stage
):
    async def run():
        entered = asyncio.Event()

        async def pause(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        if stage == "provider":
            monkeypatch.setenv("FISH_API_KEY", "synthetic-fish")
            response = SimpleNamespace(status=200, read=pause)
            request = AsyncMock()
            request.__aenter__.return_value = response
            session = SimpleNamespace(post=Mock(return_value=request))
            monkeypatch.setattr(
                "bot_tools._get_shared_session", AsyncMock(return_value=session)
            )
        elif stage == "conversion":
            monkeypatch.setattr(asyncio, "create_subprocess_exec", pause)
        else:
            tts_message.send.side_effect = pause
        task = asyncio.create_task(
            tts_runtime.tool.execute(tts_message.message, text="synthetic")
        )
        await asyncio.wait_for(entered.wait(), timeout=5)
        assert len(list(tts_runtime.scratch.iterdir())) == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert list(tts_runtime.scratch.iterdir()) == []

    asyncio.run(run())


def test_execute_concurrent_calls_have_independent_directories(
    monkeypatch, tts_runtime, tts_media
):
    monkeypatch.setattr("bot_tools.uuid.uuid4", lambda: SimpleNamespace(hex="a" * 32))

    async def run():
        paths = []
        both_sending = asyncio.Event()
        release_first = asyncio.Event()
        release_second = asyncio.Event()

        async def send_voice_file(path):
            paths.append(Path(path))
            if len(paths) == 2:
                both_sending.set()
            await (release_first if len(paths) == 1 else release_second).wait()
            assert Path(path).read_bytes() == b"ogg audio"

        tasks = [
            asyncio.create_task(
                tts_runtime.tool.execute(
                    SimpleNamespace(
                        channel=SimpleNamespace(id=channel),
                        send_voice_file=send_voice_file,
                    ),
                    text="synthetic",
                )
            )
            for channel in (111, 222)
        ]
        await asyncio.wait_for(both_sending.wait(), timeout=5)
        assert paths[0].name == paths[1].name
        assert paths[0].parent != paths[1].parent
        assert all(path.is_file() for path in paths)
        release_first.set()
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        assert next(iter(done)).result() == "__TTS_SENT__"
        assert not paths[0].parent.exists()
        assert paths[1].is_file()
        release_second.set()
        assert await next(iter(pending)) == "__TTS_SENT__"
        assert list(tts_runtime.scratch.iterdir()) == []

    asyncio.run(run())


def test_execute_cooldown_does_not_create_temp_audio(
    tts_runtime, tts_media, tts_message
):
    async def run():
        first = await tts_runtime.tool.execute(tts_message.message, text="synthetic")
        second = await tts_runtime.tool.execute(tts_message.message, text="synthetic")
        assert first == "__TTS_SENT__"
        assert second.startswith("Error: TTS on cooldown for this channel")

    asyncio.run(run())

    tts_runtime.riva.assert_called_once()
    tts_message.send.assert_awaited_once()
    assert list(tts_runtime.scratch.iterdir()) == []
