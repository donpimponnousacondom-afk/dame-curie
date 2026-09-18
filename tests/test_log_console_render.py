import json
from datetime import UTC, datetime

import pytest

from scripts.log_console.console import Console
from scripts.log_console.controls import ConsoleState, LEVELS, VERBOSITY_NOTE
from scripts.log_console.events import EventParser
from scripts.log_console.history import EventHistory
from scripts.log_console.input import KeyBuffer, LineBuffer
from scripts.log_console.paging import fit, page_text
from scripts.log_console.render import entry_evidence, inspector_text, render_frame
from scripts.log_console.scopes import SCOPE_KEYS


OBSERVED = datetime(2026, 9, 12, 12, 30, 45, tzinfo=UTC)
PROMPT = '夜空の竜 🐉 — café e\u0301 "glass" \\ moon\n' * 180 + "EXACT PROMPT TAIL\n"


def add(history, message, *, logger="bot", level="INFO", service="bot-1"):
    event = EventParser().parse(f"{service} | 2026-09-12 10:22:49,123 - {logger} - {level} - {message}\n", observed_at=OBSERVED)
    return history.append(event)


def screen(history, state, *, width=200, height=24):
    return "\n".join(line.text for line in render_frame(history, state, width, height, color=True))


@pytest.mark.parametrize("logger,service,scope", [
    ("jobs", "bot-1", "subagent"), ("discord.gateway", "bot-1", "discord"),
    ("providers", "bot-1", "provider"), ("bot_tools", "bot-1", "tool"),
    ("rag_memory", "bot-1", "context"), ("api.api_server", "api-1", "web"),
    ("docker_runtime", "bot-1", "system"), ("__main__", "bot-1", "bot"),
    ("unknown", "ollama-1", "provider"), ("unknown", "web-1", "web"),
])
def test_scope_recognition_uses_logger_or_service_metadata(logger, service, scope):
    history = EventHistory()
    entry = add(history, "synthetic diagnostic", logger=logger, service=service)
    assert entry.first.scope == scope


def test_worker_descendant_logs_are_not_guessed_from_prompt_or_body_words():
    history = EventHistory()
    entry = add(history, "background job subagent worker prompt words", logger="providers")
    assert entry.first.scope == "provider" and not entry.first.live_collapsed
    dispatched = add(history, "Executing tool hd_image", logger="__main__")
    assert dispatched.first.scope == "tool"


@pytest.mark.parametrize("folded", [True, False])
@pytest.mark.parametrize("tool_depth,provider_depth", [(0, 0), (1, 1), (2, 2)])
def test_live_agent_invariant_even_when_global_details_expand(folded, tool_depth, provider_depth):
    history = EventHistory()
    entry = add(history, "EXACT-AGENT-DETAIL " + PROMPT, logger="jobs")
    state = ConsoleState(folded=folded, tool_depth=tool_depth, provider_depth=provider_depth)
    assert entry.first.live_collapsed
    assert "EXACT-AGENT-DETAIL" not in screen(history, state)
    assert "always folded" in screen(history, state)
    state.key("r", history)
    assert "EXACT-AGENT-DETAIL" not in screen(history, state)
    state.key("\n", history)
    assert state.view == "evidence"
    assert "EXACT-AGENT-DETAIL " + PROMPT in entry_evidence(entry)
    assert "always folded" not in entry_evidence(entry)


def test_subagent_logger_scope_wins_over_image_shaped_body_recognition():
    history = EventHistory()
    entry = add(history, "Image request start " + json.dumps({"prompt": PROMPT}), logger="jobs")
    assert entry.first.kind == "image.request.start" and entry.first.scope == "subagent"
    assert entry.first.details["prompt"] == PROMPT
    assert "EXACT PROMPT TAIL" not in screen(history, ConsoleState(folded=False))
    assert PROMPT in entry_evidence(entry)


def test_enter_without_selected_history_does_not_expand_an_implicit_agent():
    history = EventHistory()
    add(history, "AGENT-PRIVATE-DETAIL", logger="jobs")
    state = ConsoleState()
    state.key("\n", history)
    assert state.view == "recent"
    assert "AGENT-PRIVATE-DETAIL" not in screen(history, state)
    state.key("\n", history)
    assert state.view == "evidence"
    assert "AGENT-PRIVATE-DETAIL" in screen(history, state, height=40)


