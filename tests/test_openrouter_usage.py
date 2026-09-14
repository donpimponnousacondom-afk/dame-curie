import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bot_tools import UsageTool
from providers import OllamaProvider
from tool_schemas import RESULT_TOOL_NAMES, build_openai_tools


@pytest.fixture
def usage_tool(monkeypatch):
    provider = SimpleNamespace(
        base_url="https://openrouter.ai/api/v1",
        api_key="synthetic-loaded-primary-key",
    )
    bot = SimpleNamespace(
        ai_provider=provider,
        config=SimpleNamespace(
            OLLAMA_BASE_URL="https://api.deepseek.com/v1",
            OLLAMA_API_KEY="synthetic-stale-config-key",
        ),
    )
    data = {
        "usage": 25.5,
        "usage_daily": 0.000031,
        "usage_weekly": 3.75,
        "usage_monthly": 9.25,
        "byok_usage": 17.38,
        "byok_usage_daily": 0.1,
        "byok_usage_weekly": 0.8,
        "byok_usage_monthly": 5.2,
        "limit": 100,
        "limit_remaining": 74.5,
        "limit_reset": "monthly",
        "include_byok_in_limit": False,
        "label": "PRIVATE-LABEL",
        "hash": "PRIVATE-HASH",
        "creator_user_id": "PRIVATE-USER-ID",
        "workspace_id": "PRIVATE-WORKSPACE-ID",
        "key": "PRIVATE-RESPONSE-KEY",
        "rate_limit": {"note": "PRIVATE-RATE-LIMIT-NOTE"},
    }
    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.text = AsyncMock(return_value=json.dumps({"data": data}))
    session = MagicMock()
    session.get.return_value = response
    get_session = AsyncMock(return_value=session)
    monkeypatch.setattr("bot_tools._get_shared_session", get_session)
    monkeypatch.setenv("OLLAMA_API_KEY", "synthetic-stale-env-key")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "synthetic-unrelated-compat-key")
    monkeypatch.setenv("MAXWELL_USAGE_URL", "https://untrusted.example.invalid/usage")
    return UsageTool(bot), session, response, get_session, data


def test_reports_per_key_usd_and_separate_byok_without_private_fields(usage_tool, caplog):
    tool, session, response, _, _ = usage_tool

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result == (
        "OpenRouter primary-key usage (USD):\n"
        "Windows: current UTC day, week (Monday–Sunday), and month.\n"
        "OpenRouter credits used — all time: $25.5\n"
        "OpenRouter credits used — day: $0.000031\n"
        "OpenRouter credits used — week: $3.75\n"
        "OpenRouter credits used — month: $9.25\n"
        "External BYOK usage — all time: $17.38\n"
        "External BYOK usage — day: $0.1\n"
        "External BYOK usage — week: $0.8\n"
        "External BYOK usage — month: $5.2\n"
        "Key spending cap: $100\n"
        "Key remaining cap: $74.5\n"
        "Key cap reset: monthly\n"
        "Scheduled resets occur at 00:00 UTC; weeks start Monday.\n"
        "External BYOK counts toward key cap: no\n"
        "External BYOK usage is separate from OpenRouter credit usage. "
        "Scope: all callers sharing the loaded primary key, not necessarily bot-only. "
        "This is not an account/workspace balance or a guarantee requests can run; "
        "token counts and cache ratios are not provided."
    )
    assert "PRIVATE-" not in result + caplog.text
    assert "synthetic-" not in result + caplog.text
    session.get.assert_called_once()
    response.text.assert_awaited_once()


@pytest.mark.parametrize(
    "base",
    [
        "https://openrouter.ai",
        "https://openrouter.ai/api/v1/",
        "https://openrouter.ai:443/api/v1",
        "https://OPENROUTER.AI/api/v1",
    ],
)
def test_uses_fixed_origin_loaded_key_and_no_redirects(usage_tool, base):
    tool, session, _, _, _ = usage_tool
    tool.bot.ai_provider.base_url = base
    tool.bot.ai_provider.api_key = "  synthetic-current-key  "

    result = asyncio.run(
        tool.execute(
            SimpleNamespace(),
            url="https://untrusted.example.invalid/override",
            api_key="synthetic-tool-argument-key",
            reasoning="synthetic reasoning",
        )
    )

    assert result.startswith("OpenRouter primary-key usage")
    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args == ("https://openrouter.ai/api/v1/key",)
    assert kwargs["headers"] == {
        "Authorization": "Bearer synthetic-current-key",
        "Accept": "application/json",
    }
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"].total == 30
    assert set(kwargs) == {"headers", "allow_redirects", "timeout"}
    session.post.assert_not_called()


