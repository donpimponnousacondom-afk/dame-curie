import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from error_reporting import PUBLIC_ERROR_TEXT
from provider_telemetry import CallMetrics
from response_observability import (
    DEFAULT_FOOTER_FORMAT,
    FOOTER_MARKER,
    DeliveryMeasurements,
    RunningBuild,
    capture_running_build,
    clean_message_content,
    footer_template_error,
    format_debug,
    format_runtime_provider,
    prepare_delivery,
    record_delivery,
    render_footer,
    strip_footer,
)


@pytest.fixture
def metrics():
    return CallMetrics(
        call_id="call-one",
        provider="provider.example",
        endpoint="primary",
        model="model-one",
        input_tokens=123,
        output_tokens=50,
        reasoning_tokens=10,
        input_source="provider",
        output_source="provider",
        elapsed_ms=2000,
        ttft_ms=125,
        ttft_estimated=False,
        stream=True,
        attempt=1,
        output_bytes=160,
    )


class Channel:
    def __init__(self, channel_id=100, fail_after=None):
        self.id = channel_id
        self.guild = SimpleNamespace(id=9)
        self.sent = []
        self.fail_after = fail_after

    async def send(self, content=None, **kwargs):
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise RuntimeError("synthetic send failure")
        sent = SimpleNamespace(id=1000 + len(self.sent), channel=self, content=content)
        self.sent.append(sent)
        return sent


class Message:
    def __init__(self, channel=None, content="hello"):
        self.channel = channel or Channel()
        self.guild = self.channel.guild
        self.author = SimpleNamespace(id=7, display_name="root", bot=False)
        self.id = 7
        self.content = content
        self.reference = None
        self.attachments = []
        self.embeds = []
        self.stickers = []
        self.mentions = []

    async def reply(self, content=None, **kwargs):
        return await self.channel.send(content, **kwargs)


def fake_bot(**kwargs):
    return SimpleNamespace(
        _control=kwargs.pop("_control", {}),
        _delivery_measurements=DeliveryMeasurements(),
        bot_name="Dame Curie",
        user=SimpleNamespace(id=42),
        **kwargs,
    )


def test_footer_tokens_and_estimates(metrics):
    measured = replace(
        metrics, input_source="cl100k_base", output_source="mixed", ttft_estimated=True
    )
    footer = render_footer(
        "{{TTFT}} {{TPS}} {{PROVIDER}} {{CONTEXT}} {{MODEL}} {{BOT}}", measured, "Curie"
    )
    assert (
        footer
        == "-# ~125ms ~25.0 provider.example ~123 model-one Curie" + FOOTER_MARKER
    )
    assert "reasoning" in format_debug_for(measured)


def format_debug_for(metrics):
    registry = DeliveryMeasurements()
    registry.record("100", "900", metrics)
    return format_debug(registry, "100")


@pytest.mark.parametrize(
    "template",
    ["", "   ", "x" * 301, "a\nb", "a\r", "a\u2028b", "{{UNKNOWN}}", FOOTER_MARKER],
)
def test_invalid_footer_template(template):
    assert footer_template_error(template)


def test_footer_template_maximum_and_literal_substitution(metrics):
    assert footer_template_error("x" * 300) is None
    assert footer_template_error("{{BOT}} {{CONTEXT}}") is None
    text = render_footer("{{BOT}}", metrics, "{{MODEL}}\n" + "x" * 400)
    assert len(text) <= 300
    assert "\n" not in text
    assert "{{MODEL}}" in text
    assert text.endswith(FOOTER_MARKER)


@pytest.mark.parametrize("bad", [None, {}, 123, "\n", "{{BAD}}", "x" * 301])
def test_persisted_bad_format_falls_back(metrics, bad):
    bot = fake_bot(_control={"footer_format": bad})
    clean, wire = prepare_delivery(bot, "answer", metrics)
    assert clean == ["answer"]
    assert wire == [
        "answer\n" + render_footer(DEFAULT_FOOTER_FORMAT, metrics, bot.bot_name)
    ]


