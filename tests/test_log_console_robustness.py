import io
import json
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

import error_reporting
from scripts.log_console import events
from scripts.log_console.events import EventParser
from scripts.log_console.jsonl import write_jsonl


OBSERVED = datetime(2026, 9, 12, 12, 30, 45, tzinfo=UTC)
PROMPT = '夜空の竜 🐉 "glass" \\ moon\n' * 100 + "EXACT PROMPT TAIL"


def image_line(payload):
    return "bot-1 | 2026-09-12 10:22:49,123 - bot_tools - INFO - Image request start " + payload + "\n"


@pytest.mark.parametrize("payload,error", [
    ('{"nested":' + '[' * 5000 + '0' + ']' * 5000 + '}', "RecursionError"),
    ('{"nested":' + '[' * 5000 + '0' + ']' * 4999 + '}', "JSONDecodeError"),
    ('{"number":' + '9' * 10000 + '}', "ValueError"),
    ('{"prompt":"unfinished', "JSONDecodeError"),
], ids=["deep-valid", "deep-malformed", "integer-digit-limit", "unfinished-string"])
@pytest.mark.parametrize("image", [False, True], ids=["generic", "image"])
def test_failed_json_ingestion_retains_safe_fallback_and_next_event(payload, error, image):
    first = image_line(payload) if image else "bot-1 | " + payload + "\n"
    lines = [first, "bot-1 | next event\n"]
    output = io.StringIO()
    write_jsonl(lines, output, clock=lambda: OBSERVED)
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(records) == 2
    assert records[0]["parse_error"] == error
    assert records[0]["details"] == {}
    assert records[0]["kind"] in {"unparsed", "image.request.unparsed"}
    assert records[0]["source_line"] == first.rstrip("\n")
    assert records[1]["message"] == "next event" and records[1]["parse_error"] is None


@pytest.mark.parametrize("key", [r"\u0061pi_key", r"\u0045nv", r"\u0041uthorization"])
def test_deep_fallback_does_not_leak_json_escaped_auth_or_config_keys(key):
    payload = '{"' + key + '": ["synthetic-secret-not-for-console"], "nested":' + '[' * 5000 + '0' + ']' * 5000 + '}'
    output = io.StringIO()
    write_jsonl([image_line(payload), "bot-1 | next event\n"], output, clock=lambda: OBSERVED)
    encoded = output.getvalue()
    assert "synthetic-secret-not-for-console" not in encoded
    records = [json.loads(line) for line in encoded.splitlines()]
    assert records[0]["parse_error"] == "RecursionError"
    assert "[REDACTED]" in records[0]["source_line"]
    assert records[1]["message"] == "next event"


def test_deep_fallback_decodes_string_escapes_before_shared_credential_redaction(monkeypatch):
    monkeypatch.setattr(error_reporting, "_secrets", ())
    error_reporting.register_secrets(["synthetic-火-credential"])
    prompt = PROMPT + "\nsynthetic-火-credential\nAuthorization: Bearer synthetic-header-secret\nretained final line"
    payload = '{"prompt":' + json.dumps(prompt) + ',"nested":' + '[' * 5000 + '0' + ']' * 5000 + '}'
    event = EventParser().parse(image_line(payload), observed_at=OBSERVED)
    encoded = event.json_line()
    assert "synthetic-header-secret" not in encoded
    assert "synthetic-火-credential" not in event.source_line
    assert r"synthetic-\u706b-credential" not in event.source_line
    assert event.parse_error == "RecursionError"
    prompt_evidence = event.message.split(',"nested":', 1)[0].removeprefix("Image request start ") + "}"
    assert json.loads(prompt_evidence)["prompt"] == PROMPT + "\n[REDACTED]\nAuthorization: [REDACTED]\nretained final line"


def test_recursive_redaction_failure_is_visible_without_clipping_source(monkeypatch):
    monkeypatch.setattr(events, "safe_fields", Mock(side_effect=RecursionError("synthetic recursion failure")))
    line = image_line(json.dumps({"prompt": PROMPT, "request_id": "synthetic-id"}))
    event = EventParser().parse(line, observed_at=OBSERVED)
    assert event.parse_error == "RecursionError" and event.details == {}
    assert event.kind == "unparsed" and event.scope == "tool"
    assert event.source_line == line.rstrip("\n")
    assert "synthetic recursion failure" not in event.json_line()


@pytest.mark.parametrize("failure", [RecursionError, ValueError])
def test_final_serialization_failure_does_not_stop_jsonl(monkeypatch, failure):
    original = json.dumps

    def fail_final_fields(value, **kwargs):
        if isinstance(value, dict) and "schema_version" in value and value.get("details"):
            raise failure("synthetic encoding failure")
        return original(value, **kwargs)

    line = image_line(json.dumps({"prompt": PROMPT}))
    monkeypatch.setattr(events.json, "dumps", fail_final_fields)
    output = io.StringIO()
    write_jsonl([line, "bot-1 | next event\n"], output, clock=lambda: OBSERVED)
    first, second = [json.loads(line) for line in output.getvalue().splitlines()]
    assert first["parse_error"] == failure.__name__ and first["kind"] == "unparsed"
    assert first["details"] == {}
    assert json.loads(first["message"].removeprefix("Image request start "))["prompt"] == PROMPT
    assert second["message"] == "next event" and second["parse_error"] is None


def test_actual_deep_detail_serialization_preserves_supported_nested_data():
    event = EventParser().parse(image_line(json.dumps({"prompt": PROMPT})), observed_at=OBSERVED)
    nested = []
    for _ in range(5000):
        nested = [nested]
    output = json.loads(replace(event, details={"nested": nested}).json_line())
    assert output["parse_error"] is None
    assert output["kind"] == event.kind
    restored = output["details"]["nested"]
    for _ in range(5000):
        assert isinstance(restored, list) and len(restored) == 1
        restored = restored[0]
    assert restored == []
    assert output["source_line"] == event.source_line
    assert output["message"] == event.message


def test_supported_nested_payload_stays_parsed_and_unmodified():
    nested = {"prompt": PROMPT}
    for _ in range(40):
        nested = {"child": nested}
    event = EventParser().parse(image_line(json.dumps(nested)), observed_at=OBSERVED)
    assert event.parse_error is None
    assert json.loads(event.json_line())["details"] == nested
