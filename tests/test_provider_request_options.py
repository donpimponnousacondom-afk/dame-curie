import asyncio
from copy import deepcopy
import os
from pathlib import Path
import runpy
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from providers import OllamaProvider
from test_providers import FakeErrorResponse, FakeResponse, FakeSequenceSession


@pytest.fixture
def provider():
    return OllamaProvider(
        "https://primary.example.test/v1", "main-model", 8192, 0.6,
        api_key="synthetic-primary-key",
        fallback_base_url="https://fallback.example.test/v1",
        fallback_model="fallback-model", fallback_api_key="synthetic-fallback-key",
        vision_base_url="https://vision.example.test/v1",
        vision_model="vision-model", vision_api_key="synthetic-vision-key",
        extra_body={"reasoning_effort": "high", "custom": {"labels": ["original"]}},
        extra_headers={"X-Primary-Only": "synthetic-header"},
    )


def test_primary_body_options_do_not_reach_fallback_or_vision(provider):
    messages = [{"role": "user", "content": "synthetic"}]
    for endpoint in provider._endpoints:
        payload = provider._request_payload(endpoint, messages, disable_reasoning=False)
        assert payload["model"] == endpoint.model
        if endpoint.name == "primary":
            assert payload["reasoning_effort"] == "high"
            assert payload["custom"] == {"labels": ["original"]}
        else:
            assert "reasoning_effort" not in payload
            assert "custom" not in payload


@pytest.mark.parametrize("endpoint_name", ["primary", "fallback", "vision"])
def test_deepinfra_gpt_oss_options_are_scoped_in_actual_post(monkeypatch, endpoint_name):
    provider = OllamaProvider(
        "https://openrouter.ai/api/v1", "openai/gpt-oss-120b:nitro", 8192, 0.6,
        fallback_base_url="https://fallback.example.test/v1",
        fallback_model="fallback-model", fallback_disable_reasoning=False,
        vision_base_url="https://vision.example.test/v1",
        vision_model="vision-model", vision_disable_reasoning=False,
        extra_body={"provider": {"only": ["deepinfra"]}, "reasoning": {"effort": "high"}},
    )
    provider.available = True
    endpoint = provider._endpoint_named(endpoint_name)
    monkeypatch.setattr(provider, "_attempt_endpoint", lambda *args, **kwargs: endpoint)
    session = FakeSequenceSession([FakeResponse()])
    provider._session = session
    result = asyncio.run(provider.generate_response([{"role": "user", "content": "synthetic"}]))
    assert result == "ok"
    assert session.urls == [f"{endpoint.base_url}/chat/completions"]
    assert len(session.payloads) == 1
    payload = session.payloads[0]
    if endpoint_name == "primary":
        assert payload["model"] == "openai/gpt-oss-120b:nitro"
        assert payload["provider"] == {"only": ["deepinfra"]}
        assert payload["reasoning"] == {"effort": "high"}
    else:
        assert payload["model"] == endpoint.model
        assert "provider" not in payload
        assert "reasoning" not in payload


@pytest.mark.parametrize("with_tools", [False, True])
def test_runtime_fields_override_reserved_extra_body(with_tools):
    extras = {
        "model": "wrong", "messages": [], "stream": False, "max_tokens": 99999,
        "temperature": 99, "top_p": 0, "top_k": 0,
        "stream_options": {"include_usage": False},
        "tools": [{"type": "function", "function": {"name": "injected"}}],
        "tool_choice": "required", "custom": {"enabled": True},
    }
    provider = OllamaProvider("https://primary.example.test", "main", 8192, 0.6,
                              top_p=0.9, top_k=30, extra_body=extras)
    endpoint = provider._endpoints[0]
    messages = [{"role": "user", "content": "synthetic"}]
    tools = [{"type": "function", "function": {"name": "actual"}}] if with_tools else None
    payload = provider._request_payload(endpoint, messages, tools=tools,
                                        model="override", max_tokens=123, temperature=0.2)
    assert {key: payload[key] for key in (
        "model", "messages", "stream", "max_tokens", "temperature", "top_p", "top_k",
    )} == {
        "model": "override", "messages": messages, "stream": True, "max_tokens": 123,
        "temperature": 0.2, "top_p": 0.9, "top_k": 30,
    }
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["custom"] == {"enabled": True}
    if with_tools:
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"
    else:
        assert "tools" not in payload
        assert "tool_choice" not in payload
    provider._stream_usage_unsupported.add("primary")
    provider._endpoint_output_caps["primary"] = 100
    provider._endpoint_temperatures["primary"] = 0.7
    retried = provider._request_payload(endpoint, messages)
    assert "stream_options" not in retried
    assert retried["max_tokens"] == 100
    assert retried["temperature"] == 0.7


