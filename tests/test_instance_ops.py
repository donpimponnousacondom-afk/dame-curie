"""Offline deployment operations checks; no Docker or runtime files are read."""

import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import subprocess
import stat
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, mock_open

import pytest

SPEC = importlib.util.spec_from_file_location("instance_ops", Path(__file__).parents[1] / "scripts" / "instance.py")
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


def deployment_text():
    return "\n".join(("INSTANCE_ID=curie", "INSTANCE_DIR=/srv/maxwell/curie",
                      "ENGINE_SOCKET=/run/user/1001/docker.sock", "APP_IMAGE=maxwell-app:test",
                      "WEB_IMAGE=maxwell-web:test", "WEB_PORT=8081"))


def container(name, *, running=True, kind="", instance="curie"):
    labels = {"maxwell.instance": instance, "maxwell.kind": kind} if kind else {
        "com.docker.compose.project": f"maxwell-{instance}",
        "com.docker.compose.service": name,
        "com.docker.compose.project.config_files": str(ops.CHECKOUT / "compose.yaml"),
    }
    return {"Id": name, "Name": f"/maxwell-{instance}-{name}",
            "Config": {"Labels": labels}, "State": {"Running": running}}


def instance(tmp_path):
    app = ops.Instance.__new__(ops.Instance)
    app.name = "curie"
    app.project = "maxwell-curie"
    app.path = tmp_path / "curie"
    app.path.mkdir()
    for root in ops.ROOTS:
        (app.path / root).mkdir()
    app.values = {"APP_IMAGE": "maxwell-app:test"}
    app.env = {"DOCKER_HOST": "unix:///private/docker.sock"}
    return app


def tar_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", pax_headers={"maxwell.instance": "curie"}) as archive:
        for root in ops.ROOTS:
            info = tarfile.TarInfo(root)
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
        for name, kind, target in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = target
            archive.addfile(info)
    output.seek(0)
    return output


def test_parse_settings_is_literal_and_complete():
    assert ops.parse_settings(deployment_text())["INSTANCE_ID"] == "curie"


@pytest.mark.parametrize("extra", ["EVIL=1", "APP_IMAGE=other", "export APP_IMAGE=x"])
def test_deployment_rejects_unknown_duplicate_and_shell(extra):
    with pytest.raises(ValueError):
        ops.parse_settings(deployment_text() + "\n" + extra)


@pytest.mark.parametrize("value", ["$(touch /tmp/no)", "`id`", '"quoted"', "a;b", "a b", "a\\b"])
def test_deployment_rejects_expansion(value):
    with pytest.raises(ValueError):
        ops.parse_settings(deployment_text().replace("maxwell-app:test", value))


def test_inventory_ignores_other_instance_and_requires_labels():
    own = container("bot")
    assert ops.select_owned([own, container("bot", instance="uni")], "curie", "maxwell-curie") == [own]
    own["Config"]["Labels"] = {}
    with pytest.raises(ValueError, match="ownership"):
        ops.select_owned([own], "curie", "maxwell-curie")


@pytest.mark.parametrize("service", ["ollama", "ollama-pull"])
def test_inventory_accepts_owned_embedding_services(service):
    own = container(service)
    foreign = container(service, instance="other")
    assert ops.select_owned([foreign, own], "curie", "maxwell-curie") == [own]


def test_inventory_rejects_unknown_compose_service():
    with pytest.raises(ValueError, match="unexpected service"):
        ops.select_owned([container("unexpected")], "curie", "maxwell-curie")


def test_stop_quiesces_embedding_clients_before_server(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[container("ollama"), container("bot"), container("api"), container("web"), container("ollama-pull", running=False)])
    app.docker = Mock()
    ops.lifecycle(app, "stop")
    assert [call.args[-1] for call in app.docker.call_args_list] == ["bot", "api", "web", "ollama"]


def test_inventory_rejects_foreign_checkout():
    own = container("bot")
    own["Config"]["Labels"]["com.docker.compose.project.config_files"] = "/elsewhere/compose.yaml"
    with pytest.raises(ValueError, match="checkout"):
        ops.select_owned([own], "curie", "maxwell-curie")


