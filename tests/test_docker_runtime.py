from pathlib import Path

import pytest

import docker_runtime as runtime


@pytest.mark.parametrize("root", runtime.ROOTS)
def test_confined_path(root):
    assert runtime.confined_path(f"/state/{root}/example") == Path(f"/state/{root}/example")


@pytest.mark.parametrize("path", ["/etc/passwd", "/state/data/../shell", "/state/database/x", "data/x"])
def test_confined_path_rejects_escape(path):
    with pytest.raises(ValueError):
        runtime.confined_path(path)


def test_confined_path_rejects_symlink(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "STATE_ROOT", tmp_path)
    (tmp_path / "data").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="symlink"):
        runtime.confined_path(tmp_path / "data" / "x")
