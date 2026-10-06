"""Container-state path confinement for shell authoring and the knowledge graph."""

import os
from pathlib import Path

STATE_ROOT = Path("/state")
ROOTS = ("data", "sites", "shell")


def container_mode() -> bool:
    return os.environ.get("DAME_CURIE_CONTAINER_MODE", "").lower() == "true"


def confined_path(path: str | Path, roots: tuple[str, ...] = ROOTS) -> Path:
    path = Path(path)
    if not roots or any(root not in ROOTS for root in roots):
        raise ValueError("unapproved state root")
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("state path must be absolute and cannot traverse parents")
    allowed = [STATE_ROOT / root for root in roots]
    if not any(path.is_relative_to(root) for root in allowed):
        raise ValueError("path is outside approved state roots")
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("state path cannot contain symlinks")
    return path
