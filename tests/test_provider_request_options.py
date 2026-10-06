import asyncio
from copy import deepcopy
import os
from pathlib import Path
import runpy
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from providers import OpenAICompatibleProvider, ProviderEndpoint
from provider_settings import parse_provider_settings
from test_providers import FakeErrorResponse, FakeResponse, FakeSequenceSession


@pytest.fixture
def provider():
    return OpenAICompatibleProvider(
        "https://primary.example.test/v1?opaque=opaque-query-credential#opaque-fragment-credential", "main-model", 64000,
        api_key="synthetic-primary-key",
        extra_body={"reasoning_effort": "high", "custom": {"labels": ["original"]}},
        extra_headers={"X-Primary-Only": "synthetic-header"},
    )


def test_primary_body_options_do_not_reach_fallback_or_vision(provider):
    messages = [{"role": "user", "content": "synthetic"}]
    assert len(provider._endpoints) == 1
    payload = provider._request_payload(provider._endpoints[0], messages)
    assert payload["reasoning_effort"] == "high"
    assert payload["custom"] == {"labels": ["original"]}
    with pytest.raises(ValueError, match="Endpoint conflicts"):
        provider._request_payload(ProviderEndpoint("fallback", "https://other.test/v1", "other"), messages)


@pytest.mark.parametrize("model", ["openai/gpt-oss-120b:nitro", "unknown/new-model", "deepseek/deepseek-v4.1-flash"])
def test_deepinfra_gpt_oss_options_are_scoped_in_actual_post(model):
    body = {"provider": {"only": ["deepinfra"], "allow_fallbacks": False}, "reasoning": {"effort": "high"}}
    provider = OpenAICompatibleProvider("https://openrouter.ai/api/v1", model, extra_body=body)
    provider.available = True
    session = FakeSequenceSession([FakeResponse()])
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "ok"
    assert session.urls == ["https://openrouter.ai/api/v1/chat/completions"]
    assert session.payloads == [{"model": model, "messages": [], **body}]


@pytest.mark.parametrize("field,value", [
    ("model", "wrong"), ("messages", [{"role": "user", "content": "wrong"}]),
    ("max_tokens", 99999), ("temperature", 99), ("top_p", 0), ("top_k", 0),
])
def test_runtime_fields_override_reserved_extra_body(field, value):
    with pytest.raises(ValueError, match=field):
        OpenAICompatibleProvider("https://primary.example.test", "main", 8192, 0.6,
            top_p=0.9, top_k=30, extra_body={field: value})


@pytest.mark.parametrize("base_url", ["https://primary.example.test/v1", "https://openrouter.ai/api/v1"])
@pytest.mark.parametrize("stream", [None, True, False])
def test_explicit_reasoning_options_and_disable_precedence(base_url, stream):
    extras = {
        "reasoning_effort": "high", "reasoning": {"effort": "high"},
        "thinking": {"type": "enabled", "budget_tokens": 4096},
        "tools": [{"type": "function", "function": {"name": "configured"}}],
        "tool_choice": "required", "stream_options": {"include_usage": False},
    }
    if stream is not None:
        extras["stream"] = stream
    original = deepcopy(extras)
    provider = OpenAICompatibleProvider(base_url, "main", extra_body=extras)
    provider.available = True
    session = FakeSequenceSession([FakeResponse()])
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "ok"
    assert session.payloads == [{"model": "main", "messages": [], **original}]
    assert extras == provider.extra_body == original
    with pytest.raises(ValueError, match="runtime tools"):
        provider._request_payload(provider._endpoints[0], [], tools=[])


def test_constructor_and_each_payload_defensively_copy_nested_body():
    body = {"custom": {"labels": ["original"]}}
    headers = {"X-Primary-Only": "original"}
    provider = OpenAICompatibleProvider("https://primary.example.test", "main", extra_body=body, extra_headers=headers)
    body["custom"]["labels"].append("caller-mutation")
    headers["X-Primary-Only"] = "caller-mutation"
    first = provider._request_payload(provider._endpoints[0], [])
    first["custom"]["labels"].append("request-mutation")
    first_headers = provider._headers()
    first_headers["X-Primary-Only"] = "request-mutation"
    assert provider._request_payload(provider._endpoints[0], [])["custom"] == {"labels": ["original"]}
    assert provider._headers() == {"X-Primary-Only": "original"}


