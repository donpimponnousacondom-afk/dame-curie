import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import bot as botmod


def test_transcribe_riva_wav_sync_parses_results(monkeypatch, tmp_path):
    # nvidia-riva-client is an optional extra; skip rather than error when
    # it is not installed.
    pytest.importorskip("riva.client")
    wav_path = tmp_path / "utt.wav"
    wav_path.write_bytes(b"RIFF")

    class FakeWav:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getframerate(self):
            return 48000

        def getnchannels(self):
            return 1

        def getnframes(self):
            return 2

        def readframes(self, n):
            return b"\x00\x00\x00\x00"

    class FakeWave:
        @staticmethod
        def open(path, mode):
            assert path == str(wav_path)
            return FakeWav()

    class FakeService:
        def offline_recognize(self, audio_bytes, config):
            assert audio_bytes == b"\x00\x00\x00\x00"
            assert config.language_code == "es-ES"
            assert config.sample_rate_hertz == 48000
            assert config.audio_channel_count == 1
            assert not {"max_alternatives", "enable_automatic_punctuation", "verbatim_transcripts"} & vars(config).keys()
            return SimpleNamespace(
                results=[
                    SimpleNamespace(
                        alternatives=[SimpleNamespace(transcript=" hey Maxwell ")]
                    )
                ]
            )

    monkeypatch.setattr(botmod.Config, "NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setattr(botmod.Config, "ASR_RIVA_FUNCTION_ID", "synthetic-asr-function")
    monkeypatch.setattr(botmod.Config, "ASR_RIVA_LANGUAGE", "es-ES")
    monkeypatch.setitem(__import__("sys").modules, "wave", FakeWave)
    monkeypatch.setattr(botmod, "_riva_asr_service_cached", lambda *a, **k: FakeService())
    monkeypatch.setattr(
        __import__("riva.client", fromlist=["RecognitionConfig"]),
        "RecognitionConfig",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    text = botmod._transcribe_riva_wav_sync(str(wav_path))
    assert text == "hey Maxwell"
    monkeypatch.setattr(botmod.Config, "ASR_RIVA_FUNCTION_ID", "")
    with pytest.raises(RuntimeError, match="ASR_RIVA_FUNCTION_ID is not configured"):
        botmod._transcribe_riva_wav_sync(str(wav_path))
    monkeypatch.setattr(botmod.Config, "ASR_RIVA_FUNCTION_ID", "synthetic-asr-function")
    monkeypatch.setattr(botmod.Config, "ASR_RIVA_LANGUAGE", "")
    with pytest.raises(RuntimeError, match="ASR_RIVA_LANGUAGE is not configured"):
        botmod._transcribe_riva_wav_sync(str(wav_path))


@pytest.mark.parametrize("engine", ["gtts", "", "auto", "unknown"])
def test_transcribe_vc_wav_returns_empty_on_error(monkeypatch, engine):
    async def _run():
        def boom(_path):
            raise RuntimeError("no nvidia")

        monkeypatch.setattr(botmod, "_transcribe_riva_wav_sync", boom)
        return await botmod._transcribe_vc_wav("/tmp/missing.wav")

    assert asyncio.run(_run()) == ""
    gtts = Mock(side_effect=AssertionError("gTTS must not be constructed"))
    local = AsyncMock(side_effect=AssertionError("local fallback must not run"))
    subprocess = AsyncMock(side_effect=AssertionError("no subprocess should run"))
    monkeypatch.setitem(sys.modules, "gtts", SimpleNamespace(gTTS=gtts))
    monkeypatch.setattr(botmod.Config, "TTS_ENGINE", engine)
    monkeypatch.setattr(botmod, "_synthesize_local_tts_wav", local)
    monkeypatch.setattr(botmod.asyncio, "create_subprocess_exec", subprocess)
    reason = "SDK injects undeclared request parameters" if engine == "gtts" else "must explicitly select"
    with pytest.raises(ValueError, match=reason):
        asyncio.run(botmod._synthesize_tts_wav("synthetic text", "/unused/output.wav"))
    gtts.assert_not_called()
    local.assert_not_awaited()
    subprocess.assert_not_awaited()
