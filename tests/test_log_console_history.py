import io
import json
from datetime import UTC, datetime

import pytest

from scripts.log_console.events import EventParser
from scripts.log_console.history import EventHistory, NOT_RETAINED
from scripts.log_console.jsonl import write_jsonl
from scripts.log_console.recognizers import Recognition


OBSERVED = datetime(2026, 9, 12, 12, 30, 45, tzinfo=UTC)
PROMPT = '夜空の竜 🐉 "glass" \\ moon\n' * 100 + "EXACT PROMPT TAIL"


def event(message, *, service="bot-1", level=None):
    prefix = f"2026-09-12 10:22:49,123 - fixture - {level} - " if level else ""
    return EventParser().parse(f"{service} | {prefix}{message}\n", observed_at=OBSERVED)


def assert_bounds(history):
    assert history.event_count == sum(len(entry.records) for entry in history.entries.values())
    assert history.evidence_bytes == sum(entry.evidence_bytes for entry in history.entries.values())
    assert history.event_count <= history.max_events
    assert history.evidence_bytes <= history.max_evidence_bytes
    assert len(history.streams) <= history.max_events


def test_whole_image_prompt_is_retained_as_an_immutable_evidence_snapshot():
    original = event("Image request start " + json.dumps({"prompt": PROMPT, "request_id": "synthetic-id"}))
    history = EventHistory()
    admitted = history.append(original)
    assert admitted.first.details["prompt"] == PROMPT
    assert admitted.events[0].source_line == original.source_line
    assert admitted.omitted_events == 0
    assert admitted.evidence_bytes == len(original.json_line().encode("ascii"))
    original.details["prompt"] = "caller mutation must not rewrite history"
    admitted.first.details["prompt"] = "inspection mutation must not rewrite history"
    assert admitted.first.details["prompt"] == PROMPT
    assert_bounds(history)


def test_count_limit_evicts_whole_events_in_recent_order():
    history = EventHistory(max_events=2)
    first = history.append(event("one", level="INFO"))
    second = history.append(event("two", level="INFO"))
    third = history.append(event("three", level="INFO"))
    assert [entry.sequence for entry in history.recent()] == [third.sequence, second.sequence]
    assert first.sequence not in history.entries and history.evicted_entries == 1
    assert_bounds(history)


def test_byte_limit_uses_serialized_evidence_bytes_and_evicts_whole_unicode_events():
    first, second = event("first 火", level="INFO"), event("second 🐉", level="INFO")
    history = EventHistory(max_events=10, max_evidence_bytes=max(len(first.json_line()), len(second.json_line())))
    history.append(first)
    latest = history.append(second)
    assert history.recent() == (latest,)
    assert latest.first.message == second.message
    assert history.evicted_entries == 1
    assert_bounds(history)


def test_oversized_event_gets_explicit_marker_without_retaining_or_truncating_prompt():
    original = event("Image request start " + json.dumps({"prompt": PROMPT, "request_id": "synthetic-id"}))
    history = EventHistory(max_evidence_bytes=2048)
    marker = history.append(original)
    assert marker.omitted_events == history.omitted_events == 1
    assert marker.first.kind == "history.omitted"
    assert marker.first.message == marker.first.source_line == NOT_RETAINED
    assert "Docker logs" in marker.first.message
    assert marker.first.timestamp == original.timestamp
    assert marker.first.details["request_id"] == "synthetic-id"
    assert "prompt" not in marker.first.details and PROMPT not in "".join(marker.records)
    assert original.details["prompt"] == PROMPT
    assert history.recent() == (marker,)
    assert_bounds(history)


def test_unretainable_marker_does_not_evict_smaller_existing_evidence():
    small = event("x")
    history = EventHistory(max_evidence_bytes=len(small.json_line()))
    admitted = history.append(small)
    marker = history.append(event("too large " + PROMPT))
    assert marker.omitted_events == 1
    assert marker.sequence not in history.entries
    assert history.recent() == (admitted,)
    assert history.evicted_entries == 0
    assert_bounds(history)


def test_tiny_positive_budget_keeps_no_oversized_evidence_or_markers():
    history = EventHistory(max_events=1, max_evidence_bytes=1)
    marker = history.append(event(PROMPT))
    assert marker.omitted_events == 1 and NOT_RETAINED == marker.first.message
    assert history.recent() == () and history.event_count == history.evidence_bytes == 0
    assert_bounds(history)


