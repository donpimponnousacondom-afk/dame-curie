"""Pure resolution of remote-generation provider settings from an environment.

Reload-side counterpart of the provider block in ``config.py``: given a fully
resolved environment mapping, return the fields the chat providers are built
from, so an operator edit to ``bot.env`` can be applied to a running bot
without a restart.

Contract:

* The mapping passed in is the *whole* environment. An absent key is unset --
  the parser never reads or writes ``os.environ``, never imports the
  application, and never opens the dotenv file (the caller resolves it).
  ``PROVIDER_FIELDS`` lists the exact keys returned, in order, so a caller can
  capture startup values off ``Config`` without parsing or revalidating.
* Absent, blank and unrecognized input resolves as ``config.py`` and the
  ``OpenAICompatibleProvider`` constructor resolve it today, so a reload and a
  restart from the same file agree field for field. ``OPENAI_API_KEY`` keeps
  the startup quirk that its shared-key fallback is taken unstripped
  (``config.py:185`` reads the raw value) while ``OPENAI_COMPAT_API_KEY`` is
  stripped.
* ``ENABLE_*`` feature switches are deliberately absent: they are resolved once
  at import time and stay restart-only. The live ``process_audio`` control
  already hot-reloads the audio flag, so ``ENABLE_AUDIO_INPUT`` is not a reload
  field.

Deliberate divergences from the startup path, all fail-closed because a reload
must not replace working clients with broken ones:

* Malformed JSON, nested non-finite numbers, non-string header values,
  non-finite floats, non-numeric integers, and a ``*_BASE_URL`` that is not an
  http(s) URL with a hostname all raise instead of silently taking a default.
* ``OPENAI_BASE_URL`` and ``OPENAI_MODEL`` must be non-blank. Every optional
  endpoint URL may still be blank, which is what disables fallback and vision.

Errors name the offending field and never its value, and suppress the original
parsing exception so no fragment of the file reaches a traceback.
"""

import json
import math
from collections.abc import Mapping
from urllib.parse import urlsplit

# Every field this module returns, in the order it returns them. Adding a field
# here without adding it to parse_provider_settings (or the reverse) fails
# tests/test_provider_settings.py.
PROVIDER_FIELDS = (
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_COMPAT_API_KEY",
    "OPENAI_MAX_TOKENS",
    "OPENAI_TEMPERATURE",
    "OPENAI_TOP_P",
    "OPENAI_TOP_K",
    "OPENAI_DISABLE_REASONING",
    "OPENAI_EXTRA_HEADERS",
    "OPENAI_EXTRA_BODY",
    "OPENAI_RETRY_ATTEMPTS",
    "OPENAI_EMPTY_RESPONSE_RETRIES",
    "OPENAI_ENDPOINT_COOLDOWN_SECONDS",
    "OPENAI_FALLBACK_BASE_URL",
    "OPENAI_FALLBACK_API_KEY",
    "OPENAI_FALLBACK_MODEL",
    "OPENAI_FALLBACK_DISABLE_REASONING",
    "OPENAI_VISION_BASE_URL",
    "OPENAI_VISION_API_KEY",
    "OPENAI_VISION_MODEL",
    "OPENAI_VISION_DISABLE_REASONING",
    "OPENAI_REM_MODEL",
    "AUTONOMY_BASE_URL",
    "AUTONOMY_API_KEY",
    "AUTONOMY_MODEL",
    "AUTONOMY_DISABLE_REASONING",
    "AUX_BASE_URL",
    "AUX_API_KEY",
    "AUX_MODEL",
    "AUX_DISABLE_REASONING",
)

# Fields that must be a usable endpoint when non-blank. Blanks stay blanks.
_URL_FIELDS = (
    "OPENAI_BASE_URL",
    "OPENAI_FALLBACK_BASE_URL",
    "OPENAI_VISION_BASE_URL",
    "AUTONOMY_BASE_URL",
    "AUX_BASE_URL",
)

_TRUE = {"1", "true", "yes", "on"}


