"""Offline legacy-state migration; run as the prepared instance service user."""

import argparse
import ast
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
from contextlib import ExitStack

INSTANCE_ROOT = Path("/srv/maxwell")
SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?")


def checked_path(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("paths must be absolute without parent traversal")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink paths are not supported")
    return path


def inventory(root: Path) -> list[Path]:
    checked_path(root)
    if not root.is_dir():
        raise ValueError("each source must be an existing directory")
    paths = sorted(root.rglob("*"))
    for path in paths:
        mode = path.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError("source contains symlinks or special files")
        if path.name == ".env" or path.name.startswith(".env."):
            raise ValueError("source contains environment files; exclude them before migration")
    return paths


def mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("migration JSON must contain an object")  # noqa: TRY004 - invalid file content
    return value


def default_personality() -> str:
    tree = ast.parse((Path(__file__).resolve().parents[1] / "control_defaults.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULT_CONTROL" for t in node.targets):
            for key, value in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant) and key.value == "base_personality":
                    return ast.literal_eval(value)
    raise ValueError("canonical default personality not found")


def migrated_registry(source: dict, instance: str) -> dict:
    if "version" in source:
        raise ValueError("expected a legacy unversioned site registry")
    sites = {}
    for slug, old in source.items():
        if not SLUG.fullmatch(slug) or len(slug) < 2 or not isinstance(old, dict):
            raise ValueError("invalid legacy site registry entry")
        if not isinstance(old.get("running", False), bool):
            raise ValueError("site running state must be boolean")  # noqa: TRY004 - invalid file content
        env, packages = old.get("env", {}), old.get("packages", [])
        if not isinstance(env, dict) or not all(isinstance(v, str) for v in env.values()):
            raise ValueError("site environment must map names to strings")
        if not isinstance(packages, list) or not all(isinstance(v, str) for v in packages):
            raise ValueError("site packages must be strings")
        running = old.get("running", False)
        sites[slug] = dict(old, version=2, instance=instance, running=running,
                           port=8000,
                           container=f"maxwell-{instance}-site-{slug}",
                           image=f"maxwell-{instance}-siteimg-{slug}" if packages else f"maxwell-{instance}-site-runtime",
                           network=f"maxwell-{instance}-backends")
    return {"version": 2, "instance": instance, "sites": sites}


def migration_json(data: Path, instance: str) -> tuple[dict, str, dict, dict]:
    control = mapping(data / "bot_control.json")
    personality = control.pop("base_personality", None)
    if personality is None:
        personality = default_personality()
    if not isinstance(personality, str) or not personality.strip():
        raise ValueError("base personality must be nonempty text")
    servers = mapping(data / "prompts.json")
    if not all(isinstance(v, str) for v in servers.values()):
        raise ValueError("server prompts must map IDs to strings")
    registry = migrated_registry(mapping(data / "site_servers.json"), instance)
    for slug, entry in registry["sites"].items():
        if entry["running"] and not (data / "site_servers" / slug / "app.py").is_file():
            raise ValueError("running site has no app.py to restore")
    return control, personality, servers, registry


def copy_inventory(source: Path, paths: list[Path], target: Path) -> None:
    for path in paths:
        dest = target / path.relative_to(source)
        if path.is_dir():
            dest.mkdir()
        else:
            shutil.copyfile(path, dest, follow_symlinks=False)


def populate(stages: list[Path], sources: list[Path], inventories: list[list[Path]], converted: tuple) -> None:
    for source, paths, stage in zip(sources, inventories, stages):
        copy_inventory(source, paths, stage)
    control, personality, servers, registry = converted
    data, _, _, prompts = stages
    (data / "prompts.json").unlink(missing_ok=True)
    (data / "bot_control.json").write_text(json.dumps(control, indent=2) + "\n")
    (data / "site_servers.json").write_text(json.dumps(registry, indent=2) + "\n")
    (prompts / "personality.txt").write_text(personality, encoding="utf-8")
    (prompts / "servers.json").write_text(json.dumps(servers, indent=2) + "\n")


def migrate(instance: str, data: Path, sites: Path, shell: Path, *, stopped: bool) -> None:
    if not stopped:
        raise ValueError("--stopped acknowledgement is required")
    if not SLUG.fullmatch(instance):
        raise ValueError("invalid instance ID")
    target = checked_path(INSTANCE_ROOT / instance)
    sources = [checked_path(path) for path in (data, sites, shell)]
    if any(target.is_relative_to(p) or p.is_relative_to(target) for p in sources):
        raise ValueError("source and target must not overlap")
    roots = [target / "data", target / "sites", target / "shell", target / "config" / "prompts"]
    for root in roots:
        checked_path(root)
        if not root.is_dir() or next(root.iterdir(), None) is not None:
            raise ValueError("target roots must be prepared empty directories")
    config = checked_path(target / "config" / "bot.env")
    if not config.is_file():
        raise ValueError("operator must prepare target config/bot.env separately")
    inventories = [inventory(source) for source in sources]
    converted = migration_json(data, instance)
    with ExitStack() as stack:
        stages = [Path(stack.enter_context(tempfile.TemporaryDirectory(prefix=".migration-", dir=root))) for root in roots]
        populate(stages, sources, inventories, converted)
        published = []
        complete = False
        try:
            for root, stage in zip(roots, stages):
                if any(p != stage for p in root.iterdir()):
                    raise ValueError("target changed during migration")
                for child in stage.iterdir():
                    destination = root / child.name
                    child.rename(destination)
                    published.append(destination)
            complete = True
        finally:
            if not complete:
                for path in reversed(published):
                    shutil.rmtree(path) if path.is_dir() else path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--sites", required=True, type=Path)
    parser.add_argument("--shell", required=True, type=Path)
    parser.add_argument("--stopped", action="store_true", help="all source writers and target daemon are stopped")
    args = parser.parse_args()
    try:
        migrate(args.instance, args.data, args.sites, args.shell, stopped=args.stopped)
    except (OSError, ValueError, UnicodeError):
        parser.exit(1, "Migration refused or failed; source untouched. Check inputs and target permissions.\n")
    print("State migrated; source unchanged. Target account/provider configuration was not read or copied.")


if __name__ == "__main__":
    main()
