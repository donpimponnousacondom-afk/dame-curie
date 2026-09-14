import os
import re
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .common import FILE_FLAGS, PublisherError, absolute_path, directory, private_directory


@dataclass(frozen=True)
class Config:
    source: Path
    staging: Path
    state: Path
    key: Path
    known_hosts: Path
    host: str
    user: str
    site_root: str
    image_root: str
    private_paths: tuple[Path, ...] = ()
    port: int = 22
    rescan_seconds: float = 60.0
    settle_seconds: float = 0.3
    timeout_seconds: int = 120

    def target(self) -> list[str | int]:
        return [self.host, self.user, self.port, self.site_root, self.image_root]


def private_file(path: Path) -> None:
    with directory(path.parent) as parent:
        value = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
    if (
        not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
        or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) & 0o077
    ):
        raise PublisherError("private file permissions refused")


def validate(config: Config, config_path: Path) -> None:
    roots = [config.source, config.staging, config.state]
    files = [config.key, config.known_hosts, config_path]
    for index, first in enumerate(roots):
        for second in roots[index + 1:]:
            if first.is_relative_to(second) or second.is_relative_to(first):
                raise PublisherError("local roots overlap")
    if any(file.is_relative_to(root) for file in files for root in roots):
        raise PublisherError("private configuration overlaps managed roots")
    if any(config.source.is_relative_to(private) for private in config.private_paths):
        raise PublisherError("public source is inside a configured private path")
    for root in (config.staging, config.state):
        private_directory(root)
    for file in files:
        private_file(file)
    if any("%" in str(path) or "${" in str(path) or "\n" in str(path) or "\r" in str(path)
           for path in (config.key, config.known_hosts)):
        raise PublisherError("SSH credential path expansion refused")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", config.host):
        raise PublisherError("SSH host refused")
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]*", config.user):
        raise PublisherError("SSH user refused")
    sites, images = absolute_path(config.site_root), absolute_path(config.image_root)
    if sites == Path("/") or images == Path("/"):
        raise PublisherError("remote filesystem root refused")
    if sites.is_relative_to(images) or images.is_relative_to(sites):
        raise PublisherError("remote roots overlap")
    if not 1 <= config.port <= 65535 or config.timeout_seconds <= 0:
        raise PublisherError("invalid connection limits")
    if not 0 < config.settle_seconds <= config.rescan_seconds:
        raise PublisherError("invalid reconciliation intervals")


def load_config(path: Path) -> Config:
    path = absolute_path(str(path))
    private_file(path)
    with directory(path.parent) as parent:
        fd = os.open(path.name, FILE_FLAGS, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        value = os.fstat(stream.fileno())
        if (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
                or value.st_uid != os.getuid() or value.st_mode & 0o077):
            raise PublisherError("private configuration changed")
        data = tomllib.load(stream)
    paths = {name: absolute_path(data.pop(name)) for name in (
        "source", "staging", "state", "key", "known_hosts",
    )}
    private_paths = tuple(absolute_path(item) for item in data.pop("private_paths", []))
    config = Config(**paths, private_paths=private_paths, **data)
    validate(config, path)
    return config
