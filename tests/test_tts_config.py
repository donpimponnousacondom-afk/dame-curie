import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from config import Config
from bot_tools import (
    TtsTool,
    _fish_reference_id,
    _tts_language_key,
    _tts_riva_voice_config,
)


def test_fish_reference_id_resolves_named_voices(monkeypatch):
    monkeypatch.setenv("TTS_FISH_REFERENCE_ID_TIKTOK", "id-tiktok")
    monkeypatch.setenv("TTS_FISH_REFERENCE_ID_MOMMY", "id-mommy")
    monkeypatch.setenv("TTS_FISH_REFERENCE_ID_ESPANOL", "id-espanol")
    monkeypatch.setattr(Config, "TTS_FISH_REFERENCE_ID", "id-default")
    for voice in ("tiktok", "TikTok", "mommy", "espanol", "español", "spanish", "britney"):
        with pytest.raises(ValueError, match="TTS_FISH_REFERENCE_ID"):
            _fish_reference_id(voice)
    assert _fish_reference_id("id-default") == "id-default"
    assert _fish_reference_id("") == "id-default"
    assert _fish_reference_id(None) == "id-default"


def test_fish_reference_id_falls_back_to_hardcoded_default(monkeypatch):
    monkeypatch.delenv("TTS_FISH_REFERENCE_ID_TIKTOK", raising=False)
    monkeypatch.delenv("TTS_FISH_REFERENCE_ID_MOMMY", raising=False)
    monkeypatch.delenv("TTS_FISH_REFERENCE_ID_ESPANOL", raising=False)
    monkeypatch.delenv("TTS_FISH_REFERENCE_ID", raising=False)

    monkeypatch.setattr(Config, "TTS_FISH_REFERENCE_ID", "")
    with pytest.raises(ValueError, match="TTS_FISH_REFERENCE_ID"):
        _fish_reference_id("tiktok")
    assert _fish_reference_id(None) == ""


def test_tts_language_key_accepts_spanish_aliases():
    assert _tts_language_key(language="spanish") == "spanish"
    assert _tts_language_key(lang="es") == "spanish"
    assert _tts_language_key(language="es-ES") == "spanish"


def test_tts_language_key_defaults_to_english():
    assert _tts_language_key() == "english"
    assert _tts_language_key(language="unknown") == "english"


def test_tts_spanish_riva_default_matches_available_nvidia_voice(monkeypatch):
    monkeypatch.setattr(Config, "TTS_RIVA_VOICE", "configured-spanish")
    monkeypatch.setattr(Config, "TTS_RIVA_LANGUAGE", "es-US")
    assert _tts_riva_voice_config("spanish") == ("configured-spanish", "es-US")
    with pytest.raises(ValueError, match="TTS_RIVA_LANGUAGE"):
        _tts_riva_voice_config("english")


def test_tts_english_riva_default_unchanged(monkeypatch):
    monkeypatch.setattr(Config, "TTS_RIVA_VOICE", "configured-english")
    monkeypatch.setattr(Config, "TTS_RIVA_LANGUAGE", "en-US")
    assert _tts_riva_voice_config("english") == ("configured-english", "en-US")


def test_tts_spanish_falls_back_to_gtts_without_nvidia_key(monkeypatch, tmp_path):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    calls = []

    gtts_module = ModuleType("gtts")

    class FakeGTTS:
        def __init__(self, text):
            calls.append(text)

        def save(self, filename):
            (tmp_path / filename).write_bytes(b"fake audio")

    gtts_module.gTTS = FakeGTTS
    monkeypatch.setitem(sys.modules, "gtts", gtts_module)

    class FakeProc:
        def __init__(self, returncode=0, stdout=b""):
            self.returncode = returncode
            self._stdout = stdout

        async def communicate(self):
            return self._stdout, b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        if args[0] == "ffprobe":
            return FakeProc(stdout=b"1.0")
        if args[0] == "ffmpeg" and args[-1] == "pipe:1":
            return FakeProc(stdout=(1).to_bytes(2, "little", signed=True) * 512)
        if args[0] == "ffmpeg":
            (tmp_path / args[-1]).write_bytes(b"fake ogg")
            return FakeProc()
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    sent = []

    async def send_message(channel_id, *, params):
        sent.append(params.files[0].fp.name)

    message = SimpleNamespace(
        id=123,
        channel=SimpleNamespace(
            id=0, _state=SimpleNamespace(http=SimpleNamespace(send_message=send_message))
        ),
    )

    async def run():
        with pytest.raises(ValueError, match="gtts is unsupported.*unconfigured"):
            await TtsTool(
                SimpleNamespace(config=SimpleNamespace(TTS_ENGINE="gtts", NVIDIA_API_KEY=""))
            ).execute(message, text="hola mundo")

    asyncio.run(run())

    assert calls == []
    assert sent == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fmt", [None, "", "mp3", "wav"])
