import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot_tools
from bot_tools import ShellTool, _ensure_sandbox_image, _sandbox_source_hash


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setenv("MAXWELL_CONTAINER_MODE", "true")
    monkeypatch.setenv("MAXWELL_INSTANCE_ID", "alice")
    monkeypatch.setenv("MAXWELL_HOST_INSTANCE_DIR", "/srv/maxwell/alice")
    monkeypatch.setenv("MAXWELL_SHELL_DIR", "/state/shell")
    monkeypatch.delenv("MAXWELL_SHELL_FULL_HOST", raising=False)
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", AsyncMock(side_effect=AssertionError("unmocked Docker call")))
    monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(side_effect=AssertionError("live subprocess forbidden")))


def shell_info(instance="alice", running=True, mode="isolated"):
    return {
        "Id": "container-id",
        "Image": "image-id",
        "State": {"Running": running},
        "Config": {"User": "root", "WorkingDir": "/home/maxwell", "Cmd": ["sleep", "infinity"], "Entrypoint": None, "Labels": {
            "maxwell.instance": instance, "maxwell.kind": "shell",
            "maxwell.shell.mode": mode, "maxwell.shell.init": "1",
        }},
        "NetworkSettings": {"Networks": {"bridge": {}}},
        "HostConfig": {
            "Memory": 4 * 1024**3, "NanoCpus": 2_000_000_000, "PidsLimit": 1024,
            "Tmpfs": {"/tmp": "rw,exec,nosuid,size=256m"},
            "NetworkMode": "bridge", "Init": True,
            "CapDrop": ["ALL"],
            "CapAdd": ["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER", "NET_RAW", "NET_BIND_SERVICE"],
            "SecurityOpt": ["no-new-privileges:true"],
        },
        "Mounts": [{"Type": "bind", "Source": f"/srv/maxwell/{instance}/shell", "Destination": "/home/maxwell", "RW": True}],
    }


def image_info(instance="alice", source=None):
    return {"Id": "image-id", "Config": {"Labels": {
        "maxwell.instance": instance, "maxwell.kind": "shell-image",
        "maxwell.shell.source": source or _sandbox_source_hash(),
    }}}


def docker_result(value):
    return (json.dumps(value).encode(), b""), 0


def test_separate_instance_names(monkeypatch):
    shell = ShellTool(bot=None)
    assert shell.CONTAINER_NAME == "maxwell-alice-shell"
    assert shell.IMAGE_NAME == "maxwell-alice-shell-image"
    monkeypatch.setenv("MAXWELL_INSTANCE_ID", "bob")
    assert shell.CONTAINER_NAME == "maxwell-bob-shell"
    assert shell.IMAGE_NAME == "maxwell-bob-shell-image"


def test_full_host_rejected_before_docker(monkeypatch):
    monkeypatch.setenv("MAXWELL_SHELL_FULL_HOST", "true")
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock()
    with pytest.raises(ValueError, match="forbidden"):
        asyncio.run(shell._ensure_container())
    shell._run_docker.assert_not_called()


@pytest.mark.parametrize("options,stderr", [(["name=seccomp"], b""), (["name=rootless"], b"permission denied")])
def test_rootful_or_failed_daemon_refused(options, stderr):
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(return_value=((json.dumps(options).encode(), stderr), 0))
    with pytest.raises(RuntimeError, match="rootless"):
        asyncio.run(shell._ensure_container())
    assert shell._run_docker.call_count == 1


def test_wrong_label_never_removed_started_or_executed():
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(side_effect=[docker_result(["name=rootless"]), docker_result([shell_info("bob")])])
    with pytest.raises(ValueError, match="not owned"):
        asyncio.run(shell._ensure_container())
    assert [call.args[0] for call in shell._run_docker.call_args_list] == ["info", "inspect"]


