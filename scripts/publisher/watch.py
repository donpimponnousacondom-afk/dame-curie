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

    def create(self) -> int:
        fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            raise OSError(ctypes.get_errno(), "inotify initialization failed")
        return fd

    def close(self) -> None:
        os.close(self.fd)

    def add(self, inotify_fd: int, directory_fd: int) -> None:
        path = os.fsencode(f"/proc/self/fd/{directory_fd}")
        if self.libc.inotify_add_watch(inotify_fd, path, MASK) < 0:
            raise OSError(ctypes.get_errno(), "inotify registration failed")

    def tree(self, inotify_fd: int, directory_fd: int, path: Path) -> None:
        self.add(inotify_fd, directory_fd)
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
                self.tree(inotify_fd, child, child_path)
            finally:
                os.close(child)

    def rebuild(self, expected_root: tuple[int, ...] = ()) -> None:
        replacement = self.create()
        try:
            with directory(self.config.source.parent) as parent:
                self.add(replacement, parent)
            with directory(self.config.source) as root:
                if expected_root and identity(os.fstat(root)) != expected_root:
                    raise ScanIncomplete("source root replacement refused")
                self.tree(replacement, root, Path("."))
            self.dirty = self.drain() or self.dirty
        except (OSError, PublisherError):
            os.close(replacement)
            raise
        os.close(self.fd)
        self.fd = replacement

    def decode(self, block: bytes) -> bool:
        offset = 0
        while offset < len(block):
            _, mask, _, length = EVENT.unpack_from(block, offset)
            self.overflow = self.overflow or bool(mask & IN_Q_OVERFLOW)
            offset += EVENT.size + length
        return bool(block)

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