def test_split_reserves_footer_once_preserves_body_and_fences(metrics):
    from bot import MaxwellBot

    text = "```python\n" + "x = 123\n" * 650 + "```"
    bot = fake_bot(_control={"footer_format": "x" * 300})
    clean, wire = prepare_delivery(bot, text, metrics, MaxwellBot._split_response)
    assert len(wire) > 1
    assert all(len(chunk) <= 2000 for chunk in wire)
    assert sum(FOOTER_MARKER in chunk for chunk in wire) == 1
    assert wire[-1].endswith(FOOTER_MARKER)
    assert all(chunk.count("```") % 2 == 0 for chunk in clean)
    assert [strip_footer(chunk, self_authored=True) for chunk in wire] == clean


@pytest.mark.parametrize(
    "platform,enabled,measured",
    [("discord", False, True), ("telegram", True, True), ("discord", True, False)],
)
def test_disabled_telegram_and_no_call_have_identical_body(
    metrics, platform, enabled, measured
):
    bot = fake_bot(_control={"footer_enabled": enabled})
    clean, wire = prepare_delivery(
        bot, "unchanged", metrics if measured else None, platform=platform
    )
    assert clean == wire == ["unchanged"]
    assert prepare_delivery(bot, "", metrics, platform=platform) == ([], [])


def test_self_footer_strip_survives_format_changes_and_preserves_foreign_text(metrics):
    bot = fake_bot()
    own = Message(
        content="answer\n" + render_footer("old literal template", metrics, "old name")
    )
    own.author.id = bot.user.id
    assert clean_message_content(bot, own) == "answer"
    own.author.id = 17
    assert clean_message_content(bot, own) == own.content
    own.author.bot = True
    assert clean_message_content(bot, own) == own.content
    assert strip_footer("answer\n-# ordinary subtext", self_authored=True).endswith(
        "ordinary subtext"
    )
    assert strip_footer(
        own.content + "\nreal continuation", self_authored=True
    ).endswith("real continuation")


def test_registry_channel_exact_reply_eviction_and_no_call(metrics):
    bot = fake_bot()
    registry = bot._delivery_measurements = DeliveryMeasurements(limit=2)
    first = Channel(100)
    second = Channel(200)
    record_delivery(bot, first, SimpleNamespace(id=1), metrics)
    record_delivery(bot, second, SimpleNamespace(id=2), replace(metrics, model="other"))
    assert "model-one" in format_debug(registry, "100")
    assert "Measured bot message: 1 (channel 100)" in format_debug(registry, "100")
    assert "No measurements" in format_debug(registry, "100", "2")
    record_delivery(bot, first, SimpleNamespace(id=3), None)
    assert registry.lookup("100")[0] == "1"
    record_delivery(bot, first, SimpleNamespace(id=4), metrics)
    assert registry.lookup("100", "1") is None
    record_delivery(bot, first, SimpleNamespace(id=4), None, replace=True)
    assert registry.lookup("100") is None


def test_usage_empty_or_plain_string_never_borrows(metrics):
    from bot import MaxwellBot
    from providers import ProviderResult

    bot = fake_bot(ai_provider=SimpleNamespace(_last_usage={"prompt_tokens": 99999}))
    assert MaxwellBot._usage_from(bot, "static") == {}
    assert MaxwellBot._usage_from(bot, ProviderResult("answer", usage={})) == {}
    assert MaxwellBot._usage_from(
        bot, ProviderResult("answer", usage={"prompt_tokens": 12})
    ) == {"prompt_tokens": 12}


def test_concurrent_send_tools_register_own_call_and_clean_results(metrics):
    from bot_tools import SendMessageTool

    async def scenario():
        bot = fake_bot()
        a, b = Message(Channel(100)), Message(Channel(200))
        one, two = (
            metrics,
            replace(metrics, call_id="call-two", model="other", ttft_ms=900),
        )
        results = await asyncio.gather(
            SendMessageTool(bot).execute(a, content="a" * 3900, _response_metrics=one),
            SendMessageTool(bot).execute(b, content="b", _response_metrics=two),
        )
        assert all(FOOTER_MARKER not in result for result in results)
        for message, measured in ((a, one), (b, two)):
            for sent in message.channel.sent:
                assert (
                    bot._delivery_measurements.lookup(
                        str(message.channel.id), str(sent.id)
                    )[1]
                    is measured
                )
        assert "125ms" in a.channel.sent[-1].content
        assert "900ms" in b.channel.sent[-1].content
        return bot

    asyncio.run(scenario())