@pytest.mark.parametrize("base_url", ["https://primary.example.test/v1", "https://openrouter.ai/api/v1"])
@pytest.mark.parametrize("endpoint_disabled, call_disabled, expected_disabled", [
    (False, None, False), (False, True, True), (True, None, True), (True, False, False),
])
def test_explicit_reasoning_options_and_disable_precedence(
    base_url, endpoint_disabled, call_disabled, expected_disabled,
):
    extras = {
        "reasoning_effort": "high", "reasoning": {"effort": "high"},
        "thinking": {"type": "enabled", "budget_tokens": 4096},
    }
    provider = OllamaProvider(base_url, "main", 8192, 0.6,
                              disable_reasoning=endpoint_disabled, extra_body=extras)
    payload = provider._request_payload(provider._endpoints[0], [],
                                        disable_reasoning=call_disabled)
    if not expected_disabled:
        assert {key: payload[key] for key in extras} == extras
    elif "openrouter.ai" in base_url:
        assert payload["reasoning"] == {"enabled": False}
        assert payload.get("reasoning_effort", "none") == "none"
        assert payload.get("thinking", {"type": "disabled"})["type"] == "disabled"
    else:
        assert payload["reasoning_effort"] == "none"
        assert payload["reasoning"] == {"effort": "none"}
        assert payload["thinking"] == {"type": "disabled", "budget_tokens": 0}
    assert extras["reasoning_effort"] == "high"


def test_constructor_and_each_payload_defensively_copy_nested_body():
    body = {"custom": {"labels": ["original"]}}
    headers = {"X-Primary-Only": "original"}
    provider = OllamaProvider("https://primary.example.test", "main", 8192, 0.6,
                              extra_body=body, extra_headers=headers)
    body["custom"]["labels"].append("caller-mutation")
    headers["X-Primary-Only"] = "caller-mutation"
    first = provider._request_payload(provider._endpoints[0], [])
    assert first["custom"] == {"labels": ["original"]}
    first["custom"]["labels"].append("request-mutation")
    first_headers = provider._headers()
    assert first_headers == {"X-Primary-Only": "original"}
    first_headers["X-Primary-Only"] = "request-mutation"
    assert provider._request_payload(provider._endpoints[0], [])["custom"] == {"labels": ["original"]}
    assert provider._headers() == {"X-Primary-Only": "original"}


def test_actual_retry_receives_fresh_nested_options(monkeypatch, provider):
    monkeypatch.setattr("providers.asyncio.sleep", AsyncMock())
    provider.available = True
    session = FakeSequenceSession([FakeErrorResponse(503, "temporarily unavailable"), FakeResponse()])
    original_post = session.post
    sent_headers = []

    def post(url, json=None, timeout=None, headers=None):
        sent_headers.append(deepcopy(headers))
        response = original_post(url, json=json, timeout=timeout, headers=headers)
        json["custom"]["labels"].append("transport-mutation")
        headers["X-Primary-Only"] = "transport-mutation"
        return response

    session.post = post
    provider._session = session
    result = asyncio.run(provider.generate_response([{"role": "user", "content": "synthetic"}]))
    assert result == "ok"
    assert len(session.payloads) == 2
    assert all(payload["custom"] == {"labels": ["original"]} for payload in session.payloads)
    assert all(headers["X-Primary-Only"] == "synthetic-header" for headers in sent_headers)


