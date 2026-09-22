"""Isolated unit checks for the Dirac operator.

These import only repository scripts, the standard library and pytest: no
engine, no container, no private configuration and no application module.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path) -> ModuleType:
    """Import a repository script by path; its own directory supplies its siblings."""
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.fixture(scope="module")
def dirac() -> ModuleType:
    return load_module("dirac_operator", ROOT / "scripts" / "dirac.py")


class FakeEngine:
    """Scripted engine: records calls and answers by longest matching argument prefix."""

    def __init__(self, replies: dict[tuple[str, ...], str]) -> None:
        self.name = "dame-curie"
        self.path = Path("/srv/dame-curie")
        self.env = {"DOCKER_HOST": "unix:///run/user/1005/docker.sock"}
        self.replies = replies
        self.calls: list[tuple[str, ...]] = []

    def docker(self, *args: str) -> str:
        self.calls.append(args)
        matches = [key for key in self.replies if args[: len(key)] == key]
        if not matches:
            raise AssertionError(f"unexpected engine call: {args}")
        return self.replies[max(matches, key=len)]


def private_tree(root: Path) -> Path:
    """Create the parent-owned Dirac layout with private modes."""
    for relative in ("config", "config/prompts", "data", "sites", "shell"):
        (root / relative).mkdir(parents=True, exist_ok=True)
        (root / relative).chmod(0o700)
    root.chmod(0o700)
    return root


def write_derived(root: Path, endpoint: str, *, rag: str = "true") -> Path:
    """Write one private derived bot.env variant."""
    config = root / "config" / "bot.env"
    config.write_text(
        "DATA_DIR=/state/data\n"
        "DAME_CURIE_SITE_DIR=/state/sites\n"
        "DAME_CURIE_SHELL_DIR=/state/shell\n"
        "DAME_CURIE_PROMPTS_DIR=/config/prompts\n"
        f"ENABLE_RAG={rag}\n"
        f"DAME_CURIE_EMBED_BASE_URL={endpoint}\n"
    )
    config.chmod(0o600)
    return config


def test_create_arguments_pin_the_reviewed_runtime(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    arguments = dirac.create_arguments(
        root, "sha256:" + "a" * 64, "dame-curie_outbound",
        {"smoke_root": Path("/srv/dame-curie/dirac/smoke"), "smoke_status": Path("/srv/dame-curie/dirac/smoke-status")},
    )
    assert arguments[0] == "create"
    assert arguments[arguments.index("--name") + 1] == "dirac-v2"
    assert arguments[arguments.index("--label") + 1] == "dame-curie.dirac=dirac-v2"
    assert arguments[arguments.index("--memory") + 1] == "4g"
    assert arguments[arguments.index("--cpus") + 1] == "4"
    assert arguments[arguments.index("--pids-limit") + 1] == "256"
    assert arguments[arguments.index("--restart") + 1] == "no"
    assert arguments[arguments.index("--stop-timeout") + 1] == "45"
    assert arguments[arguments.index("--pull") + 1] == "never"
    assert arguments[arguments.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges:true" in arguments
    assert arguments[arguments.index("--network") + 1] == "dame-curie_outbound"
    assert "--add-host" not in arguments
    assert "--read-only" not in arguments
    assert "pull" not in arguments
    mounts = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--mount"]
    assert f"type=bind,src={root}/config,dst=/config,readonly" in mounts
    assert f"type=bind,src={root}/config/prompts,dst=/config/prompts" in mounts
    assert f"type=bind,src={root}/data,dst=/state/data" in mounts
    assert f"type=bind,src={root}/sites,dst=/state/sites" in mounts
    assert f"type=bind,src={root}/shell,dst=/state/shell" in mounts
    assert "type=bind,src=/srv/dame-curie/dirac/smoke,dst=/smoke,readonly" in mounts
    assert "type=bind,src=/srv/dame-curie/dirac/smoke-status,dst=/smoke-status" in mounts
    environment = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--env"]
    assert "DAME_CURIE_ENV_FILE=/config/bot.env" in environment
    assert "DAME_CURIE_CONTAINER_MODE=true" in environment
    assert "DAME_CURIE_INSTANCE_ID=dame-curie-dirac" in environment
    assert "DAME_CURIE_EMBED_MODE=external" in environment
    assert "DAME_CURIE_DIRAC_SMOKE_CONFIG=/smoke/config.json" in environment
    assert arguments[-5:] == ["-ec", dirac.ENTRY_SCRIPT, "--", "python", "bot.py"]


def test_create_arguments_without_smoke_opt_in(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    arguments = dirac.create_arguments(root, "sha256:" + "a" * 64, "dame-curie_outbound", {})
    mounts = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--mount"]
    assert not [mount for mount in mounts if "/smoke" in mount]
    assert not [value for value in arguments if "SMOKE" in value]


def test_smoke_paths_must_live_inside_the_state_root(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    smoke = root / "smoke"
    smoke.mkdir(mode=0o700)
    smoke.chmod(0o700)
    sources = dirac.smoke_sources(root, os.getuid(), SimpleNamespace(smoke_root=smoke, smoke_status=None))
    assert sources == {"smoke_root": smoke}
    canonical = tmp_path / "canonical"
    canonical.mkdir(mode=0o700)
    canonical.chmod(0o700)
    with pytest.raises(ValueError, match="must live inside"):
        dirac.smoke_sources(root, os.getuid(), SimpleNamespace(smoke_root=canonical, smoke_status=None))
    with pytest.raises(ValueError, match="must live inside"):
        dirac.smoke_sources(root, os.getuid(), SimpleNamespace(smoke_root=root / ".." / "canonical", smoke_status=None))
    smoke.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        dirac.smoke_sources(root, os.getuid(), SimpleNamespace(smoke_root=smoke, smoke_status=None))


def test_derived_config_requires_the_bridge_endpoint(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    write_derived(root, "http://172.23.0.1:11434")
    assert dirac.derived_config(root, os.getuid(), "172.23.0.1") == (True, "")
    write_derived(root, "http://ollama:11434")
    enabled, problem = dirac.derived_config(root, os.getuid(), "172.23.0.1")
    assert enabled is True
    assert "172.23.0.1" in problem
    write_derived(root, "http://172.23.0.1:11434/v1")
    assert "172.23.0.1" in dirac.derived_config(root, os.getuid(), "172.23.0.1")[1]
    write_derived(root, "http://172.23.0.1:11434", rag="false")
    assert dirac.derived_config(root, os.getuid(), "172.23.0.1") == (False, "")
    write_derived(root, "http://172.23.0.1:11434")
    (root / "config" / "bot.env").chmod(0o644)
    assert "private" in dirac.derived_config(root, os.getuid(), "172.23.0.1")[1]


def test_derived_config_problems_never_echo_config_values(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    write_derived(root, "http://dirac:sekrit@172.23.0.1:notaport")
    enabled, problem = dirac.derived_config(root, os.getuid(), "172.23.0.1")
    assert enabled is False
    assert problem == "derived config is unreadable or not private"
    assert "sekrit" not in problem


def test_embedding_readiness_reports_only_the_outcome_class(dirac, monkeypatch):
    engine = FakeEngine({})
    captured: dict[str, object] = {}

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 1, "", "Authorization: Bearer sekrit-token\n")

    monkeypatch.setattr(dirac.subprocess, "run", run)
    assert dirac.embedding_readiness(engine, True) == "failed: exit 1"
    assert captured["argv"] == [
        "docker", "exec", "dirac-v2", "python", "/opt/dame-curie/check_embeddings.py",
    ]
    assert dirac.embedding_readiness(engine, False).startswith("skipped")


def test_derived_config_requires_container_roots(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    config = root / "config" / "bot.env"
    config.write_text("DATA_DIR=/data\n")
    config.chmod(0o600)
    enabled, problem = dirac.derived_config(root, os.getuid(), "172.23.0.1")
    assert enabled is True  # a mismatch still reports the RAG switch that was read
    assert "DATA_DIR=/state/data" in problem
    write_derived(root, "http://172.23.0.1:11434")
    config.write_text(config.read_text().replace("DAME_CURIE_SITE_DIR=/state/sites", "DAME_CURIE_SITE_DIR=/tmp"))
    config.chmod(0o600)
    assert "DAME_CURIE_SITE_DIR=/state/sites" in dirac.derived_config(root, os.getuid(), "172.23.0.1")[1]


def test_owned_container_requires_the_reserved_label_and_name(dirac):
    engine = FakeEngine({("ps", "-aq"): "abc123\n", ("inspect",): "/other\n"})
    with pytest.raises(ValueError, match="held by"):
        dirac.owned_container(engine)
    engine = FakeEngine({("ps", "-aq"): "abc123\n", ("inspect",): "/dirac-v2\n"})
    assert dirac.owned_container(engine) == "abc123"
    assert engine.calls[0] == ("ps", "-aq", "--filter", "label=dame-curie.dirac=dirac-v2")
    engine = FakeEngine({("ps", "-aq"): "\n"})
    assert dirac.owned_container(engine) is None


def test_owned_container_rejects_duplicate_names(dirac):
    engine = FakeEngine({("ps", "-aq"): "abc123\ndef456\n"})
    with pytest.raises(ValueError, match="multiple containers"):
        dirac.owned_container(engine)


def test_outbound_bridge_requires_this_instance(dirac):
    engine = FakeEngine({
        ("network", "ls"): "dame-curie_outbound\n",
        ("network", "inspect"): "other|outbound|172.23.0.1\n",
    })
    with pytest.raises(ValueError, match="outbound bridge"):
        dirac.outbound_bridge(engine)
    engine = FakeEngine({
        ("network", "ls"): "dame-curie_outbound\n",
        ("network", "inspect"): "dame-curie|outbound|8.8.8.8\n",
    })
    with pytest.raises(ValueError, match="non-private"):
        dirac.outbound_bridge(engine)


def test_start_replace_reports_the_previous_state_before_removing(dirac, tmp_path, monkeypatch):
    root = private_tree(tmp_path / "dirac")
    write_derived(root, "http://172.23.0.1:11434")
    engine = FakeEngine({
        ("network", "ls"): "dame-curie_outbound\n",
        ("network", "inspect"): "dame-curie|outbound|172.23.0.1\n",
        ("image",): "sha256:" + "a" * 64 + "\n",
        ("ps", "-aq"): "abc123\n",
        ("inspect", "abc123", "--format", "{{.Name}}"): "/dirac-v2\n",
        ("inspect", "abc123", "--format", dirac.STATE_FORMAT):
            "exited|1|false|2026-09-22T00:00:00Z|sha256:bbbb|dame-curie-app:test\n",
        ("rm",): "abc123\n",
        ("create",): "newcontainer\n",
        ("start",): "dirac-v2\n",
    })
    engine.path = root.parent
    monkeypatch.setattr(dirac, "print", lambda *values, **kwargs: engine.calls.append(("print", str(values[0]))),
                        raising=False)
    monkeypatch.setattr(dirac.subprocess, "run",
                        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "", ""))
    args = SimpleNamespace(action="start", image="dame-curie-app:test", replace=True,
                           smoke_root=None, smoke_status=None)
    report = dirac.start(engine, os.getuid(), args)
    replacement = next(call for call in engine.calls if call[0] == "print")
    assert '"exit_code": "1"' in replacement[1]
    assert '"previous"' in replacement[1] and '"replacing"' in replacement[1]
    assert engine.calls[engine.calls.index(replacement) + 1][0] == "rm"
    assert engine.calls[-1][0] == "print" and '"action": "start"' in engine.calls[-1][1]
    assert report["embedding_readiness"] == "ok"


def test_status_reports_absent_container_without_mutating(dirac, tmp_path):
    root = private_tree(tmp_path / "dirac")
    write_derived(root, "http://172.23.0.1:11434")
    engine = FakeEngine({
        ("network", "ls"): "dame-curie_outbound\n",
        ("network", "inspect"): "dame-curie|outbound|172.23.0.1\n",
        ("ps", "-aq"): "",
    })
    engine.path = root.parent
    report, code = dirac.status(engine, os.getuid())
    assert code == 1
    assert report["present"] is False
    assert report["endpoint"] == "http://172.23.0.1:11434"
    assert report["config"] == "ok"
    assert report["embedding_readiness"] == "not running"
    assert "readiness" not in report  # the status field names the embedding check, not Discord readiness
    assert engine.calls[-1] == ("ps", "-aq", "--filter", "label=dame-curie.dirac=dirac-v2")