def test_partial_send_failure_returns_clean_success_and_only_sent_ids(metrics):
    from bot_tools import SendMessageTool

    async def scenario():
        bot = fake_bot()
        message = Message(Channel(fail_after=1))
        result = await SendMessageTool(bot).execute(
            message, content="a" * 3900, reply=False, _response_metrics=metrics
        )
        assert result.startswith("__MESSAGE_SENT__\n")
        assert FOOTER_MARKER not in result
        assert len(bot._delivery_measurements.records) == len(message.channel.sent) == 1
        assert len(result.split("\n", 1)[1]) == 1900

    asyncio.run(scenario())


def test_targeted_send_registers_destination_and_telegram_stays_plain(metrics):
    from bot_tools import SendMessageTool

    async def scenario():
        destination = Channel(200)
        bot = fake_bot(get_channel=lambda cid: destination)
        message = Message(Channel(100))
        await SendMessageTool(bot).execute(
            message,
            content="cross channel",
            channel_id="200",
            _response_metrics=metrics,
        )
        assert bot._delivery_measurements.lookup("100") is None
        assert bot._delivery_measurements.lookup("200") is not None
        message.tool_platform = "telegram"
        await SendMessageTool(bot).execute(
            message, content="telegram", _response_metrics=metrics
        )
        assert message.channel.sent[0].content == "telegram"
        assert bot._delivery_measurements.lookup("100") is None

    asyncio.run(scenario())


def test_edit_replaces_footer_and_metrics_without_borrowing(metrics):
    from bot_tools import EditMessageTool

    async def scenario():
        bot = fake_bot()
        message = Message()
        target = SimpleNamespace(id=999, author=bot.user, edit=AsyncMock(
            side_effect=lambda **kwargs: SimpleNamespace(id=999, author=bot.user, content=kwargs["content"])
        ))
        message.channel.fetch_message = AsyncMock(return_value=target)
        record_delivery(bot, message.channel, target, metrics)
        newer = replace(metrics, call_id="new", ttft_ms=777)
        result = await EditMessageTool(bot).execute(
            message, message_id="999", content="new body", _response_metrics=newer
        )
        assert "successfully" in result
        assert "777ms" in target.edit.call_args.kwargs["content"]
        assert bot._delivery_measurements.lookup("100", "999")[1] is newer
        await EditMessageTool(bot).execute(
            message, message_id="999", content="static edit"
        )
        assert target.edit.call_args.kwargs["content"] == "static edit"
        assert bot._delivery_measurements.lookup("100", "999") is None
        await EditMessageTool(bot).execute(
            message, message_id="999", content="x" * 1990, _response_metrics=newer
        )
        assert target.edit.call_args.kwargs["content"] == "x" * 1990
        assert not message.channel.sent
        assert bot._delivery_measurements.lookup("100", "999")[1] is newer
        target.edit.side_effect = RuntimeError("synthetic edit failure")
        result = await EditMessageTool(bot).execute(
            message,
            message_id="999",
            content="failed change",
            _response_metrics=metrics,
        )
        assert result.startswith("Error editing message")
        assert bot._delivery_measurements.lookup("100", "999")[1] is newer

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "edit_fails,send_fails", [(False, False), (True, False), (True, True)]
)
def test_progress_registers_only_actual_success(metrics, edit_fails, send_fails):
    from tool_progress import ToolProgress

    async def scenario():
        bot = fake_bot()
        message = Message(Channel(fail_after=0 if send_fails else None))
        posted = SimpleNamespace(
            id=33,
            edit=AsyncMock(side_effect=RuntimeError("gone") if edit_fails else None),
        )
        progress = ToolProgress(message)
        progress._posted = posted
        callbacks = []
        done = asyncio.Event()

        def delivered(sent):
            callbacks.append(sent.id)
            record_delivery(bot, message.channel, sent, metrics)
            done.set()

        assert await progress.transition_to_final("answer", on_delivered=delivered)
        assert bot._delivery_measurements.lookup("100") is None
        if send_fails:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert callbacks == []
        else:
            await asyncio.wait_for(done.wait(), timeout=1)
            expected = 1000 if edit_fails else 33
            assert callbacks == [expected]
            assert bot._delivery_measurements.lookup("100")[0] == str(expected)

    asyncio.run(scenario())