@pytest.mark.parametrize("authorization_name", ["Authorization", "authorization", "AUTHORIZATION", "aUtHoRiZaTiOn"])
def test_configured_api_key_wins_case_insensitively(authorization_name):
    provider = OllamaProvider("https://primary.example.test", "main", 8192, 0.6,
                              api_key="synthetic-configured-key", extra_headers={
                                  authorization_name: "synthetic-custom-auth",
                                  "X-Primary-Only": "keep",
                              })
    for endpoint in (None, provider._endpoints[0]):
        headers = provider._headers(endpoint)
        auth = [(key, value) for key, value in headers.items() if key.lower() == "authorization"]
        assert auth == [("Authorization", "Bearer synthetic-configured-key")]
        assert headers["X-Primary-Only"] == "keep"


def test_custom_authorization_retained_without_configured_key():
    provider = OllamaProvider("https://primary.example.test", "main", 8192, 0.6,
                              extra_headers={"authorization": "synthetic-custom-auth"})
    assert provider._headers() == {"authorization": "synthetic-custom-auth"}


def test_headers_do_not_leak_to_fallback_or_vision(provider):
    assert provider._headers()["X-Primary-Only"] == "synthetic-header"
    for name in ("fallback", "vision"):
        assert provider._headers(provider._endpoint_named(name)) == {
            "Authorization": f"Bearer synthetic-{name}-key",
        }


