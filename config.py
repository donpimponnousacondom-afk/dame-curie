"""Configuration management for Maxwell Bot.

Design note — optional features
-------------------------------
Maxwell only *requires* two things: a Discord token and an OpenAI-compatible
model endpoint. Everything else (voice, YouTube, web search, TTS,
video frames, RAG embeddings) is optional and gated behind an ``ENABLE_*``
switch.

Those switches are tri-state:

    true   -> force on  (you promise the dependency is installed)
    false  -> force off (never register the tool / import the dep)
    auto   -> DEFAULT. Turn the feature on only if its dependency is
              actually present on this machine.

"auto" is what makes a bare ``git clone`` + ``.venv/bin/python -m pip install -r
requirements.txt`` work: features whose system package, Python package or
API key is missing quietly stay off instead of erroring on first use, and
``.venv/bin/python doctor.py`` explains every decision.
"""

import math
import os
import shutil
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import ClassVar

from dotenv.main import load_dotenv

APP_ROOT = Path(__file__).resolve().parent
ENV_FILE = Path(os.getenv("DAME_CURIE_ENV_FILE", APP_ROOT / ".env"))
# Runtime configuration overrides the inherited process environment.
load_dotenv(ENV_FILE, override=True)


def _int_env(
    name: str, default: int, min_value: int | None = None, max_value: int | None = None
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _float_env(
    name: str,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if not math.isfinite(value):
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _json_env(name: str, *, strict: bool = False) -> dict:
    """Read a JSON object; strict request options fail closed on malformed input."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    try:
        import json

        value = json.loads(raw)
    except (TypeError, ValueError):
        if strict:
            raise ValueError(f"{name} must be a valid JSON object") from None
        print(f"warning: {name} is not valid JSON — ignoring it", file=sys.stderr)
        return {}
    if strict and not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value if isinstance(value, dict) else {}


def _first_env(*names: str, default: str = "") -> str:
    """First non-empty value among ``names`` (aliases), else ``default``."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


# --- optional-feature detection -------------------------------------------
# Every check below is cheap and runs once, at import: find_spec() does NOT
# execute the module, and shutil.which() is a PATH scan. Restart to re-detect
# after installing something.

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _has_module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _has_binary(name: str) -> bool:
    """True if ``name`` is runnable: on PATH, or beside this interpreter.

    The second case matters for venv installs started by absolute
    interpreter path: the venv's bin/ holds the
    console scripts but is not on PATH.
    """
    if not name:
        return False
    if shutil.which(name):
        return True
    sibling = Path(sys.executable).parent / name
    return sibling.is_file() and os.access(sibling, os.X_OK)


# Human-readable reason for each feature decision, filled in by
# _feature_env(). Consumed by Config.feature_report() / doctor.py.
FEATURE_REASONS: dict[str, str] = {}


def _feature_env(
    name: str,
    detect=None,
    *,
    needs: str = "",
    default: bool = True,
    on_text: str = "",
    off_text: str = "",
) -> bool:
    """Resolve a tri-state ENABLE_* switch (true / false / auto).

    ``detect`` is a zero-arg callable returning True when the feature's
    dependency is available. With no ``detect`` the feature has no external
    dependency and ``auto`` means ``default``. Accepts the legacy plain
    booleans, so an existing .env keeps behaving exactly as before.
    """
    raw = (os.getenv(name) or "").strip().lower()
    if raw in _TRUE:
        FEATURE_REASONS[name] = f"forced on ({name}=true)"
        return True
    if raw in _FALSE:
        FEATURE_REASONS[name] = f"disabled ({name}=false)"
        return False
    # auto / unset / garbage
    if detect is None:
        FEATURE_REASONS[name] = "on by default" if default else "off by default"
        return default
    if detect():
        FEATURE_REASONS[name] = (
            on_text or (f"auto: {needs} found" if needs else "auto: available")
        )
        return True
    FEATURE_REASONS[name] = off_text or (
        f"auto: off, {needs} not installed" if needs else "auto: off, dependency missing"
    )
    return False


class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("OPENAI_COMPAT_API_KEY", ""))
    # No default model on purpose: a hardcoded one that your endpoint does
    # not serve fails later, as an opaque 404 from the provider. Empty fails
    # at startup with a sentence that says what to do.
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()
    OPENAI_REM_MODEL = os.getenv("OPENAI_REM_MODEL") or OPENAI_MODEL
    # max_tokens = max *output* tokens per completion (not context window).
    # minimax-m3 allows huge context but caps output ~131072; 8192 is a sane default.
    OPENAI_MAX_TOKENS = _int_env(
        "OPENAI_MAX_TOKENS", 16384, min_value=1, max_value=131072
    )
    OPENAI_TEMPERATURE = _float_env("OPENAI_TEMPERATURE", 0.6, min_value=0.0)
    OPENAI_TOP_P = _float_env("OPENAI_TOP_P", 0.95, min_value=0.0, max_value=1.0)
    OPENAI_TOP_K = _int_env("OPENAI_TOP_K", 20, min_value=0)
    OPENAI_DISABLE_REASONING = _bool_env("OPENAI_DISABLE_REASONING", False)
    OPENAI_EXTRA_HEADERS = _json_env("OPENAI_EXTRA_HEADERS", strict=True)
    OPENAI_EXTRA_BODY = _json_env("OPENAI_EXTRA_BODY", strict=True)
    OPENAI_FALLBACK_BASE_URL = os.getenv("OPENAI_FALLBACK_BASE_URL", "").strip()
    OPENAI_FALLBACK_API_KEY = os.getenv("OPENAI_FALLBACK_API_KEY", "").strip()
    OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "").strip()
    OPENAI_FALLBACK_DISABLE_REASONING = _bool_env(
        "OPENAI_FALLBACK_DISABLE_REASONING", True
    )
    # Optional vision/omni model for image/video (and audio, if enabled) turns.
    # Text-only primaries like deepseek-v4-flash 400 on image_url; when this is
    # set, media requests go here first. Blank base/key inherit the primary.
    OPENAI_VISION_BASE_URL = os.getenv("OPENAI_VISION_BASE_URL", "").strip()
    OPENAI_VISION_API_KEY = os.getenv("OPENAI_VISION_API_KEY", "").strip()
    OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "").strip()
    OPENAI_VISION_DISABLE_REASONING = _bool_env("OPENAI_VISION_DISABLE_REASONING", True)
    OPENAI_RETRY_ATTEMPTS = _int_env(
        "OPENAI_RETRY_ATTEMPTS", 5, min_value=1, max_value=10
    )
    # Up to this many remaining attempts can recover empty HTTP 200 content
    # with a different endpoint and non-streaming request. The total attempt
    # budget is not extended.
    OPENAI_EMPTY_RESPONSE_RETRIES = _int_env(
        "OPENAI_EMPTY_RESPONSE_RETRIES", 2, min_value=0, max_value=5
    )

    # Toggle for "omni" (audio+vision capable) model input. On by default:
    # Gemini behind the current proxy transcribes wav/mp3; endpoints that
    # 400 on input_audio fall back to text-only via the media-incapable path.
    # The process_audio control can still turn it off at runtime.
    ENABLE_AUDIO_INPUT = _feature_env("ENABLE_AUDIO_INPUT", default=True)

    # -------------------------------------------------------------------------
    # Optional features (true / false / auto — see the module docstring).
    #
    # Unset means "auto": the feature turns itself on only when whatever it
    # needs is actually installed. A bare clone with nothing but ffmpeg
    # missing loses video frames, not the whole bot. Read once at import
    # time; restart to re-detect.
    # -------------------------------------------------------------------------

    # No external dependency — pure code paths, on by default.
    ENABLE_IMAGE_INPUT = _feature_env("ENABLE_IMAGE_INPUT")
    ENABLE_FETCH_URL = _feature_env("ENABLE_FETCH_URL")
    ENABLE_AVATAR = _feature_env("ENABLE_AVATAR")
    ENABLE_AUTONOMY = _feature_env("ENABLE_AUTONOMY")
    # image_generator uses Pollinations (free, keyless); hd_image requires a
    # dedicated GEMINI_IMAGE_BASE_URL and returns a clear error when unset.
    ENABLE_IMAGE_GEN = _feature_env("ENABLE_IMAGE_GEN")

    # Needs a system binary or Python package.
    ENABLE_VIDEO_INPUT = _feature_env(
        "ENABLE_VIDEO_INPUT", lambda: _has_binary("ffmpeg"), needs="ffmpeg"
    )
    # The tool shells out to the yt-dlp binary, so the binary is what counts.
    ENABLE_YOUTUBE = _feature_env(
        "ENABLE_YOUTUBE", lambda: _has_binary("yt-dlp"), needs="the yt-dlp binary"
    )
    ENABLE_WEB_SEARCH = _feature_env(
        "ENABLE_WEB_SEARCH", lambda: _has_module("ddgs"), needs="the ddgs package"
    )
    ENABLE_VC = _feature_env(
        "ENABLE_VC",
        lambda: _has_module("discord.ext.voice_recv") and _has_module("nacl"),
        needs="discord-ext-voice-recv + PyNaCl",
    )
    # TTS works through any one of: Fish (key), NVIDIA Riva (key), gTTS
    # (package), espeak (binary). Off only when none of them exist.
    ENABLE_TTS = _feature_env(
        "ENABLE_TTS",
        lambda: bool(
            os.getenv("FISH_API_KEY", "").strip()
            or os.getenv("NVIDIA_API_KEY", "").strip()
            or _has_module("gtts")
            or _has_binary("espeak-ng")
            or _has_binary("espeak")
        ),
        needs="a TTS engine (espeak-ng, gTTS, or a Fish/NVIDIA key)",
    )
    # Playing TTS into a voice channel additionally needs ffmpeg.
    ENABLE_TTS_VC = _feature_env(
        "ENABLE_TTS_VC",
        lambda _tts=ENABLE_TTS: _tts and _has_binary("ffmpeg"),
        needs="ffmpeg + a TTS engine",
    )
    DAME_CURIE_USER_ID = os.getenv("DAME_CURIE_USER_ID", "1545541390392369165").strip()
    CREATOR_NAME = os.getenv("CREATOR_NAME", ".normal.man").strip() or ".normal.man"
    CREATOR_ID = os.getenv("CREATOR_ID", "1482143139828596916").strip() or "1482143139828596916"
    BOT_NAME = os.getenv("BOT_NAME", "Dame Curie").strip() or "Dame Curie"

    # Shell stays on by default inside the outer bot container, sharing the
    # bot user's permissions and mounted state rather than an inner sandbox.
    # validate() warns at startup about that access.
    ENABLE_SHELL = _feature_env("ENABLE_SHELL")

    # RAG vector memory. Needs a reachable embedding endpoint (see
    # EMBED_* below); without one the bot still works, it just loses
    # semantic recall and falls back to recent-history context.
    ENABLE_RAG = _feature_env("ENABLE_RAG")
    RAG_WEB_STORE_ENABLED = _bool_env("RAG_WEB_STORE_ENABLED", True)

    # -------------------------------------------------------------------------
    # Embeddings for RAG memory. Defaults target a local Ollama, but any
    # OpenAI-compatible /v1/embeddings endpoint works — set EMBED_BASE_URL
    # to e.g. https://api.openai.com/v1 with EMBED_MODEL/EMBED_DIM to match.
    # -------------------------------------------------------------------------
    EMBED_BASE_URL = _first_env(
        "DAME_CURIE_EMBED_BASE_URL", "EMBED_BASE_URL", default="http://localhost:11434"
    ).rstrip("/")
    EMBED_MODEL = _first_env(
        "DAME_CURIE_EMBED_MODEL", "EMBED_MODEL", default="qwen3-embedding:0.6b"
    )
    EMBED_API_KEY = _first_env("DAME_CURIE_EMBED_API_KEY", "EMBED_API_KEY")
    EMBED_DIM = _int_env("DAME_CURIE_EMBED_DIM", 1024, min_value=8, max_value=16384)

    # When false (default), shell refuses to run on a turn
    # that read untrusted fetched content (URLs, web search) without an
    # out-of-band `!confirm` from an admin. This blocks indirect prompt
    # injection from turning a fetched page into a shell command.
    # Set to true to skip the gate entirely — the model can call shell
    # after fetch_url/web_search without confirmation. Only do this if
    # you trust the model fully (single-user homelab install).
    DISABLE_TAINT_GATE = _bool_env("DISABLE_TAINT_GATE", False)

    # TTS engine selection. local / riva / gtts / auto. Undocumented before
    # 2026-07-21 — used to fall through a chain in bot._synthesize_tts_wav.
    TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").strip().lower()

    # Vendor-neutral shared auth fallback when primary/AUTONOMY/AUX keys are unset.
    OPENAI_COMPAT_API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()

    AUTONOMY_BASE_URL = os.getenv("AUTONOMY_BASE_URL", "").strip()
    AUTONOMY_API_KEY = os.getenv(
        "AUTONOMY_API_KEY", os.getenv("OPENAI_COMPAT_API_KEY", "")
    ).strip()
    AUTONOMY_MODEL = os.getenv("AUTONOMY_MODEL", "").strip()
    AUTONOMY_DISABLE_REASONING = _bool_env("AUTONOMY_DISABLE_REASONING", False)

    # Auxiliary background agents (REM, context-cleanup, context-watcher).
    # These are the "context manager" brains — separate from the autonomy
    # tick loop so they can run on a different (e.g. cheaper/faster) model
    # than autonomy. Defaults fall back to the autonomy config, which in
    # turn falls back to the main OPENAI_* provider, so a fresh install
    # with no AUX_* vars behaves exactly as before (all background agents
    # shared one endpoint).
    AUX_BASE_URL = os.getenv("AUX_BASE_URL", "").strip()
    AUX_API_KEY = os.getenv(
        "AUX_API_KEY", os.getenv("OPENAI_COMPAT_API_KEY", "")
    ).strip()
    AUX_MODEL = os.getenv("AUX_MODEL", "").strip()
    AUX_DISABLE_REASONING = _bool_env("AUX_DISABLE_REASONING", True)

    # Live tool progress messages. OFF by default: a per-server `!progress on`
    # opts a server in, and DAME_CURIE_PROGRESS_MESSAGES=true enables it for every
    # server as a baseline. `!progress off` silences a noisy server even under
    # the env baseline; DMs never get them. See tool_progress.py.
    PROGRESS_MESSAGES = _bool_env("DAME_CURIE_PROGRESS_MESSAGES", False)

    # Custom streaming tool-call protocol. Native OpenAI-style tools= doesn't
    # stream incrementally on some providers (notably Ollama cloud's
    # minimax-m3): the entire {name, arguments} block arrives in one final
    # delta at ~88% of stream time, so the bot's progress message stays
    # silent for the full 10-30s of generation. When this flag is on, the
    # bot asks the model to emit the tool call as a bare JSON object on its
    # own line ({"name": "...", "arguments": {...}}) and parses it from the
    # text stream AS IT STREAMS. Tool name lands in the progress UI at
    # ~12% of stream time vs ~88% for native. OFF by default to keep native
    # behavior; turn on with DAME_CURIE_CUSTOM_TOOL_CALLS=true in .env.
    CUSTOM_TOOL_CALLS = _bool_env("DAME_CURIE_CUSTOM_TOOL_CALLS", False)

    # Discord join-captcha handling. Discord sometimes challenges an invite
    # accept (or other API action) with an hCaptcha — surfaced by the library
    # as discord.CaptchaRequired. When CAPTCHA_SOLVER_SERVICE+API_KEY are set,
    # the bot solves the challenge via the external service and auto-retries.
    # When unset, the challenge details are surfaced in the tool result so the
    # user sees exactly why the join failed. Supported services: capsolver,
    # 2captcha.
    CAPTCHA_SOLVER_SERVICE = os.getenv("CAPTCHA_SOLVER_SERVICE", "").strip().lower()
    CAPTCHA_SOLVER_API_KEY = os.getenv("CAPTCHA_SOLVER_API_KEY", "").strip()
    CAPTCHA_SOLVER_TIMEOUT = _int_env(
        "CAPTCHA_SOLVER_TIMEOUT", 180, min_value=10, max_value=600
    )

    POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "MarcosFRG/sdxl-lightning")
    IMAGE_GEN_PROTOCOL = os.getenv("IMAGE_GEN_PROTOCOL", "pollinations").strip().lower()
    IMAGE_GEN_BASE_URL = os.getenv("IMAGE_GEN_BASE_URL", "").strip()
    IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY", "").strip()
    IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "gpt-image-2").strip()
    IMAGE_GEN_QUALITY = os.getenv("IMAGE_GEN_QUALITY", "low").strip()
    IMAGE_GEN_TIMEOUT = _int_env(
        "IMAGE_GEN_TIMEOUT", 300, min_value=30, max_value=900
    )

    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_IMAGE_URL = os.getenv(
        "NVIDIA_IMAGE_URL",
        "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev",
    )
    # NVIDIA Riva ASR (Parakeet) for live VC transcription. Whisper is too
    # slow for this path; VC utterances go through Riva then the text model.
    ASR_RIVA_FUNCTION_ID = os.getenv(
        "ASR_RIVA_FUNCTION_ID", "1598d209-5e27-4d3c-8079-4751568b1081"
    ).strip()
    ASR_RIVA_LANGUAGE = os.getenv("ASR_RIVA_LANGUAGE", "en-US").strip() or "en-US"

    # Legacy ChatGPT2API image endpoint. Kept only so an existing .env does
    # not error on load — hd_image no longer uses it (that host dropped every
    # image model and now 404s on /v1/images/generations).
    GPT_IMAGE_URL = os.getenv("GPT_IMAGE_URL", "")
    GPT_IMAGE_API_KEY = os.getenv("GPT_IMAGE_API_KEY", "")

    GEMINI_IMAGE_PROTOCOL = os.getenv(
        "GEMINI_IMAGE_PROTOCOL", "chat_completions"
    ).strip().lower()
    GEMINI_IMAGE_QUALITY = os.getenv("GEMINI_IMAGE_QUALITY", "high").strip()
    GEMINI_IMAGE_BASE_URL = os.getenv("GEMINI_IMAGE_BASE_URL", "").strip()
    GEMINI_IMAGE_API_KEY = os.getenv("GEMINI_IMAGE_API_KEY", "").strip()
    GEMINI_IMAGE_MODEL = (
        os.getenv("GEMINI_IMAGE_MODEL", "").strip() or "gemini-3.1-flash-image"
    )
    # Input images are downscaled to this longest edge before upload. Payload
    # size dominates latency on this endpoint: a 629KB input took 89s where
    # the same edit with a 64KB input took 20s.
    GEMINI_IMAGE_MAX_INPUT_EDGE = _int_env(
        "GEMINI_IMAGE_MAX_INPUT_EDGE", 1024, min_value=256, max_value=4096
    )
    GEMINI_IMAGE_TIMEOUT = _int_env(
        "GEMINI_IMAGE_TIMEOUT", 300, min_value=30, max_value=900
    )

    MEMORY_MESSAGE_LIMIT = _int_env(
        "MEMORY_MESSAGE_LIMIT", 2000, min_value=1, max_value=10000
    )
    # REM is a background LLM loop: it spends tokens on its own schedule.
    # Opt-in, so a fresh install never quietly bills you. `ENABLE_REM` is
    # accepted as an alias because that is the name the docs always used.
    REM_ENABLED = _bool_env("REM_ENABLED", _bool_env("ENABLE_REM", False))
    FEATURE_REASONS["REM_ENABLED"] = (
        "enabled in .env" if REM_ENABLED else "off by default (opt in with ENABLE_REM=true)"
    )
    REM_INTERVAL_SECONDS = _int_env("REM_INTERVAL_SECONDS", 600, min_value=10)
    REM_MAX_TURNS = _int_env("REM_MAX_TURNS", 3, min_value=0, max_value=10)
    REM_EVENT_BUFFER_MAX = _int_env(
        "REM_EVENT_BUFFER_MAX", 500, min_value=1, max_value=10000
    )
    REM_RUN_HISTORY = _int_env("REM_RUN_HISTORY", 50, min_value=1, max_value=1000)

    DATA_DIR = os.getenv("DATA_DIR", "data")
    DAME_CURIE_PROMPTS_DIR = os.getenv("DAME_CURIE_PROMPTS_DIR", "").strip()
    LOGS_DIR = os.getenv("LOGS_DIR", os.getenv("LOGS", "logs"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

    DAME_CURIE_SITE_DIR = os.getenv("DAME_CURIE_SITE_DIR", "public/bot")
    DAME_CURIE_PUBLIC_BASE_URL = os.getenv(
        "DAME_CURIE_PUBLIC_BASE_URL", "https://dame-curie.example.invalid"
    )
    DAME_CURIE_SITE_PUBLIC_BASE_URL = os.getenv("DAME_CURIE_SITE_PUBLIC_BASE_URL", "").strip()

    # Owner allowlist. Re-exported here so Config is the single
    # source of truth; bot_tools.refresh_owner_ids() still does a runtime
    # reload but the initial parse lives here.
    DAME_CURIE_OWNER_IDS: ClassVar[set[str]] = {
        item.strip()
        for item in os.getenv("DAME_CURIE_OWNER_IDS", "").split(",")
        if item.strip()
    }

    # Every optional feature, in the order doctor.py and the startup log
    # print them. (attribute, human label).
    FEATURE_SWITCHES = (
        ("ENABLE_IMAGE_INPUT", "image input (vision)"),
        ("ENABLE_VIDEO_INPUT", "video input (frame extraction)"),
        ("ENABLE_AUDIO_INPUT", "audio input (omni models)"),
        ("ENABLE_IMAGE_GEN", "image generation"),
        ("ENABLE_TTS", "text-to-speech"),
        ("ENABLE_TTS_VC", "TTS playback in voice channels"),
        ("ENABLE_VC", "voice channels (live listening)"),
        ("ENABLE_WEB_SEARCH", "web search"),
        ("ENABLE_FETCH_URL", "fetch_url"),
        ("ENABLE_YOUTUBE", "YouTube"),
        ("ENABLE_AVATAR", "avatar changes"),
        ("ENABLE_SHELL", "shell (outer container)"),
        ("ENABLE_RAG", "RAG vector memory"),
        ("ENABLE_AUTONOMY", "autonomy engine"),
        ("REM_ENABLED", "REM dreaming pass"),
    )

    @classmethod
    def feature_report(cls) -> list[tuple[str, str, bool, str]]:
        """(env name, label, enabled, reason) for every optional feature."""
        report = []
        for name, label in cls.FEATURE_SWITCHES:
            enabled = bool(getattr(cls, name, False))
            reason = FEATURE_REASONS.get(name, "")
            if not reason:
                reason = "set in .env" if os.getenv(name) else "default"
            report.append((name, label, enabled, reason))
        return report

    @classmethod
    def validate(cls):
        # Discord token and explicit remote endpoint/model are required.
        # Other features default or degrade to "feature off", which is the
        # point of the ENABLE_*=auto design.
        if not cls.DISCORD_TOKEN:
            raise ValueError(
                "DISCORD_TOKEN is required. Run ./setup.sh, or set it in .env, "
                "then start the bot again."
            )
        if not cls.OPENAI_BASE_URL:
            raise ValueError(
                "OPENAI_BASE_URL is required — set your remote OpenAI-compatible "
                "chat endpoint explicitly; no vendor or endpoint is assumed."
            )
        if not cls.OPENAI_MODEL:
            raise ValueError(
                "OPENAI_MODEL is required — set the model name your endpoint serves."
            )
        if cls.OPENAI_MAX_TOKENS < 1:
            raise ValueError("OPENAI_MAX_TOKENS must be >= 1")

        # Soft warnings — these don't block startup but they WILL cause
        # runtime errors the first time someone hits the feature, which is
        # confusing without a hint. Log via the standard logging facility
        # so pm2 captures it.
        import logging

        _log = logging.getLogger("maxwell.config")

        if not cls.DAME_CURIE_OWNER_IDS:
            _log.warning(
                "DAME_CURIE_OWNER_IDS is empty — admin commands (`!prompt`, "
                "`!clearmem`, `!autonomy`, `!rem`, etc.) will be denied to "
                "everyone. Set your Discord user ID in .env."
            )
        if cls.ENABLE_SHELL:
            _log.warning(
                "ENABLE_SHELL is on — the model can run commands inside the bot container "
                "with the bot's permissions and mounted state. Set ENABLE_SHELL=false "
                "in .env if you did not mean to grant that."
            )
        # TTS engine sanity check
        if cls.TTS_ENGINE not in {"auto", "local", "riva", "gtts", "fish"}:
            _log.warning(
                "TTS_ENGINE=%r is not one of auto/local/riva/gtts/fish — falling "
                "back to 'auto' behaviour.",
                cls.TTS_ENGINE,
            )

        # One line per optional feature, so "why isn't X working" is answered
        # by the top of the log instead of by reading the source.
        on = [label for _, label, enabled, _ in cls.feature_report() if enabled]
        off = [
            f"{label} ({reason})"
            for _, label, enabled, reason in cls.feature_report()
            if not enabled
        ]
        _log.info("Features on: %s", ", ".join(on) or "none")
        if off:
            _log.info("Features off: %s", "; ".join(off))