def test_footer_commands_auth_validation_and_static_replies(
    metrics, monkeypatch, tmp_path
):
    import response_observability as observability
    from bot import MaxwellBot

    writes = []
    atomic_write = observability._atomic_json_write_sync

    def write(path, control):
        writes.append((path, dict(control)))
        atomic_write(path, control)

    monkeypatch.setattr(observability, "_atomic_json_write_sync", write)

    async def scenario():
        bot = fake_bot(
            _is_admin=lambda uid: uid == 7,
            config=SimpleNamespace(DATA_DIR=str(tmp_path), MAXWELL_PROMPTS_DIR=""),
            command_prefix="!",
            _ai_concurrency=2,
            _apply_x_control=lambda control: None,
            _sync_audio_input_flags=lambda: None,
            _conversation_watch_enabled=lambda: True,
        )
        bot._load_control = lambda force: MaxwellBot._load_control(bot, force=force)
        message = Message()
        record_delivery(bot, message.channel, SimpleNamespace(id=999), metrics)
        await MaxwellBot._handle_footer_command(bot, message, "disable")
        assert bot._control["footer_enabled"] is False
        await MaxwellBot._handle_footer_command(bot, message, "enable")
        assert bot._control["footer_enabled"] is True
        await MaxwellBot._handle_footer_command(
            bot, message, "format {{MODEL}} {{CONTEXT}}"
        )
        assert bot._control["footer_format"] == "{{MODEL}} {{CONTEXT}}"
        await MaxwellBot._handle_footer_command(bot, message, "format " + "x" * 301)
        message.author.id = 8
        await MaxwellBot._handle_footer_command(bot, message, "off")
        assert message.channel.sent[-1].content.startswith("not authorized\n")
        await MaxwellBot._handle_footer_command(bot, message, "status")
        assert "Footer: on" in message.channel.sent[-1].content
        assert FOOTER_MARKER not in message.channel.sent[0].content
        assert message.channel.sent[1].content.endswith(
            "-# TTFT — | TPS —" + FOOTER_MARKER
        )
        assert all(
            sent.content.endswith("-# — —" + FOOTER_MARKER)
            and not sent.content.startswith("```")
            for sent in message.channel.sent[2:-1]
        )
        assert message.channel.sent[-1].content.startswith("```\nFooter: on\n")
        assert message.channel.sent[-1].content.endswith("— —" + FOOTER_MARKER + "\n```")
        assert message.channel.sent[-1].content.count("```") == 2
        assert bot._delivery_measurements.lookup("100")[0] == "999"
        assert len(writes) == 3

    asyncio.run(scenario())


def test_debug_command_exact_reference_and_version_are_unmeasured(metrics):
    from bot import MaxwellBot

    async def scenario():
        build = RunningBuild(
            "a" * 40, "branch", "date", "subject", False, "start", "3.14.4"
        )
        bot = fake_bot(
            _is_admin=lambda uid: uid == 7, command_prefix="!", _running_build=build
        )
        message = Message(content="!debug")
        record_delivery(bot, message.channel, SimpleNamespace(id=999), metrics)
        await MaxwellBot._handle_command(bot, message)
        assert "message: 999" in message.channel.sent[-1].content
        message.reference = SimpleNamespace(message_id=123, channel_id=100)
        await MaxwellBot._handle_command(bot, message)
        assert "No measurements" in message.channel.sent[-1].content
        message.reference = SimpleNamespace(message_id=999, channel_id=200)
        await MaxwellBot._handle_command(bot, message)
        assert "must be in this channel" in message.channel.sent[-1].content
        message.content = "!version"
        await MaxwellBot._handle_command(bot, message)
        assert "Checkout at boot:" in message.channel.sent[-1].content
        assert all(
            sent.content.startswith("```\n") and sent.content.endswith("\n```")
            and FOOTER_MARKER not in sent.content
            for sent in message.channel.sent[:-1]
        )
        assert message.channel.sent[-1].content == (
            "```\n" + build.format() + "\nTTFT — | TPS —" + FOOTER_MARKER + "\n```"
        )
        assert len(bot._delivery_measurements.records) == 1
        bot._control["footer_enabled"] = False
        await MaxwellBot._handle_command(bot, message)
        assert message.channel.sent[-1].content == "```\n" + build.format() + "\n```"
        message.content = "!debug"
        message.author.id = 8
        await MaxwellBot._handle_command(bot, message)
        assert message.channel.sent[-1].content == "not authorized"

    asyncio.run(scenario())


