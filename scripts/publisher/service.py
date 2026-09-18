import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event

from .common import ScanIncomplete, directory, identity
from .mirror import Mirror
from .watch import Watcher


class Pending:
    def __init__(self, settle_seconds: float, max_wait: float):
        self.settle_seconds = settle_seconds
        self.max_wait = max_wait
        self.dirty: dict[str, tuple[float, float]] = {}
        self.background: dict[str, None] = {}

    def changed(self, names: set[str], now: float) -> None:
        for name in names:
            first = self.dirty.get(name, (now, now))[0]
            self.dirty[name] = (first, min(now + self.settle_seconds, first + self.max_wait))
            self.background.pop(name, None)

    def rescan(self, names: set[str]) -> None:
        for name in sorted(names):
            if name not in self.dirty:
                self.background.setdefault(name, None)

    def take(self, now: float) -> str | None:
        name = None
        if self.dirty:
            candidate = min(self.dirty, key=lambda key: self.dirty[key][1])
            if self.dirty[candidate][1] <= now:
                name = candidate
                del self.dirty[name]
        elif self.background:
            name = next(iter(self.background))
            del self.background[name]
        return name


class Publisher:
    def __init__(self, mirror: Mirror, watcher: Watcher):
        self.mirror = mirror
        self.watcher = watcher
        self.pending = Pending(mirror.config.settle_seconds, mirror.config.rescan_seconds)
        self.known = set(mirror.state.sites)
        self.stopped = Event()
        self.next_rescan = 0.0

    def inventory(self) -> None:
        with directory(self.mirror.config.source) as root:
            if identity(os.fstat(root)) != self.watcher.root_identity:
                raise ScanIncomplete("source root replacement refused")
            names = set(os.listdir(root))
        names = {name for name in names if self.watcher.scanner.allowed(Path(name))}
        self.pending.rescan(self.known | names)
        self.known = names
        self.next_rescan = time.monotonic() + self.mirror.config.rescan_seconds

    def observe(self) -> None:
        self.watcher.wait(0.05)
        if self.watcher.topology:
            self.watcher.rebuild(self.watcher.root_identity)
        changes = self.watcher.take_changes()
        self.known.update(changes)
        self.pending.changed(changes, time.monotonic())
        if self.watcher.overflow or time.monotonic() >= self.next_rescan:
            self.inventory()
            self.watcher.overflow = False

    def run(self) -> None:
        while not self.stopped.is_set() and not self.watcher.rebuild(self.mirror.state.source_identity or self.watcher.root_identity):
            self.watcher.wait(0.05)
        if self.stopped.is_set():
            return
        if not self.mirror.state.source_identity:
            self.mirror.state.source_identity = self.watcher.root_identity
            self.mirror.state.save()
        self.inventory()
        active: Future[None] | None = None
        active_name = ""
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="publisher-transfer") as worker:
            while not self.stopped.is_set():
                self.observe()
                if active is not None and active.done():
                    error = active.exception()
                    if not (isinstance(error, ScanIncomplete) and active_name in self.pending.dirty):
                        active.result()
                    active = None
                if active is None:
                    name = self.pending.take(time.monotonic())
                    if name is not None:
                        active_name = name
                        active = worker.submit(self.mirror.reconcile_site, name)
            if active is not None:
                active.result()
