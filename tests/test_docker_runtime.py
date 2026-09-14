from pathlib import Path

import pytest

import docker_runtime as runtime


@pytest.fixture
def container_env(monkeypatch):
    monkeypatch.setenv("MAXWELL_CONTAINER_MODE", "true")
    monkeypatch.setenv("MAXWELL_INSTANCE_ID", "curie")
    monkeypatch.setenv("MAXWELL_HOST_INSTANCE_DIR", "/srv/maxwell/curie")
    monkeypatch.setenv("MAXWELL_BACKEND_NETWORK", "maxwell-curie-backends")


@pytest.mark.parametrize("root", runtime.ROOTS)
def test_host_translation(container_env, root):
    assert runtime.host_path(f"/state/{root}/example") == Path(f"/srv/maxwell/curie/{root}/example")


@pytest.mark.parametrize("path", ["/etc/passwd", "/state/data/../shell", "/state/database/x", "data/x"])
def test_host_translation_rejects_escape(container_env, path):
    with pytest.raises(ValueError):
        runtime.host_path(path)


def test_host_translation_rejects_symlink(container_env, monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "STATE_ROOT", tmp_path)
    (tmp_path / "data").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="symlink"):
        runtime.host_path(tmp_path / "data" / "x")


@pytest.mark.parametrize("slug", ["Root", "../root", "", "-root", "root-", "a" * 31])
def test_instance_slug_validation(monkeypatch, slug):
    monkeypatch.setenv("MAXWELL_INSTANCE_ID", slug)
    with pytest.raises(ValueError):
        runtime.instance_id()


def test_instance_ownership_and_network(container_env, monkeypatch):
    assert runtime.resource_name("shell") == "maxwell-curie-shell"
    assert runtime.backend_network() == "maxwell-curie-backends"
    runtime.require_ownership(runtime.ownership_labels("site", "demo"), "site", "demo")
    with pytest.raises(ValueError, match="owned"):
        runtime.require_ownership({"maxwell.instance": "other"}, "shell")
    monkeypatch.setenv("MAXWELL_BACKEND_NETWORK", "bridge")
    with pytest.raises(ValueError):
        runtime.backend_network()


def test_host_root_cannot_be_overridden(container_env, monkeypatch):
    monkeypatch.setenv("MAXWELL_HOST_INSTANCE_DIR", "/srv/maxwell/other")
    with pytest.raises(ValueError):
        runtime.host_path("/state/data")
