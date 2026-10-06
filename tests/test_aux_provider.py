"""Auxiliary profiles preserve declared main request options without hidden routes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import job_routing
from bot import MaxwellBot


class _FakeProvider:
    """Stand-in for OpenAICompatibleProvider; records close() and init()."""

    def __init__(self, name="main"):
        self.name = name
        self.available = True
        self.closed = False
        self.inited = 0

    async def initialize(self):
        self.inited += 1

    async def close(self):
        self.closed = True


def _make_bot(monkeypatch, *, control=None, aux_env=None, auto_env=None):
    """Build only the bot surface needed for configured-profile resolution."""
    cfg = {
        "AUX_BASE_URL": (aux_env or {}).get("base_url", ""),
        "AUX_API_KEY": (aux_env or {}).get("api_key"),
        "AUX_MODEL": (aux_env or {}).get("model", ""),
        "AUTONOMY_BASE_URL": (auto_env or {}).get("base_url", ""),
        "AUTONOMY_API_KEY": (auto_env or {}).get("api_key"),
        "AUTONOMY_MODEL": (auto_env or {}).get("model", ""),
        "OPENAI_BASE_URL": "https://main.example/v1",
        "OPENAI_API_KEY": "synthetic-main-key",
        "OPENAI_MODEL": "main-model",
        "OPENAI_MAX_TOKENS": 64000,
        "OPENAI_TEMPERATURE": 0.6,
        "OPENAI_TOP_P": 0.95,
        "OPENAI_TOP_K": 20,
        "OPENAI_EXTRA_BODY": {"reasoning": {"effort": 37}, "provider": {"only": ["chosen"], "allow_fallbacks": False}},
        "OPENAI_EXTRA_HEADERS": {"X-Profile": "main"},
        "OPENAI_RETRY_ATTEMPTS": 1,
        "OPENAI_EMPTY_RESPONSE_RETRIES": None,
        "ENABLE_AUDIO_INPUT": False,
    }
    inst = MaxwellBot.__new__(MaxwellBot)
    inst.config = SimpleNamespace(**cfg)
    inst._control = control or {}
    inst.ai_provider = _FakeProvider("main")
    inst.autonomy_provider = None
    inst._autonomy_provider_sig = ""
    inst.aux_provider = None
    inst._aux_provider_sig = ""
    inst._tracked = []

    def _track(task):
        inst._tracked.append(task)

    inst._track_task = _track
    built = []

    class _FakeOpenAICompatible:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.available = True
            self.closed = False
            built.append(self)

        async def initialize(self):
            self.inited = True

        async def close(self):
            self.closed = True

    monkeypatch.setattr(job_routing, "OpenAICompatibleProvider", _FakeOpenAICompatible)
    inst._built = built
    return inst


def test_aux_model_falls_back_to_autonomy_then_main(monkeypatch):
    bot = _make_bot(monkeypatch, control={"aux_model": "stale", "autonomy_model": "stale-auto"})
    assert asyncio.run(bot._get_aux_provider()) is bot.ai_provider
    assert asyncio.run(bot._get_autonomy_provider()) is bot.ai_provider
    assert bot._built == []


def test_aux_model_env_fallback(monkeypatch):
    bot = _make_bot(monkeypatch, auto_env={"model": "auto-env"})
    assert asyncio.run(bot._get_aux_provider()) is bot.ai_provider
    assert asyncio.run(bot._get_autonomy_provider()).kwargs["model"] == "auto-env"
    bot.config.AUX_MODEL = "aux-env"
    assert asyncio.run(bot._get_aux_provider()).kwargs["model"] == "aux-env"


def test_get_aux_provider_without_aux_config_defers_to_autonomy(monkeypatch):
    bot = _make_bot(monkeypatch, auto_env={"base_url": "https://other.example/v1", "model": "auto"})
    assert asyncio.run(bot._get_aux_provider()) is bot.ai_provider
    assert bot.aux_provider is None
    assert bot._aux_provider_sig == ""
    with pytest.raises(ValueError, match="complete provider configuration"):
        asyncio.run(bot._get_autonomy_provider())


@pytest.mark.parametrize("profile", ["aux", "autonomy"])
@pytest.mark.parametrize("settings", [
    {"base_url": "https://aux.example", "model": "aux-m"},
    {"api_key": "synthetic-other-key", "model": "aux-m"},
    {"api_key": "", "model": "aux-m"},
    {"api_key": "synthetic-other-key"},
    {"api_key": ""},
])
def test_get_aux_provider_builds_dedicated_when_aux_base_url_set(monkeypatch, profile, settings):
    bot = _make_bot(
        monkeypatch,
        aux_env=settings if profile == "aux" else None,
        auto_env=settings if profile == "autonomy" else None,
    )
    with pytest.raises(ValueError, match="complete provider configuration"):
        asyncio.run(getattr(bot, f"_get_{profile}_provider")())
    assert getattr(bot, f"{profile}_provider") is None
    assert bot._built == []


@pytest.mark.parametrize("profile", ["aux", "autonomy"])
@pytest.mark.parametrize("max_tokens", [64000, None])
@pytest.mark.parametrize("main_key", ["", "synthetic-main-key"])
def test_get_autonomy_provider_forwards_main_sampling(monkeypatch, profile, max_tokens, main_key):
    bot = _make_bot(monkeypatch, aux_env={"model": "aux-m"}, auto_env={"model": "auto-m"})
    assert bot.config.AUX_API_KEY is None
    assert bot.config.AUTONOMY_API_KEY is None
    bot.config.OPENAI_API_KEY = main_key
    bot.config.OPENAI_MAX_TOKENS = max_tokens
    bot._control = {"aux_disable_reasoning": True, "autonomy_disable_reasoning": True}
    provider = asyncio.run(getattr(bot, f"_get_{profile}_provider")())
    assert provider.kwargs["base_url"] == bot.config.OPENAI_BASE_URL
    assert provider.kwargs["api_key"] == bot.config.OPENAI_API_KEY
    assert provider.kwargs["model"] == ("aux-m" if profile == "aux" else "auto-m")
    assert provider.kwargs["max_tokens"] == max_tokens
    assert provider.kwargs["temperature"] == 0.6
    assert provider.kwargs["top_p"] == 0.95
    assert provider.kwargs["top_k"] == 20
    assert provider.kwargs["extra_body"] == bot.config.OPENAI_EXTRA_BODY
    assert provider.kwargs["extra_headers"] == bot.config.OPENAI_EXTRA_HEADERS
    assert not {"disable_reasoning", "reasoning_control", "fallback_model"} & provider.kwargs.keys()


def test_get_aux_provider_caches(monkeypatch):
    bot = _make_bot(monkeypatch, aux_env={"model": "aux-m"})
    first = asyncio.run(bot._get_aux_provider())
    assert asyncio.run(bot._get_aux_provider()) is first
    assert len(bot._built) == 1


def test_get_aux_provider_retires_prior_on_config_churn(monkeypatch):
    bot = _make_bot(monkeypatch, aux_env={"model": "aux-m"})
    first = asyncio.run(bot._get_aux_provider())
    bot.config.AUX_MODEL = "aux-m2"
    asyncio.run(bot._get_aux_provider())
    assert len(bot._built) == 2
    assert bot._retired_providers == [first]
    assert first.closed is False
    assert bot._tracked == []


@pytest.mark.parametrize("profile", ["aux", "autonomy"])
@pytest.mark.parametrize("raises", [False, True])
def test_get_aux_provider_falls_back_to_main_when_unavailable(monkeypatch, profile, raises):
    bot = _make_bot(monkeypatch, aux_env={"model": "aux-m"}, auto_env={"model": "auto-m"})
    getter = getattr(bot, f"_get_{profile}_provider")
    provider = asyncio.run(getter())
    provider.available = False
    provider.initialize = AsyncMock(side_effect=RuntimeError("init failed") if raises else None)
    with pytest.raises(RuntimeError, match="init failed" if raises else "unavailable"):
        asyncio.run(getter())
    provider.initialize.assert_awaited_once()
    assert getattr(bot, f"{profile}_provider") is provider
    assert provider is not bot.ai_provider