@pytest.fixture
def runtime_provider():
    from providers import OllamaProvider

    provider = OllamaProvider(
        base_url="https://private-user:private-pass@loaded.example/secret-path?token=secret-query#secret-fragment",
        model="loaded-model",
        max_tokens=100,
        temperature=0.6,
        api_key="secret-api-key",
        extra_headers={"X-Private": "secret-header"},
        extra_body={"private": "secret-body"},
    )
    provider.initialize = AsyncMock(side_effect=AssertionError("unexpected probe"))
    provider.generate_response = AsyncMock(side_effect=AssertionError("unexpected inference"))
    return provider


@pytest.mark.parametrize(
    "base_url,hostname",
    [
        ("https://user:password@OPENROUTER.ai:443/api/v1?api_key=secret#private", "openrouter.ai"),
        ("http://user:password@127.0.0.1:11434/v1?api_key=secret#private", "127.0.0.1"),
        ("http://user:password@[::1]:11434/v1?api_key=secret#private", "::1"),
    ],
)
def test_debug_runtime_provider_labels_only_expose_hostname(runtime_provider, base_url, hostname):
    runtime_provider._endpoints[0] = replace(
        runtime_provider._endpoints[0], base_url=base_url
    )
    text = format_runtime_provider(runtime_provider)
    assert text.splitlines()[2] == f"Primary provider: {hostname}"
    for secret in ("user", "password", "api_key", "secret", "private", "/v1", "11434"):
        assert secret not in text


@pytest.mark.parametrize("footer_enabled", [True, False])
def test_debug_loaded_runtime_before_completion_without_config_reads(runtime_provider, footer_enabled):
    from bot import MaxwellBot

    class UnreadableConfig:
        def __getattribute__(self, name):
            raise AssertionError("debug must use the runtime provider, not Config")

    async def scenario():
        bot = fake_bot(
            _is_admin=lambda uid: True, command_prefix="!",
            _control={"footer_enabled": footer_enabled},
            ai_provider=runtime_provider, config=UnreadableConfig(),
        )
        message = Message(content="!debug")
        await MaxwellBot._handle_command(bot, message)
        text = message.channel.sent[-1].content
        assert text.startswith("```\nLoaded runtime configuration:\n")
        assert text.endswith("\n```")
        assert "Primary model: loaded-model" in text
        assert "Primary provider: loaded.example" in text
        assert "Fallback model:" not in text
        assert "No measurements recorded by this process" in text
        assert "TTFT" not in text and FOOTER_MARKER not in text
        for secret in (
            "private-user", "private-pass", "secret-path", "secret-query",
            "secret-fragment", "secret-api-key", "X-Private", "secret-header", "secret-body",
        ):
            assert secret not in text
        runtime_provider.initialize.assert_not_called()
        runtime_provider.generate_response.assert_not_called()
        assert runtime_provider._session is None
        assert not bot._delivery_measurements.records

    asyncio.run(scenario())


