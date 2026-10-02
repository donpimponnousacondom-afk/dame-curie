import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from .common import (
    DIRECTORY_FLAGS, FILE_FLAGS, ScanIncomplete,
    directory, eligible, fingerprint, identity,
)


IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
CHUNK_SIZE = 1024 * 1024


class BlobStore:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir(mode=0o700, exist_ok=True)

    def capture(self, fd: int, before: os.stat_result) -> str:
        digest = hashlib.sha256()
        while block := os.read(fd, CHUNK_SIZE):
            digest.update(block)
        if fingerprint(os.fstat(fd)) != fingerprint(before):
            raise ScanIncomplete("source changed during scan")
        name = digest.hexdigest()
        target = self.path / name
        if not target.exists():
            self.copy(fd, before, target, name)
        return name

    def copy(self, fd: int, before: os.stat_result, target: Path, digest: str) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        temporary_fd, temporary = tempfile.mkstemp(dir=self.path, prefix=".scan-")
        try:
            copied = hashlib.sha256()
            with os.fdopen(temporary_fd, "wb") as output:
                while block := os.read(fd, CHUNK_SIZE):
                    copied.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if copied.hexdigest() != digest or fingerprint(os.fstat(fd)) != fingerprint(before):
                raise ScanIncomplete("source changed during staging")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


@dataclass
class Snapshot:
    root_identity: tuple[int, int]
    present: set[str] = field(default_factory=set)
    sites: set[str] = field(default_factory=set)
    directories: set[Path] = field(default_factory=set)
    files: dict[Path, str] = field(default_factory=dict)
    signatures: dict[Path, tuple[int, ...]] = field(default_factory=dict)


class Scanner:
    def __init__(
        self, source: Path, blobs: BlobStore, private_paths: tuple[Path, ...] = (),
        *, marker_namespace: str = "dame-curie",
    ):
        self.source = source
        self.blobs = blobs
        self.private_paths = private_paths
        self.marker_namespace = marker_namespace

    def allowed(self, path: Path) -> bool:
        absolute = self.source / path
        return eligible(
            path.name, top_level=path.parent == Path("."), marker_namespace=self.marker_namespace,
        ) and not any(absolute.is_relative_to(private) for private in self.private_paths)

    def file(self, parent: int, path: Path, value: os.stat_result, result: Snapshot, copy: bool) -> None:
        if value.st_nlink != 1:
            raise ScanIncomplete("hardlinked source refused")
        fd = os.open(path.name, FILE_FLAGS, dir_fd=parent)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or fingerprint(opened) != fingerprint(value):
                raise ScanIncomplete("source identity changed")
            result.signatures[path] = fingerprint(opened)
            if copy:
                result.files[path] = self.blobs.capture(fd, opened)
        finally:
            os.close(fd)

    def walk(self, fd: int, path: Path, result: Snapshot, copy: bool) -> None:
        before = os.fstat(fd)
        result.signatures[path] = fingerprint(before)
        names = os.listdir(fd)
        image_stems = self.image_stems(fd, names) if path == Path("_images") else set()
        if path == Path("."):
            result.present.update(names)
        for name in sorted(names):
            child = path / name
            if not self.allowed(child):
                continue
            value = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if path == Path("_images") and not self.archive_file(name, image_stems, value):
                continue
            if stat.S_ISDIR(value.st_mode):
                self.descend(fd, child, value, result, copy)
            elif stat.S_ISREG(value.st_mode) and path != Path("."):
                self.file(fd, child, value, result, copy)
        if fingerprint(os.fstat(fd)) != fingerprint(before) or sorted(os.listdir(fd)) != sorted(names):
            raise ScanIncomplete("directory changed during scan")

    def descend(self, parent: int, path: Path, value: os.stat_result, result: Snapshot, copy: bool) -> None:
        if path.parent == Path(".") and path.name != "_images":
            result.sites.add(path.name)
        child = os.open(path.name, DIRECTORY_FLAGS, dir_fd=parent)
        try:
            if fingerprint(os.fstat(child)) != fingerprint(value):
                raise ScanIncomplete("directory identity changed")
            result.directories.add(path)
            self.walk(child, path, result, copy)
        finally:
            os.close(child)

    def image_stems(self, fd: int, names: list[str]) -> set[str]:
        stems = set()
        for name in names:
            if not self.allowed(Path("_images") / name) or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            value = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISREG(value.st_mode) and value.st_nlink == 1:
                stems.add(Path(name).stem)
        return stems

    def archive_file(self, name: str, stems: set[str], value: os.stat_result) -> bool:
        path = Path(name)
        is_sidecar = path.suffix == ".txt" and path.stem in stems
        return stat.S_ISREG(value.st_mode) and (path.suffix.lower() in IMAGE_SUFFIXES or is_sidecar)

    def collect(self, copy: bool, expected_root: tuple[int, ...]) -> Snapshot:
        with directory(self.source) as fd:
            result = Snapshot(identity(os.fstat(fd)))
            if expected_root and result.root_identity != expected_root:
                raise ScanIncomplete("source root replacement refused")
            self.walk(fd, Path("."), result, copy)
        return result

    def collect_site(self, name: str, copy: bool, expected_root: tuple[int, ...]) -> Snapshot:
        path = Path(name)
        if not name or path.name != name or not self.allowed(path):
            raise ScanIncomplete("site name refused")
        with directory(self.source) as fd:
            result = Snapshot(identity(os.fstat(fd)))
            if expected_root and result.root_identity != expected_root:
                raise ScanIncomplete("source root replacement refused")
            if name in os.listdir(fd):
                value = os.stat(name, dir_fd=fd, follow_symlinks=False)
                result.present.add(name)
                result.signatures[path] = fingerprint(value)
                if stat.S_ISDIR(value.st_mode):
                    self.descend(fd, path, value, result, copy)
        return result

    def scan_site(self, name: str, expected_root: tuple[int, ...] = (), *, copy: bool = True) -> Snapshot:
        return self.scan(expected_root, name=name, copy=copy)

    def scan(self, expected_root: tuple[int, ...] = (), *, name: str | None = None, copy: bool = True) -> Snapshot:
        collect = self.collect if name is None else partial(self.collect_site, name)
        try:
            first = collect(copy, expected_root)
            second = collect(False, expected_root)
        except OSError:
            raise ScanIncomplete("source unavailable or changed") from None
        if expected_root and first.root_identity != expected_root:
            raise ScanIncomplete("source root replacement refused")
        if (
            first.root_identity != second.root_identity or first.signatures != second.signatures
            or first.present != second.present or first.sites != second.sites
        ):
            raise ScanIncomplete("source changed during complete scan")
        images = {path.stem for path in first.files if path.parent == Path("_images") and path.suffix != ".txt"}
        first.files = {
            path: digest for path, digest in first.files.items()
            if path.parent != Path("_images") or path.suffix != ".txt" or path.stem in images
        }
        return first