def test_docker_rejects_stderr_even_with_exit_zero(tmp_path, monkeypatch):
    app = instance(tmp_path)
    monkeypatch.setattr(ops.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0, "{}", "permission denied")))
    with pytest.raises(RuntimeError, match="diagnostics"):
        app.docker("info")


def test_compose_does_not_load_checkout_env(tmp_path, monkeypatch):
    app = instance(tmp_path)
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(ops.subprocess, "run", run)
    app.compose("up", "-d")
    command = run.call_args.args[0]
    assert command[command.index("--env-file") + 1] == "/dev/null"
    assert command[command.index("-f") + 1] == str(ops.CHECKOUT / "compose.yaml")
    assert run.call_args.kwargs["env"] == app.env


def test_down_stops_all_writers_before_removing_managed_containers(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[container("web"), container("shell", kind="shell"), container("api"), container("bot"), container("site", kind="site")])
    events = []
    app.docker = lambda *args: events.append(args)
    app.compose = lambda *args: events.append(("compose", *args))
    ops.lifecycle(app, "down")
    assert [event[-1] for event in events[:5]] == ["bot", "api", "shell", "site", "web"]
    assert events[5:7] == [("rm", "shell"), ("rm", "site")]
    assert events[-1] == ("compose", "down", "--timeout", "45")


@pytest.mark.parametrize("action", ["up", "start"])
def test_up_waits_for_live_service_health(tmp_path, action):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[])
    app.compose = Mock()
    ops.lifecycle(app, action)
    app.inventory.assert_called_once_with()
    app.compose.assert_called_once_with("up", "-d", "--wait", "--wait-timeout", "300")


@pytest.mark.parametrize("action", ["up", "start"])
def test_start_alias_rejects_failed_inventory(tmp_path, action):
    app = instance(tmp_path)
    app.inventory = Mock(side_effect=ValueError("foreign ownership"))
    app.compose = Mock()
    with pytest.raises(ValueError, match="foreign ownership"):
        ops.lifecycle(app, action)
    app.compose.assert_not_called()


@pytest.mark.parametrize("action", ["up", "start"])
@pytest.mark.parametrize("lock_busy", [False, True])
def test_start_alias_cli_uses_same_operation_lock_and_health_wait(monkeypatch, action, lock_busy):
    events = Mock()
    app = SimpleNamespace(path=Path("/synthetic/curie"), inventory=events.inventory, compose=events.compose)
    account = object()
    service_account = Mock(return_value=account)
    constructor = Mock(return_value=app)
    file_open = mock_open()
    file_open.return_value.fileno.return_value = 123
    file_api = SimpleNamespace(
        open=Mock(return_value=123), fdopen=file_open,
        O_CREAT=os.O_CREAT, O_RDWR=os.O_RDWR, O_NOFOLLOW=os.O_NOFOLLOW,
    )
    monkeypatch.setattr(ops.sys, "argv", ["instance.py", "curie", action])
    monkeypatch.setattr(ops, "service_account", service_account)
    monkeypatch.setattr(ops, "Instance", constructor)
    monkeypatch.setattr(ops, "os", file_api)
    monkeypatch.setattr(ops.fcntl, "flock", events.flock)
    if lock_busy:
        events.flock.side_effect = BlockingIOError("operation busy")
        with pytest.raises(BlockingIOError, match="operation busy"):
            ops.main()
    else:
        ops.main()
    service_account.assert_called_once_with("curie")
    constructor.assert_called_once_with("curie", account)
    file_api.open.assert_called_once_with(
        app.path / ".operations.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    file_open.assert_called_once_with(123, "w")
    expected = [call.flock(123, ops.fcntl.LOCK_EX | ops.fcntl.LOCK_NB)]
    if not lock_busy:
        expected += [call.inventory(), call.compose("up", "-d", "--wait", "--wait-timeout", "300")]
    assert events.mock_calls == expected


@pytest.mark.parametrize("action", ["up", "start"])
def test_start_alias_cli_rejects_archive_before_identity_lookup(monkeypatch, capsys, action):
    service_account = Mock(side_effect=AssertionError("identity must not be inspected"))
    monkeypatch.setattr(ops, "service_account", service_account)
    monkeypatch.setattr(ops.sys, "argv", ["instance.py", "curie", action, "/synthetic/archive.tar"])
    with pytest.raises(SystemExit) as error:
        ops.main()
    assert error.value.code == 2
    assert "backup/restore require an archive path; other commands do not" in capsys.readouterr().err
    service_account.assert_not_called()


def test_restart_remains_bot_api_only(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[])
    app.compose = Mock()
    ops.lifecycle(app, "restart")
    app.inventory.assert_called_once_with()
    app.compose.assert_called_once_with("restart", "--timeout", "45", "bot", "api")


def test_helper_mounts_only_state_and_no_network(tmp_path):
    app = instance(tmp_path)
    args = app.helper(ops.ARCHIVE_PROGRAM)
    assert args[args.index("--network") + 1] == "none"
    mounts = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
    assert len(mounts) == 4
    assert all(mount.endswith(",readonly") for mount in mounts)
    assert not any("docker.sock" in mount or "deploy.env" in mount for mount in mounts)


@pytest.mark.parametrize("failed", [False, True])
def test_backup_restores_only_previously_running_containers(tmp_path, monkeypatch, failed):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[container("bot"), container("api", running=False), container("shell", kind="shell")])
    app.docker = Mock()
    monkeypatch.setattr(ops.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=int(failed), stderr=b"")))
    target = tmp_path / "backup.tar"
    if failed:
        with pytest.raises(RuntimeError):
            ops.backup(app, target)
        assert not target.exists()
    else:
        ops.backup(app, target)
        assert target.stat().st_mode & 0o777 == 0o600
    assert app.docker.call_args.args == ("start", "shell", "bot")
    assert all("api" not in call.args for call in app.docker.call_args_list)


