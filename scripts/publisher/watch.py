import ctypes
import errno
import os
import select
import stat
import struct
import time
from pathlib import Path

from .common import DIRECTORY_FLAGS, PublisherError, ScanIncomplete, directory, fingerprint, identity
from .config import Config
from .scan import Scanner


IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
IN_ISDIR = 0x40000000
IN_ONLYDIR = 0x01000000
MASK = (IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO
        | IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF | IN_ONLYDIR)
EVENT = struct.Struct("iIII")


class Watcher:
    def __init__(self, config: Config, scanner: Scanner):
        self.config = config
        self.scanner = scanner
        self.libc = ctypes.CDLL("libc.so.6", use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.fd = self.create()
        self.overflow = False
        self.dirty = False
        self.paths: dict[int, Path] = {}
        self.changes: set[str] = set()
        self.topology = False
        self.coverage_lost = False
        self.root_identity: tuple[int, ...] = ()

    def create(self) -> int:
        fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            raise OSError(ctypes.get_errno(), "inotify initialization failed")
        return fd

    def close(self) -> None:
        os.close(self.fd)

    def add(self, inotify_fd: int, directory_fd: int, path: Path, paths: dict[int, Path]) -> None:
        descriptor = self.libc.inotify_add_watch(inotify_fd, os.fsencode(f"/proc/self/fd/{directory_fd}"), MASK)
        if descriptor < 0:
            raise OSError(ctypes.get_errno(), "inotify registration failed")
        paths[descriptor] = path

    def tree(self, inotify_fd: int, directory_fd: int, path: Path, paths: dict[int, Path]) -> None:
        self.add(inotify_fd, directory_fd, path, paths)
        if path == Path("_images"):
            return
        for name in os.listdir(directory_fd):
            child_path = path / name
            if not self.scanner.allowed(child_path):
                continue
            value = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if not stat.S_ISDIR(value.st_mode):
                continue
            child = os.open(name, DIRECTORY_FLAGS, dir_fd=directory_fd)
            try:
                if fingerprint(os.fstat(child)) != fingerprint(value):
                    raise ScanIncomplete("watch tree changed")
                self.tree(inotify_fd, child, child_path, paths)
            finally:
                os.close(child)

    def rebuild(self, expected_root: tuple[int, ...] = ()) -> bool:
        replacement = self.create()
        paths: dict[int, Path] = {}
        root_identity = expected_root or self.root_identity
        self.topology = False
        try:
            with directory(self.config.source.parent) as parent:
                self.add(replacement, parent, Path(".."), paths)
            with directory(self.config.source) as root:
                root_identity = identity(os.fstat(root))
                if expected_root and root_identity != expected_root:
                    raise ScanIncomplete("source root replacement refused")
                self.tree(replacement, root, Path("."), paths)
            self.dirty = self.drain() or self.dirty
        except (OSError, PublisherError) as error:
            os.close(replacement)
            transient = isinstance(error, OSError) and error.errno in (errno.ENOENT, errno.ENOTDIR)
            if transient or isinstance(error, ScanIncomplete) and str(error) == "watch tree changed":
                with directory(self.config.source) as root:
                    current = identity(os.fstat(root))
                if root_identity and current != root_identity:
                    raise ScanIncomplete("source root replacement refused") from None
                self.root_identity = current
                self.topology = self.coverage_lost = True
                return False
            raise
        os.close(self.fd)
        self.fd, self.paths = replacement, paths
        self.root_identity = root_identity
        self.overflow = self.overflow or self.coverage_lost
        self.coverage_lost = False
        return True

    def decode(self, block: bytes) -> bool:
        offset = 0
        while offset < len(block):
            descriptor, mask, _, length = EVENT.unpack_from(block, offset)
            start = offset + EVENT.size
            name = os.fsdecode(block[start:start + length].split(b"\0", 1)[0])
            offset = start + length
            self.record(descriptor, mask, name)
        return bool(block)

    def record(self, descriptor: int, mask: int, name: str) -> None:
        path = self.paths.get(descriptor)
        if mask & IN_Q_OVERFLOW or path is None:
            self.overflow = self.topology = True
        elif path == Path(".."):
            if name == self.config.source.name or not name:
                self.overflow = self.topology = True
        else:
            relative = path / name if name else path
            if relative == Path("."):
                self.overflow = self.topology = True
            elif self.scanner.allowed(relative):
                self.changes.add(relative.parts[0])
                self.topology = self.topology or bool(mask & (IN_ISDIR | IN_DELETE_SELF | IN_MOVE_SELF | IN_IGNORED))
        if mask & IN_IGNORED:
            self.paths.pop(descriptor, None)

    def take_changes(self) -> set[str]:
        changes, self.changes = self.changes, set()
        return changes

    def drain(self) -> bool:
        changed = False
        while True:
            try:
                block = os.read(self.fd, 256 * 1024)
            except BlockingIOError as error:
                if error.errno != errno.EAGAIN:
                    raise
                break
            changed = self.decode(block) or changed
        return changed

    def wait(self, timeout: float) -> bool:
        ready = self.dirty or bool(select.select([self.fd], [], [], timeout)[0])
        self.dirty = False
        return self.drain() or ready

    def settle(self) -> None:
        deadline = time.monotonic() + self.config.rescan_seconds
        while time.monotonic() < deadline:
            remaining = min(self.config.settle_seconds, deadline - time.monotonic())
            if not self.wait(max(0.0, remaining)):
                break
