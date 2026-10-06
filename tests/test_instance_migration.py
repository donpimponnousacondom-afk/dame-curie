import json
import os
from pathlib import Path

import pytest

from scripts import migrate_instance as migration


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, "INSTANCE_ROOT", tmp_path / "instances")
    target = migration.INSTANCE_ROOT / "dame-curie"
    for part in ("data", "sites", "shell", "config/prompts"):
        (target / part).mkdir(parents=True)
    (target / "config/bot.env").write_text("OPERATOR=independent\n")
    sources = [tmp_path / f"legacy-{part}" for part in ("data", "sites", "shell")]
    for source in sources:
        source.mkdir()
    return target, sources


def execute(layout, stopped=True, source_prompts=None):
    _, sources = layout
    migration.migrate("dame-curie", *sources, stopped=stopped, source_prompts=source_prompts)


def test_migrate_preserves_source_and_externalizes_prompts(layout):
    target, (data, sites, shell) = layout
    control = {"base_personality": "legacy personality", "bot_enabled": False}
    (data / "bot_control.json").write_text(json.dumps(control))
    (data / "prompts.json").write_text(json.dumps({"123": "server prompt"}))
    (data / "memory.db").write_bytes(b"offline fixture")
    (data / "maxwell_rag.db").write_bytes(b"synthetic database")
    (data / "maxwell_rag.db-wal").write_bytes(b"synthetic WAL")
    (data / "maxwell_rag.db-shm").write_bytes(b"synthetic SHM")
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
    assert not any(
        (target / "data" / name).exists()
        for name in ("maxwell_rag.db", "maxwell_rag.db-wal", "maxwell_rag.db-shm")
    )
    for name, content in (
        ("dame-curie-rag.db", b"synthetic database"),
        ("dame-curie-rag.db-wal", b"synthetic WAL"),
        ("dame-curie-rag.db-shm", b"synthetic SHM"),
    ):
        assert (target / "data" / name).read_bytes() == content
    assert (data / "maxwell_rag.db").read_bytes() == b"synthetic database"
    assert (data / "maxwell_rag.db-wal").read_bytes() == b"synthetic WAL"
    assert (data / "maxwell_rag.db-shm").read_bytes() == b"synthetic SHM"
    assert (target / "sites/index.html").read_text() == "page"
    assert (target / "shell/work.txt").read_text() == "work"
    assert (target / "config/bot.env").read_text() == "OPERATOR=independent\n"


@pytest.mark.parametrize(
    "prompt_state",
    ["default", "external", "missing_personality", "empty_personality", "missing_servers"],
)
def test_prompt_sources_are_selected_without_importing_config(layout, tmp_path, prompt_state):
    target, (data, _, _) = layout
    if prompt_state == "default":
        execute(layout)
        assert (target / "config/prompts/personality.txt").read_text() == migration.default_personality()
    else:
        prompt_root = tmp_path / "source-config" / "prompts"
        prompt_root.mkdir(parents=True)
        (data / "bot_control.json").write_text(json.dumps({"base_personality": "", "bot_enabled": False}))
        (data / "prompts.json").write_text(json.dumps({"old": "stale prompt"}))
        if prompt_state != "missing_personality":
            personality = "" if prompt_state == "empty_personality" else "external personality"
            (prompt_root / "personality.txt").write_text(personality)
        if prompt_state != "missing_servers":
            (prompt_root / "servers.json").write_text(json.dumps({"123": "external prompt"}))
        if prompt_state in ("missing_personality", "empty_personality", "missing_servers"):
            with pytest.raises(ValueError):
                execute(layout, source_prompts=prompt_root)
            assert list((target / "data").iterdir()) == []
            assert list((target / "config/prompts").iterdir()) == []
        else:
            execute(layout, source_prompts=prompt_root)
            assert json.loads((target / "config/prompts/servers.json").read_text()) == {"123": "external prompt"}
            assert (target / "config/prompts/personality.txt").read_text() == "external personality"
            assert json.loads((target / "data/bot_control.json").read_text()) == {"bot_enabled": False}
            assert (data / "prompts.json").exists()


@pytest.mark.parametrize("filename,content", [("prompts.json", "not json"), ("prompts.json", "[]"),
                                             ("bot_control.json", '{"base_personality": 12}')])
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


@pytest.mark.parametrize("kind", ["symlink", "fifo", "env", "rag_conflict"])
def test_unsafe_source_refused(layout, kind):
    target, (data, _, _) = layout
    if kind == "symlink":
        (data / "link").symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(data / "pipe")
    elif kind == "rag_conflict":
        for name in (
            "maxwell_rag.db",
            "maxwell_rag.db-wal",
            "maxwell_rag.db-shm",
            "dame-curie-rag.db",
            "dame-curie-rag.db-wal",
            "dame-curie-rag.db-shm",
        ):
            (data / name).write_bytes(name.encode())
    else:
        (data / ".env").write_text("fixture")
    with pytest.raises(ValueError):
        execute(layout)
    assert list((target / "data").iterdir()) == []
    if kind == "rag_conflict":
        for part in ("data", "sites", "shell", "config/prompts"):
            assert list((target / part).iterdir()) == []
        for name in (
            "maxwell_rag.db",
            "maxwell_rag.db-wal",
            "maxwell_rag.db-shm",
            "dame-curie-rag.db",
            "dame-curie-rag.db-wal",
            "dame-curie-rag.db-shm",
        ):
            assert (data / name).read_bytes() == name.encode()


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
    tool = data / "tool"
    tool.write_text("executable fixture")
    tool.chmod(0o755)
    execute(layout)
    copied = target / "data/fixture"
    copied_tool = target / "data/tool"
    assert copied.stat().st_uid == os.getuid()
    assert copied.stat().st_mode & 0o200
    assert copied_tool.stat().st_mode & 0o111 == tool.stat().st_mode & 0o111
    assert tool.stat().st_mode & 0o111 == 0o111


@pytest.mark.parametrize("value", ["../other", "UPPER", "-bad"])
def test_invalid_instance_refused(layout, value):
    _, sources = layout
    with pytest.raises(ValueError):
        migration.migrate(value, *sources, stopped=True)


def test_parent_traversal_refused(layout):
    _, sources = layout
    with pytest.raises(ValueError, match="traversal"):
        migration.migrate("dame-curie", sources[0] / ".." / sources[0].name, *sources[1:], stopped=True)