def test_backup_stop_failure_still_resumes_and_removes_partial(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[container("bot")])
    app.docker = Mock(side_effect=[RuntimeError("stop failed"), ""])
    target = tmp_path / "backup.tar"
    with pytest.raises(RuntimeError, match="stop failed"):
        ops.backup(app, target)
    assert app.docker.call_args.args == ("start", "bot")
    assert not target.exists()


@pytest.mark.parametrize("name,kind,target", [
    ("../escape", tarfile.REGTYPE, ""), ("/escape", tarfile.REGTYPE, ""),
    ("config/../../escape", tarfile.REGTYPE, ""), ("other/file", tarfile.REGTYPE, ""),
    ("shell/link", tarfile.SYMTYPE, "../../escape"),
    ("shell/link", tarfile.SYMTYPE, "/etc/passwd"),
    ("shell/link", tarfile.LNKTYPE, "config/file"),
    ("data/device", tarfile.CHRTYPE, ""), ("data/pipe", tarfile.FIFOTYPE, ""),
])
def test_archive_rejects_unsafe_paths_and_types(name, kind, target):
    with tarfile.open(fileobj=tar_bytes([(name, kind, target)])) as archive:
        with pytest.raises(ValueError):
            ops.validate_archive(archive, "curie")


def test_archive_accepts_confined_symlink_and_numeric_owner():
    entries = [("shell/file", tarfile.REGTYPE, ""), ("shell/link", tarfile.SYMTYPE, "file")]
    with tarfile.open(fileobj=tar_bytes(entries)) as archive:
        ops.validate_archive(archive, "curie")


def test_archive_rejects_members_under_links():
    entries = [("shell/link", tarfile.SYMTYPE, "directory"), ("shell/link/file", tarfile.REGTYPE, "")]
    with tarfile.open(fileobj=tar_bytes(entries)) as archive:
        with pytest.raises(ValueError, match="descends"):
            ops.validate_archive(archive, "curie")


def test_restore_refuses_nonempty_or_existing_containers(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[container("bot", running=False)])
    with pytest.raises(ValueError, match="fresh"):
        ops.restore(app, tmp_path / "backup.tar")
    app.inventory.return_value = []
    (app.path / "data" / "existing").touch()
    with pytest.raises(ValueError, match="nonempty"):
        ops.restore(app, tmp_path / "backup.tar")