@pytest.mark.parametrize("measured_endpoint", ["primary", "fallback", "vision"])
def test_debug_separates_loaded_primary_from_last_request(runtime_provider, metrics, measured_endpoint):
    from bot import MaxwellBot
    from providers import ProviderEndpoint

    async def scenario():
        runtime_provider._endpoints.append(ProviderEndpoint(
            "fallback", "https://fallback-user:fallback-pass@fallback.example/private?key=fallback-secret",
            "loaded-fallback", "fallback-key",
        ))
        bot = fake_bot(
            _is_admin=lambda uid: True, command_prefix="!", ai_provider=runtime_provider,
            config=SimpleNamespace(OLLAMA_MODEL="stale-config-model", OLLAMA_BASE_URL="https://stale.example"),
        )
        message = Message(content="!debug")
        measured = replace(metrics, model="old-request-override", provider="old.example", endpoint=measured_endpoint)
        record_delivery(bot, message.channel, SimpleNamespace(id=999), measured)
        await MaxwellBot._handle_command(bot, message)
        text = message.channel.sent[-1].content
        runtime, measurement = text.split("\n\n", 1)
        assert "Primary model: loaded-model" in runtime
        assert "Primary provider: loaded.example" in runtime
        assert "Fallback model: loaded-fallback" in runtime
        assert "Fallback provider: fallback.example" in runtime
        assert "Per-request fallback/overrides may differ" in runtime
        assert "Measured bot message: 999" in measurement
        assert "Model: old-request-override" in measurement
        assert f"Provider: old.example ({measured_endpoint})" in measurement
        assert "TTFT: 125ms | TPS: 25.0 tok/s" in measurement
        for absent in ("old-request-override", "old.example", "stale-config-model", "stale.example", "fallback-user", "fallback-pass", "fallback-secret", "fallback-key"):
            assert absent not in runtime
        assert FOOTER_MARKER not in text
        assert bot._delivery_measurements.lookup("100")[1] is measured
        runtime_provider.generate_response.assert_not_called()

    asyncio.run(scenario())


def test_debug_fences_every_chunk_and_neutralizes_embedded_fences(runtime_provider):
    from bot import MaxwellBot

    async def scenario():
        runtime_provider._endpoints[0] = replace(
            runtime_provider._endpoints[0], model="```embedded``` " * 300
        )
        bot = fake_bot(
            _is_admin=lambda uid: True, command_prefix="!", ai_provider=runtime_provider,
            _split_response=MaxwellBot._split_response,
        )
        message = Message(content="!debug")
        await MaxwellBot._handle_command(bot, message)
        assert len(message.channel.sent) > 1
        for sent in message.channel.sent:
            assert sent.content.startswith("```\n") and sent.content.endswith("\n```")
            assert sent.content.count("```") == 2
            assert len(sent.content) <= 2000
            assert FOOTER_MARKER not in sent.content

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "commit_date,utc_date",
    [
        ("2026-09-09T00:00:00Z", "2026-09-09T00:00:00+00:00"),
        ("2026-09-09T12:44:04+02:00", "2026-09-09T10:44:04+00:00"),
        ("2026-09-09T23:44:04-05:00", "2026-09-10T04:44:04+00:00"),
    ],
)
def test_version_is_frozen_after_source_head_changes(
    monkeypatch, tmp_path, commit_date, utc_date
):
    import response_observability as observability

    (tmp_path / ".git").mkdir()
    calls = []
    outputs = iter(
        [
            "a" * 40 + f"\n{commit_date}\nfirst commit\n",
            "first-branch\n",
            " M source.py\n",
        ]
    )

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=next(outputs))

    monkeypatch.setattr(observability.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(observability.subprocess, "run", run)
    snapshot = capture_running_build(tmp_path)
    first = snapshot.format()
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("version queried git after startup"),
    )
    assert snapshot.format() == first
    assert "dirty at startup: yes" in first
    assert len(calls) == 3
    assert snapshot.commit == "a" * 40
    assert snapshot.date == utc_date
    assert f"Commit date: {utc_date}" in first
    assert snapshot.started_at.endswith("+00:00")


@pytest.mark.parametrize("enabled", [True, False])
def test_fenced_report_bounds_footer_hygiene_and_embedded_fences(enabled):
    from bot import MaxwellBot

    bot = fake_bot(_control={"footer_enabled": enabled, "footer_format": "```" * 100})
    clean, wire = prepare_delivery(
        bot,
        "Subject: ```example```\n" * 200,
        None,
        MaxwellBot._split_response,
        unmeasured=True,
        code_block=True,
    )
    assert len(wire) > 1
    assert all(len(chunk) <= 2000 for chunk in wire)
    assert all(chunk.startswith("```\n") and chunk.endswith("\n```") for chunk in wire)
    assert all(chunk.count("```") == 2 for chunk in wire)
    assert sum(FOOTER_MARKER in chunk for chunk in wire) == int(enabled)
    assert [strip_footer(chunk, self_authored=True) for chunk in wire] == clean
    assert [strip_footer(chunk, self_authored=False) for chunk in wire] == wire
    if enabled:
        assert len(wire[-1].splitlines()[-2]) <= 300
        assert not wire[-1].splitlines()[-2].startswith("-# ")


