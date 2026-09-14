"""Instance-scoped Docker names, ownership, and daemon-host bind paths."""

import os
import re
from pathlib import Path

SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?")
STATE_ROOT = Path("/state")
ROOTS = ("data", "sites", "shell")


def container_mode() -> bool:
    return os.environ.get("MAXWELL_CONTAINER_MODE", "").lower() == "true"


def instance_id() -> str:
    value = os.environ.get("MAXWELL_INSTANCE_ID", "")
    if not SLUG.fullmatch(value):
        raise ValueError("MAXWELL_INSTANCE_ID must be a lower-case safe slug (1-30 characters)")
    return value


def resource_name(kind: str, slug: str = "") -> str:
    if not SLUG.fullmatch(kind) or (slug and not SLUG.fullmatch(slug)):
        raise ValueError("unsafe Docker resource name")
    return f"maxwell-{instance_id()}-{kind}" + (f"-{slug}" if slug else "")


def ownership_labels(kind: str, slug: str = "") -> dict[str, str]:
    resource_name(kind, slug)
    labels = {"maxwell.instance": instance_id(), "maxwell.kind": kind}
    if slug:
        labels["maxwell.site"] = slug
    return labels


def label_args(kind: str, slug: str = "") -> list[str]:
    return [arg for key, value in ownership_labels(kind, slug).items()
            for arg in ("--label", f"{key}={value}")]


def require_ownership(labels: dict, kind: str, slug: str = "") -> None:
    expected = ownership_labels(kind, slug)
    if not isinstance(labels, dict) or any(labels.get(k) != v for k, v in expected.items()):
        raise ValueError("Docker resource is not owned by this Maxwell instance")


def backend_network() -> str:
    expected = resource_name("backends")
    if os.environ.get("MAXWELL_BACKEND_NETWORK") != expected:
        raise ValueError("MAXWELL_BACKEND_NETWORK must match the instance backend network")
    return expected


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


def host_path(path: str | Path, roots: tuple[str, ...] = ROOTS) -> Path:
    path = confined_path(path, roots)
    expected = f"/srv/maxwell/{instance_id()}"
    if os.environ.get("MAXWELL_HOST_INSTANCE_DIR") != expected:
        raise ValueError("MAXWELL_HOST_INSTANCE_DIR must be /srv/maxwell/<instance-id>")
    return Path(expected) / path.relative_to(STATE_ROOT)
