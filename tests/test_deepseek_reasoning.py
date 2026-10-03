import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from providers import OpenAICompatibleProvider
from test_providers import FakeErrorResponse, FakeResponse, FakeSequenceSession

ROUTES = [
    ("https://openrouter.ai/api/v1", "deepseek/deepseek-v4.1-flash", "openrouter"),
    ("https://api.deepseek.com", "deepseek-flash", "deepseek"),
    ("https://api.deepseek.com/v1", "deepseek-v4-flash", "deepseek"),
    ("https://api.deepseek.com/v1", "deepseek-v4-flash-vision-exp", "deepseek"),
    ("https://new.example/v9", "unknown/new-model", "openrouter"),
]


def reasoning_fields(payload):
    return {key: payload[key] for key in ("reasoning", "reasoning_effort", "thinking") if key in payload}


def expected_fields(transport, level):
    if transport == "openrouter":
        return {"reasoning": {"effort": level}}
    return {"thinking": {"type": "enabled"}, "reasoning_effort": level}


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("level", [None, "", "low", "high", "max", "off"])
def test_baseline_and_runtime_are_always_explicit(base, model, transport, level):
    body = {} if level is None else expected_fields(transport, level)
    provider = OpenAICompatibleProvider(base, model, extra_body=body)
    provider.available = True
    provider._session = FakeSequenceSession([FakeResponse()])
    assert asyncio.run(provider.generate_response([])) == "ok"
    assert reasoning_fields(provider._session.payloads[0]) == body
    assert provider.extra_body == body


@pytest.mark.parametrize("number", range(1, 101))
def test_numeric_openrouter_effort_reaches_payload_as_integer(number):
    body = {"provider": {"only": ["deepseek"]}, "reasoning": {"effort": number}}
    provider = OpenAICompatibleProvider(ROUTES[0][0], ROUTES[0][1], extra_body=body)
    payload = provider._request_payload(provider._endpoints[0], [])
    assert payload["reasoning"] == {"effort": number}
    assert type(payload["reasoning"]["effort"]) is int
    assert payload["provider"] == body["provider"]
    assert "enabled" not in payload["reasoning"]


@pytest.mark.parametrize("base,model,transport", ROUTES[1:])
@pytest.mark.parametrize("value", [1, 37, 50, 75, 100])
def test_direct_api_numeric_behavior_is_unchanged(base, model, transport, value):
    body = {"reasoning_effort": value}
    provider = OpenAICompatibleProvider(base, model, extra_body=body)
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == body


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("disable", [False, True])
def test_per_call_override_wins_without_mutating_main(base, model, transport, disable):
    provider = OpenAICompatibleProvider(base, model, extra_body={"reasoning_effort": "low"})
    before = deepcopy(provider.extra_body)
    with pytest.raises(TypeError, match="disable_reasoning"):
        provider._request_payload(provider._endpoints[0], [], disable_reasoning=disable)
    assert provider.extra_body == before


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("disabled", [False, True])
def test_endpoint_disable_has_valid_explicit_fields(base, model, transport, disabled):
    with pytest.raises(TypeError, match="disable_reasoning"):
        OpenAICompatibleProvider(base, model, disable_reasoning=disabled)


@pytest.mark.parametrize("base,model,transport", ROUTES)
def test_live_control_changes_future_payloads_only(base, model, transport):
    body = {"reasoning_effort": "low"}
    provider = OpenAICompatibleProvider(base, model, extra_body=body)
    first = provider._request_payload(provider._endpoints[0], [])
    body["reasoning_effort"] = "max"
    assert provider._request_payload(provider._endpoints[0], []) == first
    replacement = OpenAICompatibleProvider(base, model, extra_body=body)
    assert replacement._request_payload(replacement._endpoints[0], [])["reasoning_effort"] == "max"


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("body", [
    {"reasoning_effort": "low"}, {"reasoning": {"effort": "max"}},
    {"reasoning": {"enabled": False}}, {"thinking": {"type": "disabled"}},
    {"reasoning_effort": "none"}, {"reasoning": None},
])
def test_existing_configuration_becomes_explicit_without_changing_intent(base, model, transport, body):
    provider = OpenAICompatibleProvider(base, model, extra_body=body)
    provider.available = True
    provider._session = FakeSequenceSession([FakeResponse()])
    assert asyncio.run(provider.generate_response([])) == "ok"
    assert reasoning_fields(provider._session.payloads[0]) == body