@pytest.mark.parametrize("metadata_size", [0, 90000])
def test_actual_retry_receives_fresh_nested_options(monkeypatch, provider, caplog, metadata_size):
    provider.extra_body["opaque"] = "opaque-credential-marker"
    provider.extra_body["prompt"] = "configured-prompt-marker"
    provider.extra_body["response_format"] = {"schema": {"description": "schema-content-marker" * 5000}}
    if metadata_size:
        provider.extra_body["🙂" * metadata_size] = "opaque-credential-marker"
    caplog.set_level("INFO", logger="providers")
    monkeypatch.setattr("providers.asyncio.sleep", AsyncMock())
    provider.available = True
    session = FakeSequenceSession([FakeErrorResponse(503, "temporarily unavailable"), FakeResponse()])
    original_post = session.post
    sent_headers = []

    def post(url, json=None, timeout=None, headers=None, allow_redirects=None):
        assert allow_redirects is False
        sent_headers.append(deepcopy(headers))
        snapshots = [record.getMessage() for record in caplog.records if record.getMessage().startswith("Provider request settings")]
        assert len(snapshots) == len(sent_headers)
        metadata = snapshots[-1].replace("\n", "")
        assert '"max_tokens": {"type": "int", "count": null}' in metadata
        assert '"temperature"' not in metadata
        assert '"hostname": "primary.example.test"' in metadata
        assert '"route": "chat/completions"' in metadata
        for private in ("synthetic-primary-key", "private-prompt-marker", "opaque-credential-marker", "configured-prompt-marker", "schema-content-marker", "opaque-query-credential", "opaque-fragment-credential"):
            assert private not in metadata
        assert all(len(line.encode("utf-8")) < 65536 for line in snapshots[-1].splitlines())
        assert len(snapshots[-1]) < 66000
        assert ("metadata characters omitted" in snapshots[-1]) is bool(metadata_size)
        response = original_post(url, json=json, timeout=timeout, headers=headers, allow_redirects=allow_redirects)
        json["custom"]["labels"].append("transport-mutation")
        headers["X-Primary-Only"] = "transport-mutation"
        return response

    session.post = post
    provider._session = session
    assert asyncio.run(provider.generate_response([{"role": "user", "content": "private-prompt-marker"}])) == "ok"
    assert len(session.payloads) == 2
    assert session.payloads[0] == session.payloads[1]
    assert session.urls == ["https://primary.example.test/v1/chat/completions?opaque=opaque-query-credential#opaque-fragment-credential"] * 2
    assert all(payload["max_tokens"] == 64000 for payload in session.payloads)
    assert all(headers["X-Primary-Only"] == "synthetic-header" for headers in sent_headers)
    assert "temperature" not in session.payloads[0]
    assert "stream" not in session.payloads[0]
    assert "top_p" not in session.payloads[0]
    assert "top_k" not in session.payloads[0]


@pytest.mark.parametrize("authorization_name", ["Authorization", "authorization", "AUTHORIZATION", "aUtHoRiZaTiOn"])
def test_configured_api_key_wins_case_insensitively(authorization_name):
    with pytest.raises(ValueError, match="conflicts"):
        OpenAICompatibleProvider("https://primary.example.test", "main", api_key="synthetic-key",
            extra_headers={authorization_name: "synthetic-custom-auth"})


def test_custom_authorization_retained_without_configured_key():
    provider = OpenAICompatibleProvider("https://primary.example.test", "main",
        extra_headers={"authorization": "synthetic-custom-auth"})
    assert provider._headers() == {"authorization": "synthetic-custom-auth"}


