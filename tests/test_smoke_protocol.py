"""Synthetic CLI and protocol checks for smoke runtime-health semantics."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.dirac_smoke import main
from smoke_protocol import (
    SmokeProtocolError,
    SmokeSettings,
    build_request,
    create_json_exclusive,
    read_json_object,
    request_path,
    runtime_state_path,
    write_json_atomic,
)


def _settings(tmp_path: Path) -> SmokeSettings:
    """Build a disposable CLI layout without reading runtime configuration."""
    root = tmp_path / "smoke"
    requests = root / "requests"
    status = tmp_path / "smoke-status"
    requests.mkdir(parents=True)
    status.mkdir()
    config = {
        "enabled": True,
        "channel_id": 4242,
        "operator_id": 1482143139828596916,
        "requests_dir": "requests",
        "status_dir": "../smoke-status",
    }
    path = root / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return SmokeSettings.load(path)


def test_runtime_health_uses_a_non_record_filename(tmp_path):
    settings = _settings(tmp_path)
    state = runtime_state_path(settings)

    assert state.name == "runtime-state"
    assert state not in settings.status_dir.glob("*.json")


def test_missing_result_and_unavailable_health_are_unknown(tmp_path, capsys, monkeypatch):
    settings = _settings(tmp_path)
    request = build_request(request_id="a" * 32, task="synthetic")
    create_json_exclusive(request_path(settings, request.request_id), request.as_json())
    settings.status_dir.rmdir()

    assert main(["--config", str(settings.config_path), "result", request.request_id]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "request_id": request.request_id,
        "status": "pending",
        "acceptance": "no_record",
        "worker_liveness": "unknown",
    }

    assert main(["--config", str(settings.config_path), "pending"]) == 0
    pending = json.loads(capsys.readouterr().out)
    assert pending[0]["request_id"] == request.request_id
    assert pending[0]["acceptance"] == "no_record"
    assert pending[0]["worker_liveness"] == "unknown"

    withdrawn = request_path(settings, request.request_id)
    withdrawn.unlink()
    monkeypatch.setattr("scripts.dirac_smoke.request_files", Mock(return_value=[withdrawn]))
    assert main(["--config", str(settings.config_path), "pending"]) == 0
    assert json.loads(capsys.readouterr().out) == []

    assert main(["--config", str(settings.config_path), "health"]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health == {"worker_liveness": "unknown", "last_observed": None}


def test_non_utf8_health_snapshot_is_unavailable(tmp_path, capsys):
    settings = _settings(tmp_path)
    runtime_state_path(settings).write_bytes(b"\xff")

    assert main(["--config", str(settings.config_path), "health"]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health == {"worker_liveness": "unknown", "last_observed": None}


def test_non_object_diagnostic_does_not_include_the_path(tmp_path):
    path = tmp_path / "synthetic-private-config.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(SmokeProtocolError) as error:
        read_json_object(path, "config")

    assert str(path) not in str(error.value)
    assert str(error.value) == "config is not a JSON object"


def test_health_snapshot_reports_only_last_observed_failure(tmp_path, capsys):
    settings = _settings(tmp_path)
    write_json_atomic(
        runtime_state_path(settings),
        {
            "status": "failed",
            "observed_at": "synthetic-stale-time",
            "failure_type": "OSError",
        },
    )

    assert main(["--config", str(settings.config_path), "health"]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["worker_liveness"] == "unknown"
    assert health["last_observed"] == {
        "status": "failed",
        "observed_at": "synthetic-stale-time",
        "failure_type": "OSError",
    }
