import asyncio
from copy import deepcopy

import pytest

from providers import OllamaProvider, deepseek_reasoning_transport
from test_providers import FakeErrorResponse, FakeResponse, FakeSequenceSession


ROUTES = [
    ("https://openrouter.ai/api/v1", "deepseek/deepseek-v4.1-flash", "openrouter"),
    ("https://api.deepseek.com", "deepseek-flash", "deepseek"),
    ("https://api.deepseek.com/v1", "deepseek-v4-flash", "deepseek"),
    ("https://api.deepseek.com/v1", "deepseek-v4-flash-vision-exp", "deepseek"),
]


def reasoning_fields(payload):
    return {key: payload[key] for key in ("reasoning", "reasoning_effort", "thinking") if key in payload}


def expected_fields(transport, level):
    effort = "none" if level == "off" else level
    if transport == "openrouter":
        result = {"reasoning": {"enabled": level != "off", "effort": effort}}
    else:
        result = {"thinking": {"type": "disabled" if level == "off" else "enabled"}, "reasoning_effort": effort}
    return result


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("level", ["", "low", "high", "max", "off"])
def test_baseline_and_runtime_are_always_explicit(base, model, transport, level):
    provider = OllamaProvider(base, model, 8192, 0.6, reasoning_control=lambda: level)
    assert deepseek_reasoning_transport(base, model) == transport
    payload = provider._request_payload(provider._endpoints[0], [])
    assert reasoning_fields(payload) == expected_fields(transport, level or "high")


@pytest.mark.parametrize("number", range(1, 101))
@pytest.mark.parametrize("source", ["control", "extra_body"])
def test_numeric_openrouter_effort_reaches_payload_as_integer(number, source):
    provider = OllamaProvider(
        ROUTES[0][0], ROUTES[0][1], 8192, 0.6,
        reasoning_control=(lambda: number) if source == "control" else None,
        extra_body={"provider": {"only": ["deepseek"]}, "reasoning": {"effort": number}} if source == "extra_body" else {"provider": {"only": ["deepseek"]}},
    )
    endpoint = provider._endpoints[0]
    payload = provider._request_payload(endpoint, [])
    assert payload["reasoning"] == {"enabled": True, "effort": number}
    assert type(payload["reasoning"]["effort"]) is int
    assert payload["provider"] == {"only": ["deepseek"]}
    assert provider._request_payload(endpoint, [], disable_reasoning=True)["reasoning"] == {"enabled": False, "effort": "none"}
    assert provider._request_payload(endpoint, [], disable_reasoning=False)["reasoning"] == payload["reasoning"]
    assert provider._request_payload(endpoint, []) == payload


@pytest.mark.parametrize("base,model,transport", ROUTES[1:])
@pytest.mark.parametrize("value", [1, 37, 50, 75, 100])
def test_direct_api_numeric_behavior_is_unchanged(base, model, transport, value):
    provider = OllamaProvider(base, model, 8192, 0.6, reasoning_control=lambda: value)
    with pytest.raises(ValueError, match="DeepSeek reasoning control"):
        provider._request_payload(provider._endpoints[0], [])


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("level", ["low", "max", "off"])
@pytest.mark.parametrize("disable", [False, True])
def test_per_call_override_wins_without_mutating_main(base, model, transport, level, disable):
    provider = OllamaProvider(base, model, 8192, 0.6, reasoning_control=lambda: level)
    endpoint = provider._endpoints[0]
    before = provider._request_payload(endpoint, [])
    payload = provider._request_payload(endpoint, [], disable_reasoning=disable)
    effective = "off" if disable else "high" if level == "off" else level
    assert reasoning_fields(payload) == expected_fields(transport, effective)
    assert provider._request_payload(endpoint, []) == before


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("disabled", [False, True])
def test_endpoint_disable_has_valid_explicit_fields(base, model, transport, disabled):
    provider = OllamaProvider(base, model, 8192, 0.6, disable_reasoning=disabled)
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == expected_fields(transport, "off" if disabled else "high")


@pytest.mark.parametrize("base,model,transport", ROUTES)
def test_live_control_changes_future_payloads_only(base, model, transport):
    control = {"deepseek_reasoning": "low"}
    provider = OllamaProvider(base, model, 8192, 0.6, reasoning_control=lambda: control["deepseek_reasoning"])
    first = provider._request_payload(provider._endpoints[0], [])
    control["deepseek_reasoning"] = "max"
    second = provider._request_payload(provider._endpoints[0], [])
    assert reasoning_fields(first) == expected_fields(transport, "low")
    assert reasoning_fields(second) == expected_fields(transport, "max")


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("body,expected", [
    ({"reasoning_effort": "low"}, "low"),
    ({"reasoning": {"effort": "max"}}, "max"),
    ({"reasoning": {"enabled": False}}, "off"),
    ({"thinking": {"type": "disabled"}}, "off"),
    ({"reasoning_effort": "none"}, "off"),
])
def test_existing_configuration_becomes_explicit_without_changing_intent(base, model, transport, body, expected):
    provider = OllamaProvider(base, model, 8192, 0.6, extra_body=body)
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == expected_fields(transport, expected)