@pytest.mark.parametrize("size", [0, 8192, 200000])
def test_restore_child_inherits_rewound_archive_descriptor(tmp_path, size):
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[])
    app.env = os.environ.copy()
    source = tmp_path / "backup.tar"
    source.write_bytes(tar_bytes([]).getvalue())
    with tarfile.open(source, "a") as archive:
        member = tarfile.TarInfo("data/sacred")
        member.size = size
        archive.addfile(member, io.BytesIO(b"x" * size))
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    program = f"import hashlib,sys; assert hashlib.sha256(sys.stdin.buffer.read()).hexdigest() == {expected!r}"
    app.helper = Mock(return_value=[sys.executable, "-c", program])
    ops.restore(app, source)
    app.helper.assert_called_once_with(ops.RESTORE_PROGRAM, writable=True)
    assert not any((app.path / "data").iterdir())


def test_archive_destination_cannot_be_inside_state_or_redirected(tmp_path):
    app = instance(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        ops.archive_outside(app.path / "data" / "backup.tar", app)
    (tmp_path / "link").symlink_to(app.path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        ops.archive_outside(tmp_path / "link" / "backup.tar", app)


def test_private_directory_rejects_shared_permissions(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        ops.require_private(tmp_path, tmp_path.stat().st_uid)


@pytest.mark.parametrize("options,accepted", [(["name=rootless", "name=seccomp"], True), (["name=seccomp"], False), ([], False)])
def test_engine_rootless_security_info_is_required(monkeypatch, options, accepted):
    account = SimpleNamespace(pw_uid=1001, pw_dir="/home/maxwell-curie")
    monkeypatch.setattr(ops, "require_private", Mock())
    monkeypatch.setattr(ops.Path, "read_text", Mock(return_value=deployment_text()))
    monkeypatch.setattr(ops.Path, "is_symlink", Mock(return_value=False))
    monkeypatch.setattr(ops.Path, "is_dir", Mock(return_value=True))
    original_stat = ops.Path.stat
    def socket_stat(path, *args, **kwargs):
        if str(path) == "/run/user/1001/docker.sock":
            return SimpleNamespace(st_mode=stat.S_IFSOCK | 0o600, st_uid=1001)
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(ops.Path, "stat", socket_stat)
    docker = Mock(return_value=json.dumps({"SecurityOptions": options}))
    monkeypatch.setattr(ops.Instance, "docker", docker)
    if accepted:
        app = ops.Instance("curie", account)
        assert app.env["DOCKER_HOST"] == "unix:///run/user/1001/docker.sock"
        assert app.env["COMPOSE_DISABLE_ENV_FILE"] == "1"
    else:
        with pytest.raises(ValueError, match="not rootless"):
            ops.Instance("curie", account)
    docker.assert_called_once_with("info", "--format", "{{json .}}")


def test_archive_rejects_cross_identity_restore():
    with tarfile.open(fileobj=tar_bytes([])) as archive:
        with pytest.raises(ValueError, match="identity"):
            ops.validate_archive(archive, "uni")


def test_backup_catches_child_created_while_bot_stops(tmp_path, monkeypatch):
    app = instance(tmp_path)
    app.inventory = Mock(side_effect=[
        [container("bot"), container("api", running=False)],
        [container("bot", running=False), container("api", running=False), container("late-site", kind="site")],
    ])
    app.docker = Mock()
    monkeypatch.setattr(ops.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0, stderr=b"")))
    ops.backup(app, tmp_path / "backup.tar")
    assert [call.args for call in app.docker.call_args_list] == [
        ("stop", "--time", "45", "bot"), ("stop", "--time", "45", "late-site"),
        ("start", "late-site", "bot"),
    ]


def test_down_catches_child_created_while_bot_stops(tmp_path):
    app = instance(tmp_path)
    app.inventory = Mock(side_effect=[
        [container("bot")], [container("bot", running=False), container("late-shell", kind="shell")],
    ])
    app.docker = Mock()
    app.compose = Mock()
    ops.lifecycle(app, "down")
    assert [call.args for call in app.docker.call_args_list] == [
        ("stop", "--time", "45", "bot"), ("stop", "--time", "45", "late-shell"), ("rm", "late-shell"),
    ]


def test_inventory_rejects_conflicting_instance_labels():
    own = container("bot")
    own["Config"]["Labels"]["maxwell.instance"] = "uni"
    with pytest.raises(ValueError, match="conflicting"):
        ops.select_owned([own], "curie", "maxwell-curie")


@pytest.fixture
def actual_archive(tmp_path):
    source = tmp_path / "fixture-source"
    for root in ops.ROOTS:
        (source / root).mkdir(parents=True)
    (source / "config" / "prompts").mkdir()
    (source / "config" / "prompts" / "personality.txt").write_text("Fixture persona: Curie\n")
    (source / "sites" / "index.html").write_bytes(b"<h1>Fixture site</h1>\n")
    (source / "shell" / "payload.bin").write_bytes(bytes(range(256)))
    (source / "shell" / "relative-link").symlink_to("payload.bin")
    os.link(source / "shell" / "payload.bin", source / "shell" / "hardlink")
    db = source / "data" / "fixture.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE fixture (value TEXT)")
        connection.execute("INSERT INTO fixture VALUES ('offline sample')")
    program = ops.ARCHIVE_PROGRAM.replace('Path("/instance")', f"Path({str(source)!r})")
    result = subprocess.run([sys.executable, "-c", program, "curie"], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    return source, result.stdout


def test_actual_archive_and_restore_roundtrip(tmp_path, actual_archive):
    source, content = actual_archive
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        ops.validate_archive(archive, "curie")
        assert archive.pax_headers["maxwell.instance"] == "curie"
        assert archive.getmember("shell/relative-link").issym()
        assert any(member.islnk() for member in archive.getmembers())
        assert all(member.uid == os.getuid() and member.gid == os.getgid() for member in archive.getmembers())
    target = tmp_path / "fixture-restored"
    target.mkdir()
    program = ops.RESTORE_PROGRAM.replace('"/instance"', repr(str(target)))
    result = subprocess.run([sys.executable, "-c", program], input=content, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == result.stderr == b""
    for relative in ("config/prompts/personality.txt", "sites/index.html", "shell/payload.bin", "data/fixture.db"):
        assert (target / relative).read_bytes() == (source / relative).read_bytes()
        assert (target / relative).stat().st_uid == os.getuid()
        assert (target / relative).stat().st_gid == os.getgid()
    assert (target / "shell/relative-link").readlink() == Path("payload.bin")
    assert (target / "shell/payload.bin").stat().st_ino == (target / "shell/hardlink").stat().st_ino
    with sqlite3.connect(target / "data/fixture.db") as connection:
        assert connection.execute("SELECT value FROM fixture").fetchall() == [("offline sample",)]


def test_actual_archive_restore_wrapper_refuses_overwrite(tmp_path, actual_archive):
    source, content = actual_archive
    app = instance(tmp_path)
    app.inventory = Mock(return_value=[])
    app.helper = Mock(side_effect=AssertionError("restore helper must not run"))
    archive_path = tmp_path / "fixture.tar"
    archive_path.write_bytes(content)
    existing = app.path / "config" / "existing.txt"
    existing.write_text("keep this fixture")
    with pytest.raises(ValueError, match="nonempty"):
        ops.restore(app, archive_path)
    assert existing.read_text() == "keep this fixture"
    app.helper.assert_not_called()
    assert (source / "config/prompts/personality.txt").exists()


def test_actual_restore_data_filter_blocks_escaping_symlink(tmp_path):
    target = tmp_path / "fixture-target"
    target.mkdir()
    content = tar_bytes([("shell/escape", tarfile.SYMTYPE, "../../outside")]).getvalue()
    program = ops.RESTORE_PROGRAM.replace('"/instance"', repr(str(target)))
    result = subprocess.run([sys.executable, "-c", program], input=content, capture_output=True)
    assert result.returncode != 0
    assert b"LinkOutsideDestinationError" in result.stderr
    assert not (target / "shell/escape").is_symlink()
    assert not (tmp_path / "outside").exists()


def test_restore_filter_preserves_numeric_ownership_contract():
    assert "tarfile.data_filter" in ops.RESTORE_PROGRAM
    assert "setattr(result, kind, value)" in ops.RESTORE_PROGRAM
    assert '"/proc/self/" + kind + "_map"' in ops.RESTORE_PROGRAM
