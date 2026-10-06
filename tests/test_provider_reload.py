"""Provider reload staging: dotenv resolution, idle gating, atomic swap, retirement.

Driven through the real ``provider_reload`` functions, the real ``MaxwellBot``
factory bound to a synthetic bot, and the ``FakeSession`` transport from
``tests/test_providers.py``. No network, no private file: every environment is
either an explicit mapping or a file under ``tmp_path``.
"""

import asyncio
import contextlib
import logging
import os
from types import MethodType, SimpleNamespace

import pytest

import job_routing
from bot import MaxwellBot
from config import Config
from jobs import BackgroundJobManager
from message_pipeline import ReplyQueue
from provider_reload import (
    ProviderReload,
    apply_provider_reload,
    close_retired_providers,
    provider_environment,
    provider_round,
    providers_idle,
    retire_provider,
)
from provider_settings import PROVIDER_FIELDS, parse_provider_settings
from providers import OpenAICompatibleProvider, track_provider_activity
from test_providers import FakeResponse, FakeSession

_BASE_ENV = {
    "OPENAI_BASE_URL": "https://primary.example.test/v1",
    "OPENAI_MODEL": "primary-model",
    "OPENAI_API_KEY": "synthetic-primary-key",
}
_SECRET_MARKER = "synthetic-secret-marker"
_ENDPOINT_MARKER = "edited.example.test"


# --- helpers --------------------------------------------------------------


def _settings(**overrides):
    """Baseline provider settings exactly as the parser produces them."""
    return parse_provider_settings({**_BASE_ENV, **overrides})


def _env_text(**pairs):
    """Render a dotenv body for the given keys."""
    return "".join(f"{key}={value}\n" for key, value in pairs.items())


def _baseline_text(**overrides):
    """Render the baseline environment as a dotenv body, with overrides applied."""
    return _env_text(**{**_BASE_ENV, **overrides})


def _run(coro):
    """Run one coroutine to completion on a private loop."""
    return asyncio.run(coro)


def _attach_transport(provider, response=None):
    """Give a provider an offline transport and skip the /models probe."""
    provider.available = True
    provider._session = FakeSession(response or FakeResponse())
    return provider


class _CloseableSession(FakeSession):
    """FakeSession plus the async close() that provider.close() awaits."""

    async def close(self):
        self.closed = True


class _ObservingSession(FakeSession):
    """Records the activity counter as seen from inside the transport call."""

    def __init__(self, provider, response=None):
        super().__init__(response)
        self.provider = provider
        self.observed = []

    def post(self, url, json=None, timeout=None, headers=None, allow_redirects=None):
        assert allow_redirects is False
        self.observed.append(self.provider.active_requests)
        return super().post(url, json=json, timeout=timeout, headers=headers, allow_redirects=allow_redirects)


class _ExplodingSession(FakeSession):
    """Transport that fails outright instead of returning an HTTP status."""

    def post(self, url, json=None, timeout=None, headers=None, allow_redirects=None):
        assert allow_redirects is False
        raise RuntimeError("synthetic transport failure")


class _Retiree:
    """Transport double for retirement bookkeeping."""

    def __init__(self, *, active: int = 0, cancel_on_close: bool = False):
        self.active_requests = active
        self.cancel_on_close = cancel_on_close
        self.closed = False

    async def close(self):
        if self.cancel_on_close:
            raise asyncio.CancelledError
        self.closed = True


class _JobStub:
    """Stands in for BackgroundJobManager; only the idle gate reads it."""

    def __init__(self, active: int = 0):
        self._active = active
        self._tasks: dict[str, object] = {}

    def active_count(self):
        return self._active


class _QueueStub:
    """Records the exclusion the idle gate forwards to the reply queue."""

    def __init__(self, *, active: bool = False):
        self._active = active
        self.exclusions = []

    def any_active(self, *, excluding=None):
        self.exclusions.append(excluding)
        return self._active


class _RacingPath:
    """A file that changes between the pre-read and post-read stat calls."""

    def __init__(self, text):
        self.text = text
        self.stats = 0

    def stat(self):
        self.stats += 1
        return SimpleNamespace(
            st_ino=1,
            st_mtime_ns=self.stats,
            st_ctime_ns=0,
            st_size=len(self.text),
        )

    def read_text(self, encoding="utf-8"):
        return self.text


def _make_bot(tmp_path, *, text=None, inherited=None, settings=None):
    """Build a synthetic MaxwellBot wired to the real factory and reload seams."""
    settings = dict(settings or _settings())
    bot = MaxwellBot.__new__(MaxwellBot)
    bot._control = {}
    config = Config()
    vars(config).update(settings)
    bot.config = config
    bot._ai_slots = SimpleNamespace(stats=lambda: {"active": 0, "waiting": 0})
    bot._active_requests = {}
    bot._vc_active_tasks = {}
    bot._context_tasks = set()
    bot._inflight_context = {}
    bot._replying_channels = set()
    bot._reply_queue = ReplyQueue()
    bot.bg_jobs = _JobStub()
    bot._rem_running = False
    bot.autonomy_engine = SimpleNamespace(_tick_in_flight=False)
    bot.autonomy_provider = None
    bot.aux_provider = None
    bot._autonomy_provider_sig = ""
    bot._aux_provider_sig = ""
    bot._retired_providers = []
    bot._provider_rounds_active = 0
    path = tmp_path / "bot.env"
    path.write_text(text if text is not None else _baseline_text(), encoding="utf-8")
    bot._provider_reload = ProviderReload(path, inherited or {}, settings)
    bot._create_main_provider = MethodType(MaxwellBot._create_main_provider, bot)
    bot.ai_slot_stats = MethodType(MaxwellBot.ai_slot_stats, bot)
    bot.ai_provider = _attach_transport(bot._create_main_provider(bot.config))
    return bot