def test_fish_tts_writes_audio_on_success(monkeypatch, tmp_path, fmt):
    """The Fish provider must POST its OpenAI-shaped speech request and write
    the response bytes to output_path."""
    from bot_tools import _synthesize_fish_tts

    captured = {}

    class FakeResponse:
        status = 200

        async def read(self):
            return b"\xff\xfb" + b"X" * 200  # fake mp3 magic + payload

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def post(self, url, json=None, headers=None, timeout=None, allow_redirects=True):
            captured["allow_redirects"] = allow_redirects
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("bot_tools._get_shared_session", fake_get_session)

    out = tmp_path / "fish.mp3"

    async def run():
        result = await _synthesize_fish_tts(
            "hello fish",
            str(out),
            api_key="sk-fish-test",
            model="s2.1-pro-free",
            reference_id="abc123",
            fmt=fmt,
        )
        assert result == str(out)

    asyncio.run(run())

    assert captured["url"] == "https://api.ppq.ai/v1/audio/speech"
    assert captured["allow_redirects"] is False
    assert captured["headers"]["Authorization"] == "Bearer sk-fish-test"
    assert captured["json"]["model"] == "s2.1-pro-free"
    assert captured["json"]["input"] == "hello fish"
    assert captured["json"]["voice"] == "abc123"
    expected = {"model": "s2.1-pro-free", "input": "hello fish", "voice": "abc123"}
    if fmt is not None:
        expected["response_format"] = fmt
    assert captured["json"] == expected
    assert out.read_bytes().startswith(b"\xff\xfb")
    assert len(out.read_bytes()) == 202


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308, 401])
def test_fish_tts_returns_none_on_api_error(monkeypatch, code):
    """A rejection remains visible instead of selecting another provider."""
    from bot_tools import _synthesize_fish_tts

    calls = []

    class FakeResponse:
        status = code

        async def read(self):
            return b""

        async def text(self):
            return "unauthorized"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            assert kwargs["allow_redirects"] is False
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("bot_tools._get_shared_session", fake_get_session)

    async def run():
        with pytest.raises(RuntimeError, match=f"{code}.*unauthorized"):
            await _synthesize_fish_tts(
                "x", "/tmp/should_not_exist.mp3", api_key="synthetic-key",
                model="s2.1-pro-free", reference_id="configured-voice",
            )

    asyncio.run(run())
    assert len(calls) == 1


def test_fish_tts_returns_none_when_key_missing():
    """Missing required configuration fails before contacting a service."""
    from bot_tools import _synthesize_fish_tts

    async def run():
        with pytest.raises(ValueError, match="FISH_API_KEY"):
            await _synthesize_fish_tts(
                "x", "/tmp/x.mp3", api_key="", model="s2.1-pro-free", reference_id=""
            )

    asyncio.run(run())


def test_tts_tool_prefers_fish_over_riva(monkeypatch, tmp_path):
    """When FISH_API_KEY is set, TtsTool must call Fish first and skip Riva."""
    from bot_tools import TtsTool

    fish_calls = []
    riva_called = {"count": 0}

    async def fake_fish(text, output_path, *, api_key, model, reference_id, fmt):
        fish_calls.append((text, output_path, model, reference_id))
        # Simulate writing a real audio file.
        (tmp_path / output_path).write_bytes(b"\xff\xfb" + b"X" * 200)
        return output_path

    def fake_riva(*args, **kwargs):
        riva_called["count"] += 1
        raise AssertionError("Riva should NOT be called when Fish succeeds")

    monkeypatch.setenv("FISH_API_KEY", "sk-fish-test")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr("bot_tools._synthesize_fish_tts", fake_fish)

    # Stub ffmpeg/ffprobe subprocess calls the downstream pipeline runs.
    class FakeProc:
        def __init__(self, returncode=0, stdout=b""):
            self.returncode = returncode
            self.stdout = stdout

        async def communicate(self):
            return self.stdout, b""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeOggProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        if args[0] == "ffprobe":
            return FakeProc(stdout=b"1.0")
        if args[0] == "ffmpeg" and args[-1] == "pipe:1":
            return FakeProc(stdout=(1).to_bytes(2, "little", signed=True) * 512)
        if args[0] == "ffmpeg":
            # Write the OGG output file the rest of the code expects.
            Path(args[-1]).write_bytes(b"fake ogg")
            return FakeOggProc()
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.chdir(tmp_path)

    sent = []

    async def send_message(channel_id, *, params):
        sent.append(params.files[0].fp.name)

    message = SimpleNamespace(
        id=999,
        channel=SimpleNamespace(
            id=0, _state=SimpleNamespace(http=SimpleNamespace(send_message=send_message))
        ),
    )

    async def run():
        result = await TtsTool(
            SimpleNamespace(
                config=SimpleNamespace(
                    TTS_ENGINE="fish", NVIDIA_API_KEY="", FISH_API_KEY="sk-fish-test",
                    TTS_FISH_MODEL="s2.1-pro-free", TTS_FISH_REFERENCE_ID="configured-voice",
                    TTS_FISH_FORMAT=None,
                )
            )
        ).execute(
            message,
            text="hello from fish",
        )
        assert result == "__TTS_SENT__"

    asyncio.run(run())

    assert len(fish_calls) == 1
    assert fish_calls[0][0] == "hello from fish"
    assert fish_calls[0][2] == "s2.1-pro-free"
    assert len(sent) == 1
    assert Path(sent[0]).is_absolute()
    assert Path(sent[0]).name.startswith("tts_") and sent[0].endswith(".ogg")
    assert not Path(sent[0]).parent.exists()