def _int_field(
    env: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Integer field clamped like ``config._int_env``; non-integers raise."""
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_field(
    env: Mapping[str, str],
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Finite float field clamped like ``config._float_env``; non-finite raises."""
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _bool_field(env: Mapping[str, str], name: str, default: bool) -> bool:
    """Boolean flag matching ``config._bool_env``.

    Unset keeps ``default``; anything outside the true-words is false, so
    ``OPENAI_DISABLE_REASONING=maybe`` reads as false exactly as it does at
    startup. That stays for now: a reload must not disagree with a restart.
    """
    raw = env.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _json_field(env: Mapping[str, str], name: str) -> dict[str, object]:
    """JSON object field; blank is empty, malformed or non-finite fails closed.

    ``json.loads`` accepts bare ``NaN``/``Infinity`` literals, so the parsed
    value is re-serialised with ``allow_nan=False`` to reject them anywhere in
    the structure -- a non-finite number in a request body is not JSON any
    upstream will accept.
    """
    raw = (env.get(name) or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        raise ValueError(f"{name} must be a valid JSON object") from None
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    try:
        json.dumps(value, allow_nan=False)
    except ValueError:
        raise ValueError(f"{name} must not contain non-finite numbers") from None
    return value


def _headers_field(env: Mapping[str, str], name: str) -> dict[str, str]:
    """JSON object of request headers; every value must be a string."""
    raw_headers = _json_field(env, name)
    headers: dict[str, str] = {}
    for header, value in raw_headers.items():
        if not isinstance(value, str):
            raise ValueError(f"{name} values must all be strings")
        headers[header] = value
    return headers


def _url_field(env: Mapping[str, str], name: str) -> str:
    """Stripped endpoint URL; blank stays blank, anything else must parse."""
    value = env.get(name, "").strip()
    if not value:
        return value
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        _ = parts.port
    except ValueError:
        raise ValueError(f"{name} must be an http(s) URL with a hostname and a valid port") from None
    if parts.scheme not in {"http", "https"} or not hostname:
        raise ValueError(f"{name} must be an http(s) URL with a hostname and a valid port")
    return value


def parse_provider_settings(env: Mapping[str, str]) -> dict[str, object]:
    """Resolve the remote-generation provider fields from ``env``.

    ``env`` is the whole resolved environment, so an absent key is unset.
    Returns the ``PROVIDER_FIELDS`` names in order. Raises ``ValueError``
    naming the offending field -- never its value -- when the file is
    unusable, so the caller can keep the last valid clients instead of
    applying half a configuration.
    """
    compat_raw = env.get("OPENAI_COMPAT_API_KEY", "")
    compat_key = compat_raw.strip()
    base_url = _url_field(env, "OPENAI_BASE_URL")
    model = env.get("OPENAI_MODEL", "").strip()
    if not base_url:
        raise ValueError("OPENAI_BASE_URL must not be blank")
    if not model:
        raise ValueError("OPENAI_MODEL must not be blank")
    return {
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model,
        "OPENAI_API_KEY": env.get("OPENAI_API_KEY", compat_raw),
        "OPENAI_COMPAT_API_KEY": compat_key,
        "OPENAI_MAX_TOKENS": _int_field(
            env, "OPENAI_MAX_TOKENS", 16384, minimum=1, maximum=131072
        ),
        "OPENAI_TEMPERATURE": _float_field(
            env, "OPENAI_TEMPERATURE", 0.6, minimum=0.0
        ),
        "OPENAI_TOP_P": _float_field(
            env, "OPENAI_TOP_P", 0.95, minimum=0.0, maximum=1.0
        ),
        "OPENAI_TOP_K": _int_field(env, "OPENAI_TOP_K", 20, minimum=0),
        "OPENAI_DISABLE_REASONING": _bool_field(
            env, "OPENAI_DISABLE_REASONING", False
        ),
        "OPENAI_EXTRA_HEADERS": _headers_field(env, "OPENAI_EXTRA_HEADERS"),
        "OPENAI_EXTRA_BODY": _json_field(env, "OPENAI_EXTRA_BODY"),
        "OPENAI_RETRY_ATTEMPTS": _int_field(
            env, "OPENAI_RETRY_ATTEMPTS", 5, minimum=1, maximum=10
        ),
        "OPENAI_EMPTY_RESPONSE_RETRIES": _int_field(
            env, "OPENAI_EMPTY_RESPONSE_RETRIES", 2, minimum=0, maximum=5
        ),
        "OPENAI_ENDPOINT_COOLDOWN_SECONDS": _float_field(
            env, "OPENAI_ENDPOINT_COOLDOWN_SECONDS", 60.0
        ),
        "OPENAI_FALLBACK_BASE_URL": _url_field(env, "OPENAI_FALLBACK_BASE_URL"),
        "OPENAI_FALLBACK_API_KEY": env.get("OPENAI_FALLBACK_API_KEY", "").strip(),
        "OPENAI_FALLBACK_MODEL": env.get("OPENAI_FALLBACK_MODEL", "").strip(),
        "OPENAI_FALLBACK_DISABLE_REASONING": _bool_field(
            env, "OPENAI_FALLBACK_DISABLE_REASONING", True
        ),
        "OPENAI_VISION_BASE_URL": _url_field(env, "OPENAI_VISION_BASE_URL"),
        "OPENAI_VISION_API_KEY": env.get("OPENAI_VISION_API_KEY", "").strip(),
        "OPENAI_VISION_MODEL": env.get("OPENAI_VISION_MODEL", "").strip(),
        "OPENAI_VISION_DISABLE_REASONING": _bool_field(
            env, "OPENAI_VISION_DISABLE_REASONING", True
        ),
        "OPENAI_REM_MODEL": env.get("OPENAI_REM_MODEL") or model,
        "AUTONOMY_BASE_URL": _url_field(env, "AUTONOMY_BASE_URL"),
        "AUTONOMY_API_KEY": env.get("AUTONOMY_API_KEY", compat_key).strip(),
        "AUTONOMY_MODEL": env.get("AUTONOMY_MODEL", "").strip(),
        "AUTONOMY_DISABLE_REASONING": _bool_field(
            env, "AUTONOMY_DISABLE_REASONING", False
        ),
        "AUX_BASE_URL": _url_field(env, "AUX_BASE_URL"),
        "AUX_API_KEY": env.get("AUX_API_KEY", compat_key).strip(),
        "AUX_MODEL": env.get("AUX_MODEL", "").strip(),
        "AUX_DISABLE_REASONING": _bool_field(env, "AUX_DISABLE_REASONING", True),
    }