def test_manual_paging_preserves_complete_exact_prompt_and_source_without_filter_clipping():
    history = EventHistory()
    entry = add(history, "Image request start " + json.dumps({"prompt": PROMPT, "request_id": "synthetic-id", "model": "fixture"}), logger="bot_tools")
    before = entry.records
    state = ConsoleState(enabled_scopes=set(), verbosity=4, folded=True, tool_depth=0)
    state.key("r", history)
    state.key("\n", history)
    text = entry_evidence(entry)
    first = page_text(text, 43, 7, 0)
    pages = [page_text(text, 43, 7, number) for number in range(first.count)]
    assert len(pages) > 10
    assert "".join(page.text for page in pages) == text
    assert PROMPT in text
    for _ in range(first.count + 5):
        state.key("n", history)
    render_frame(history, state, 43, 10, color=False)
    assert state.page == first.count - 1
    state.key("N", history)
    assert state.page == first.count - 2
    assert entry.records == before and entry.first.details["prompt"] == PROMPT


@pytest.mark.parametrize("text", ["", "a\n", "a\n\nb\n", "火🐉 e\u0301\tX\n" * 40])
def test_paging_is_a_lossless_partition_of_display_text(text):
    first = page_text(text, 9, 3, 0)
    assert "".join(page_text(text, 9, 3, number).text for number in range(first.count)) == text


def test_fit_reads_only_one_display_row_from_a_million_character_line():
    class BudgetText(str):
        def __iter__(self):
            for index, char in enumerate(str.__iter__(self)):
                assert index < 80, "fit scanned beyond the first row and its boundary character"
                yield char

    text = BudgetText("x" * 1_000_000)
    assert fit(text, 79) == "x" * 79
    assert len(text) == 1_000_000


@pytest.mark.parametrize("text,width", [
    ("", 0), ("abc\nrest", 20), ("abc\nrest", 3), ("\nrest", 2),
    ("火🐉suffix", 3), ("🐉suffix", 1), ("e\u0301tail", 1),
    ("a\tb", 8), ("\tx", 1), ("\u0301火suffix", 1),
])
def test_fit_preserves_the_full_pager_first_row_semantics(text, width):
    assert fit(text, width) == page_text(text, width, 1, 0).rows[0]


def test_every_live_event_has_a_timestamp_span_with_honest_source_facts():
    history = EventHistory()
    add(history, "warning", level="WARNING")
    history.append(EventParser().parse("ollama-1 | slot update_slots: ready\n", observed_at=OBSERVED))
    frame = render_frame(history, ConsoleState(), 200, 24, color=True)
    timestamped = [line for line in frame if line.timestamp]
    assert len(timestamped) == 2
    assert any(" O]" in line.text for line in timestamped)
    assert any(" P?]" in line.text for line in timestamped)
    assert all(line.text[:line.timestamp].startswith("[") for line in timestamped)
    assert "producer; TZ unspecified]" in entry_evidence(history.recent()[-1])


def test_eighty_column_live_rows_show_meaningful_event_tool_and_model_text():
    history = EventHistory()
    add(history, "Discord connection ready")
    entry = add(history, "Image request start " + json.dumps({
        "tool": "image_generator", "model": "gpt-image-2", "prompt": PROMPT,
        "request_id": "synthetic-1234567890-long-id", "endpoint": "http://fixture.invalid/v1/images",
    }), logger="bot_tools")
    displayed = screen(history, ConsoleState(), width=79)
    assert "Discord connection ready" in displayed
    assert "image_generator start model=gpt-image-2" in displayed
    assert "P?=TZ?" in displayed and "O=observed" in displayed
    assert "EXACT PROMPT TAIL" not in displayed
    assert "2026-09-12T10:22:49.123 producer; TZ unspecified" in entry_evidence(entry)
    assert entry.first.details["prompt"] == PROMPT


def test_terminal_control_evidence_is_neutralized_only_in_rendering():
    history = EventHistory()
    prompt = PROMPT + "\x1b]52;c;synthetic-clipboard\x07\x1b[2J\u202e\udc80"
    entry = add(history, "Image request start " + json.dumps({"prompt": prompt}), logger="bot_tools")
    displayed = entry_evidence(entry)
    assert "\x1b" not in displayed and "\x07" not in displayed and "\u202e" not in displayed
    assert "\\x1b]52" in displayed and "\\udc80" in displayed
    assert entry.first.details["prompt"] == prompt


def test_all_scope_toggles_depth_controls_verbosity_and_reset_are_local(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "info")
    history = EventHistory()
    original = add(history, "info record")
    state = ConsoleState()
    for key, scope in SCOPE_KEYS.items():
        state.key(key, history)
        assert scope not in state.enabled_scopes
        state.key(key, history)
        assert scope in state.enabled_scopes
    for _ in range(20):
        state.key("+", history)
    assert LEVELS[state.verbosity] == "DEBUG"
    for _ in range(20):
        state.key("-", history)
    assert LEVELS[state.verbosity] == "CRITICAL" and not state.visible(original.first)
    state.key("T", history)
    state.key("P", history)
    assert state.tool_depth == state.provider_depth == 0
    state.key("f", history)
    assert not state.folded
    state.key("0", history)
    assert state == ConsoleState()
    assert original.first.level == "INFO"
    assert "cannot create DEBUG" in VERBOSITY_NOTE