def test_container_run_uses_host_translated_bind_and_labels(monkeypatch):
    shell = ShellTool(bot=None)
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot_tools, "_ensure_sandbox_image", AsyncMock())
    shell._run_docker = AsyncMock(side_effect=[
        docker_result(["name=rootless"]), ((b"", b"No such container"), 1),
        ((b"container-id", b""), 0), docker_result(["name=rootless"]),
        docker_result([shell_info()]), docker_result([image_info()]),
    ])
    assert asyncio.run(shell._ensure_container()) == "container-id"
    args = shell._run_docker.call_args_list[2].args
    assert "/srv/maxwell/alice/shell:/home/maxwell:rw" in args
    assert "maxwell.instance=alice" in args
    assert "maxwell.kind=shell" in args
    assert args[args.index("--name") + 1] == "maxwell-alice-shell"
    assert args[-1] == "maxwell-alice-shell-image"
    assert args[args.index("--network") + 1] == "bridge"
    assert "--privileged" not in args
    assert not any("docker.sock" in arg or ":/host" in arg for arg in args)


@pytest.mark.parametrize("mutation", ["socket", "hostnet", "privileged", "image", "mode", "source", "security"])
def test_export_rejects_unexpected_container(mutation):
    info = shell_info()
    if mutation == "socket":
        info["Mounts"].append({"Type": "bind", "Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock", "RW": True})
    elif mutation == "hostnet":
        info["HostConfig"]["NetworkMode"] = "host"
    elif mutation == "privileged":
        info["HostConfig"]["Privileged"] = True
    elif mutation == "image":
        info["Image"] = "foreign-image"
    elif mutation == "mode":
        info["Config"]["Labels"]["maxwell.shell.mode"] = "full"
    elif mutation == "source":
        info["Mounts"][0]["Source"] = "/srv/maxwell/bob/shell"
    else:
        info["HostConfig"]["SecurityOpt"] = []
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(side_effect=[docker_result(["name=rootless"]), docker_result([info]), docker_result([image_info()])])
    with pytest.raises(ValueError):
        asyncio.run(shell._verify_export_container())


@pytest.mark.parametrize("section,key,value", [
    ("HostConfig", "Memory", 0),
    ("HostConfig", "NanoCpus", 0),
    ("HostConfig", "PidsLimit", -1),
    ("HostConfig", "PortBindings", {"80/tcp": [{"HostPort": "8080"}]}),
    ("HostConfig", "PublishAllPorts", True),
    ("HostConfig", "DeviceRequests", [{"Count": -1}]),
    ("HostConfig", "Tmpfs", {"/tmp": "rw,size=4g"}),
    ("HostConfig", "SecurityOpt", ["no-new-privileges:true", "seccomp=unconfined"]),
    ("Config", "User", "other"),
    ("Config", "WorkingDir", "/"),
    ("Config", "Cmd", ["bash"]),
    ("Config", "Entrypoint", ["/unexpected"]),
    ("NetworkSettings", "Networks", {"bridge": {}, "private-embeddings": {}}),
])
def test_export_refuses_configuration_drift_before_image_or_execution(section, key, value):
    info = shell_info()
    info[section][key] = value
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(side_effect=[docker_result(["name=rootless"]), docker_result([info])])
    with pytest.raises(ValueError):
        asyncio.run(shell._verify_export_container())
    assert shell._run_docker.call_count == 2


def test_owned_mode_transition_removes_by_id(monkeypatch):
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(side_effect=[docker_result(["name=rootless"]), docker_result([shell_info(mode="full")]), ((b"", b"stop here"), 1)])
    with pytest.raises(RuntimeError, match="stop here"):
        asyncio.run(shell._ensure_container())
    assert shell._run_docker.call_args.args == ("rm", "-f", "container-id")