def _reload(tmp_path, *, text=None, inherited=None, settings=None):
    """Build a ProviderReload over a synthetic dotenv file."""
    settings = dict(settings or _settings())
    path = tmp_path / "bot.env"
    path.write_text(text if text is not None else _baseline_text(), encoding="utf-8")
    return ProviderReload(path, inherited or {}, settings)


# --- dotenv resolution ----------------------------------------------------


def test_environment_keeps_inherited_values_for_absent_keys():
    environment = provider_environment("", {"OPENAI_MODEL": "inherited-model"})
    assert environment["OPENAI_MODEL"] == "inherited-model"


def test_environment_blank_key_beats_the_inherited_value():
    environment = provider_environment(
        "OPENAI_MODEL=\n", {"OPENAI_MODEL": "inherited-model"}
    )
    assert environment["OPENAI_MODEL"] == ""


def test_environment_bare_key_leaves_the_inherited_value_alone():
    environment = provider_environment(
        "OPENAI_MODEL\n", {"OPENAI_MODEL": "inherited-model"}
    )
    assert environment["OPENAI_MODEL"] == "inherited-model"


def test_environment_deleted_provider_key_falls_back_to_the_inherited_baseline():
    inherited = {
        "OPENAI_MODEL": "baseline-model",
        "OPENAI_BASE_URL": "https://baseline.example.test/v1",
    }
    text = _env_text(OPENAI_BASE_URL=f"https://{_ENDPOINT_MARKER}/v1")
    environment = provider_environment(text, inherited)
    assert environment["OPENAI_MODEL"] == "baseline-model"
    assert environment["OPENAI_BASE_URL"] == f"https://{_ENDPOINT_MARKER}/v1"


def test_environment_interpolates_against_the_inherited_baseline():
    text = "OPENAI_BASE_URL=${SHARED_BASE_URL}\n"
    environment = provider_environment(
        text, {"SHARED_BASE_URL": "https://inherited.example.test/v1"}
    )
    assert environment["OPENAI_BASE_URL"] == "https://inherited.example.test/v1"


def test_environment_interpolates_against_earlier_keys_in_the_same_file():
    text = (
        "SHARED_BASE_URL=https://file.example.test\n"
        "OPENAI_BASE_URL=${SHARED_BASE_URL}/v1\n"
    )
    environment = provider_environment(text, {})
    assert environment["OPENAI_BASE_URL"] == "https://file.example.test/v1"


def test_environment_ignores_a_contaminated_process_environment(monkeypatch):
    """Only the captured pre-load baseline may feed interpolation."""
    monkeypatch.setenv("OPENAI_MODEL", "contaminated-model")
    environment = provider_environment(
        "OPENAI_MODEL=${OPENAI_MODEL}\n", {"OPENAI_MODEL": "baseline-model"}
    )
    assert environment["OPENAI_MODEL"] == "baseline-model"


def test_environment_does_not_mutate_the_process_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "baseline-model")
    before = dict(os.environ)
    provider_environment(
        _env_text(OPENAI_MODEL="edited-model"), {"OPENAI_MODEL": "baseline-model"}
    )
    assert dict(os.environ) == before


def test_environment_passes_unrelated_keys_through_untouched():
    inherited = {
        "DISCORD_TOKEN": "synthetic-token-never-used",
        "DATA_DIR": "/synthetic/data",
        "ENABLE_RAG": "true",
    }
    environment = provider_environment(
        _env_text(OPENAI_MODEL="edited-model"), inherited
    )
    assert environment["DISCORD_TOKEN"] == "synthetic-token-never-used"
    assert environment["DATA_DIR"] == "/synthetic/data"
    assert environment["ENABLE_RAG"] == "true"


def test_environment_rejects_invalid_syntax():
    with pytest.raises(ValueError):
        provider_environment("'unterminated\n", {})


# --- staging --------------------------------------------------------------


def test_poll_reports_unchanged_when_the_file_matches_the_applied_settings(tmp_path):
    reload = _reload(tmp_path)
    assert reload.poll() is None
    assert reload.status == "unchanged"
    assert reload.generation == 1


