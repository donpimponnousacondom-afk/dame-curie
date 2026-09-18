import errno
import json
import shlex
import shutil
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from scripts.publisher.common import RemoteFailure, ScanIncomplete
from scripts.publisher.config import Config
from scripts.publisher.mirror import Mirror
from scripts.publisher.service import Pending, Publisher
from scripts.publisher.state import State
from scripts.publisher.watch import Watcher
from test_publisher_remote import LocalSSH


class PendingTests(unittest.TestCase):
    def test_dirty_site_preempts_background_after_its_own_debounce(self):
        pending = Pending(0.3, 30)
        pending.rescan({'a-background', 'b-background'})
        pending.changed({'z-dirty'}, 10)
        self.assertIsNone(pending.take(10.2))
        self.assertEqual(pending.take(10.31), 'z-dirty')
        self.assertEqual(pending.take(10.31), 'a-background')

    def test_events_during_active_job_remain_queued_for_another_pass(self):
        pending = Pending(0.3, 30)
        pending.changed({'site'}, 10)
        self.assertEqual(pending.take(10.31), 'site')
        pending.changed({'site'}, 10.4)
        self.assertIsNone(pending.take(10.6))
        self.assertEqual(pending.take(10.71), 'site')

    def test_noisy_site_does_not_postpone_other_sites_or_wait_forever(self):
        pending = Pending(0.3, 1)
        pending.changed({'noisy', 'quiet'}, 10)
        pending.changed({'noisy'}, 10.2)
        self.assertEqual(pending.take(10.31), 'quiet')
        pending.changed({'noisy'}, 10.49)
        pending.changed({'noisy'}, 10.78)
        pending.changed({'noisy'}, 10.99)
        self.assertEqual(pending.take(11.01), 'noisy')

    def test_periodic_discovery_does_not_reset_dirty_deadline(self):
        pending = Pending(0.3, 30)
        pending.changed({'site'}, 10)
        pending.rescan({'site', 'other'})
        self.assertEqual(pending.take(10.31), 'site')
        self.assertEqual(pending.take(10.31), 'other')


class ControlledSSH(LocalSSH):
    def __init__(self, config):
        super().__init__(config)
        self.blocked = Event()
        self.release = Event()
        self.changed_published = Event()
        self.new_site_published = Event()
        self.synced = []
        self.block_name = ''

    def execute(self, argv, capture):
        command = argv[-1] if capture else argv[argv.index('--rsync-path') + 1]
        request = json.loads(shlex.split(command)[-1])
        if not capture and request['name'] == self.block_name and not self.blocked.is_set():
            self.blocked.set()
            if not self.release.wait(5):
                raise RuntimeError('test did not release blocked transfer')
        result = super().execute(argv, capture)
        if not capture:
            name = request['name']
            self.synced.append(name)
            target = Path(self.config.site_root) / name / 'index.html'
            if name == 'b-new':
                self.new_site_published.set()
            if name == 'a-blocked' and target.read_bytes() == b'updated during transfer':
                self.changed_published.set()
        return result


class PublisherServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('public', 'stage', 'state', 'remote', 'images'):
            (self.root / name).mkdir(mode=0o700)
        config = Config(
            source=self.root / 'public', staging=self.root / 'stage', state=self.root / 'state',
            key=self.root / 'key', known_hosts=self.root / 'known_hosts',
            host='synthetic.invalid', user='publisher', site_root=str(self.root / 'remote'),
            image_root=str(self.root / 'images'), settle_seconds=0.02, rescan_seconds=30,
        )
        self.state = State(config)
        self.addCleanup(self.state.close)
        self.transport = ControlledSSH(config)
        self.mirror = Mirror(config, self.state, self.transport)
        self.watcher = Watcher(config, self.mirror.scanner)
        self.addCleanup(self.watcher.close)
        self.publisher = Publisher(self.mirror, self.watcher)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(self.executor.shutdown, wait=True)
        self.addCleanup(self.publisher.stopped.set)
        self.addCleanup(self.transport.release.set)

    def put(self, relative, content=b'initial'):
        path = self.root / 'public' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_watcher_observes_new_site_and_repeat_edit_while_transfer_is_blocked(self):
        page = self.put('a-blocked/index.html')
        self.put('z-background/index.html')
        self.transport.block_name = 'a-blocked'
        observed = Event()
        seen = set()
        original = self.watcher.take_changes

        def take_changes():
            changes = original()
            seen.update(changes)
            if {'a-blocked', 'b-new'} <= seen:
                observed.set()
            return changes

        with patch.object(self.watcher, 'take_changes', side_effect=take_changes):
            task = self.executor.submit(self.publisher.run)
            self.assertTrue(self.transport.blocked.wait(2))
            started = time.monotonic()
            page.write_bytes(b'updated during transfer')
            self.put('b-new/index.html', b'new before registration')
            self.assertTrue(observed.wait(0.5))
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertFalse(self.transport.new_site_published.is_set())
            self.transport.release.set()
            self.assertTrue(self.transport.new_site_published.wait(2))
            self.assertTrue(self.transport.changed_published.wait(2))
            self.publisher.stopped.set()
            task.result(timeout=2)
        self.assertEqual((self.root / 'remote/b-new/index.html').read_bytes(), b'new before registration')
        if 'z-background' in self.transport.synced:
            self.assertLess(self.transport.synced.index('b-new'), self.transport.synced.index('z-background'))

    def test_overflow_inventory_removes_site_created_between_periodic_inventories(self):
        self.watcher.rebuild()
        self.publisher.inventory()
        page = self.put('event-only/index.html')
        self.publisher.observe()
        self.assertEqual(self.publisher.pending.take(time.monotonic() + 1), 'event-only')
        self.mirror.reconcile_site('event-only')
        shutil.rmtree(page.parent)
        self.watcher.wait(0)
        self.watcher.take_changes()
        self.publisher.inventory()
        name = self.publisher.pending.take(time.monotonic() + 1)
        self.assertEqual(name, 'event-only')
        self.mirror.reconcile_site(name)
        self.assertFalse((self.root / 'remote/event-only').exists())

    def test_watch_retry_catches_edits_made_before_new_directory_registration(self):
        self.put('initial/index.html')
        startup = Event()
        registration = Event()
        self.addCleanup(registration.set)
        original_tree = self.watcher.tree
        original_rebuild = self.watcher.rebuild

        def tree(fd, directory_fd, path, paths):
            if path == Path('b-new') and not registration.is_set():
                raise FileNotFoundError(errno.ENOENT, 'synthetic registration race')
            original_tree(fd, directory_fd, path, paths)

        def rebuild(expected=()):
            result = original_rebuild(expected)
            if result:
                startup.set()
            return result

        with patch.object(self.watcher, 'tree', side_effect=tree), patch.object(self.watcher, 'rebuild', side_effect=rebuild):
            task = self.executor.submit(self.publisher.run)
            self.assertTrue(startup.wait(2))
            page = self.put('b-new/index.html', b'first version')
            self.assertTrue(self.transport.new_site_published.wait(2))
            self.transport.new_site_published.clear()
            page.write_bytes(b'edited while directory was unwatched')
            registration.set()
            self.assertTrue(self.transport.new_site_published.wait(2))
            self.publisher.stopped.set()
            task.result(timeout=2)
        self.assertEqual((self.root / 'remote/b-new/index.html').read_bytes(), b'edited while directory was unwatched')

    def test_worker_error_reaches_service_owner_instead_of_silently_dying(self):
        self.put('site/index.html')
        self.transport.fail_action = 'site'
        task = self.executor.submit(self.publisher.run)
        with self.assertRaises(RemoteFailure):
            task.result(timeout=2)

    def test_root_replacement_fails_closed_with_worker_active(self):
        self.put('a-blocked/index.html')
        self.transport.block_name = 'a-blocked'
        task = self.executor.submit(self.publisher.run)
        self.assertTrue(self.transport.blocked.wait(2))
        (self.root / 'public').rename(self.root / 'old-public')
        (self.root / 'public').mkdir()
        self.transport.release.set()
        with self.assertRaises(ScanIncomplete):
            task.result(timeout=2)
