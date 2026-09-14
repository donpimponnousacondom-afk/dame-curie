from pathlib import Path
from types import SimpleNamespace

import pytest

import response_observability as observability


@pytest.fixture
def image_metadata(monkeypatch):
    values = {
        "COMMIT": "a" * 40,
        "BRANCH": "deployment/build",
        "DATE": "2026-09-09T01:30:00+02:00",
        "SUBJECT": "Preserve image provenance",
        "DIRTY": "false",
    }
    for field, value in values.items():
        monkeypatch.setenv(f"MAXWELL_BUILD_{field}", value)
    return values


@pytest.mark.parametrize("dirty", ["true", "false", "unknown"])
def test_image_metadata_is_never_reported_as_checkout_state(
    image_metadata, monkeypatch, tmp_path, dirty
):
    monkeypatch.setenv("MAXWELL_BUILD_DIRTY", dirty)
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("invoked git in source-only image"),
    )
    snapshot = observability.capture_running_build(tmp_path)
    report = snapshot.format()
    assert snapshot.commit == snapshot.branch == snapshot.subject == snapshot.date == "unknown"
    assert snapshot.dirty is None
    assert "Checkout at boot:" in report
    assert image_metadata["COMMIT"] not in report
    assert snapshot.started_at.endswith("+00:00")
    monkeypatch.setenv("MAXWELL_BUILD_COMMIT", "b" * 40)
    assert snapshot.format() == report


def test_source_checkout_git_takes_precedence_over_image_metadata(
    image_metadata, monkeypatch, tmp_path
):
    (tmp_path / ".git").mkdir()
    outputs = iter(
        ["b" * 40 + "\n2026-09-09T12:00:00Z\nLocal source\n", "local-branch\n", ""]
    )
    monkeypatch.setattr(observability.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=next(outputs)),
    )
    snapshot = observability.capture_running_build(tmp_path)
    assert snapshot.commit == "b" * 40
    assert snapshot.branch == "local-branch"
    assert snapshot.subject == "Local source"
    assert snapshot.dirty is False


def test_unspecified_container_build_metadata_stays_unknown(monkeypatch, tmp_path):
    for field in ("COMMIT", "BRANCH", "DATE", "SUBJECT", "DIRTY"):
        monkeypatch.setenv(f"MAXWELL_BUILD_{field}", "unknown")
    snapshot = observability.capture_running_build(Path(tmp_path))
    assert (
        snapshot.commit
        == snapshot.branch
        == snapshot.date
        == snapshot.subject
        == "unknown"
    )
    assert snapshot.dirty is None
