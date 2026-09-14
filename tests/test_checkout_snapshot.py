import configparser
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "checkout_snapshot", ROOT / "scripts" / "checkout_snapshot.py"
)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)
COMMIT = "a" * 40


def status_bytes(commit=COMMIT, branch="development", entries=b""):
    return f"# branch.oid {commit}\0# branch.head {branch}\0".encode() + entries


def git(repository, *arguments):
    return subprocess.run(
        ["/usr/bin/git", "-C", str(repository), *arguments],
        env={
            **snapshot.GIT_ENV,
            "GIT_AUTHOR_NAME": "Snapshot Test",
            "GIT_AUTHOR_EMAIL": "snapshot@example.invalid",
            "GIT_COMMITTER_NAME": "Snapshot Test",
            "GIT_COMMITTER_EMAIL": "snapshot@example.invalid",
            "GIT_AUTHOR_DATE": "2026-09-11T12:00:00+02:00",
            "GIT_COMMITTER_DATE": "2026-09-11T12:00:00+02:00",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout.decode().strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "--initial-branch=development")
    (tmp_path / "README.md").write_text("Initial documentation.\n")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-m", "Initial snapshot")
    return tmp_path


def test_real_snapshot_has_exact_fields_and_utc_date(repository):
    result = json.loads(snapshot.snapshot_response(repository))
    assert result == {
        "commit": git(repository, "rev-parse", "HEAD"),
        "branch": "development",
        "date": "2026-09-11T10:00:00+00:00",
        "subject": "Initial snapshot",
        "dirty": False,
    }


def test_empty_and_docs_commits_and_branch_switch_refresh_new_capture(repository):
    first = snapshot.capture_snapshot(repository)
    git(repository, "commit", "--allow-empty", "-m", "Empty boot marker")
    second = snapshot.capture_snapshot(repository)
    assert second["commit"] != first["commit"]
    assert first["subject"] == "Initial snapshot"
    (repository / "README.md").write_text("Documentation changed.\n")
    git(repository, "add", "README.md")
    git(repository, "commit", "-m", "Documentation-only marker")
    third = snapshot.capture_snapshot(repository)
    assert third["commit"] != second["commit"]
    git(repository, "switch", "-c", "another-branch")
    fourth = snapshot.capture_snapshot(repository)
    assert fourth["commit"] == third["commit"]
    assert fourth["branch"] == "another-branch"
    assert third["branch"] == "development"
    assert all(result["dirty"] is False for result in (first, second, third, fourth))


@pytest.mark.parametrize("change", ["modified", "staged", "untracked", "deleted"])
def test_real_dirty_status_without_exporting_paths(repository, change):
    if change == "untracked":
        (repository / "untracked-private-name").write_text("Synthetic content")
    elif change == "deleted":
        (repository / "README.md").unlink()
    else:
        (repository / "README.md").write_text("Modified synthetic content")
        if change == "staged":
            git(repository, "add", "README.md")
    response = snapshot.snapshot_response(repository)
    assert json.loads(response)["dirty"] is True
    assert b"README.md" not in response
    assert b"untracked-private-name" not in response
    assert b"Synthetic content" not in response


def test_read_does_not_refresh_index_or_run_fsmonitor(repository):
    git(repository, "config", "core.fsmonitor", "/nonexistent/synthetic-fsmonitor")
    index = repository / ".git" / "index"
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    (repository / "README.md").write_text("Initial documentation.\n")
    assert snapshot.capture_snapshot(repository)["dirty"] is False
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before
    assert not (repository / ".git" / "index.lock").exists()


def test_detached_head_is_explicit(repository):
    commit = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "--detach", commit)
    result = snapshot.capture_snapshot(repository)
    assert result["commit"] == commit
    assert result["branch"] == "(detached)"


def test_unborn_head_fails_instead_of_inventing_snapshot(tmp_path):
    git(tmp_path, "init", "--initial-branch=development")
    with pytest.raises(ValueError):
        snapshot.capture_snapshot(tmp_path)


def test_corrupt_index_is_failure(repository):
    (repository / ".git" / "index").write_bytes(b"invalid synthetic index")
    with pytest.raises(ValueError, match="Git read failed"):
        snapshot.capture_snapshot(repository)


@pytest.mark.parametrize("entries", [b"? \xff-untracked\0", b"1 M. N... synthetic\0"])
def test_status_filenames_are_never_decoded(entries):
    assert snapshot.parse_status(status_bytes(entries=entries)) == (COMMIT, "development", True)