@pytest.mark.parametrize("logger,key", [("bot_tools", "T"), ("providers", "P")])
def test_tool_and_provider_depth_change_actual_live_detail_visibility(logger, key):
    history = EventHistory()
    add(history, "producer failed", logger=logger, level="ERROR")
    history.append(EventParser().parse("bot-1 |   DETAIL-EVIDENCE\n", observed_at=OBSERVED))
    state = ConsoleState(folded=False)
    state.key(key, history)
    assert "DETAIL-EVIDENCE" not in screen(history, state, height=70)
    state.key(key, history)
    assert "DETAIL-EVIDENCE" not in screen(history, state, height=70)
    state.key(key, history)
    assert "DETAIL-EVIDENCE" in screen(history, state, height=70)
    state.key("f", history)
    assert "DETAIL-EVIDENCE" not in screen(history, state, height=70)


def test_local_inspector_lists_only_allowlisted_console_metadata(monkeypatch):
    monkeypatch.setenv("API_KEY", "synthetic-environment-secret")
    history = EventHistory()
    add(history, "synthetic-private-prompt-not-for-inspector")
    state = ConsoleState()
    state.key("i", history)
    text = inspector_text(history, state, color=False)
    assert "LOCAL CONSOLE INSPECTOR" in text and "NOT a bot/container/runtime probe" in text
    assert "synthetic-environment-secret" not in text and "API_KEY" not in text
    assert "synthetic-private-prompt-not-for-inspector" not in text


def test_history_selection_is_stable_and_eviction_is_not_silently_replaced():
    history = EventHistory(max_events=2)
    oldest = add(history, "oldest")
    newest = add(history, "newest")
    state = ConsoleState()
    state.key("r", history)
    assert state.selected == newest.sequence
    state.key("[", history)
    assert state.selected == oldest.sequence
    state.key("\n", history)
    add(history, "replacement")
    assert state.selected == oldest.sequence
    assert "no longer retained" in screen(history, state)


def test_live_health_requests_stay_coalesced_but_history_keeps_every_record():
    console = Console()
    for second in (0, 10, 20):
        console.ingest(f'ollama-1 | [GIN] 2026/09/12 - 10:22:{second:02d} | 200 | 12µs | 127.0.0.1 | HEAD "/"\n', second)
    assert console.history.event_count == 3 and len(console.health.hidden) == 2
    before = console.frame(250, 24, color=False)
    assert sum(bool(line.timestamp) for line in before) == 1
    assert console.health.flush(30)
    after = "\n".join(line.text for line in console.frame(250, 24, color=False))
    assert "2 additional repeats" in after
    console.state.key("r", console.history)
    assert sum(bool(line.timestamp) for line in console.frame(250, 24, color=False)) == 3


def test_byte_line_buffer_handles_partial_utf8_and_bounds_oversized_input():
    buffer = LineBuffer(limit=12)
    assert list(buffer.feed(b"bot | \xe7")) == []
    assert list(buffer.feed(b"\x81\xab\n")) == ["bot | 火\n"]
    assert list(buffer.feed(b"x" * 13)) == [None]
    assert len(buffer.pending) == 0
    assert list(buffer.feed(b"x" * 1000)) == []
    assert list(buffer.feed(b"\nnext\n")) == ["next\n"]
    assert list(buffer.feed(b"tail\xff")) == []
    assert list(buffer.finish()) == ["tail\udcff"]


def test_input_overflow_is_a_local_omission_notice_not_a_fake_producer_record():
    console = Console()
    console.ingest(None, 0)
    entry = console.history.recent()[0]
    assert entry.first.kind == "console.omitted"
    assert entry.first.parse_error == "InputRecordTooLarge"
    assert entry.first.timestamp_origin == "observed" and entry.first.level is None
    assert "Docker logs" in entry.first.message


def test_escape_sequences_do_not_trigger_scope_or_history_keys():
    keys = KeyBuffer()
    assert keys.feed(b"\x1b", 0) == []
    assert keys.feed(b"[", 0.01) == []
    assert keys.feed(b"Aq", 0.02) == ["q"]
    assert keys.feed(b"\x1b[1;2aq", 0.03) == ["q"]
    assert keys.feed(b"\x1b", 1) == []
    assert keys.flush(1.2) == ["\x1b"]