def test_intentional_unmeasured_footer_has_no_call_fields():
    template = "{{TTFT}} {{TPS}} {{PROVIDER}} {{CONTEXT}} {{MODEL}} {{BOT}}"
    bot = fake_bot(_control={"footer_format": template})
    assert (
        render_footer(template, None, "Curie") == "-# — — — — — Curie" + FOOTER_MARKER
    )
    clean, wire = prepare_delivery(bot, "static reply", None, unmeasured=True)
    assert clean == ["static reply"]
    assert wire[0].endswith("-# — — — — — Dame Curie" + FOOTER_MARKER)
    assert prepare_delivery(bot, "other static reply", None)[1] == [
        "other static reply"
    ]


def test_footer_does_not_ping_but_body_mentions_remain(metrics):
    bot = fake_bot(_control={"footer_format": "@everyone {{MODEL}}"})
    _, wire = prepare_delivery(bot, "hello <@123>", replace(metrics, model="<@456>"))
    assert wire[0].startswith("hello <@123>\n")
    assert "@everyone" not in wire[0]
    assert "<@456>" not in wire[0]
    assert "@\u200beveryone" in wire[0]


@pytest.mark.parametrize("fail_followup", [False, True])
def test_background_producing_call_survives_string_recovery_without_error_borrow(
    metrics, fail_followup
):
    from jobs import run_background_job
    from providers import ProviderResult

    async def scenario():
        message = Message()
        job = SimpleNamespace(
            id="job", guild_id="9", channel_id="100", user_id="7", goal="test", context=""
        )
        manager = SimpleNamespace(
            get=lambda job_id: job,
            runtime=lambda job_id: {"message": message, "channel": message.channel},
            mark=lambda job_id, **updates: vars(job).update(updates),
            cleanup_runtime=lambda job_id: None,
        )
        if fail_followup:
            call = {"id": "tool", "function": {"name": "web_search", "arguments": "{}"}}
            responses = [
                ProviderResult("", tool_calls=[call], metrics=metrics),
                RuntimeError("synthetic failure"),
            ]
            dispatched = [("", ["Tool web_search: found things"])]
        else:
            responses = [ProviderResult("x" * 3500, metrics=metrics)]
            dispatched = [("x" * 3500, [])]
        bot = fake_bot(
            bg_jobs=manager,
            config=SimpleNamespace(),
            _message_tool_platform=lambda message: "discord",
            _tool_system_prompt=lambda *args, **kwargs: "",
            _build_openai_tools=lambda *args, **kwargs: [],
            _select_tool_protocol=lambda tools: (False, []),
            _acquire_ai_slot=AsyncMock(),
            _release_ai_slot=AsyncMock(),
            _generate_response=AsyncMock(side_effect=responses),
            _native_calls_from=lambda response: response.tool_calls,
            _recover_text_tool_calls=lambda response: ([], str(response)),
            _dispatch_tool_calls=AsyncMock(side_effect=dispatched),
        )
        await run_background_job(bot, "job")
        assert bot._dispatch_tool_calls.call_args.kwargs["response_metrics"] is metrics
        assert message.channel.sent
        if fail_followup:
            assert message.channel.sent[-1].content == PUBLIC_ERROR_TEXT
            assert job.status == "error"
            assert not bot._delivery_measurements.records
            assert all(
                FOOTER_MARKER not in sent.content for sent in message.channel.sent
            )
        else:
            assert len(message.channel.sent) > 1
            assert message.channel.sent[-1].content.endswith(FOOTER_MARKER)
            assert FOOTER_MARKER not in job.result
            for sent in message.channel.sent:
                assert (
                    bot._delivery_measurements.lookup("100", str(sent.id))[1] is metrics
                )

    asyncio.run(scenario())