def test_error_traceback_group_retains_interleaved_services_and_exception_chain():
    history = EventHistory()
    root = event("tool failed", level="ERROR")
    trace = [
        event("Traceback (most recent call last):"), event('  File "/synthetic/first.py", line 3'),
        event("    first()"), event("ValueError: first failure"), event(""),
        event("The above exception was the direct cause of the following exception:"), event(""),
        event("Traceback (most recent call last):"), event('  File "/synthetic/second.py", line 8'),
        event("    second()"), event("RuntimeError: second failure"),
    ]
    entry = history.append(root)
    for index, line in enumerate(trace):
        history.append(event(f"independent {index}", service="api-1", level="INFO"))
        updated = history.append(line)
        assert updated.sequence == entry.sequence
        assert_bounds(history)
    before_boundary = history.recent(errors_only=True)[0]
    assert before_boundary.boundary == "open"
    assert [item.source_line for item in before_boundary.events] == [root.source_line, *(item.source_line for item in trace)]
    assert all(item.service == "bot-1" for item in before_boundary.events)
    history.append(event("recovered", level="INFO"))
    closed = history.recent(errors_only=True)[0]
    assert closed.boundary == "next-record" and closed.partial_reason is None
    assert len(closed.events) == len(trace) + 1
    assert "RuntimeError: second failure" in closed.events[-1].message


def test_unparsed_undated_continuation_does_not_create_a_false_producer_boundary():
    history = EventHistory()
    original = history.append(event("failed", level="ERROR"))
    continuation = event("[unfinished diagnostic fragment")
    assert continuation.parse_error == "JSONDecodeError"
    grouped = history.append(continuation)
    assert grouped.sequence == original.sequence and grouped.boundary == "open"
    assert grouped.events[-1].source_line == continuation.source_line
    assert len(grouped.events) == 2


def test_concurrent_error_groups_are_kept_separate_by_service():
    history = EventHistory()
    bot = history.append(event("bot failed", level="ERROR"))
    api = history.append(event("api failed", service="api-1", level="ERROR"))
    history.append(event("Traceback (most recent call last):"))
    history.append(event("Traceback (most recent call last):", service="api-1"))
    history.append(event("BotFailure: final bot error"))
    history.append(event("ApiFailure: final api error", service="api-1"))
    errors = {entry.sequence: entry for entry in history.recent(errors_only=True)}
    assert errors[bot.sequence].events[-1].message == "BotFailure: final bot error"
    assert errors[api.sequence].events[-1].message == "ApiFailure: final api error"
    assert len(errors[bot.sequence].events) == len(errors[api.sequence].events) == 3
    assert_bounds(history)


@pytest.mark.parametrize("fragment", [
    "Traceback (most recent call last):", '  File "/synthetic/truncated.py", line 3',
    "  + Exception Group Traceback (most recent call last):",
    "During handling of the above exception, another exception occurred:",
])
def test_tail_starting_inside_traceback_is_explicitly_partial(fragment):
    history = EventHistory()
    partial = history.append(event(fragment))
    assert partial.is_error and partial.partial_reason is not None
    assert "no preceding retained producer" in partial.partial_reason
    history.append(event("Exception: retained tail"))
    history.finish()
    final = history.recent(errors_only=True)[0]
    assert final.boundary == "stream-ended"
    assert final.partial_reason == partial.partial_reason
    assert final.events[-1].message == "Exception: retained tail"


def test_stream_end_does_not_claim_an_open_traceback_is_complete():
    history = EventHistory()
    history.append(event("failed", level="ERROR"))
    history.append(event("Traceback (most recent call last):"))
    history.finish()
    entry = history.recent(errors_only=True)[0]
    assert entry.boundary == "stream-ended"
    assert entry.partial_reason == "stream ended before a following producer record"


def test_evicted_error_group_continuation_gets_partial_label_instead_of_false_full_trace():
    history = EventHistory(max_events=2)
    old = history.append(event("failed", level="ERROR"))
    history.append(event("api one", service="api-1", level="INFO"))
    history.append(event("api two", service="api-1", level="INFO"))
    assert old.sequence not in history.entries
    tail = history.append(event("Exception: retained continuation"))
    assert tail.is_error and tail.partial_reason == "preceding error lines are outside retained history"
    assert tail.sequence != old.sequence and len(tail.events) == 1
    assert_bounds(history)


