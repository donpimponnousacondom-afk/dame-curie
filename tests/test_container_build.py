import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import response_observability as observability


MANIFEST = {
    "commit": "a" * 40,
    "branch": "deployment/build",
    "date": "2026-09-09T01:30:00+02:00",
    "subject": "Preserve image provenance",
    "dirty": False,
}


@pytest.mark.parametrize("commit", ["a" * 40, "unknown"])
def test_actual_dockerfile_manifest_recipe(tmp_path, commit):
    dockerfile = (Path(__file__).resolve().parents[1] / "docker/app.Dockerfile").read_text()
    recipe = dockerfile.split("RUN python -c '", 1)[1].split("'\nLABEL", 1)[0]
    destination = tmp_path / observability.MANIFEST_FILENAME
    recipe = recipe.replace('Path("/app/build_provenance.json")', f"Path({str(destination)!r})")
    recipe = recipe.replace("\\\n", "")
    manifest = {**MANIFEST, "commit": commit, "subject": 'Exact "quotes", back\\slash, café'}
    environment = {f"DAME_CURIE_BUILD_{key.upper()}": str(value) for key, value in manifest.items()}
    environment["DAME_CURIE_BUILD_DIRTY"] = "false"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", recipe],
        env=environment, capture_output=True, text=True, check=False,
    )
    if commit == "unknown":
        assert result.returncode != 0
        assert not destination.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(destination.read_text()) == manifest
        assert observability.capture_running_build(tmp_path).subject == manifest["subject"]


@pytest.fixture
def manifest_root(monkeypatch, tmp_path):
    """A source root whose image manifest is where the running image puts it."""
    (tmp_path / observability.MANIFEST_FILENAME).write_text(
        json.dumps(MANIFEST), encoding="utf-8"
    )
    monkeypatch.delenv("DAME_CURIE_STARTUP_GIT_SOCKET", raising=False)
    return tmp_path


def test_baked_manifest_reports_the_running_image(manifest_root, monkeypatch):
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("queried Git despite a baked manifest"),
    )
    snapshot = observability.capture_running_build(manifest_root)
    assert snapshot.commit == MANIFEST["commit"]
    assert snapshot.branch == MANIFEST["branch"]
    assert snapshot.subject == MANIFEST["subject"]
    assert snapshot.date == "2026-09-08T23:30:00+00:00"
    assert snapshot.dirty is False
    assert snapshot.provenance == observability.PROVENANCE_IMAGE
    report = snapshot.format()
    assert "Provenance: image" in report
    assert "Source: image build manifest" in report
    assert f"Commit: {'a' * 12} ({'a' * 40})" in report
    assert f"Commit date: {snapshot.date}" in report
    assert "Subject: Preserve image provenance" in report
    assert "Branch: deployment/build | dirty: no" in report
    assert snapshot.started_at.endswith("+00:00")
    assert snapshot.python.startswith("3.14")


@pytest.mark.parametrize(
    "subject",
    [
        'fix: handle "quoted" and back\\slash paths',
        "fix: preserve\ttabs and \\u escapes",
        "emoji \U0001f680 and accents \u00e9\u00e8",
    ],
)
def test_manifest_reports_the_commit_subject_exactly(
    manifest_root, monkeypatch, subject
):
    manifest = manifest_root / observability.MANIFEST_FILENAME
    manifest.write_text(json.dumps({**MANIFEST, "subject": subject}), encoding="utf-8")
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("queried Git despite a baked manifest"),
    )
    snapshot = observability.capture_running_build(manifest_root)
    assert snapshot.subject == subject
    assert f"Subject: {subject}" in snapshot.format()


def test_manifest_snapshot_is_frozen_after_manifest_and_env_changes(manifest_root):
    snapshot = observability.capture_running_build(manifest_root)
    report = snapshot.format()
    manifest = manifest_root / observability.MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({**MANIFEST, "commit": "c" * 40, "dirty": True}), encoding="utf-8"
    )
    assert snapshot.format() == report
    assert "c" * 40 not in report


@pytest.mark.parametrize(
    "field,value",
    [
        ("COMMIT", "b" * 40),
        ("BRANCH", "spoofed"),
        ("DATE", "2026-09-09T01:30:00+02:00"),
        ("SUBJECT", "Preserve image provenance"),
        ("DIRTY", "true"),
    ],
)
def test_build_environment_cannot_change_the_baked_manifest(
    manifest_root, monkeypatch, field, value
):
    monkeypatch.setenv(f"DAME_CURIE_BUILD_{field}", value)
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("queried Git despite a baked manifest"),
    )
    snapshot = observability.capture_running_build(manifest_root)
    report = snapshot.format()
    assert snapshot.provenance == observability.PROVENANCE_IMAGE
    assert snapshot.commit == MANIFEST["commit"]
    assert value not in report or value == MANIFEST["subject"]


def test_build_environment_alone_cannot_claim_image_provenance(monkeypatch, tmp_path):
    for field, value in (
        ("COMMIT", "a" * 40),
        ("BRANCH", "deployment/build"),
        ("DATE", "2026-09-09T01:30:00+02:00"),
        ("SUBJECT", "Preserve image provenance"),
        ("DIRTY", "false"),
    ):
        monkeypatch.setenv(f"DAME_CURIE_BUILD_{field}", value)
    monkeypatch.delenv("DAME_CURIE_STARTUP_GIT_SOCKET", raising=False)
    monkeypatch.setattr(observability.shutil, "which", lambda name: None)
    snapshot = observability.capture_running_build(tmp_path)
    assert snapshot.commit == "unknown"
    assert snapshot.branch == "unknown"
    assert snapshot.date == "unknown"
    assert snapshot.subject == "unknown"
    assert snapshot.dirty is None
    assert snapshot.provenance == observability.PROVENANCE_UNKNOWN
    assert "Provenance: unknown" in snapshot.format()
    assert "a" * 40 not in snapshot.format()


