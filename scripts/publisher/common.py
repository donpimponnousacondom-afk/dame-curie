import os
import stat
from contextlib import contextmanager
from pathlib import Path


MARKER = ".curie-publisher-owner"
EXCLUDED = frozenset({"_data", "_build", ".env", ".git", MARKER, ".publisher-link"})
CREDENTIAL_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----", b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----", b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN DSA PRIVATE KEY-----", b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
)
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class PublisherError(Exception):
    pass


class ScanIncomplete(PublisherError):
    pass


class RemoteFailure(PublisherError):
    pass


def eligible(name: str, *, top_level: bool = True) -> bool:
    return not (
        name in EXCLUDED or name.startswith(".curie-publisher-claim-")
        or top_level and name.startswith(".")
    )


def fingerprint(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
        value.st_size, value.st_mtime_ns, value.st_ctime_ns,
    )


def identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


@contextmanager
def directory(path: Path):
    fd = os.open("/", DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def private_directory(path: Path) -> None:
    with directory(path) as fd:
        value = os.fstat(fd)
        if value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) & 0o077:
            raise PublisherError("private directory permissions refused")


def absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise PublisherError("absolute normalized path required")
    return path