@pytest.mark.parametrize("limit", ["count", "bytes"])
def test_over_budget_error_group_becomes_one_marker_not_a_clipped_trace(limit):
    root = event("failed", level="ERROR")
    history = EventHistory(max_events=2 if limit == "count" else 20, max_evidence_bytes=2048)
    original = history.append(root)
    history.append(event("Traceback (most recent call last):"))
    marker = history.append(event("    large frame " + PROMPT if limit == "bytes" else "Exception: final"))
    assert marker.sequence == original.sequence and marker.is_error
    assert marker.omitted_events == 3 and marker.first.kind == "history.omitted"
    assert len(marker.events) == 1 and "whole event/error group" in marker.partial_reason
    tail = history.append(event("second omitted continuation"))
    assert tail.omitted_events == history.omitted_events == 4
    assert len(tail.events) == 1 and "second omitted continuation" not in tail.first.source_line
    history.append(event("recovered", level="INFO"))
    assert history.recent(errors_only=True)[0].boundary == "next-record"
    assert_bounds(history)


def test_jsonl_remains_complete_when_display_history_rejects_oversized_event():
    line = "bot-1 | Image request start " + json.dumps({"prompt": PROMPT}) + "\n"
    history = EventHistory(max_evidence_bytes=1024)
    marker = history.append(EventParser().parse(line, observed_at=OBSERVED))
    output = io.StringIO()
    write_jsonl([line], output, clock=lambda: OBSERVED)
    assert marker.omitted_events == 1
    assert json.loads(output.getvalue())["details"]["prompt"] == PROMPT
    assert "history.omitted" not in output.getvalue()


def test_error_recognition_uses_record_metadata_not_prompt_error_words():
    history = EventHistory()
    history.append(event("Image request start " + json.dumps({"prompt": "Traceback (most recent call last): Error ERROR"})))
    history.append(event("Error: ordinary message quoted by a model", level="INFO"))
    history.append(event("Image request done " + json.dumps({"outcome": "cancelled"})))
    history.append(event("Image request done " + json.dumps({"outcome": ["error"]})))
    assert history.recent(errors_only=True) == ()
    failed = history.append(event("Image request done " + json.dumps({"outcome": "http_error", "status": 503})))
    assert history.recent(errors_only=True) == (failed,)


@pytest.mark.parametrize("status,is_error", [(200, False), (201, False), (400, True), (503, True)])
def test_gin_http_errors_are_available_without_inventing_log_levels(status, is_error):
    line = f'ollama-1 | [GIN] 2026/09/12 - 10:22:49 | {status} | 12µs | 127.0.0.1 | HEAD "/"\n'
    original = EventParser().parse(line, observed_at=OBSERVED)
    entry = EventHistory().append(original)
    assert entry.is_error is is_error
    assert entry.first.level is None
    assert entry.first.source_line == line.rstrip("\n")


def test_recognized_subagent_scope_survives_history_and_oversized_marker():
    def synthetic_scope(envelope, service):
        return Recognition("fixture.only", "subagent", {"prompt": envelope.message})

    parser = EventParser(recognizers=(synthetic_scope,))
    original = parser.parse("bot-1 | " + PROMPT, observed_at=OBSERVED)
    retained = EventHistory().append(original)
    omitted = EventHistory(max_evidence_bytes=2048).append(original)
    assert retained.first.live_collapsed and omitted.first.live_collapsed
    assert retained.first.details["prompt"] == PROMPT
    assert omitted.omitted_events == 1


def test_stream_context_count_is_bounded_along_with_history():
    history = EventHistory(max_events=3)
    for index in range(20):
        history.append(event("failed", service=f"service-{index}", level="ERROR"))
        assert_bounds(history)
    assert len(history.streams) == len(history.entries) == 3


@pytest.mark.parametrize("settings", [{"max_events": 0}, {"max_evidence_bytes": 0}])
def test_history_rejects_nonpositive_limits(settings):
    with pytest.raises(ValueError, match="positive"):
        EventHistory(**settings)
