"""Focused unit checks for the Dirac mount boundary and publisher unit isolation.

These import the operator script by path and read the unit files as text: no
engine, no container, no private configuration and no application module.
"""

import configparser
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "scripts" / "publisher"
STATE_TREES = ("config", "config/prompts", "data", "sites", "shell",
               "smoke", "smoke-status", "status")


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
    return load_module("dirac_mount_boundary", ROOT / "scripts" / "dirac.py")


def state_root(tmp_path: Path) -> Path:
    """Create the private Dirac layout the operator validates, including its smoke trees."""
    root = tmp_path / "dirac"
    for relative in STATE_TREES:
        directory = root / relative
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
    root.chmod(0o700)
    return root


def test_documented_smoke_pair_is_accepted(dirac, tmp_path):
    root = state_root(tmp_path)
    pair = {"smoke_root": root / "smoke", "smoke_status": root / "smoke-status"}
    assert dirac.smoke_sources(root, os.getuid(), SimpleNamespace(**pair)) == pair
    custom = SimpleNamespace(smoke_root=None, smoke_status=root / "status")
    assert dirac.smoke_sources(root, os.getuid(), custom) == {"smoke_status": root / "status"}


def test_writable_smoke_mount_refuses_the_dirac_root(dirac, tmp_path):
    root = state_root(tmp_path)
    with pytest.raises(ValueError, match="must not mount the Dirac root itself"):
        dirac.smoke_sources(root, os.getuid(),
                            SimpleNamespace(smoke_root=None, smoke_status=root))


def test_writable_smoke_mount_refuses_the_read_only_config_tree(dirac, tmp_path):
    root = state_root(tmp_path)
    aliases = (root / "config", root / "config" / "prompts", root / "data" / ".." / "config")
    for source in aliases:
        with pytest.raises(ValueError, match="must not overlap the read-only mount"):
            dirac.smoke_sources(root, os.getuid(),
                                SimpleNamespace(smoke_root=None, smoke_status=source))


def test_writable_smoke_mount_refuses_the_read_only_smoke_root(dirac, tmp_path):
    root = state_root(tmp_path)
    smoke, inside = root / "smoke", root / "smoke" / "status"
    inside.mkdir()
    inside.chmod(0o700)
    for source in (smoke, inside):
        with pytest.raises(ValueError, match="must not overlap the read-only mount"):
            dirac.smoke_sources(root, os.getuid(),
                                SimpleNamespace(smoke_root=smoke, smoke_status=source))
    with pytest.raises(ValueError, match="must not overlap the read-only mount"):
        dirac.smoke_sources(root, os.getuid(),
                            SimpleNamespace(smoke_root=inside, smoke_status=smoke))


def test_read_only_smoke_root_dot_segments_still_block_a_nested_status(dirac, tmp_path):
    """A `..` spelling of the read-only smoke root must not hide the overlap from a nested status dir."""
    root = state_root(tmp_path)
    status = root / "smoke" / "status"
    status.mkdir()
    status.chmod(0o700)
    aliased = root / "data" / ".." / "smoke"
    assert aliased.resolve() == root / "smoke"
    with pytest.raises(ValueError, match="must not overlap the read-only mount"):
        dirac.smoke_sources(root, os.getuid(),
                            SimpleNamespace(smoke_root=aliased, smoke_status=status))


def test_smoke_mount_refuses_a_symlinked_directory(dirac, tmp_path):
    root = state_root(tmp_path)
    link = root / "smoke-link"
    link.symlink_to(root / "config")
    with pytest.raises(ValueError, match="must be a real directory"):
        dirac.smoke_sources(root, os.getuid(),
                            SimpleNamespace(smoke_root=None, smoke_status=link))


def service_directives(name: str) -> dict[str, str]:
    """Parse one publisher unit file's [Service] directives."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PUBLISHER / name)
    return dict(parser["Service"])


def hidden_paths(directives: dict[str, str]) -> set[str]:
    """The unit's inaccessible paths without the optional-path prefix, ignoring continuations."""
    entries = (entry.lstrip("-") for entry in directives["inaccessiblepaths"].split())
    return {entry for entry in entries if entry.startswith("/")}


def test_dirac_publisher_runs_as_the_shared_service_account():
    """Same account as both instances on a read-only filesystem, so InaccessiblePaths is the separator."""
    directives = service_directives("dirac-publisher.service")
    assert directives["user"] == directives["group"] == "dame-curie"
    assert directives["protectsystem"] == "strict"
    assert directives["protecthome"] == "yes"
    assert directives["nonewprivileges"] == "yes"


def test_dirac_publisher_hides_both_instances_credentials():
    hidden = hidden_paths(service_directives("dirac-publisher.service"))
    canonical_bot = {"/srv/dame-curie/config", "/srv/dame-curie/data",
                     "/srv/dame-curie/logs", "/srv/dame-curie/shell"}
    dirac_bot = {"/srv/dame-curie/dirac/config", "/srv/dame-curie/dirac/data",
                 "/srv/dame-curie/dirac/logs", "/srv/dame-curie/dirac/shell"}
    assert canonical_bot <= hidden
    assert dirac_bot <= hidden
    assert "/srv/dame-curie/publisher/config" in hidden


def test_dirac_publisher_keeps_its_own_credentials_and_paths_reachable():
    directives = service_directives("dirac-publisher.service")
    hidden = hidden_paths(directives)
    config = Path(directives["execstart"].split("--config", 1)[1].strip())
    assert config == Path("/srv/dame-curie/dirac/publisher/config/publisher.toml")
    managed = [config, config.parent, config.parent / "publisher_key",
               *(Path(entry) for entry in directives["readonlypaths"].split()),
               *(Path(entry) for entry in directives["readwritepaths"].split())]
    for path in managed:
        for entry in hidden:
            assert not path.is_relative_to(Path(entry)), path
