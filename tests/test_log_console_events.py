import io
import json
from datetime import UTC, datetime

import pytest

import error_reporting
from scripts.log_console.events import EventParser
from scripts.log_console.jsonl import write_jsonl
from scripts.log_console.recognizers import RECOGNIZERS, Recognition
from scripts.log_console.safety import terminal_text


OBSERVED = datetime(2026, 9, 12, 12, 30, 45, tzinfo=UTC)
PROMPT = '夜空の竜 🐉 — café e\u0301 "glass" \\ moon\n' * 180 + "EXACT PROMPT TAIL\n"


def image_line(phase, fields):
    return "bot-1 | 2026-09-12 10:22:49,123 - bot_tools - INFO - Image request " + phase + " " + json.dumps(fields, ensure_ascii=False) + "\n"


@pytest.mark.parametrize("protocol", ["images", "chat_completions", "pollinations"])
def test_full_image_prompt_and_correlated_details_survive_jsonl(protocol):
    fields = {
        "request_id": "synthetic-request-1", "tool": "hd_image", "model": "synthetic-model",
        "endpoint": "https://image.example.invalid/v1/images/generations", "protocol": protocol,
    }
    sent = PROMPT[:1500] if protocol == "pollinations" else PROMPT
    start = fields | {"prompt": sent}
    if protocol == "pollinations":
        start["requested_prompt"] = PROMPT
    lines = [image_line("start", start), image_line("done", fields | {"outcome": "success", "status": 200})]
    before = lines.copy()
    output = io.StringIO()
    write_jsonl(lines, output, clock=lambda: OBSERVED)
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert lines == before
    assert [record["kind"] for record in records] == ["image.request.start", "image.request.done"]
    assert records[0]["details"]["prompt"] == sent
    if protocol == "pollinations":
        assert records[0]["details"]["requested_prompt"] == PROMPT
    for record, phase in zip(records, ("start", "done")):
        assert record["schema_version"] == 1
        assert record["scope"] == "tool"
        assert record["details"]["request_id"] == fields["request_id"]
        assert record["details"]["model"] == fields["model"]
        assert record["details"]["endpoint"] == fields["endpoint"]
        assert json.loads(record["source_line"].split(f"Image request {phase} ", 1)[1]) == record["details"]
        assert json.loads(record["message"].split(f"Image request {phase} ", 1)[1]) == record["details"]


@pytest.mark.parametrize("line,source,normalized,zone,logger,level", [
    ("bot-1 | 2026-09-12 10:22:49,123 - bot - WARNING - message\n", "2026-09-12 10:22:49,123", "2026-09-12T10:22:49.123", "unspecified", "bot", "WARNING"),
    ("bot-1 | 2026-09-12T10:22:49.123+02:30 - bot - DEBUG - message\n", "2026-09-12T10:22:49.123+02:30", "2026-09-12T10:22:49.123+02:30", "+02:30", "bot", "DEBUG"),
    ("bot-1 | 2026-09-12 10:22:49,123-0430 - bot - INFO - message\n", "2026-09-12 10:22:49,123-0430", "2026-09-12T10:22:49.123-04:30", "-0430", "bot", "INFO"),
    ("ollama-1 | time=2026-09-12T10:22:49.123Z level=INFO source=runner.go msg=ready\n", "2026-09-12T10:22:49.123Z", "2026-09-12T10:22:49.123Z", "UTC", None, "INFO"),
    ("ollama-1 | time=2026-09-12T10:22:49.123456789+01:00 level=INFO source=runner.go msg=ready\n", "2026-09-12T10:22:49.123456789+01:00", "2026-09-12T10:22:49.123456789+01:00", "+01:00", None, "INFO"),
    ('ollama-1 | [GIN] 2026/09/12 - 10:22:49 | 200 | 12µs | 127.0.0.1 | HEAD "/"\n', "2026/09/12 - 10:22:49", "2026-09-12T10:22:49", "unspecified", "gin", None),
])
def test_producer_timestamp_is_iso_shaped_without_rewriting_source_or_timezone(line, source, normalized, zone, logger, level):
    event = EventParser().parse(line, observed_at=OBSERVED)
    assert event.timestamp == normalized
    assert json.loads(event.json_line())["timestamp"] == normalized
    assert event.source_timestamp == source
    assert event.source_timezone == zone
    assert (datetime.fromisoformat(event.timestamp).tzinfo is None) == (zone == "unspecified")
    assert event.timestamp_origin == "producer"
    assert event.observed_at == OBSERVED.isoformat()
    assert event.logger == logger and event.level == level
    assert event.source_line == line.rstrip("\n")


