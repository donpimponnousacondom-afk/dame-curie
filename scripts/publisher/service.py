import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event

from .common import RemoteFailure, ScanIncomplete
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

    def take(self, now: float, prefer_background: bool = False) -> str | None:
        name = None
        candidate = min(self.dirty, key=lambda key: self.dirty[key][1], default=None)
        ready = candidate is not None and self.dirty[candidate][1] <= now
        if ready and not (prefer_background and self.background):
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
        self.stopped = Event()
        self.next_rescan = 0.0
        self.audit_pending = False
        self.audit_due = 0.0
        self.audit_reported = False
        self.background_turn = True
        self.force: set[str] = set()
        self.retry: set[str] = set()

    def inventory(self) -> None:
        if not self.audit_pending:
            self.audit_due = time.monotonic()
        self.audit_pending = True
        self.next_rescan = float("inf")

    def observe(self) -> None:
        self.watcher.wait(0.05)
        if self.watcher.topology:
            self.watcher.rebuild(self.watcher.root_identity)
        self.pending.changed(self.watcher.take_changes(), time.monotonic())
        if self.watcher.overflow or time.monotonic() >= self.next_rescan:
            self.inventory()
            self.watcher.overflow = False

    def complete(self, active: Future, name: str | None) -> None:
        error = active.exception()
        if name is None:
            self.next_rescan = time.monotonic() + self.mirror.config.rescan_seconds
            if isinstance(error, (RemoteFailure, ScanIncomplete)):
                print(f"publisher: remote check failed: {error}; retry on next scan", file=sys.stderr)
            else:
                repairs = active.result()
                self.force.update(repairs | self.retry)
                self.pending.rescan(repairs | self.retry)
                self.retry.clear()
                for site, failure in self.mirror.inventory_errors.items():
                    print(f"publisher: site={site!r}: local scan: {failure}; retry on next scan", file=sys.stderr)
                if not self.audit_reported or repairs or self.mirror.inventory_hashed:
                    print(f"publisher: remote check: sites={self.mirror.inventory_count} "
                          f"content_checked={self.mirror.inventory_hashed} repairs={len(repairs)}; "
                          "unchanged checks are quiet", file=sys.stderr)
                self.audit_reported = True
        elif isinstance(error, (RemoteFailure, ScanIncomplete)):
            self.retry.add(name)
            print(f"publisher: site={name!r}: {error}; retry on next scan", file=sys.stderr)
        elif active.result():
            print(f"publisher: site={name!r}: changes synchronized", file=sys.stderr)

    def run(self) -> None:
        while not self.stopped.is_set() and not self.watcher.rebuild(self.mirror.state.source_identity or self.watcher.root_identity):
            self.watcher.wait(0.05)
        if self.stopped.is_set():
            return
        if not self.mirror.state.source_identity:
            self.mirror.state.source_identity = self.watcher.root_identity
            self.mirror.state.save()
        self.inventory()
        active: Future | None = None
        active_name: str | None = None
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="publisher-transfer") as worker:
            while not self.stopped.is_set():
                self.observe()
                if active is not None and active.done():
                    self.complete(active, active_name)
                    active = None
                if active is None:
                    overdue = time.monotonic() - self.audit_due >= self.mirror.config.rescan_seconds
                    if self.audit_pending and (not self.pending.dirty or overdue):
                        self.audit_pending = False
                        active_name = None
                        active = worker.submit(self.mirror.inventory)
                    else:
                        name = self.pending.take(time.monotonic(), prefer_background=self.background_turn)
                        if name is not None:
                            self.background_turn = not self.background_turn
                            active_name = name
                            force = name in self.force
                            self.force.discard(name)
                            active = worker.submit(self.mirror.reconcile_site, name, force=force)
            if active is not None:
                self.complete(active, active_name)