def test_build_environment_cannot_choose_another_manifest_path(monkeypatch, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / observability.MANIFEST_FILENAME).write_text(
        json.dumps(MANIFEST), encoding="utf-8"
    )
    monkeypatch.setenv("DAME_CURIE_BUILD_MANIFEST", str(other / observability.MANIFEST_FILENAME))
    monkeypatch.delenv("DAME_CURIE_STARTUP_GIT_SOCKET", raising=False)
    monkeypatch.setattr(observability.shutil, "which", lambda name: None)
    snapshot = observability.capture_running_build(tmp_path)
    assert snapshot.provenance == observability.PROVENANCE_UNKNOWN
    assert snapshot.commit == "unknown"
    assert "a" * 40 not in snapshot.format()


@pytest.mark.parametrize(
    "change",
    [
        {"commit": "unknown"},
        {"commit": "A" * 40},
        {"commit": "a" * 39},
        {"commit": 5},
        {"branch": None},
        {"branch": ""},
        {"subject": None},
        {"subject": ""},
        {"date": "09/09/2026"},
        {"date": "2026-09-09T01:30:00"},
        {"date": None},
        {"dirty": "false"},
        {"dirty": 0},
        {"dirty": None},
    ],
)
def test_present_but_unusable_manifest_fails_instead_of_falling_back(
    manifest_root, monkeypatch, change
):
    manifest = manifest_root / observability.MANIFEST_FILENAME
    manifest.write_text(json.dumps({**MANIFEST, **change}), encoding="utf-8")
    monkeypatch.setenv("DAME_CURIE_BUILD_COMMIT", "b" * 40)
    monkeypatch.setattr(observability.shutil, "which", lambda name: "/usr/bin/git")
    (manifest_root / ".git").mkdir()
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("fell back to a checkout or a socket"),
    )
    with pytest.raises(observability.ImageManifestError):
        observability.capture_running_build(manifest_root)


@pytest.mark.parametrize("field", ["commit", "branch", "date", "subject", "dirty"])
def test_manifest_missing_a_required_field_fails(manifest_root, field):
    manifest = manifest_root / observability.MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({key: value for key, value in MANIFEST.items() if key != field}),
        encoding="utf-8",
    )
    with pytest.raises(observability.ImageManifestError):
        observability.capture_running_build(manifest_root)


@pytest.mark.parametrize("body", ["", "{", "[]", "null", '"text"', '{"commit": }'])
def test_unreadable_manifest_cannot_become_provenance(manifest_root, body):
    manifest = manifest_root / observability.MANIFEST_FILENAME
    manifest.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        observability.capture_running_build(manifest_root)


def test_manifest_wins_over_a_configured_startup_socket(manifest_root, monkeypatch):
    def contacted(path):
        raise AssertionError("consulted the socket despite a baked manifest")

    monkeypatch.setenv(
        "DAME_CURIE_STARTUP_GIT_SOCKET", str(manifest_root / "never-contacted.sock")
    )
    monkeypatch.setattr(observability, "read_startup_git_snapshot", contacted)
    snapshot = observability.capture_running_build(manifest_root)
    assert snapshot.provenance == observability.PROVENANCE_IMAGE
    assert snapshot.commit == MANIFEST["commit"]


def test_source_checkout_is_labelled_and_does_not_claim_image_provenance(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("DAME_CURIE_STARTUP_GIT_SOCKET", raising=False)
    monkeypatch.setattr(observability.shutil, "which", lambda name: "/usr/bin/git")
    (tmp_path / ".git").mkdir()
    outputs = iter(
        [
            "b" * 40 + "\n2026-09-09T12:00:00Z\nLocal source\n",
            "local-branch\n",
            " M source.py\n",
        ]
    )
    monkeypatch.setattr(
        observability.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=next(outputs)),
    )
    snapshot = observability.capture_running_build(tmp_path)
    assert snapshot.provenance == observability.PROVENANCE_CHECKOUT
    assert snapshot.commit == "b" * 40
    assert snapshot.branch == "local-branch"
    assert snapshot.subject == "Local source"
    assert snapshot.dirty is True
    report = snapshot.format()
    assert "Provenance: checkout at boot" in report
    assert "Source: checkout at boot" in report
    assert f"Commit date: {snapshot.date}" in report
    assert snapshot.date == "2026-09-09T12:00:00+00:00"
    assert "dirty: yes" in report


def test_source_is_the_root_the_caller_runs_from(monkeypatch, tmp_path):
    """The manifest name is fixed, so the caller's root alone selects it."""
    (tmp_path / observability.MANIFEST_FILENAME).write_text(
        json.dumps(MANIFEST), encoding="utf-8"
    )
    monkeypatch.delenv("DAME_CURIE_STARTUP_GIT_SOCKET", raising=False)
    empty = tmp_path / "not-the-running-source"
    empty.mkdir()
    monkeypatch.setattr(observability.shutil, "which", lambda name: None)
    assert (
        observability.capture_running_build(tmp_path).provenance
        == observability.PROVENANCE_IMAGE
    )
    assert (
        observability.capture_running_build(empty).provenance
        == observability.PROVENANCE_UNKNOWN
    )