def test_autonomy_post_splits_clean_memory_and_tracks_plan_metrics(metrics):
    from autonomy import AutonomyEngine

    async def scenario():
        channel = Channel()
        bot = fake_bot(
            _control={"footer_format": "x" * 300}, get_channel=lambda cid: channel
        )
        engine = object.__new__(AutonomyEngine)
        engine.bot = bot
        engine._channel_allowed = lambda cid: True
        engine._guild_allowed = lambda gid: True
        engine._note_autonomy_post = lambda *args: None
        engine._remember_visible_self_message = AsyncMock()
        result = {}
        await engine._exec_post_channel(
            {"target_channel_id": "100", "content": "x" * 1900},
            result,
            response_metrics=metrics,
        )
        assert len(channel.sent) == 2
        assert all(len(sent.content) <= 2000 for sent in channel.sent)
        assert channel.sent[-1].content.endswith(FOOTER_MARKER)
        remembered = [
            call.args[2]
            for call in engine._remember_visible_self_message.call_args_list
        ]
        assert "".join(remembered) == "x" * 1900
        assert all(FOOTER_MARKER not in text for text in remembered)
        assert all(
            measured is metrics
            for measured in bot._delivery_measurements.records.values()
        )

    asyncio.run(scenario())


def test_autonomy_followup_slice_preserves_each_plan_call(metrics):
    from autonomy import AutonomyEngine
    from response_observability import MeasuredActions

    async def scenario():
        engine = object.__new__(AutonomyEngine)
        first = MeasuredActions([{"kind": "run_tool"}], metrics)
        second_metrics = replace(metrics, call_id="plan-two")
        second = MeasuredActions([{"kind": "post_channel"}], second_metrics)
        engine._should_call_planner = AsyncMock(return_value=True)
        engine.plan = AsyncMock(side_effect=[first, second])
        engine.policy_gate = AsyncMock(
            side_effect=lambda actions, channels: [
                SimpleNamespace(allowed=True) for action in actions
            ]
        )
        engine.run_allowed = AsyncMock(return_value=[{"result": "success"}])
        engine._tool_loop_feedback = lambda rows: (
            "continue" if engine.plan.await_count == 1 else ""
        )
        await engine._plan_execute_loop("context")
        calls = engine.run_allowed.call_args_list
        assert calls[0].kwargs["response_metrics"] is metrics
        assert calls[1].kwargs["response_metrics"] is second_metrics

    asyncio.run(scenario())


@pytest.mark.parametrize("has_metrics", [False, True])
def test_dispatch_overwrites_forged_metrics_without_polluting_tool_history(
    metrics, monkeypatch, has_metrics
):
    import bot as bot_module
    from bot import MaxwellBot

    trace = AsyncMock()
    monkeypatch.setattr(bot_module, "record_reasoning", trace)

    async def scenario():
        tool = SimpleNamespace(
            execute=AsyncMock(return_value="__MESSAGE_SENT__\\nanswer")
        )
        breaker = SimpleNamespace(
            is_open=lambda name: False, record_success=lambda name: None
        )
        bot = fake_bot(
            tools={"send_message": tool},
            _tool_breaker=breaker,
            _render_custom_emojis=lambda text, guild: text,
        )
        measured = metrics if has_metrics else None
        result = await MaxwellBot._execute_tool_by_name(
            bot,
            Message(),
            "send_message",
            {"content": "answer", "_response_metrics": {"call_id": "forged"}},
            disabled=set(),
            compatible={"send_message"},
            response_metrics=measured,
        )
        assert "__MESSAGE_SENT__" in result
        assert tool.execute.call_args.kwargs.get("_response_metrics") is measured
        assert "_response_metrics" not in trace.call_args.kwargs["params"]

    asyncio.run(scenario())


def test_self_memory_and_reply_quote_strip_footer_before_persistence(metrics):
    from bot import MaxwellBot

    message = Message(
        content="answer\n" + render_footer(DEFAULT_FOOTER_FORMAT, metrics, "Maxwell")
    )
    bot = fake_bot(_recent_users={}, _payload_attr_list=lambda *args: [])
    message.author.id = 42
    assert MaxwellBot._message_memory_content(bot, message) == "answer"
    child = Message(content="reply")
    child.reference = SimpleNamespace(resolved=message, message_id=message.id)
    assert (
        MaxwellBot._reply_meta_from_message(bot, child)["reply_to_content"] == "answer"
    )
    message.author.id = 7
    assert FOOTER_MARKER in MaxwellBot._message_memory_content(bot, message)


def test_version_without_git_is_honest_unknown(tmp_path):
    snapshot = capture_running_build(tmp_path)
    assert snapshot.commit == snapshot.branch == "unknown"
    assert snapshot.dirty is None
    assert snapshot.python.startswith("3.14")
