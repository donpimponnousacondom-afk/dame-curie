import json
import math
from collections.abc import Mapping
from urllib.parse import urlsplit

PROVIDER_FIELDS = (
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_COMPAT_API_KEY",
    "OPENAI_MAX_TOKENS",
    "OPENAI_TEMPERATURE",
    "OPENAI_TOP_P",
    "OPENAI_TOP_K",
    "OPENAI_EXTRA_HEADERS",
    "OPENAI_EXTRA_BODY",
    "OPENAI_RETRY_ATTEMPTS",
    "OPENAI_EMPTY_RESPONSE_RETRIES",
    "AUTONOMY_BASE_URL",
    "AUTONOMY_API_KEY",
    "AUTONOMY_MODEL",
    "AUX_BASE_URL",
    "AUX_API_KEY",
    "AUX_MODEL",
)


def _int_field(
    env: Mapping[str, str],
    name: str,
    default: int | None,
    *,
    minimum: int | None = None,
) -> int | None:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _float_field(
    env: Mapping[str, str],
    name: str,
    default: float | None,
) -> float | None:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _json_field(env: Mapping[str, str], name: str) -> dict[str, object]:
    raw = env.get(name, "")
    if not raw.strip():
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
    raw_headers = _json_field(env, name)
    headers: dict[str, str] = {}
    for header, value in raw_headers.items():
        if not isinstance(value, str):
            raise ValueError(f"{name} values must all be strings")
        headers[header] = value
    names = [header.lower() for header in headers]
    if len(names) != len(set(names)):
        raise ValueError(f"{name} contains conflicting header names")
    return headers


def _url_field(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        return value
    if any(char.isspace() for char in value):
        raise ValueError(f"{name} must not contain whitespace")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        _ = parts.port
    except ValueError:
        raise ValueError(f"{name} must be an http(s) URL with a hostname and a valid port") from None
    if parts.scheme not in {"http", "https"} or not hostname or parts.query or parts.fragment:
        raise ValueError(f"{name} must be an http(s) API root without query or fragment")
    return value


def parse_provider_settings(env: Mapping[str, str], *, require_primary: bool = True) -> dict[str, object]:
    for name in env:
        if (
            name in {"OPENAI_DISABLE_REASONING", "AUTONOMY_DISABLE_REASONING", "AUX_DISABLE_REASONING",
                     "OPENAI_ENDPOINT_COOLDOWN_SECONDS", "OPENAI_REM_MODEL"}
            or name.startswith(("OPENAI_FALLBACK_", "OPENAI_VISION_"))
        ):
            raise ValueError(f"{name} is unsupported; remove this legacy setting and configure the provider profile explicitly")
    base_url = _url_field(env, "OPENAI_BASE_URL")
    model = env.get("OPENAI_MODEL", "")
    if require_primary and not base_url:
        raise ValueError("OPENAI_BASE_URL must not be blank")
    if (require_primary or model) and not model.strip():
        raise ValueError("OPENAI_MODEL must not be blank")
    settings = {
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model,
        "OPENAI_API_KEY": env.get("OPENAI_API_KEY", env.get("OPENAI_COMPAT_API_KEY", "")),
        "OPENAI_COMPAT_API_KEY": env.get("OPENAI_COMPAT_API_KEY", ""),
        "OPENAI_MAX_TOKENS": _int_field(env, "OPENAI_MAX_TOKENS", None, minimum=1),
        "OPENAI_TEMPERATURE": _float_field(env, "OPENAI_TEMPERATURE", None),
        "OPENAI_TOP_P": _float_field(env, "OPENAI_TOP_P", None),
        "OPENAI_TOP_K": _int_field(env, "OPENAI_TOP_K", None),
        "OPENAI_EXTRA_HEADERS": _headers_field(env, "OPENAI_EXTRA_HEADERS"),
        "OPENAI_EXTRA_BODY": _json_field(env, "OPENAI_EXTRA_BODY"),
        "OPENAI_RETRY_ATTEMPTS": _int_field(env, "OPENAI_RETRY_ATTEMPTS", 5, minimum=1),
        "OPENAI_EMPTY_RESPONSE_RETRIES": _int_field(env, "OPENAI_EMPTY_RESPONSE_RETRIES", 2, minimum=0),
        "AUTONOMY_BASE_URL": _url_field(env, "AUTONOMY_BASE_URL"),
        "AUTONOMY_API_KEY": env.get("AUTONOMY_API_KEY"),
        "AUTONOMY_MODEL": env.get("AUTONOMY_MODEL", ""),
        "AUX_BASE_URL": _url_field(env, "AUX_BASE_URL"),
        "AUX_API_KEY": env.get("AUX_API_KEY"),
        "AUX_MODEL": env.get("AUX_MODEL", ""),
    }
    body = settings["OPENAI_EXTRA_BODY"]
    for name in ("model", "max_tokens", "temperature", "top_p", "top_k"):
        value = settings[f"OPENAI_{name.upper()}"]
        if name in body and value is not None and (type(body[name]) is not type(value) or body[name] != value):
            raise ValueError(f"OPENAI_EXTRA_BODY conflicts with OPENAI_{name.upper()}")
    if "messages" in body:
        raise ValueError("OPENAI_EXTRA_BODY conflicts with runtime messages")
    if settings["OPENAI_API_KEY"] and any(name.lower() == "authorization" for name in settings["OPENAI_EXTRA_HEADERS"]):
        raise ValueError("OPENAI_API_KEY conflicts with OPENAI_EXTRA_HEADERS Authorization")
    for role in ("AUTONOMY", "AUX"):
        role_base, role_model, role_key = (settings[f"{role}_{field}"] for field in ("BASE_URL", "MODEL", "API_KEY"))
        if role_base or role_model or role_key:
            if role_base and role_base != base_url:
                raise ValueError(f"{role}_BASE_URL requires its own complete provider configuration")
            if role_key is not None and role_key != settings["OPENAI_API_KEY"]:
                raise ValueError(f"{role}_API_KEY conflicts with the shared provider profile")
            if role_model and not role_model.strip():
                raise ValueError(f"{role}_MODEL must not be blank")
    return settings