@pytest.mark.parametrize("base,model,transport", ROUTES)
def test_runtime_wins_conflicting_extra_options_and_preserves_routing(base, model, transport):
    extras = {
        "provider": {"only": ["deepseek"], "allow_fallbacks": False},
        "reasoning": {"effort": "max", "enabled": False, "max_tokens": 123, "exclude": True},
        "reasoning_effort": "none", "thinking": {"type": "disabled", "budget_tokens": 0},
        "custom": {"labels": ["keep"]},
    }
    original = deepcopy(extras)
    provider = OllamaProvider(base, model, 8192, 0.6, extra_body=extras,
                              reasoning_control=lambda: "low", api_key="synthetic-key",
                              extra_headers={"HTTP-Referer": "https://app.example/", "X-OpenRouter-Title": "Synthetic"})
    payload = provider._request_payload(provider._endpoints[0], [])
    expected = expected_fields(transport, "low")
    if transport == "openrouter":
        expected["reasoning"]["exclude"] = True
    assert reasoning_fields(payload) == expected
    assert payload["provider"] == extras["provider"]
    assert payload["custom"] == extras["custom"]
    assert provider._headers() == {"HTTP-Referer": "https://app.example/", "X-OpenRouter-Title": "Synthetic", "Authorization": "Bearer synthetic-key"}
    payload["provider"]["only"].append("mutated")
    assert provider.extra_body == original == extras


@pytest.mark.parametrize("base,model", [
    ("https://openrouter.ai/api/v1", "deepseek/deepseek-v4-flash"),
    ("https://openrouter.ai/api/v1", "google/gemini-3.7-flash"),
    ("https://api.deepseek.com/v1", "deepseek-v4-pro"),
    ("https://api.deepseek.com/v1", "deepseek-v4.1-flash"),
    ("https://api.deepseek.com.evil.test/v1", "deepseek-flash"),
    ("https://openrouter.ai.evil.test/api/v1", "deepseek/deepseek-v4.1-flash"),
    ("https://gateway.example/v1", "deepseek-flash"),
])
def test_other_models_and_hosts_are_untouched(base, model):
    assert deepseek_reasoning_transport(base, model) == ""
    provider = OllamaProvider(base, model, 8192, 0.6, reasoning_control=lambda: "max")
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == {}


def test_main_control_does_not_leak_to_model_overrides_fallback_or_vision():
    provider = OllamaProvider(ROUTES[0][0], ROUTES[0][1], 8192, 0.6,
                              reasoning_control=lambda: "max",
                              fallback_base_url="https://api.deepseek.com/v1", fallback_model="deepseek-flash",
                              vision_base_url="https://vision.example/v1", vision_model="other")
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [], model="other")) == {}
    assert reasoning_fields(provider._request_payload(provider._endpoints[1], [])) == expected_fields("deepseek", "off")
    assert reasoning_fields(provider._request_payload(provider._endpoints[2], [], disable_reasoning=False)) == {}


@pytest.mark.parametrize("alias,expected", [("minimal", "low"), ("medium", "high"), ("xhigh", "high"), ("ultra", "max")])
def test_official_direct_compatibility_aliases_are_canonical(alias, expected):
    provider = OllamaProvider("https://api.deepseek.com", "deepseek-flash", 8192, 0.6, extra_body={"reasoning_effort": alias})
    assert reasoning_fields(provider._request_payload(provider._endpoints[0], [])) == expected_fields("deepseek", expected)


@pytest.mark.parametrize("base,model,transport", ROUTES)
@pytest.mark.parametrize("value", [-1, 0, 101, True, False, 75.0, "75", "medium-unknown"])
def test_unsupported_native_effort_is_not_sent(base, model, transport, value):
    provider = OllamaProvider(base, model, 8192, 0.6, extra_body={"reasoning_effort": value})
    with pytest.raises(ValueError, match="DeepSeek reasoning supports"):
        provider._request_payload(provider._endpoints[0], [])


@pytest.mark.parametrize("value", ["bogus", 0, 101, True, False, 75.0, "75", None, {}])
def test_malformed_runtime_control_fails_closed(value):
    provider = OllamaProvider(ROUTES[0][0], ROUTES[0][1], 8192, 0.6, reasoning_control=lambda: value)
    with pytest.raises(ValueError, match="reasoning control"):
        provider._request_payload(provider._endpoints[0], [])


def test_actual_retry_and_next_call_use_explicit_current_controls(monkeypatch):
    control = {"level": "high"}
    provider = OllamaProvider(ROUTES[0][0], ROUTES[0][1], 8192, 0.6,
                              reasoning_control=lambda: control["level"], retry_attempts=2,
                              extra_body={"provider": {"only": ["deepseek"]}})
    provider.available = True
    session = FakeSequenceSession([FakeErrorResponse(503, "temporary"), FakeResponse(), FakeResponse()])
    provider._session = session

    async def change_control(*args):
        control["level"] = "low"

    monkeypatch.setattr("providers.asyncio.sleep", change_control)

    async def scenario():
        assert await provider.generate_response([{"role": "user", "content": "synthetic"}]) == "ok"
        control["level"] = "max"
        assert await provider.generate_response([{"role": "user", "content": "synthetic"}], disable_reasoning=True) == "ok"

    asyncio.run(scenario())
    assert [payload["reasoning"] for payload in session.payloads] == [
        {"enabled": True, "effort": "high"}, {"enabled": True, "effort": "low"},
        {"enabled": False, "effort": "none"},
    ]
    assert all(payload["provider"] == {"only": ["deepseek"]} for payload in session.payloads)
    assert control["level"] == "max"
