import fcntl
import json
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass, field

from .common import FILE_FLAGS, PublisherError, eligible, private_directory
from .config import Config


@dataclass
class Site:
    token: str
    identity: list[int] = field(default_factory=list)
    deleting: bool = False


class State:
    def __init__(self, config: Config):
        private_directory(config.state)
        self.path = config.state / "ownership.json"
        self.target = config.target()
        self.source = str(config.source)
        self.source_identity: tuple[int, ...] = ()
        self.roots: list[list[int]] = []
        self.sites: dict[str, Site] = {}
        self.lock_fd = os.open(config.state / "lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        value = os.fstat(self.lock_fd)
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_mode & 0o077:
            os.close(self.lock_fd)
            raise PublisherError("state lock refused")
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists():
                self.load()
        except (OSError, ValueError, TypeError, KeyError, PublisherError):
            os.close(self.lock_fd)
            raise

    def close(self) -> None:
        os.close(self.lock_fd)

    def load(self) -> None:
        fd = os.open(self.path, FILE_FLAGS)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            value = os.fstat(stream.fileno())
            if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_mode & 0o077:
                raise PublisherError("ownership state refused")
            data = json.load(stream)
        if data["version"] != 1 or data["target"] != self.target or data["source"] != self.source:
            raise PublisherError("ownership configuration changed")
        self.source_identity = tuple(data["source_identity"])
        self.roots = data["roots"]
        pairs = [self.source_identity, *self.roots]
        if (any(len(pair) != 2 or any(type(value) is not int or value < 0 for value in pair) for pair in pairs)
                or len(self.roots) not in (0, 2) or data["sites"] and not self.roots):
            raise PublisherError("ownership root binding refused")
        for name, saved in data["sites"].items():
            if not eligible(name) or name == "_images" or "/" in name or not name:
                raise PublisherError("ownership site name refused")
            token = str(uuid.UUID(saved["token"]))
            self.sites[name] = Site(token, saved["identity"], saved["deleting"])

    def save(self) -> None:
        data = {
            "version": 1, "target": self.target, "source": self.source,
            "source_identity": self.source_identity, "roots": self.roots,
            "sites": {name: {"token": site.token, "identity": site.identity, "deleting": site.deleting}
                      for name, site in self.sites.items()},
        }
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".ownership-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def add_site(self, name: str) -> Site:
        self.sites[name] = Site(str(uuid.uuid4()))
        self.save()
        return self.sites[name]