@pytest.mark.parametrize("line", [
    "ollama-1 | slot update_slots: id 0 | task 5 | prompt done\n",
    "bot-1 | Traceback (most recent call last):\n", "bot-1 |   File /synthetic/tool.py, line 9\n",
    "unknown final line", "\n",
])
def test_undated_lines_use_explicit_observed_time_without_invented_level(line):
    event = EventParser().parse(line, observed_at=OBSERVED)
    assert event.timestamp == event.observed_at == OBSERVED.isoformat()
    assert event.timestamp_origin == "observed"
    assert event.source_timestamp is None and event.source_timezone is None
    assert event.level is None
    assert event.source_line == line.rstrip("\n")


def test_basic_python_logging_retains_level_without_manufacturing_producer_time():
    event = EventParser().parse("api-1 | ERROR:api.api_server:synthetic failure\n", observed_at=OBSERVED)
    assert event.logger == "api.api_server" and event.level == "ERROR"
    assert event.timestamp_origin == "observed" and event.message == "synthetic failure"


def test_docker_timestamp_remains_distinct_from_producer_and_observation():
    docker = "2026-09-12T10:22:49.123456789Z"
    parser = EventParser()
    slot = parser.parse(f"ollama-1 | {docker} slot update_slots: ready\n", observed_at=OBSERVED)
    assert slot.timestamp == slot.docker_timestamp == docker
    assert slot.timestamp_origin == "docker"
    assert slot.source_timestamp is None and slot.source_timezone is None
    dated = parser.parse(f"bot-1 | {docker} 2026-09-12 10:22:48,999 - bot - INFO - ready\n", observed_at=OBSERVED)
    assert dated.timestamp_origin == "producer"
    assert dated.timestamp == "2026-09-12T10:22:48.999"
    assert datetime.fromisoformat(dated.timestamp).tzinfo is None
    assert dated.source_timestamp == "2026-09-12 10:22:48,999"
    assert dated.docker_timestamp == docker and dated.source_timezone == "unspecified"


@pytest.mark.parametrize("payload", ['{"prompt": "unfinished', '[]', 'null', '42'])
def test_malformed_or_wrong_shape_image_record_falls_back_without_dropping_text(payload):
    line = "bot-1 | Image request start " + payload + "\n"
    event = EventParser().parse(line, observed_at=OBSERVED)
    assert event.kind == "image.request.unparsed" and event.details == {}
    assert event.parse_error is not None
    assert event.source_line == line.rstrip("\n")


def test_jsonl_does_not_coalesce_health_or_drop_interleaved_traceback_lines():
    health = 'ollama-1 | [GIN] 2026/09/12 - 10:22:49 | 200 | 12µs | 127.0.0.1 | HEAD "/"\n'
    lines = [health, health, "bot-1 | Traceback (most recent call last):\n", health]
    output = io.StringIO()
    write_jsonl(lines, output, clock=lambda: OBSERVED)
    assert [json.loads(line)["source_line"] for line in output.getvalue().splitlines()] == [line.rstrip("\n") for line in lines]
    assert "additional repeats" not in output.getvalue()


def test_registry_hook_marks_subagent_scope_without_inventing_native_events():
    def synthetic_scope(envelope, service):
        assert service == "bot-1"
        return Recognition("fixture.only", "subagent", {"exact": envelope.message})

    line = "bot-1 | synthetic registry extension\n"
    ordinary = EventParser().parse(line, observed_at=OBSERVED)
    scoped = EventParser(recognizers=(synthetic_scope, *RECOGNIZERS)).parse(line, observed_at=OBSERVED)
    assert ordinary.kind == "text" and not ordinary.live_collapsed
    assert scoped.scope == "subagent" and scoped.live_collapsed
    assert scoped.details["exact"] == "synthetic registry extension"


