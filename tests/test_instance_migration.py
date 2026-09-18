import json
import os
from pathlib import Path

import pytest

from scripts import migrate_instance as migration


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, "INSTANCE_ROOT", tmp_path / "instances")
    target = migration.INSTANCE_ROOT / "curie"
    for part in ("data", "sites", "shell", "config/prompts"):
        (target / part).mkdir(parents=True)
    (target / "config/bot.env").write_text("OPERATOR=independent\n")
    sources = [tmp_path / f"legacy-{part}" for part in ("data", "sites", "shell")]
    for source in sources:
        source.mkdir()
    return target, sources


def execute(layout, stopped=True):
    _, sources = layout
    migration.migrate("curie", *sources, stopped=stopped)


def test_migrate_preserves_source_and_externalizes_prompts(layout):
    target, (data, sites, shell) = layout
    control = {"base_personality": "legacy personality", "bot_enabled": False}
    (data / "bot_control.json").write_text(json.dumps(control))
    (data / "prompts.json").write_text(json.dumps({"123": "server prompt"}))
    (data / "memory.db").write_bytes(b"offline fixture")
    (sites / "index.html").write_text("page")
    (shell / "work.txt").write_text("work")
    execute(layout)
    assert json.loads((data / "bot_control.json").read_text()) == control
    assert (data / "prompts.json").exists()
    assert (target / "config/prompts/personality.txt").read_text() == "legacy personality"
    assert json.loads((target / "config/prompts/servers.json").read_text()) == {"123": "server prompt"}
    assert json.loads((target / "data/bot_control.json").read_text()) == {"bot_enabled": False}
    assert not (target / "data/prompts.json").exists()
    assert (target / "data/memory.db").read_bytes() == b"offline fixture"
    assert (target / "sites/index.html").read_text() == "page"
    assert (target / "shell/work.txt").read_text() == "work"
    assert (target / "config/bot.env").read_text() == "OPERATOR=independent\n"


def test_registry_retargets_and_preserves_desired_state(layout):
    target, (data, _, _) = layout
    app = data / "site_servers/demo/app.py"
    app.parent.mkdir(parents=True)
    app.write_text("fixture")
    original = {"demo": {"running": True, "env": {"FIXTURE": "value"}, "packages": ["redis==5.0.1"], "port": 8800},
                "idle": {"running": False}}
    (data / "site_servers.json").write_text(json.dumps(original))
    execute(layout)
    registry = json.loads((target / "data/site_servers.json").read_text())
    assert registry["version"] == 2 and registry["instance"] == "curie"
    active = registry["sites"]["demo"]
    assert active["container"] == "maxwell-curie-site-demo"
    assert active["image"] == "maxwell-curie-siteimg-demo"
    assert active["network"] == "maxwell-curie-backends"
    assert active["port"] == 8000 and active["running"] is True
    assert active["env"] == original["demo"]["env"]
    assert registry["sites"]["idle"]["running"] is False
    assert json.loads((data / "site_servers.json").read_text()) == original


def test_default_prompt_reads_literal_without_importing_config(layout):
    target, _ = layout
    execute(layout)
    assert (target / "config/prompts/personality.txt").read_text() == migration.default_personality()


@pytest.mark.parametrize("filename,content", [("prompts.json", "not json"), ("prompts.json", "[]"),
                                             ("bot_control.json", '{"base_personality": 12}'),
                                             ("site_servers.json", '{"demo":{"running":"false"}}')])
def test_invalid_json_leaves_target_empty(layout, filename, content):
    target, (data, _, _) = layout
    (data / filename).write_text(content)
    with pytest.raises(ValueError):
        execute(layout)
    assert list((target / "data").iterdir()) == []
    assert list((target / "config/prompts").iterdir()) == []


@pytest.mark.parametrize("part", ["data", "sites", "shell", "config/prompts"])
def test_nonempty_target_refused(layout, part):
    target, _ = layout
    (target / part / "existing").write_text("keep")
    with pytest.raises(ValueError, match="empty"):
        execute(layout)
    assert (target / part / "existing").read_text() == "keep"


def test_requires_stopped_acknowledgement(layout):
    with pytest.raises(ValueError, match="stopped"):
        execute(layout, stopped=False)


@pytest.mark.parametrize("kind", ["symlink", "fifo", "env"])
def test_unsafe_source_refused(layout, kind):
    target, (data, _, _) = layout
    if kind == "symlink":
        (data / "link").symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(data / "pipe")
    else:
        (data / ".env").write_text("fixture")
    with pytest.raises(ValueError):
        execute(layout)
    assert list((target / "data").iterdir()) == []


def test_copy_failure_cleans_staging(layout, monkeypatch):
    target, (data, _, _) = layout
    (data / "fixture").write_text("keep")

    def fail(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(migration.shutil, "copyfile", fail)
    with pytest.raises(OSError):
        execute(layout)
    assert list((target / "data").iterdir()) == []
    assert (data / "fixture").read_text() == "keep"


def test_publish_failure_rolls_back_completed_roots(layout, monkeypatch):
    target, (data, _, _) = layout
    (data / "fixture").write_text("keep")
    rename = Path.rename

    def fail_prompts(self, destination):
        if Path(destination).parent == target / "config/prompts":
            raise OSError("simulated publish failure")
        return rename(self, destination)

    monkeypatch.setattr(Path, "rename", fail_prompts)
    with pytest.raises(OSError):
        execute(layout)
    for part in ("data", "sites", "shell", "config/prompts"):
        assert list((target / part).iterdir()) == []
    assert (data / "fixture").read_text() == "keep"


def test_operator_configuration_is_never_read(layout, monkeypatch):
    original = Path.read_text

    def read(self, *args, **kwargs):
        assert self.name != "bot.env"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    execute(layout)


def test_does_not_copy_source_ownership_or_modes(layout):
    target, (data, _, _) = layout
    source = data / "fixture"
    source.write_text("keep")
    source.chmod(0o400)
    execute(layout)
    copied = target / "data/fixture"
    assert copied.stat().st_uid == os.getuid()
    assert copied.stat().st_mode & 0o200


@pytest.mark.parametrize("value", ["../other", "UPPER", "-bad"])
def test_invalid_instance_refused(layout, value):
    _, sources = layout
    with pytest.raises(ValueError):
        migration.migrate(value, *sources, stopped=True)


def test_parent_traversal_refused(layout):
    _, sources = layout
    with pytest.raises(ValueError, match="traversal"):
        migration.migrate("curie", sources[0] / ".." / sources[0].name, *sources[1:], stopped=True)