@pytest.mark.parametrize(
    "output",
    [
        b"", status_bytes(commit="(initial)"), status_bytes(branch=""),
        status_bytes(commit="not-a-hash"),
        status_bytes() + b"# branch.head duplicate\0",
    ],
)
def test_invalid_status_is_not_clean(output):
    with pytest.raises(ValueError):
        snapshot.parse_status(output)


@pytest.mark.parametrize("length", [40, 64])
def test_full_git_object_ids_are_preserved(length):
    commit = "b" * length
    assert snapshot.parse_status(status_bytes(commit=commit))[0] == commit


@pytest.mark.parametrize(
    "last",
    [status_bytes(commit="b" * 40), status_bytes(branch="changed"), status_bytes(entries=b"? new\0")],
)
def test_changed_head_branch_or_dirty_is_refused(monkeypatch, tmp_path, last):
    run = Mock(side_effect=[
        status_bytes(),
        f"{COMMIT}\0".encode() + b"2026-09-11T12:00:00+02:00\0Subject\n",
        last,
    ])
    monkeypatch.setattr(snapshot, "git_output", run)
    with pytest.raises(ValueError, match="changed during capture"):
        snapshot.capture_snapshot(tmp_path)
    assert run.call_args_list[1].args[1] == (
        "log", "-1", "--format=%H%x00%cI%x00%s", COMMIT, "--"
    )
    assert len({call.args[2] for call in run.call_args_list}) == 1


@pytest.mark.parametrize(
    "metadata",
    [
        b"incomplete", b"\0".join([b"b" * 40, b"2026-09-11T12:00:00Z", b"Other"]),
        b"\0".join([COMMIT.encode(), b"invalid-date", b"Subject"]),
        b"\0".join([COMMIT.encode(), b"2026-09-11T12:00:00", b"Subject"]),
    ],
)
def test_invalid_commit_metadata_fails(monkeypatch, tmp_path, metadata):
    monkeypatch.setattr(snapshot, "git_output", Mock(side_effect=[status_bytes(), metadata]))
    with pytest.raises(ValueError):
        snapshot.capture_snapshot(tmp_path)