def test_jsonl_redacts_registered_secrets_auth_fields_and_config_without_clipping(monkeypatch):
    monkeypatch.setattr(error_reporting, "_secrets", ())
    secret = "synthetic-only-credential-abc"
    error_reporting.register_secrets([secret])
    fields = {
        "prompt": PROMPT + f"{secret}\nAuthorization: Bearer synthetic-auth\nCookie: session=synthetic-cookie\nretained tail",
        "model": "synthetic-model", "request_id": "synthetic-id",
        "headers": ["synthetic-header-array"], "Config": {"Env": ["SOMETHING=synthetic-env-array"]},
        "nested": {"api_key": "synthetic-nested-key", "useful": "keep diagnostic"},
    }
    line = image_line("start", fields)
    event = EventParser().parse(line, observed_at=OBSERVED)
    encoded = event.json_line()
    for value in (secret, "synthetic-auth", "synthetic-cookie", "synthetic-header-array", "synthetic-env-array", "synthetic-nested-key"):
        assert value not in encoded
    assert secret in line
    assert event.details["prompt"] == PROMPT + "[REDACTED]\nAuthorization: [REDACTED]\nCookie: [REDACTED]\nretained tail"
    assert event.details["nested"]["useful"] == "keep diagnostic"


@pytest.mark.parametrize("message", [
    'server config env="map[OPAQUE:synthetic-config-secret]"',
    '{"Config":{"Env":["OPAQUE=synthetic-config-secret"]},"useful":"kept"}',
    'Authorization: Bearer synthetic-config-secret',
    'https://user:synthetic-config-secret@example.invalid/path?token=synthetic-config-secret',
])
def test_generic_diagnostics_do_not_emit_auth_or_configuration_arrays(message):
    event = EventParser().parse("ollama-1 | " + message + "\n", observed_at=OBSERVED)
    assert "synthetic-config-secret" not in event.json_line()


def test_multiline_private_key_and_config_blocks_are_redacted_per_service():
    lines = [
        "bot-1 | -----BEGIN PRIVATE KEY-----\n", "bot-1 | synthetic-key-body\n",
        "api-1 | independent ready\n", "bot-1 | -----END PRIVATE KEY-----\n",
        'bot-1 | "Config": {\n', 'bot-1 | "Env": [\n', 'bot-1 | "OPAQUE=synthetic-config-secret"\n',
        "bot-1 | ]\n", "bot-1 | }\n", "bot-1 | resumed ready\n",
    ]
    output = io.StringIO()
    write_jsonl(lines, output, clock=lambda: OBSERVED)
    value = output.getvalue()
    assert "synthetic-key-body" not in value and "synthetic-config-secret" not in value
    assert "independent ready" in value and "resumed ready" in value
    assert len(value.splitlines()) == len(lines)


def test_untrusted_terminal_controls_are_encoded_without_losing_prompt_evidence():
    prompt = PROMPT + "\x1b]52;c;synthetic-clipboard\x07\x1b[2J\r\b\x9b31m\u202e\udc80"
    line = image_line("start", {"prompt": prompt, "model": "synthetic"})
    event = EventParser().parse(line, observed_at=OBSERVED)
    encoded = event.json_line()
    assert json.loads(encoded)["details"]["prompt"] == prompt
    assert all(ord(char) >= 32 or char == "\n" for char in encoded)
    assert "\x1b" not in encoded and "\x9b" not in encoded and "\u202e" not in encoded
    displayed = terminal_text(event.details["prompt"])
    assert displayed.startswith(PROMPT)
    assert "\\x1b]52" in displayed and "\\x9b31m" in displayed and "\\u202e" in displayed
    assert "\x1b" not in displayed and "\r" not in displayed and "\b" not in displayed


def test_nonfinite_untrusted_json_numbers_do_not_break_the_jsonl_stream():
    output = io.StringIO()
    write_jsonl(['bot-1 | Image request done {"elapsed_ms": NaN}\n', "bot-1 | next\n"], output, clock=lambda: OBSERVED)
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert records[0]["details"]["elapsed_ms"] == "nan"
    assert records[1]["message"] == "next"