def test_image_build_is_namespaced_labeled_and_hashed(monkeypatch):
    docker = AsyncMock(side_effect=[((b"", b"No such image"), 1), ((b"", b""), 0)])
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    asyncio.run(_ensure_sandbox_image("maxwell-alice-shell-image"))
    args = docker.call_args.args
    assert args[:3] == ("build", "-t", "maxwell-alice-shell-image")
    assert "maxwell.instance=alice" in args
    assert "maxwell.kind=shell-image" in args
    assert f"maxwell.shell.source={_sandbox_source_hash()}" in args
    assert args[args.index("-f") + 1].endswith("docker/Dockerfile")


def test_wrong_image_owner_not_overwritten(monkeypatch):
    docker = AsyncMock(return_value=docker_result([image_info("bob")]))
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    with pytest.raises(ValueError, match="not owned"):
        asyncio.run(_ensure_sandbox_image("maxwell-alice-shell-image"))
    assert docker.call_count == 1


def test_legacy_names_and_workspace_preserved(monkeypatch):
    monkeypatch.delenv("MAXWELL_CONTAINER_MODE")
    shell = ShellTool(bot=None)
    assert shell.CONTAINER_NAME == shell.IMAGE_NAME == "maxwell-shell"
    assert bot_tools._shell_workspace() == Path(bot_tools.__file__).parent / "shelldocker"


def test_export_stopped_container_not_started():
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(side_effect=[docker_result(["name=rootless"]), docker_result([shell_info(running=False)])])
    with pytest.raises(ValueError, match="not running"):
        asyncio.run(shell._verify_export_container())
    assert shell._run_docker.call_count == 2


def test_exec_uses_verified_immutable_id(monkeypatch):
    shell = ShellTool(bot=None)
    shell._ensure_container = AsyncMock(return_value="verified-container-id")

    async def run():
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"ok")
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0, wait=AsyncMock(return_value=0))
        spawn = AsyncMock(return_value=process)
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", spawn)
        assert await shell._run_shell_command("printf ok") == (b"ok", b"", 0)
        args = spawn.call_args.args
        assert args[:2] == ("docker", "exec")
        assert "verified-container-id" in args
        assert shell.CONTAINER_NAME not in args

    asyncio.run(run())


def test_timeout_cleanup_refuses_replaced_container():
    shell = ShellTool(bot=None)
    shell._verify_export_container = AsyncMock(return_value="replacement-id")
    shell._run_docker = AsyncMock()
    asyncio.run(shell._kill_container_exec("/tmp/exec.pid", "original-id"))
    shell._run_docker.assert_not_called()


def test_legacy_export_checks_mode_and_bind(monkeypatch):
    monkeypatch.delenv("MAXWELL_CONTAINER_MODE")
    info = shell_info()
    info["Config"]["Labels"] = {"maxwell.shell.mode": "isolated", "maxwell.shell.init": "1"}
    info["Mounts"][0]["Source"] = str(bot_tools._shell_workspace())
    shell = ShellTool(bot=None)
    shell._run_docker = AsyncMock(return_value=docker_result([info]))
    assert asyncio.run(shell._verify_export_container()) == "container-id"
    info["Config"]["Labels"]["maxwell.shell.mode"] = "full"
    shell._run_docker = AsyncMock(return_value=docker_result([info]))
    with pytest.raises(ValueError, match="mode"):
        asyncio.run(shell._verify_export_container())


def test_image_inspect_denial_does_not_build(monkeypatch):
    docker = AsyncMock(return_value=((b"", b"permission denied"), 1))
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    with pytest.raises(RuntimeError, match="permission denied"):
        asyncio.run(_ensure_sandbox_image())
    assert docker.call_count == 1
    assert docker.call_args.args == ("image", "inspect", "maxwell-alice-shell-image")


def test_owned_outdated_image_rebuilt_with_current_hash(monkeypatch):
    docker = AsyncMock(side_effect=[docker_result([image_info(source="old-hash")]), ((b"", b""), 0)])
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    asyncio.run(_ensure_sandbox_image())
    assert docker.call_count == 2
    assert f"maxwell.shell.source={_sandbox_source_hash()}" in docker.call_args.args