@pytest.mark.parametrize(
    "base",
    [
        "https://api.deepseek.com/v1",
        "http://openrouter.ai/api/v1",
        "https://openrouter.ai.evil.invalid/api/v1",
        "https://sub.openrouter.ai/api/v1",
        "https://openrouter.ai@evil.invalid/api/v1",
        "https://PRIVATE-USER@openrouter.ai/api/v1",
        "https://PRIVATE-USER:PRIVATE-PASSWORD@openrouter.ai/api/v1",
        "https://openrouter.ai:8443/api/v1",
        "https://openrouter.ai:not-a-port/api/v1",
        "https://openrouter.ai./api/v1",
        "https://openrouter.ai/api/v1?key=PRIVATE-QUERY",
        "https://openrouter.ai/api/v1#PRIVATE-FRAGMENT",
        "https://[invalid-host/api/v1",
        "openrouter.ai/api/v1",
        "",
    ],
)
def test_untrusted_or_non_openrouter_primary_sends_nothing(usage_tool, base):
    tool, session, _, get_session, _ = usage_tool
    tool.bot.ai_provider.base_url = base
    tool.bot.config.OLLAMA_BASE_URL = "https://openrouter.ai/api/v1"

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result.startswith("Error:")
    assert "PRIVATE-" not in result
    assert "synthetic-" not in result
    get_session.assert_not_awaited()
    session.get.assert_not_called()


@pytest.mark.parametrize("key", ["", "   "])
def test_missing_loaded_key_never_borrows_environment_or_config(usage_tool, key):
    tool, session, _, get_session, _ = usage_tool
    tool.bot.ai_provider.api_key = key

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "no API key" in result
    get_session.assert_not_awaited()
    session.get.assert_not_called()


def test_missing_loaded_provider_does_not_fall_back_to_config(usage_tool):
    tool, session, _, get_session, _ = usage_tool
    del tool.bot.ai_provider
    tool.bot.config.OLLAMA_BASE_URL = "https://openrouter.ai/api/v1"

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "only a loaded HTTPS OpenRouter primary is supported" in result
    get_session.assert_not_awaited()
    session.get.assert_not_called()


def test_real_provider_uses_primary_not_fallback_or_last_response(usage_tool):
    tool, session, _, _, _ = usage_tool
    tool.bot.ai_provider = OllamaProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="synthetic-real-primary",
        model="synthetic-primary-model",
        max_tokens=100,
        temperature=0.6,
        fallback_base_url="https://api.deepseek.com/v1",
        fallback_api_key="synthetic-fallback-key",
        fallback_model="synthetic-fallback-model",
    )
    tool.bot.ai_provider._last_usage = {"provider": "fallback", "usage": 999}

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "OpenRouter credits used — all time: $25.5" in result
    assert session.get.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer synthetic-real-primary"
    )


@pytest.mark.parametrize("status", [301, 302, 307, 308, 401, 402, 403, 429, 500])
def test_http_errors_and_redirects_never_read_or_expose_response_body(usage_tool, status, caplog):
    tool, session, response, _, _ = usage_tool
    response.status = status
    response.text.return_value = "PRIVATE-ERROR-BODY synthetic-loaded-primary-key"
    response.headers = {"Location": "https://untrusted.example.invalid/PRIVATE-REDIRECT"}

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result == f"Error: OpenRouter key usage returned HTTP {status}; no usage data available."
    assert "PRIVATE-" not in result + caplog.text
    assert "synthetic-" not in result + caplog.text
    response.text.assert_not_awaited()
    session.get.assert_called_once()
    assert session.get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "body",
    [
        "<html>PRIVATE-HTML-BODY</html>",
        "PRIVATE-INVALID-JSON",
        "null",
        "[]",
        '"PRIVATE-STRING"',
        '{"data": null, "label": "PRIVATE-LABEL"}',
        '{"data": [], "label": "PRIVATE-LABEL"}',
        '{"error": "PRIVATE-ERROR"}',
    ],
)
def test_malformed_responses_never_echo_raw_data(usage_tool, body, caplog):
    tool, session, response, _, _ = usage_tool
    response.text.return_value = body

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result.startswith("Error: OpenRouter key usage")
    assert "no usage data available" in result
    assert "PRIVATE-" not in result + caplog.text
    session.get.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        asyncio.TimeoutError("PRIVATE-TIMEOUT"),
        aiohttp.ClientConnectionError("PRIVATE-TRANSPORT synthetic-loaded-primary-key"),
        RuntimeError("PRIVATE-FAILURE synthetic-loaded-primary-key"),
    ],
)
def test_transport_failures_are_sanitized_without_retry(usage_tool, error, caplog):
    tool, session, _, _, _ = usage_tool
    session.get.side_effect = error

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result.startswith("Error: OpenRouter key usage")
    assert "no usage data available" in result
    assert "PRIVATE-" not in result + caplog.text
    assert "synthetic-" not in result + caplog.text
    session.get.assert_called_once()