@pytest.fixture
def load_config(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "config.py"
    target = tmp_path / "config.py"
    shutil.copyfile(source, target)
    monkeypatch.setattr("dotenv.main.load_dotenv", lambda *args, **kwargs: False)

    def load(overrides):
        environment = {
            "HOME": str(tmp_path), "DATA_DIR": str(tmp_path / "data"),
            "MAXWELL_SITE_DIR": str(tmp_path / "sites"),
            "MAXWELL_ENV_FILE": os.devnull, "PYTHON_DOTENV_DISABLED": "1",
            **overrides,
        }
        with patch.dict(os.environ, environment, clear=True):
            return runpy.run_path(str(target))

    return load


@pytest.mark.parametrize("value", [None, "", "  \n ", "{}"])
def test_request_option_config_defaults_are_empty_objects(load_config, value):
    overrides = {} if value is None else {"OLLAMA_EXTRA_BODY": value, "OLLAMA_EXTRA_HEADERS": value}
    config = load_config(overrides)["Config"]
    assert config.OLLAMA_EXTRA_BODY == {}
    assert config.OLLAMA_EXTRA_HEADERS == {}


def test_request_option_config_parses_json_objects(load_config):
    config = load_config({
        "OLLAMA_EXTRA_BODY": '{"reasoning_effort":"high","custom":{"enabled":true}}',
        "OLLAMA_EXTRA_HEADERS": '{"X-Synthetic":"test-value"}',
    })["Config"]
    assert config.OLLAMA_EXTRA_BODY == {"reasoning_effort": "high", "custom": {"enabled": True}}
    assert config.OLLAMA_EXTRA_HEADERS == {"X-Synthetic": "test-value"}


@pytest.mark.parametrize("name", ["OLLAMA_EXTRA_BODY", "OLLAMA_EXTRA_HEADERS"])
@pytest.mark.parametrize("value", ['{"secret":"synthetic-secret",', '["synthetic-secret"]', '"synthetic-secret"', "null", "true", "123"])
def test_invalid_request_option_config_is_strict_and_secret_safe(load_config, capsys, name, value):
    with pytest.raises(ValueError) as error:
        load_config({name: value})
    assert name in str(error.value)
    captured = capsys.readouterr()
    assert "synthetic-secret" not in str(error.value) + captured.out + captured.err


def test_existing_json_config_remains_lenient(load_config):
    config = load_config({"X_API_PATHS": "not-json", "X_RSS_PATHS": "[]"})["Config"]
    assert config.X_API_PATHS == {}
    assert config.X_RSS_PATHS == {}


@pytest.fixture
def synthetic_bot(monkeypatch):
    import bot as bot_module

    config = SimpleNamespace(
        OLLAMA_BASE_URL="https://primary.example.test/v1", OLLAMA_MODEL="main",
        OLLAMA_API_KEY="synthetic-primary-key", OLLAMA_MAX_TOKENS=8192,
        OLLAMA_TEMPERATURE=0.6, OLLAMA_TOP_P=0.95, OLLAMA_TOP_K=20,
        OLLAMA_DISABLE_REASONING=False, OLLAMA_FALLBACK_BASE_URL="",
        OLLAMA_FALLBACK_MODEL="", OLLAMA_FALLBACK_API_KEY="",
        OLLAMA_FALLBACK_DISABLE_REASONING=True, OLLAMA_RETRY_ATTEMPTS=2,
        OLLAMA_VISION_BASE_URL="", OLLAMA_VISION_MODEL="", OLLAMA_VISION_API_KEY="",
        OLLAMA_VISION_DISABLE_REASONING=True, ENABLE_AUDIO_INPUT=False,
        OLLAMA_EXTRA_BODY={"reasoning_effort": "high", "custom": {"main_only": True}},
        OLLAMA_EXTRA_HEADERS={"X-Primary-Only": "synthetic"},
        AUX_BASE_URL="", AUX_MODEL="", AUX_API_KEY="", AUX_DISABLE_REASONING=True,
        AUTONOMY_BASE_URL="", AUTONOMY_MODEL="", AUTONOMY_API_KEY="",
        AUTONOMY_DISABLE_REASONING=False,
    )
    instance = bot_module.MaxwellBot.__new__(bot_module.MaxwellBot)
    instance.config = config
    instance._control = {}
    instance.autonomy_provider = None
    instance.aux_provider = None
    instance._autonomy_provider_sig = ""
    instance._aux_provider_sig = ""

    async def initialize(provider):
        provider.available = True

    monkeypatch.setattr(bot_module, "OllamaProvider", OllamaProvider)
    monkeypatch.setattr(OllamaProvider, "initialize", initialize)
    instance._setup_ai()
    return instance


def test_actual_main_setup_and_shared_background_clients_inherit_options(synthetic_bot):
    main = synthetic_bot.ai_provider
    assert main._request_payload(main._endpoints[0], [])["custom"] == {"main_only": True}
    assert main._headers()["X-Primary-Only"] == "synthetic"
    assert asyncio.run(synthetic_bot._get_autonomy_provider()) is main
    assert asyncio.run(synthetic_bot._get_aux_provider()) is main
    disabled = main._request_payload(main._endpoints[0], [], disable_reasoning=True)
    assert disabled["reasoning_effort"] == "none"
    assert main._request_payload(main._endpoints[0], [])["reasoning_effort"] == "high"


@pytest.mark.parametrize("kind", ["aux", "autonomy"])
def test_dedicated_background_client_does_not_inherit_primary_options(synthetic_bot, kind):
    setattr(synthetic_bot.config, f"{kind.upper()}_BASE_URL", f"https://{kind}.example.test/v1")
    setattr(synthetic_bot.config, f"{kind.upper()}_MODEL", f"{kind}-model")
    provider = asyncio.run(getattr(synthetic_bot, f"_get_{kind}_provider")())
    assert provider is not synthetic_bot.ai_provider
    payload = provider._request_payload(provider._endpoints[0], [], disable_reasoning=False)
    assert "custom" not in payload
    assert "reasoning_effort" not in payload
    assert "X-Primary-Only" not in provider._headers()