def test_git_uses_clean_environment_readonly_flags_and_deadline(monkeypatch, tmp_path):
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=b"result", stderr=b""))
    monkeypatch.setattr(snapshot.subprocess, "run", run)
    monkeypatch.setattr(snapshot.time, "monotonic", lambda: 5.0)
    monkeypatch.setenv("GIT_INDEX_FILE", "/synthetic/private-index")
    monkeypatch.setenv("DISCORD_TOKEN", "synthetic-not-a-credential")
    assert snapshot.git_output(tmp_path, snapshot.STATUS_ARGS, 9.0) == b"result"
    command = run.call_args.args[0]
    assert command[0] == "/usr/bin/git"
    assert "--no-optional-locks" in command
    assert "core.fsmonitor=false" in command
    assert "core.untrackedCache=false" in command
    assert "core.hooksPath=/dev/null" in command
    options = run.call_args.kwargs
    assert options["timeout"] == 4.0
    assert options["stdin"] == subprocess.DEVNULL
    assert options["env"] == snapshot.GIT_ENV
    assert "DISCORD_TOKEN" not in options["env"]
    assert "GIT_INDEX_FILE" not in options["env"]
    assert options["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert options["env"]["GIT_CONFIG_SYSTEM"] == "/dev/null"


def test_expired_deadline_does_not_start_git(monkeypatch, tmp_path):
    run = Mock()
    monkeypatch.setattr(snapshot.subprocess, "run", run)
    monkeypatch.setattr(snapshot.time, "monotonic", lambda: 10.0)
    with pytest.raises(TimeoutError):
        snapshot.git_output(tmp_path, snapshot.STATUS_ARGS, 9.0)
    run.assert_not_called()


@pytest.mark.parametrize("code,stderr", [(1, b"private failure"), (0, b"private warning")])
def test_git_failure_and_permission_warnings_are_not_exported(monkeypatch, tmp_path, code, stderr):
    monkeypatch.setattr(snapshot.subprocess, "run", Mock(return_value=SimpleNamespace(
        returncode=code, stdout=b"private stdout", stderr=stderr,
    )))
    with pytest.raises(ValueError, match="^checkout Git read failed$"):
        snapshot.git_output(tmp_path, snapshot.STATUS_ARGS, snapshot.time.monotonic() + 10)


def test_response_limit_counts_encoded_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot, "capture_snapshot", lambda root: {
        "commit": COMMIT, "branch": "development", "date": "2026-09-11T10:00:00+00:00",
        "subject": "\u2603" * (snapshot.MAX_RESPONSE_BYTES // 6), "dirty": False,
    })
    with pytest.raises(ValueError, match="response exceeds limit"):
        snapshot.snapshot_response(tmp_path)


@pytest.mark.parametrize("failure", [
    PermissionError("private path"), ValueError("private metadata"),
    subprocess.TimeoutExpired("private command", 10),
])
def test_cli_failure_is_generic_and_has_no_response(monkeypatch, tmp_path, capsys, failure):
    monkeypatch.setattr(sys, "argv", ["checkout_snapshot.py", str(tmp_path)])
    monkeypatch.setattr(snapshot, "snapshot_response", Mock(side_effect=failure))
    assert snapshot.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Checkout snapshot unavailable.\n"


def test_cli_writes_one_response_and_never_reads_client(monkeypatch, tmp_path):
    response = b'{"commit":"synthetic"}\n'
    output = io.BytesIO()
    monkeypatch.setattr(sys, "argv", ["checkout_snapshot.py", str(tmp_path)])
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setattr(sys, "stdin", Mock(read=Mock(side_effect=AssertionError("client input read"))))
    monkeypatch.setattr(snapshot, "snapshot_response", Mock(return_value=response))
    assert snapshot.main() == 0
    assert output.getvalue() == response
    sys.stdin.read.assert_not_called()


def test_relative_repository_is_rejected_without_git(monkeypatch):
    run = Mock()
    monkeypatch.setattr(snapshot, "git_output", run)
    with pytest.raises(ValueError, match="absolute"):
        snapshot.capture_snapshot(Path("relative"))
    run.assert_not_called()


def test_rendered_unit_names_match_accept_yes_and_preserve_boundary():
    replacements = {
        "@INSTANCE@": "curie", "@CHECKOUT_OWNER@": "codexy",
        "@READER@": "/usr/local/libexec/maxwell-checkout-snapshot.py",
        "@CHECKOUT_ROOT@": "/home/codexy/Dame_Curie/Maxwell-bot",
    }
    names = {
        "maxwell-checkout.socket.in": "maxwell-checkout-curie.socket",
        "maxwell-checkout-worker.service.in": "maxwell-checkout-curie@.service",
    }
    rendered = {}
    for template, destination in names.items():
        text = (ROOT / "docker" / "systemd" / template).read_text()
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        assert "@" not in text
        unit = configparser.ConfigParser(interpolation=None)
        unit.read_string(text)
        rendered[destination] = unit
    socket_name, service_name = names.values()
    assert service_name == socket_name.removesuffix(".socket") + "@.service"
    socket_unit = rendered[socket_name]["Socket"]
    assert socket_unit["ListenStream"] == "/srv/maxwell-checkout/curie/snapshot.sock"
    assert socket_unit["SocketUser"] == socket_unit["SocketGroup"] == "maxwell-curie"
    assert socket_unit["SocketMode"] == "0600"
    assert socket_unit["DirectoryMode"] == "0711"
    assert socket_unit["Accept"] == "yes"
    assert socket_unit["MaxConnections"] == "2"
    assert "Service" not in socket_unit
    worker = rendered[service_name]["Service"]
    assert worker["User"] == "codexy"
    assert worker["Type"] == "exec"
    assert worker["StandardInput"] == "socket"
    assert worker["StandardOutput"] == "inherit"
    assert worker["StandardError"] == "journal"
    assert worker["ExecStart"] == (
        '/usr/local/bin/python3.14 -I "/usr/local/libexec/maxwell-checkout-snapshot.py" '
        '"/home/codexy/Dame_Curie/Maxwell-bot"'
    )
    for key in ("NoNewPrivileges", "PrivateNetwork", "PrivateTmp"):
        assert worker[key] == "yes"
    assert worker["ProtectSystem"] == "strict"
    assert worker["ProtectHome"] == "read-only"
    assert worker["CapabilityBoundingSet"] == worker["AmbientCapabilities"] == ""
    assert worker["RuntimeMaxSec"] == "15s"
    assert worker["TasksMax"] == "16"
    assert worker["MemoryMax"] == "128M"
    assert worker["RestrictAddressFamilies"] == "AF_UNIX"