def test_session_failure_is_sanitized(usage_tool):
    tool, session, _, get_session, _ = usage_tool
    get_session.side_effect = RuntimeError("PRIVATE-SESSION-ERROR")

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "no usage data available" in result
    assert "PRIVATE-" not in result
    session.get.assert_not_called()


def test_cancellation_propagates(usage_tool):
    tool, session, _, _, _ = usage_tool
    session.get.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(tool.execute(SimpleNamespace()))

    session.get.assert_called_once()


@pytest.mark.parametrize("reset", ["daily", "weekly", "monthly", None])
@pytest.mark.parametrize("include_byok", [True, False])
def test_nullable_cap_and_reset_are_not_workspace_credit_balance(usage_tool, reset, include_byok):
    tool, _, response, _, data = usage_tool
    data.update(limit=None, limit_remaining=None, limit_reset=reset, include_byok_in_limit=include_byok)
    response.text.return_value = json.dumps({"data": data})

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "Key spending cap: no key cap" in result
    assert "Key remaining cap: no key cap" in result
    assert f"Key cap reset: {'none' if reset is None else reset}" in result
    assert f"External BYOK counts toward key cap: {'yes' if include_byok else 'no'}" in result
    assert "not an account/workspace balance or a guarantee requests can run" in result


def test_missing_fields_are_unknown_not_zero_unlimited_or_no_reset(usage_tool):
    tool, _, response, _, _ = usage_tool
    response.text.return_value = '{"data": {}}'

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert result.count(": unknown") == 12
    assert "$0" not in result
    assert "no key cap" not in result
    assert "Key cap reset: none" not in result
    assert "Rate-limited: none" not in result


@pytest.mark.parametrize("invalid", [True, False, "PRIVATE-NUMBER", {"key": "PRIVATE-NUMBER"}, float("nan"), float("inf"), -float("inf")])
def test_monetary_values_cannot_expose_unexpected_strings_or_fake_numbers(usage_tool, invalid):
    tool, _, response, _, data = usage_tool
    data.update(usage=invalid, byok_usage=invalid, limit=invalid, limit_remaining=invalid)
    data["limit_reset"] = "PRIVATE-RESET"
    data["include_byok_in_limit"] = "PRIVATE-BYOK"
    response.text.return_value = json.dumps({"data": data})

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "OpenRouter credits used — all time: unknown" in result
    assert "External BYOK usage — all time: unknown" in result
    assert "Key spending cap: unknown" in result
    assert "Key remaining cap: unknown" in result
    assert "Key cap reset: unknown" in result
    assert "External BYOK counts toward key cap: unknown" in result
    assert "PRIVATE-" not in result


def test_zero_and_negative_remaining_are_preserved_without_claiming_capacity(usage_tool):
    tool, _, response, _, data = usage_tool
    data.update(usage=0, byok_usage=0, limit_remaining=-0.125)
    response.text.return_value = json.dumps({"data": data})

    result = asyncio.run(tool.execute(SimpleNamespace()))

    assert "OpenRouter credits used — all time: $0\n" in result
    assert "External BYOK usage — all time: $0\n" in result
    assert "Key remaining cap: $-0.125" in result
    assert "not an account/workspace balance or a guarantee requests can run" in result


def test_schema_preserves_name_and_explains_per_key_scope(usage_tool):
    tool, _, _, _, _ = usage_tool

    schema = build_openai_tools({"usage": tool})[0]["function"]

    assert schema["name"] == "usage"
    assert "usage" in RESULT_TOOL_NAMES
    assert schema["description"].endswith("[returns output]")
    assert "current UTC day/week/month" in schema["description"]
    assert "Not account/workspace balance, token counts or cache ratios" in schema["description"]
    assert "not necessarily this bot alone" in schema["description"]
    assert set(schema["parameters"]["properties"]) == {"reasoning"}
    assert "z3ki" not in schema["description"]