@pytest.mark.parametrize("base,model,transport", ROUTES)
def test_runtime_wins_conflicting_extra_options_and_preserves_routing(base, model, transport):
    extras = {
        "provider": {"only": ["deepseek"], "allow_fallbacks": False},
        "reasoning": {"effort": "max", "enabled": False, "max_tokens": 123, "exclude": True},
        "reasoning_effort": "none", "thinking": {"type": "disabled", "budget_tokens": 0},
        "custom": {"labels": ["keep"]},
    }
    original = deepcopy(extras)
    provider = OpenAICompatibleProvider(base, model, extra_body=extras, api_key="synthetic-key",
        extra_headers={"HTTP-Referer": "https://app.example/", "X-OpenRouter-Title": "Synthetic"})
    payload = provider._request_payload(provider._endpoints[0], [])
    assert {key: payload[key] for key in extras} == original
    assert provider._headers() == {
        "HTTP-Referer": "https://app.example/", "X-OpenRouter-Title": "Synthetic",
        "Authorization": "Bearer synthetic-key",
    }
    payload["provider"]["only"].append("mutated")
    assert provider.extra_body == original == extras


@pytest.mark.parametrize("base,model", [
    ("https://openrouter.ai/api/v1", "google/gemini-3.7-flash"),
    ("https://api.deepseek.com/v1", "deepseek-v4-pro"),
    ("https://gateway.example/v1", "deepseek-flash"),
    ("https://new.example/v9", "unknown/new-model"),
])
def test_other_models_and_hosts_are_untouched(base, model):
    provider = OpenAICompatibleProvider(base, model)
    assert provider._request_payload(provider._endpoints[0], []) == {"model": model, "messages": []}


@pytest.mark.parametrize("options", [
    {"fallback_base_url": "https://other.example/v1"}, {"vision_model": "other"},
    {"reasoning_control": lambda: "max"},
])
def test_main_control_does_not_leak_to_model_overrides_fallback_or_vision(options):
    with pytest.raises(TypeError):
        OpenAICompatibleProvider(ROUTES[0][0], ROUTES[0][1], **options)


@pytest.mark.parametrize("alias", ["minimal", "medium", "xhigh", "ultra"])
def test_official_direct_compatibility_aliases_are_canonical(alias):
    provider = OpenAICompatibleProvider("https://api.deepseek.com", "deepseek-flash", extra_body={"reasoning_effort": alias})
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == {"reasoning_effort": alias}


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("value", [-1, 0, 101, True, False, 75.0, "75", "medium-unknown"])
def test_unsupported_native_effort_is_not_sent(base, model, transport, value):
    provider = OpenAICompatibleProvider(base, model, extra_body={"reasoning_effort": value})
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == {"reasoning_effort": value}


@pytest.mark.parametrize("value", ["bogus", 0, 101, True, False, 75.0, "75", None, {}])
def test_malformed_runtime_control_fails_closed(value):
    with pytest.raises(TypeError, match="reasoning_control"):
        OpenAICompatibleProvider(ROUTES[0][0], ROUTES[0][1], reasoning_control=lambda: value)


def test_actual_retry_and_next_call_use_explicit_current_controls(monkeypatch):
    body = {"reasoning": {"effort": "high"}, "provider": {"only": ["declared"], "allow_fallbacks": False}}
    original = deepcopy(body)
    provider = OpenAICompatibleProvider(ROUTES[0][0], ROUTES[0][1], extra_body=body, retry_attempts=2)
    provider.available = True
    session = FakeSequenceSession([FakeErrorResponse(503, "temporary"), FakeResponse(), FakeResponse()])
    provider._session = session
    monkeypatch.setattr("providers.asyncio.sleep", AsyncMock())
    assert asyncio.run(provider.generate_response([])) == "ok"
    body["reasoning"]["effort"] = "low"
    assert asyncio.run(provider.generate_response([])) == "ok"
    assert session.payloads[0] == session.payloads[1] == session.payloads[2]
    assert all(payload["provider"] == original["provider"] for payload in session.payloads)
    assert provider.extra_body == original