def test_poll_stages_a_valid_edit_without_applying_it(tmp_path):
    reload = _reload(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    pending = reload.poll()
    assert pending is not None
    assert pending["OPENAI_MODEL"] == "edited-model"
    assert reload.status == "pending idle"
    assert reload.generation == 1
    assert reload.applied["OPENAI_MODEL"] == "primary-model"


@pytest.mark.parametrize(
    "text",
    [
        _baseline_text(OPENAI_EXTRA_BODY='{"broken": '),
        _baseline_text(OPENAI_EXTRA_BODY='{"n": NaN}'),
        _baseline_text(OPENAI_EXTRA_HEADERS='{"X-Retries": 3}'),
        _baseline_text(OPENAI_BASE_URL="not-a-url"),
        _baseline_text(
            OPENAI_BASE_URL="https://primary.example.test:synthetic-secret-port/v1"
        ),
        _baseline_text(OPENAI_BASE_URL="https://primary.example.test:99999/v1"),
        _baseline_text(OPENAI_TEMPERATURE="nan"),
        "'unterminated\n",
    ],
)
def test_poll_rejects_an_unusable_file_and_keeps_the_applied_generation(tmp_path, text):
    reload = _reload(tmp_path, text=text)
    assert reload.poll() is None
    assert reload.status == "rejected"
    assert reload.generation == 1
    assert reload.applied == _settings()
    assert reload.pending is None


def test_a_rejected_port_edit_keeps_the_active_objects_and_logs_no_marker(
    tmp_path, caplog
):
    """A bad authority port fails closed without touching what is already running."""
    bot = _make_bot(
        tmp_path,
        text=_baseline_text(
            OPENAI_BASE_URL=(
                "https://synthetic-secret-marker:synthetic-secret-port/v1"
            )
        ),
    )
    config, provider = bot.config, bot.ai_provider
    with caplog.at_level(logging.WARNING):
        applied = apply_provider_reload(bot)
    assert applied is False
    assert bot.config is config
    assert bot.ai_provider is provider
    assert bot.config.OPENAI_BASE_URL == _BASE_ENV["OPENAI_BASE_URL"]
    assert bot._provider_reload.generation == 1
    assert bot._provider_reload.status == "rejected"
    assert "synthetic-secret-port" not in caplog.text
    assert "synthetic-secret-marker" not in caplog.text


def test_poll_reports_editing_when_the_file_changes_during_the_read(tmp_path):
    reload = _reload(tmp_path)
    reload.path = _RacingPath(_baseline_text(OPENAI_MODEL="edited-model"))
    assert reload.poll() is None
    assert reload.status == "editing"
    assert reload.pending is None
    assert reload.generation == 1


def test_poll_supersedes_an_earlier_pending_edit_with_newest(tmp_path):
    reload = _reload(tmp_path, text=_baseline_text(OPENAI_MODEL="first-model"))
    assert reload.poll()["OPENAI_MODEL"] == "first-model"
    reload.path.write_text(
        _baseline_text(OPENAI_MODEL="second-model"), encoding="utf-8"
    )
    newest = reload.poll()
    assert newest["OPENAI_MODEL"] == "second-model"
    assert reload.pending == newest
    assert reload.applied["OPENAI_MODEL"] == "primary-model"


def test_poll_recovers_after_a_rejected_edit(tmp_path):
    reload = _reload(tmp_path, text=_baseline_text(OPENAI_EXTRA_BODY='{"broken": '))
    assert reload.poll() is None
    assert reload.status == "rejected"
    reload.path.write_text(
        _baseline_text(OPENAI_MODEL="recovered-model"), encoding="utf-8"
    )
    pending = reload.poll()
    assert pending["OPENAI_MODEL"] == "recovered-model"
    assert reload.status == "pending idle"


def test_poll_no_longer_holds_a_pending_edit_once_it_is_reverted(tmp_path):
    reload = _reload(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    assert reload.poll() is not None
    reload.path.write_text(_baseline_text(), encoding="utf-8")
    assert reload.poll() is None
    assert reload.status == "unchanged"


def test_rejected_edit_logs_the_error_type_and_never_a_value(tmp_path, caplog):
    reload = _reload(
        tmp_path,
        text=_baseline_text(
            OPENAI_API_KEY=_SECRET_MARKER, OPENAI_EXTRA_BODY='{"broken": '
        ),
    )
    with caplog.at_level(logging.WARNING):
        reload.poll()
    assert reload.status == "rejected"
    assert "ValueError" in caplog.text
    assert _SECRET_MARKER not in caplog.text
    assert _ENDPOINT_MARKER not in caplog.text


def test_describe_exposes_only_the_generation_and_status(tmp_path):
    reload = _reload(
        tmp_path,
        text=_baseline_text(
            OPENAI_API_KEY=_SECRET_MARKER, OPENAI_MODEL="edited-model"
        ),
    )
    reload.poll()
    text = reload.describe()
    assert "generation: 1" in text
    assert "pending idle" in text
    assert _SECRET_MARKER not in text
    assert "edited-model" not in text


def test_accept_advances_the_generation_and_clears_the_pending_edit(tmp_path):
    reload = _reload(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    pending = reload.poll()
    reload.accept(pending)
    assert reload.generation == 2
    assert reload.pending is None
    assert reload.status == "applied"
    assert reload.applied == pending


def test_accept_logs_changed_field_names_but_never_their_values(tmp_path, caplog):
    reload = _reload(
        tmp_path,
        text=_baseline_text(
            OPENAI_MODEL="edited-model", OPENAI_API_KEY=_SECRET_MARKER
        ),
    )
    pending = reload.poll()
    with caplog.at_level(logging.INFO):
        reload.accept(pending)
    assert "OPENAI_MODEL" in caplog.text
    assert "OPENAI_API_KEY" in caplog.text
    assert _SECRET_MARKER not in caplog.text
    assert "edited-model" not in caplog.text


# --- idle gating ----------------------------------------------------------


def _foreground_turn(bot, task):
    """A turn is in flight, possibly in the gap between two tool calls."""
    bot._replying_channels.add("channel")


def _inflight_context(bot, task):
    bot._inflight_context["message"] = {}


def _reply_queue_active(bot, task):
    bot._reply_queue = _QueueStub(active=True)


def _ai_slot_active(bot, task):
    bot._ai_slots = SimpleNamespace(stats=lambda: {"active": 1, "waiting": 0})


def _ai_slot_waiting(bot, task):
    bot._ai_slots = SimpleNamespace(stats=lambda: {"active": 0, "waiting": 1})


def _background_job(bot, task):
    bot.bg_jobs = _JobStub(active=1)


def _rem_running(bot, task):
    bot._rem_running = True


def _autonomy_tick(bot, task):
    bot.autonomy_engine._tick_in_flight = True


def _context_task(bot, task):
    bot._context_tasks.add(task)


def _voice_task(bot, task):
    bot._vc_active_tasks[1] = task


def _foreground_request(bot, task):
    bot._active_requests["channel"] = task


def _main_provider_activity(bot, task):
    bot.ai_provider.active_requests = 1


def _autonomy_provider_activity(bot, task):
    bot.autonomy_provider = bot._create_main_provider(bot.config)
    bot.autonomy_provider.active_requests = 1


def _aux_provider_activity(bot, task):
    bot.aux_provider = bot._create_main_provider(bot.config)
    bot.aux_provider.active_requests = 1


def _provider_round_active(bot, task):
    bot._provider_rounds_active = 1


def _job_worker(bot, task):
    bot.bg_jobs._tasks["job"] = task


def _retired_activity(bot, task):
    bot._retired_providers.append(_Retiree(active=1))


_BUSY_CASES = {
    "foreground_turn": _foreground_turn,
    "inflight_context": _inflight_context,
    "reply_queue_active": _reply_queue_active,
    "ai_slot_active": _ai_slot_active,
    "ai_slot_waiting": _ai_slot_waiting,
    "background_job": _background_job,
    "rem_running": _rem_running,
    "autonomy_tick": _autonomy_tick,
    "context_task": _context_task,
    "voice_task": _voice_task,
    "foreground_request": _foreground_request,
    "main_provider_activity": _main_provider_activity,
    "autonomy_provider_activity": _autonomy_provider_activity,
    "aux_provider_activity": _aux_provider_activity,
    "provider_round_active": _provider_round_active,
    "job_worker": _job_worker,
    "retired_activity": _retired_activity,
}


def test_idle_when_everything_is_quiet(tmp_path):
    assert providers_idle(_make_bot(tmp_path)) is True


@pytest.mark.parametrize("name", sorted(_BUSY_CASES))
def test_not_idle_while_work_is_outstanding(tmp_path, name):
    async def scenario():
        bot = _make_bot(tmp_path)
        task = asyncio.ensure_future(asyncio.sleep(30))
        _BUSY_CASES[name](bot, task)
        try:
            return providers_idle(bot)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    assert _run(scenario()) is False


def test_idle_ignores_the_callers_own_task_but_not_other_tasks(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        task = asyncio.ensure_future(asyncio.sleep(30))
        bot._active_requests["channel"] = task
        bot._context_tasks.add(task)
        try:
            return providers_idle(bot, excluding=task), providers_idle(bot)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    excluded, included = _run(scenario())
    assert excluded is True
    assert included is False


def test_idle_ignores_tasks_that_already_finished(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        finished = asyncio.ensure_future(asyncio.sleep(0))
        await finished
        bot._active_requests["channel"] = finished
        bot._vc_active_tasks[1] = finished
        bot._context_tasks.add(finished)
        return providers_idle(bot)

    assert _run(scenario()) is True


def test_idle_forwards_the_exclusion_to_the_reply_queue(tmp_path):
    bot = _make_bot(tmp_path)
    queue = _QueueStub(active=False)
    bot._reply_queue = queue
    sentinel = object()
    assert providers_idle(bot, excluding=sentinel) is True
    assert queue.exclusions == [sentinel]


def test_idle_tolerates_absent_role_providers(tmp_path):
    bot = _make_bot(tmp_path)
    bot.autonomy_provider = None
    bot.aux_provider = None
    assert providers_idle(bot) is True


# --- applying -------------------------------------------------------------


def test_apply_returns_false_when_nothing_is_pending(tmp_path):
    bot = _make_bot(tmp_path)
    assert apply_provider_reload(bot) is False
    assert bot._provider_reload.status == "unchanged"


def test_apply_leaves_everything_alone_while_a_turn_is_in_flight(tmp_path):
    """The whole-turn gate is what keeps a mid-gap edit from swapping clients."""
    bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    config, provider = bot.config, bot.ai_provider
    bot._replying_channels.add("channel")
    assert apply_provider_reload(bot) is False
    assert bot.config is config
    assert bot.config.OPENAI_MODEL == "primary-model"
    assert bot.ai_provider is provider
    assert bot._provider_reload.generation == 1
    assert bot._provider_reload.status == "pending idle"


def test_apply_mutates_the_same_config_instance_in_place(tmp_path):
    bot = _make_bot(
        tmp_path,
        text=_baseline_text(OPENAI_MODEL="edited-model", OPENAI_TEMPERATURE="0.25"),
    )
    config, provider = bot.config, bot.ai_provider
    assert apply_provider_reload(bot) is True
    assert bot.config is config
    assert bot.config.OPENAI_MODEL == "edited-model"
    assert bot.config.OPENAI_TEMPERATURE == 0.25
    assert bot.ai_provider is not provider
    assert bot._provider_reload.generation == 2
    assert bot._provider_reload.status == "applied"


def test_apply_builds_the_new_provider_from_the_edited_settings(tmp_path):
    bot = _make_bot(
        tmp_path,
        text=_baseline_text(
            OPENAI_MODEL="edited-model",
            OPENAI_BASE_URL=f"https://{_ENDPOINT_MARKER}/v1",
            OPENAI_API_KEY="synthetic-edited-key",
            OPENAI_EXTRA_BODY='{"marker": "edited-body"}',
        ),
    )
    assert apply_provider_reload(bot) is True
    provider = bot.ai_provider
    assert provider.model == "edited-model"
    assert provider.base_url == f"https://{_ENDPOINT_MARKER}/v1"
    assert provider.api_key == "synthetic-edited-key"
    assert provider.extra_body == {"marker": "edited-body"}
    assert provider._headers(provider._endpoints[0]) == {
        "Authorization": "Bearer synthetic-edited-key"
    }


@pytest.mark.parametrize("field,value", [
    ("OPENAI_TEMPERATURE", "0.6"), ("OPENAI_TOP_P", "0.95"),
    ("OPENAI_TOP_K", "20"), ("OPENAI_MAX_TOKENS", "64000"),
])
def test_apply_retires_the_old_providers_on_a_sampling_only_change(tmp_path, field, value):
    bot = _make_bot(
        tmp_path, settings=_settings(**{field: value}),
        text=_baseline_text() + f"# {field}={value}\n",
    )
    assert _run(bot.ai_provider.generate_response([])) == "ok"
    parameter = field.removeprefix("OPENAI_").lower()
    assert parameter in bot.ai_provider._session.payloads[0]
    bot.autonomy_provider = bot._create_main_provider(bot.config)
    bot.aux_provider = bot._create_main_provider(bot.config)
    bot._autonomy_provider_sig = "stale-autonomy-signature"
    bot._aux_provider_sig = "stale-aux-signature"
    old = (bot.ai_provider, bot.autonomy_provider, bot.aux_provider)
    assert apply_provider_reload(bot) is True
    assert bot.autonomy_provider is None
    assert bot.aux_provider is None
    assert bot._autonomy_provider_sig == ""
    assert bot._aux_provider_sig == ""
    assert all(item in bot._retired_providers for item in old)
    provider = _attach_transport(bot.ai_provider)
    assert _run(provider.generate_response([])) == "ok"
    assert parameter not in provider._session.payloads[0]
    assert getattr(bot.config, field) is None


def test_apply_touches_only_the_provider_field_surface(tmp_path):
    """Nothing outside PROVIDER_FIELDS may be rewritten by a reload."""
    bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    before = {
        "DISCORD_TOKEN": bot.config.DISCORD_TOKEN,
        "DATA_DIR": bot.config.DATA_DIR,
        "ENABLE_RAG": bot.config.ENABLE_RAG,
        "LOGS_DIR": bot.config.LOGS_DIR,
    }
    assert apply_provider_reload(bot) is True
    assert set(vars(bot.config)) == set(PROVIDER_FIELDS)
    for field, value in before.items():
        assert getattr(bot.config, field) == value


def test_apply_keeps_the_active_configuration_when_construction_fails(
    tmp_path, monkeypatch
):
    bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    config, provider = bot.config, bot.ai_provider

    def refuse(candidate):
        raise ValueError("OPENAI_MODEL")

    monkeypatch.setattr(bot, "_create_main_provider", refuse)
    assert apply_provider_reload(bot) is False
    assert bot.config is config
    assert bot.config.OPENAI_MODEL == "primary-model"
    assert bot.ai_provider is provider
    assert bot._provider_reload.generation == 1
    assert bot._provider_reload.status == "rejected"
    assert bot._provider_reload.pending is None


def test_apply_uses_the_newest_pending_edit(tmp_path):
    bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="first-model"))
    assert bot._provider_reload.poll()["OPENAI_MODEL"] == "first-model"
    bot._provider_reload.path.write_text(
        _baseline_text(OPENAI_MODEL="second-model"), encoding="utf-8"
    )
    assert apply_provider_reload(bot) is True
    assert bot.config.OPENAI_MODEL == "second-model"
    assert bot.ai_provider.model == "second-model"


def test_apply_forwards_the_exclusion_to_the_idle_check(tmp_path):
    bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
    queue = _QueueStub(active=False)
    bot._reply_queue = queue
    sentinel = object()
    assert apply_provider_reload(bot, excluding=sentinel) is True
    assert queue.exclusions == [sentinel]


# --- requests across the swap --------------------------------------------


def test_a_request_after_the_swap_uses_the_edited_transport(tmp_path):
    bot = _make_bot(
        tmp_path,
        text=_baseline_text(
            OPENAI_MODEL="edited-model",
            OPENAI_BASE_URL=f"https://{_ENDPOINT_MARKER}/v1",
            OPENAI_API_KEY="synthetic-edited-key",
            OPENAI_EXTRA_BODY='{"marker": "edited-body"}',
        ),
    )
    assert apply_provider_reload(bot) is True
    provider = bot.ai_provider
    session = _ObservingSession(provider, FakeResponse())
    provider.available = True
    provider._session = session
    result = _run(provider.generate_response([{"role": "user", "content": "x"}]))
    assert result == "ok"
    assert session.urls == [f"https://{_ENDPOINT_MARKER}/v1/chat/completions"]
    assert session.payloads[0]["model"] == "edited-model"
    assert session.payloads[0]["marker"] == "edited-body"
    assert session.observed and all(count > 0 for count in session.observed)
    assert provider.active_requests == 0


def test_the_retired_provider_still_answers_with_its_old_settings(tmp_path):
    bot = _make_bot(
        tmp_path,
        text=_baseline_text(
            OPENAI_MODEL="edited-model",
            OPENAI_BASE_URL=f"https://{_ENDPOINT_MARKER}/v1",
        ),
    )
    stale = bot.ai_provider
    assert apply_provider_reload(bot) is True
    session = _ObservingSession(stale, FakeResponse())
    stale.available = True
    stale._session = session
    result = _run(stale.generate_response([{"role": "user", "content": "x"}]))
    assert result == "ok"
    assert session.urls == ["https://primary.example.test/v1/chat/completions"]
    assert session.payloads[0]["model"] == "primary-model"
    assert stale.model == "primary-model"
    assert stale.base_url == "https://primary.example.test/v1"


# --- retirement -----------------------------------------------------------


def test_retired_transport_with_activity_is_kept_until_it_finishes(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree(active=1)
        bot._retired_providers.append(retiree)
        await close_retired_providers(bot)
        return bot, retiree

    bot, retiree = _run(scenario())
    assert retiree.closed is False
    assert bot._retired_providers == [retiree]


def test_idle_retired_transport_is_closed_and_untracked(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree()
        bot._retired_providers.append(retiree)
        await close_retired_providers(bot)
        return bot, retiree

    bot, retiree = _run(scenario())
    assert retiree.closed is True
    assert bot._retired_providers == []


def test_shutdown_closes_even_an_active_retired_transport(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree(active=1)
        bot._retired_providers.append(retiree)
        await close_retired_providers(bot, shutdown=True)
        return bot, retiree

    bot, retiree = _run(scenario())
    assert retiree.closed is True
    assert bot._retired_providers == []


def test_a_cancelled_close_leaves_the_transport_tracked(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree(cancel_on_close=True)
        bot._retired_providers.append(retiree)
        with pytest.raises(asyncio.CancelledError):
            await close_retired_providers(bot)
        return bot, retiree

    bot, retiree = _run(scenario())
    assert retiree.closed is False
    assert bot._retired_providers == [retiree]


def test_a_real_retired_transport_is_closed_and_untracked(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        provider = OpenAICompatibleProvider(
            "https://retired.example.test/v1", "retired-model", 8192, 0.6
        )
        provider.available = True
        provider._session = _CloseableSession()
        bot._retired_providers.append(provider)
        await close_retired_providers(bot)
        return bot, provider

    bot, provider = _run(scenario())
    assert provider._session.closed is True
    assert bot._retired_providers == []


def test_close_retired_tolerates_a_bot_without_retired_transports(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        del bot._retired_providers
        await close_retired_providers(bot)

    _run(scenario())


# --- activity tracking ----------------------------------------------------


def test_activity_counter_is_held_during_a_real_request_and_cleared_after():
    provider = OpenAICompatibleProvider(
        "https://activity.example.test/v1", "activity-model", 8192, 0.6,
        retry_attempts=1,
    )
    provider.available = True
    session = _ObservingSession(provider, FakeResponse())
    provider._session = session
    assert provider.active_requests == 0
    result = _run(provider.generate_response([{"role": "user", "content": "x"}]))
    assert result == "ok"
    assert session.observed and all(count > 0 for count in session.observed)
    assert provider.active_requests == 0


def test_activity_counter_is_cleared_after_a_failed_request():
    provider = OpenAICompatibleProvider(
        "https://activity.example.test/v1", "activity-model", 8192, 0.6,
        retry_attempts=1,
    )
    provider.available = True
    provider._session = _ExplodingSession()

    async def scenario():
        try:
            await provider.generate_response([{"role": "user", "content": "x"}])
        except RuntimeError:
            return True
        return False

    assert _run(scenario()) is True
    assert provider.active_requests == 0


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
def test_activity_counter_is_cleared_for_every_outcome(outcome):
    provider = SimpleNamespace(active_requests=0)
    observed = []

    @track_provider_activity
    async def operation(target):
        observed.append(target.active_requests)
        if outcome == "error":
            raise RuntimeError("synthetic failure")
        if outcome == "cancel":
            raise asyncio.CancelledError

    async def scenario():
        if outcome == "success":
            await operation(provider)
        else:
            expected = RuntimeError if outcome == "error" else asyncio.CancelledError
            with pytest.raises(expected):
                await operation(provider)

    _run(scenario())
    assert observed == [1]
    assert provider.active_requests == 0


# --- whole-round tracking -------------------------------------------------


def test_provider_round_counts_nesting_and_restores_on_exit(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        seen = []
        async with provider_round(bot):
            seen.append(bot._provider_rounds_active)
            async with provider_round(bot):
                seen.append(bot._provider_rounds_active)
            seen.append(bot._provider_rounds_active)
        seen.append(bot._provider_rounds_active)
        return seen

    assert _run(scenario()) == [1, 2, 1, 0]


def test_provider_round_restores_the_counter_when_the_body_raises(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        with pytest.raises(RuntimeError):
            async with provider_round(bot):
                raise RuntimeError("synthetic round failure")
        return bot._provider_rounds_active

    assert _run(scenario()) == 0


def test_provider_round_restores_the_counter_when_the_body_is_cancelled(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        entered = asyncio.Event()

        async def maintenance():
            async with provider_round(bot):
                entered.set()
                await asyncio.sleep(30)

        task = asyncio.ensure_future(maintenance())
        await entered.wait()
        inside = bot._provider_rounds_active
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return inside, bot._provider_rounds_active

    inside, after = _run(scenario())
    assert inside == 1
    assert after == 0


def test_not_idle_while_a_provider_round_is_open(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        async with provider_round(bot):
            return providers_idle(bot), bot._provider_rounds_active

    idle, rounds = _run(scenario())
    assert rounds == 1
    assert idle is False


def test_an_open_round_blocks_a_reload_between_maintenance_calls(tmp_path):
    """A round spans the gaps between calls, which is where a swap would split state."""

    async def scenario():
        bot = _make_bot(tmp_path, text=_baseline_text(OPENAI_MODEL="edited-model"))
        async with provider_round(bot):
            during = apply_provider_reload(bot)
        after = apply_provider_reload(bot)
        return during, after, bot.config.OPENAI_MODEL

    during, after, model = _run(scenario())
    assert during is False
    assert after is True
    assert model == "edited-model"


# --- retirement registry --------------------------------------------------


def test_retire_provider_deduplicates_by_identity(tmp_path):
    bot = _make_bot(tmp_path)
    provider = bot.ai_provider
    retire_provider(bot, provider)
    retire_provider(bot, provider)
    assert bot._retired_providers == [provider]


def test_retire_provider_keeps_distinct_transports(tmp_path):
    bot = _make_bot(tmp_path)
    first = bot.ai_provider
    second = bot._create_main_provider(bot.config)
    retire_provider(bot, first)
    retire_provider(bot, second)
    assert bot._retired_providers == [first, second]


def test_retire_provider_creates_the_registry_when_absent(tmp_path):
    bot = _make_bot(tmp_path)
    provider = bot.ai_provider
    del bot._retired_providers
    retire_provider(bot, provider)
    assert bot._retired_providers == [provider]


def test_not_idle_while_a_retired_transport_is_still_answering(tmp_path):
    bot = _make_bot(tmp_path)
    bot._retired_providers.append(_Retiree(active=1))
    assert providers_idle(bot) is False


def test_close_retired_waits_for_global_idle_not_just_client_activity(tmp_path):
    """An idle client is not enough: the whole round must have finished too."""

    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree()
        bot._retired_providers.append(retiree)
        async with provider_round(bot):
            await close_retired_providers(bot)
            during = (retiree.closed, list(bot._retired_providers))
        await close_retired_providers(bot)
        return retiree, during, retiree.closed, list(bot._retired_providers)

    retiree, during, closed, remaining = _run(scenario())
    assert during == (False, [retiree])
    assert closed is True
    assert remaining == []


def test_close_retired_shutdown_forces_close_during_an_open_round(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        retiree = _Retiree()
        bot._retired_providers.append(retiree)
        async with provider_round(bot):
            await close_retired_providers(bot, shutdown=True)
        return retiree.closed, list(bot._retired_providers)

    closed, remaining = _run(scenario())
    assert closed is True
    assert remaining == []


# --- role client lifecycle ------------------------------------------------


def test_concurrent_role_initialization_shares_one_cached_client(tmp_path, monkeypatch):
    """The getter publishes the client before awaiting init, so callers share it."""

    async def scenario():
        bot = _make_bot(tmp_path)
        bot.config.AUTONOMY_MODEL = "autonomy-model"
        started = asyncio.Event()
        release = asyncio.Event()
        initialized = []

        async def slow_initialize(self):
            initialized.append(self)
            started.set()
            await release.wait()
            self.available = True
            return True

        monkeypatch.setattr(OpenAICompatibleProvider, "initialize", slow_initialize)
        first = asyncio.ensure_future(bot._get_autonomy_provider())
        await started.wait()
        second = asyncio.ensure_future(bot._get_autonomy_provider())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release.set()
        resolved = await asyncio.gather(first, second)
        return (
            resolved,
            initialized,
            bot.autonomy_provider,
            list(bot._retired_providers),
        )

    resolved, initialized, cached, retired = _run(scenario())
    assert resolved[0] is resolved[1]
    assert cached is resolved[0]
    assert len(initialized) == 2
    assert len({id(client) for client in initialized}) == 1
    assert retired == []


def test_autonomy_construction_failure_keeps_the_previous_client(tmp_path, monkeypatch):
    async def scenario():
        bot = _make_bot(tmp_path)
        bot.config.AUTONOMY_MODEL = "autonomy-model"
        bot.autonomy_provider = bot._create_main_provider(bot.config)
        bot._autonomy_provider_sig = "existing-autonomy-signature"

        def explode(*args, **kwargs):
            raise TypeError("synthetic constructor failure")

        monkeypatch.setattr(job_routing, "OpenAICompatibleProvider", explode)
        with pytest.raises(TypeError, match="synthetic constructor failure"):
            await bot._get_autonomy_provider()
        resolved = None
        return (
            resolved,
            bot.ai_provider,
            bot.autonomy_provider,
            bot._autonomy_provider_sig,
            list(bot._retired_providers),
        )

    resolved, main, cached, sig, retired = _run(scenario())
    assert resolved is None
    assert cached is not None and cached is not main
    assert sig == "existing-autonomy-signature"
    assert retired == []


def test_aux_construction_failure_keeps_the_previous_client(tmp_path, monkeypatch):
    async def scenario():
        bot = _make_bot(tmp_path)
        bot.config.AUX_MODEL = "aux-model"
        bot.aux_provider = bot._create_main_provider(bot.config)
        bot._aux_provider_sig = "existing-aux-signature"

        def explode(*args, **kwargs):
            raise TypeError("synthetic constructor failure")

        monkeypatch.setattr(job_routing, "OpenAICompatibleProvider", explode)
        with pytest.raises(TypeError, match="synthetic constructor failure"):
            await bot._get_aux_provider()
        resolved = None
        return (
            resolved,
            bot.ai_provider,
            bot.aux_provider,
            bot._aux_provider_sig,
            list(bot._retired_providers),
        )

    resolved, main, cached, sig, retired = _run(scenario())
    assert resolved is None
    assert cached is not None and cached is not main
    assert sig == "existing-aux-signature"
    assert retired == []


# --- job worker visibility ------------------------------------------------


def test_not_idle_while_a_finished_job_still_owes_its_final_delivery(tmp_path):
    """active_count() is already zero while the worker is still delivering."""

    async def scenario():
        bot = _make_bot(tmp_path)
        delivering = asyncio.Event()
        release = asyncio.Event()

        async def worker():
            delivering.set()
            await release.wait()

        task = asyncio.ensure_future(worker())
        bot.bg_jobs._tasks["job"] = task
        await delivering.wait()
        active = bot.bg_jobs.active_count()
        busy = providers_idle(bot)
        release.set()
        await task
        return active, busy, providers_idle(bot)

    active, busy, after = _run(scenario())
    assert active == 0
    assert busy is False
    assert after is True


def test_not_idle_while_a_cancelled_job_worker_is_still_unwinding(tmp_path):
    async def scenario():
        bot = _make_bot(tmp_path)
        started = asyncio.Event()
        unwinding = asyncio.Event()
        release = asyncio.Event()

        async def worker():
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                unwinding.set()
                await release.wait()
                raise

        task = asyncio.ensure_future(worker())
        bot.bg_jobs._tasks["job"] = task
        await started.wait()
        task.cancel()
        await unwinding.wait()
        busy = providers_idle(bot)
        release.set()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return busy, task.done(), providers_idle(bot)

    busy, done, after = _run(scenario())
    assert busy is False
    assert done is True
    assert after is True


def test_job_manager_keeps_a_worker_registered_until_it_exits(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(str(tmp_path / "background_jobs.json"))
        release = asyncio.Event()

        async def worker():
            await release.wait()

        task = asyncio.ensure_future(worker())
        manager.track_task("job", task)
        registered = sorted(manager._tasks)
        release.set()
        await task
        await asyncio.sleep(0)
        return registered, sorted(manager._tasks)

    registered, remaining = _run(scenario())
    assert registered == ["job"]
    assert remaining == []


def test_job_manager_cleanup_runtime_leaves_the_worker_registration(tmp_path):
    manager = BackgroundJobManager(str(tmp_path / "background_jobs.json"))
    manager.attach_runtime("job", message=object())
    manager._tasks["job"] = object()
    manager.cleanup_runtime("job")
    assert manager.runtime("job") == {}
    assert sorted(manager._tasks) == ["job"]


def test_job_manager_close_cancels_and_gathers_workers(tmp_path):
    async def scenario():
        manager = BackgroundJobManager(str(tmp_path / "background_jobs.json"))
        started = asyncio.Event()
        finished = []

        async def worker():
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                finished.append("cancelled")
                raise

        task = asyncio.ensure_future(worker())
        manager.track_task("job", task)
        await started.wait()
        await manager.close()
        return finished, task.done(), sorted(manager._tasks)

    finished, done, remaining = _run(scenario())
    assert finished == ["cancelled"]
    assert done is True
    assert remaining == []