@pytest.mark.parametrize("path", ["models", "chat/completions"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_headers_do_not_leak_to_fallback_or_vision(provider, path, status):
    assert provider._headers()["X-Primary-Only"] == "synthetic-header"
    with pytest.raises(ValueError, match="Endpoint conflicts"):
        provider._headers(ProviderEndpoint("other", "https://other.test/v1", "other"))
    response = FakeErrorResponse(status, "redirect refused")
    response.headers = {"Location": "https://other.test/redirected"}
    boundary = Mock(return_value=response)
    provider._session = SimpleNamespace(closed=False, get=boundary, post=boundary)
    if path == "models":
        assert asyncio.run(provider.initialize()) is False
    else:
        provider.available = True
        with pytest.raises(RuntimeError, match=f"Provider API error: {status}: redirect refused"):
            asyncio.run(provider.generate_response([]))
    assert boundary.call_count == 1
    assert boundary.call_args.args == (f"https://primary.example.test/v1/{path}?opaque=opaque-query-credential#opaque-fragment-credential",)
    assert boundary.call_args.kwargs["allow_redirects"] is False
    assert boundary.call_args.kwargs["headers"]["Authorization"] == "Bearer synthetic-primary-key"


@pytest.fixture
def load_config(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "config.py"
    target = tmp_path / "config.py"
    shutil.copyfile(source, target)
    monkeypatch.setattr("dotenv.main.load_dotenv", lambda *args, **kwargs: False)

    def load(overrides):
        environment = {
            "HOME": str(tmp_path), "DATA_DIR": str(tmp_path / "data"),
            "DAME_CURIE_SITE_DIR": str(tmp_path / "sites"),
            "DAME_CURIE_ENV_FILE": os.devnull, "PYTHON_DOTENV_DISABLED": "1",
            **overrides,
        }
        with patch.dict(os.environ, environment, clear=True):
            return runpy.run_path(str(target))

    return load


@pytest.mark.parametrize("value", [None, "", "  \n ", "{}"])
def test_request_option_config_defaults_are_empty_objects(load_config, value):
    overrides = {} if value is None else {"OPENAI_EXTRA_BODY": value, "OPENAI_EXTRA_HEADERS": value}
    config = load_config(overrides)["Config"]
    assert config.OPENAI_EXTRA_BODY == {}
    assert config.OPENAI_EXTRA_HEADERS == {}
    for field in ("OPENAI_MAX_TOKENS", "OPENAI_TEMPERATURE", "OPENAI_TOP_P", "OPENAI_TOP_K"):
        assert getattr(config, field) is None


@pytest.mark.parametrize("fields", [{}, {
    "OPENAI_MAX_TOKENS": "64000", "OPENAI_EXTRA_BODY": '{"temperature":0.8,"stream":false}',
    "OPENAI_EXTRA_HEADERS": '{"X-Synthetic":"test-value"}',
}])
def test_request_option_config_parses_json_objects(load_config, fields):
    environment = {"OPENAI_BASE_URL": "https://synthetic.test/v1", "OPENAI_MODEL": "literal-model", **fields}
    config = load_config(environment)["Config"]
    settings = parse_provider_settings(environment)
    assert {name: getattr(config, name) for name in settings} == settings
    provider = OpenAICompatibleProvider(config.OPENAI_BASE_URL, config.OPENAI_MODEL,
        max_tokens=config.OPENAI_MAX_TOKENS, temperature=config.OPENAI_TEMPERATURE,
        top_p=config.OPENAI_TOP_P, top_k=config.OPENAI_TOP_K,
        extra_body=config.OPENAI_EXTRA_BODY, extra_headers=config.OPENAI_EXTRA_HEADERS)
    provider.available = True
    session = FakeSequenceSession([FakeResponse()])
    provider._session = session
    assert asyncio.run(provider.generate_response([])) == "ok"
    expected = {"model": "literal-model", "messages": []}
    if fields:
        expected.update({"max_tokens": 64000, "temperature": 0.8, "stream": False})
    assert session.payloads == [expected]


@pytest.mark.parametrize("name", ["OPENAI_EXTRA_BODY", "OPENAI_EXTRA_HEADERS"])
@pytest.mark.parametrize("value", ['{"secret":"synthetic-secret",', '["synthetic-secret"]', '"synthetic-secret"', "null", "true", "123"])
def test_invalid_request_option_config_is_strict_and_secret_safe(load_config, capsys, name, value):
    with pytest.raises(ValueError) as error:
        load_config({name: value})
    assert name in str(error.value)
    captured = capsys.readouterr()
    assert "synthetic-secret" not in str(error.value) + captured.out + captured.err


@pytest.fixture
def synthetic_bot(monkeypatch):
    import bot as bot_module

    config = SimpleNamespace(**parse_provider_settings({
        "OPENAI_BASE_URL": "https://primary.example.test/v1", "OPENAI_MODEL": "main",
        "OPENAI_API_KEY": "synthetic-primary-key", "OPENAI_MAX_TOKENS": "64000",
        "OPENAI_EXTRA_BODY": '{"reasoning_effort":"high","custom":{"main_only":true}}',
        "OPENAI_EXTRA_HEADERS": '{"X-Primary-Only":"synthetic"}',
    }), ENABLE_AUDIO_INPUT=False)
    instance = bot_module.MaxwellBot.__new__(bot_module.MaxwellBot)
    instance.config = config
    instance._control = {}
    instance.autonomy_provider = None
    instance.aux_provider = None
    instance._autonomy_provider_sig = ""
    instance._aux_provider_sig = ""

    async def initialize(provider):
        provider.available = True

    monkeypatch.setattr(bot_module, "OpenAICompatibleProvider", OpenAICompatibleProvider)
    monkeypatch.setattr("job_routing.OpenAICompatibleProvider", OpenAICompatibleProvider)
    monkeypatch.setattr(OpenAICompatibleProvider, "initialize", initialize)
    instance._setup_ai()
    return instance


def test_actual_main_setup_and_shared_background_clients_inherit_options(synthetic_bot):
    main = synthetic_bot.ai_provider
    assert main._request_payload(main._endpoints[0], [])["custom"] == {"main_only": True}
    assert main._headers()["X-Primary-Only"] == "synthetic"
    assert asyncio.run(synthetic_bot._get_autonomy_provider()) is main
    assert asyncio.run(synthetic_bot._get_aux_provider()) is main
    assert main._request_payload(main._endpoints[0], [])["max_tokens"] == 64000


@pytest.mark.parametrize("kind", ["aux", "autonomy"])
def test_dedicated_background_client_does_not_inherit_primary_options(synthetic_bot, kind):
    setattr(synthetic_bot.config, f"{kind.upper()}_BASE_URL", f"https://{kind}.example.test/v1")
    setattr(synthetic_bot.config, f"{kind.upper()}_MODEL", f"{kind}-model")
    with pytest.raises(ValueError):
        asyncio.run(getattr(synthetic_bot, f"_get_{kind}_provider")())
