"""Configured profile selection without caller-side routing overrides."""

from enum import StrEnum
from typing import TYPE_CHECKING

from providers import OpenAICompatibleProvider, ProviderEndpoint

if TYPE_CHECKING:
    from config import Config


class JobProvider(StrEnum):
    MAIN = "main"
    AUTONOMY = "autonomy"
    AUX = "aux"


def parse_background_request(text: str, *, prefix: str = "!") -> tuple[str, JobProvider, str | None]:
    """Keep job prose intact and reject obsolete provider-selection flags."""
    text = text.strip()
    if text and text.split(maxsplit=1)[0] in {"--provider", "--model"}:
        raise ValueError(f"{prefix}bg uses the active provider configuration; edit provider/model there, then use {prefix}bg GOAL")
    if text and text.split(maxsplit=1)[0] == "--":
        text = text[2:].strip()
    return text, JobProvider.MAIN, None


def resolve_job_endpoint(profile: JobProvider, config: Config) -> ProviderEndpoint:
    """Resolve declared same-endpoint profiles without moving credentials or options."""
    base_url = config.OPENAI_BASE_URL
    model = config.OPENAI_MODEL
    api_key = config.OPENAI_API_KEY
    if profile != JobProvider.MAIN:
        role_base, role_model, role_key = {
            JobProvider.AUTONOMY: (config.AUTONOMY_BASE_URL, config.AUTONOMY_MODEL, config.AUTONOMY_API_KEY),
            JobProvider.AUX: (config.AUX_BASE_URL, config.AUX_MODEL, config.AUX_API_KEY),
        }[profile]
        if (role_base and role_base != base_url) or (role_key and role_key != api_key):
            raise ValueError(f"{profile} requires its own complete provider configuration; endpoint/credential overrides cannot inherit main request options")
        model = role_model or model
    return ProviderEndpoint("primary", base_url, model, api_key)


def create_job_provider(
    profile: JobProvider, config: Config, *, enable_audio_input: bool,
) -> OpenAICompatibleProvider:
    """Construct a same-endpoint profile with every configured request option."""
    endpoint = resolve_job_endpoint(profile, config)
    return OpenAICompatibleProvider(
        base_url=endpoint.base_url,
        model=endpoint.model,
        api_key=endpoint.api_key,
        max_tokens=config.OPENAI_MAX_TOKENS,
        temperature=config.OPENAI_TEMPERATURE,
        top_p=config.OPENAI_TOP_P,
        top_k=config.OPENAI_TOP_K,
        extra_headers=config.OPENAI_EXTRA_HEADERS,
        extra_body=config.OPENAI_EXTRA_BODY,
        retry_attempts=config.OPENAI_RETRY_ATTEMPTS,
        empty_response_retries=config.OPENAI_EMPTY_RESPONSE_RETRIES,
        enable_audio_input=enable_audio_input,
    )
