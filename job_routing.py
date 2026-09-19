"""Trusted profile selection for detached jobs, independent of REM cascades."""

import shlex
from collections.abc import Callable, Mapping
from enum import StrEnum
from io import StringIO
from typing import TYPE_CHECKING

from providers import OpenAICompatibleProvider, ProviderEndpoint

if TYPE_CHECKING:
    from config import Config


class JobProvider(StrEnum):
    MAIN = "main"
    AUTONOMY = "autonomy"
    AUX = "aux"


def parse_background_request(text: str) -> tuple[str, JobProvider, str | None]:
    """Parse only an opt-in flag header; leave the goal's prose untouched."""
    text = text.strip()
    provider = JobProvider.MAIN
    model = None
    if text and text.split(maxsplit=1)[0] in {"--provider", "--model", "--"}:
        stream = StringIO(text)
        header = shlex.shlex(stream, posix=True)
        header.whitespace_split = True
        header.commenters = ""
        seen = set()
        while True:
            start = stream.tell()
            flag = header.get_token()
            if flag == "--" and text[start:stream.tell()].strip() == "--":
                text = text[stream.tell():].strip()
                break
            if flag not in {"--provider", "--model"} or flag in seen:
                raise ValueError("usage: !bg [--provider PROFILE] [--model MODEL] -- GOAL; each flag once")
            seen.add(flag)
            start = stream.tell()
            value = header.get_token()
            if value is None or (value == "--" and text[start:stream.tell()].strip() == "--"):
                raise ValueError(f"background header needs a value for {flag} before --")
            if flag == "--provider":
                provider = JobProvider(value)
            else:
                model = value
    return text, provider, model


def resolve_job_endpoint(
    profile: JobProvider, control: Mapping[str, object], config: Config,
) -> ProviderEndpoint:
    """Resolve the selected role only, without initializing or borrowing a role."""
    if profile == JobProvider.MAIN:
        base_url = config.OPENAI_BASE_URL.strip()
        model = config.OPENAI_MODEL.strip()
        api_key = config.OPENAI_API_KEY
        disable_reasoning = config.OPENAI_DISABLE_REASONING
    else:
        role_defaults = {
            JobProvider.AUTONOMY: (
                config.AUTONOMY_BASE_URL, config.AUTONOMY_MODEL,
                config.AUTONOMY_API_KEY, config.AUTONOMY_DISABLE_REASONING,
            ),
            JobProvider.AUX: (
                config.AUX_BASE_URL, config.AUX_MODEL,
                config.AUX_API_KEY, config.AUX_DISABLE_REASONING,
            ),
        }
        base_url, model, api_key, disable_reasoning = role_defaults[profile]
        prefix = profile.value
        base_url = str(control.get(f"{prefix}_base_url") or "").strip() or base_url
        model = str(control.get(f"{prefix}_model") or "").strip() or model
        api_key = str(control.get(f"{prefix}_api_key") or "").strip() or api_key
        disable_reasoning = bool(control.get(f"{prefix}_disable_reasoning", disable_reasoning))
    if not base_url or not model:
        raise ValueError(f"background provider '{profile}' requires its own configured base URL and model")
    return ProviderEndpoint("primary", base_url, model, api_key, disable_reasoning)


def create_job_provider(
    profile: JobProvider, control: Mapping[str, object], config: Config,
    *, enable_audio_input: bool, reasoning_control: Callable[[], str | int] | None,
) -> OpenAICompatibleProvider:
    """Construct an uninitialized job-owned transport using existing role settings."""
    endpoint = resolve_job_endpoint(profile, control, config)
    main = profile == JobProvider.MAIN
    return OpenAICompatibleProvider(
        base_url=endpoint.base_url,
        model=endpoint.model,
        api_key=endpoint.api_key,
        disable_reasoning=endpoint.disable_reasoning,
        max_tokens=config.OPENAI_MAX_TOKENS,
        temperature=0.2 if profile == JobProvider.AUX else config.OPENAI_TEMPERATURE,
        top_p=config.OPENAI_TOP_P,
        top_k=config.OPENAI_TOP_K,
        extra_headers=config.OPENAI_EXTRA_HEADERS if main else None,
        extra_body=config.OPENAI_EXTRA_BODY if main else None,
        reasoning_control=reasoning_control if main else None,
        fallback_base_url=config.OPENAI_FALLBACK_BASE_URL,
        fallback_model=config.OPENAI_FALLBACK_MODEL,
        fallback_api_key=config.OPENAI_FALLBACK_API_KEY,
        fallback_disable_reasoning=config.OPENAI_FALLBACK_DISABLE_REASONING,
        retry_attempts=config.OPENAI_RETRY_ATTEMPTS,
        empty_response_retries=config.OPENAI_EMPTY_RESPONSE_RETRIES,
        enable_audio_input=enable_audio_input,
        vision_base_url=config.OPENAI_VISION_BASE_URL if main else "",
        vision_model=config.OPENAI_VISION_MODEL if main else "",
        vision_api_key=config.OPENAI_VISION_API_KEY if main else "",
        vision_disable_reasoning=config.OPENAI_VISION_DISABLE_REASONING,
    )
