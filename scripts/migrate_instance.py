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

INSTANCE_ROOT = Path("/srv")
SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?")
INSTANCE = re.compile(rf"dame-curie(?:-{SLUG.pattern})?")
RAG_DATABASE_NAMES = {
    "maxwell_rag.db": "dame-curie-rag.db",
    "maxwell_rag.db-wal": "dame-curie-rag.db-wal",
    "maxwell_rag.db-shm": "dame-curie-rag.db-shm",
}


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


def migration_json(data: Path, source_prompts: Path | None = None) -> tuple[dict, str, dict]:
    control = mapping(data / "bot_control.json")
    personality = control.pop("base_personality", None)
    if source_prompts is None:
        if personality is None:
            personality = default_personality()
        servers = mapping(data / "prompts.json")
    else:
        prompt_root = source_prompts
        personality_path = checked_path(prompt_root / "personality.txt")
        servers_path = checked_path(prompt_root / "servers.json")
        if not personality_path.is_file() or not servers_path.is_file():
            raise ValueError("source prompts must contain personality.txt and servers.json")
        personality = personality_path.read_text(encoding="utf-8")
        servers = mapping(servers_path)
    if not isinstance(personality, str) or not personality.strip():
        raise ValueError("base personality must be nonempty text")
    if not all(isinstance(v, str) for v in servers.values()):
        raise ValueError("server prompts must map IDs to strings")
    return control, personality, servers


def copy_inventory(source: Path, paths: list[Path], target: Path, *, map_rag_database: bool = False) -> None:
    if map_rag_database:
        names = {path.name for path in paths if path.parent == source}
        if names.intersection(RAG_DATABASE_NAMES) and names.intersection(RAG_DATABASE_NAMES.values()):
            raise ValueError("source contains both legacy and canonical RAG database files")
    for path in paths:
        relative = path.relative_to(source)
        if map_rag_database and path.parent == source:
            relative = relative.with_name(RAG_DATABASE_NAMES.get(relative.name, relative.name))
        dest = target / relative
        if path.is_dir():
            dest.mkdir()
        else:
            shutil.copyfile(path, dest, follow_symlinks=False)
            mode = stat.S_IMODE(dest.stat().st_mode)
            dest.chmod(mode | (path.stat().st_mode & 0o111))


def populate(stages: list[Path], sources: list[Path], inventories: list[list[Path]], converted: tuple) -> None:
    for index, (source, paths, stage) in enumerate(zip(sources, inventories, stages)):
        copy_inventory(source, paths, stage, map_rag_database=index == 0)
    control, personality, servers = converted
    data, _, _, prompts = stages
    (data / "prompts.json").unlink(missing_ok=True)
    (data / "bot_control.json").write_text(json.dumps(control, indent=2) + "\n")
    (prompts / "personality.txt").write_text(personality, encoding="utf-8")
    (prompts / "servers.json").write_text(json.dumps(servers, indent=2) + "\n")


def migrate(
    instance: str, data: Path, sites: Path, shell: Path, *, stopped: bool, source_prompts: Path | None = None
) -> None:
    if not stopped:
        raise ValueError("--stopped acknowledgement is required")
    if not INSTANCE.fullmatch(instance) or len(instance) > 30:
        raise ValueError("invalid instance ID")
    target = checked_path(INSTANCE_ROOT / instance)
    sources = [checked_path(path) for path in (data, sites, shell)]
    if any(target.is_relative_to(p) or p.is_relative_to(target) for p in sources):
        raise ValueError("source and target must not overlap")
    if source_prompts is not None:
        source_prompts = checked_path(source_prompts)
        if not source_prompts.is_dir():
            raise ValueError("source prompts must be an existing directory")
        if target.is_relative_to(source_prompts) or source_prompts.is_relative_to(target):
            raise ValueError("source prompts and target must not overlap")
        if any(source_prompts.is_relative_to(p) or p.is_relative_to(source_prompts) for p in sources):
            raise ValueError("source prompts must be separate from migration sources")
    roots = [target / "data", target / "sites", target / "shell", target / "config" / "prompts"]
    for root in roots:
        checked_path(root)
        if not root.is_dir() or next(root.iterdir(), None) is not None:
            raise ValueError("target roots must be prepared empty directories")
    config = checked_path(target / "config" / "bot.env")
    if not config.is_file():
        raise ValueError("operator must prepare target config/bot.env separately")
    inventories = [inventory(source) for source in sources]
    converted = migration_json(data, source_prompts)
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
    parser.add_argument("--source-prompts", type=Path, help="external source config/prompts directory")
    parser.add_argument("--stopped", action="store_true", help="all source writers and target daemon are stopped")
    args = parser.parse_args()
    try:
        migrate(
            args.instance,
            args.data,
            args.sites,
            args.shell,
            stopped=args.stopped,
            source_prompts=args.source_prompts,
        )
    except (OSError, ValueError, UnicodeError):
        parser.exit(1, "Migration refused or failed; source untouched. Check inputs and target permissions.\n")
    print("State migrated; source unchanged. Target account/provider configuration was not read or copied.")


if __name__ == "__main__":
    main()
