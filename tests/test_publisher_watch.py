import errno
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.publisher.common import ScanIncomplete
from scripts.publisher.config import Config
from scripts.publisher.scan import Scanner
from scripts.publisher.staging import Staging
from scripts.publisher.watch import EVENT, IN_MODIFY, IN_Q_OVERFLOW, MASK, Watcher


class PublisherWatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source, stage = self.root / "public", self.root / "stage"
        source.mkdir()
        stage.mkdir(mode=0o700)
        self.config = Config(
            source=source, staging=stage, state=self.root / "state",
            key=self.root / "key", known_hosts=self.root / "known_hosts",
            host="static.example.invalid", user="publisher",
            site_root="/synthetic/sites", image_root="/synthetic/images",
            rescan_seconds=0.1, settle_seconds=0.01,
        )
        self.scanner = Scanner(source, Staging(stage).blobs)
        self.watcher = Watcher(self.config, self.scanner)
        self.addCleanup(self.watcher.close)
        self.watcher.rebuild()
        self.watcher.wait(0)

    def test_real_create_close_write_and_new_directory_events(self):
        site = self.config.source / "new café"
        site.mkdir()
        (site / "index.html").write_bytes(b"created before recursive watch")
        self.assertTrue(self.watcher.wait(1))
        self.watcher.rebuild()
        self.assertIn(Path("new café/index.html"), self.scanner.scan().files)
        self.watcher.wait(0)
        (site / "index.html").write_bytes(b"changed after registration")
        self.assertTrue(self.watcher.wait(1))
        snapshot = self.scanner.scan()
        self.assertIn(Path("new café/index.html"), snapshot.files)

    def test_reads_and_scanner_work_do_not_trigger_own_events(self):
        site = self.config.source / "site"
        site.mkdir()
        page = site / "index.html"
        page.write_bytes(b"read-only")
        self.watcher.rebuild()
        self.watcher.wait(0)
        self.assertEqual(page.read_bytes(), b"read-only")
        self.scanner.scan()
        self.assertFalse(self.watcher.wait(0.02))
        self.assertEqual(MASK & (0x1 | 0x10 | 0x20), 0)

    def test_nested_creation_and_rename_are_reconciled(self):
        site = self.config.source / "site"
        (site / "assets").mkdir(parents=True)
        self.watcher.rebuild()
        self.watcher.wait(0)
        original = site / "assets/temporary"
        original.write_bytes(b"complete")
        original.rename(site / "assets/final.png")
        self.assertTrue(self.watcher.wait(1))
        self.assertIn(Path("site/assets/final.png"), self.scanner.scan().files)
        (site / "assets/final.png").unlink()
        self.assertTrue(self.watcher.wait(1))

    def test_root_replacement_wakes_then_refuses_rebind(self):
        expected = self.scanner.scan().root_identity
        self.config.source.rename(self.root / "old-source")
        self.config.source.mkdir()
        self.assertTrue(self.watcher.wait(1))
        with self.assertRaises(ScanIncomplete):
            self.watcher.rebuild(expected)

    def test_overflow_record_requests_full_reconciliation(self):
        event = EVENT.pack(-1, IN_Q_OVERFLOW, 0, 0)
        self.watcher.dirty = self.watcher.decode(event)
        self.assertTrue(self.watcher.overflow)
        self.assertTrue(self.watcher.wait(0))
        self.watcher.rebuild()
        self.assertEqual(self.scanner.scan().sites, set())

    def test_idle_wait_expires_for_periodic_full_scan(self):
        started = time.monotonic()
        self.assertFalse(self.watcher.wait(0.02))
        self.assertGreaterEqual(time.monotonic() - started, 0.015)

    def test_changes_queued_during_transfer_are_available_immediately(self):
        site = self.config.source / "site"
        site.mkdir()
        self.watcher.rebuild()
        self.watcher.wait(0)
        (site / "after-snapshot.txt").write_bytes(b"arrived during transfer")
        self.assertTrue(self.watcher.wait(0))
        self.watcher.settle()
        self.watcher.rebuild()
        self.assertIn(Path("site/after-snapshot.txt"), self.scanner.scan().files)

    def test_excluded_data_directory_is_not_recursively_watched(self):
        private = self.config.source / "_data"
        private.mkdir()
        self.watcher.rebuild()
        self.watcher.wait(0)
        (private / "synthetic-private").write_bytes(b"not observed")
        self.assertFalse(self.watcher.wait(0.02))

    def test_transient_disappearance_during_rebuild_keeps_old_watches_and_retries(self):
        site = self.config.source / 'site'
        site.mkdir()
        (site / 'transient').write_bytes(b'atomic-save placeholder')
        self.watcher.rebuild()
        old_fd = self.watcher.fd
        original = os.stat

        def disappear(name, *args, **kwargs):
            if name == 'transient':
                raise FileNotFoundError(errno.ENOENT, 'synthetic rename')
            return original(name, *args, **kwargs)

        with patch('scripts.publisher.watch.os.stat', side_effect=disappear):
            self.assertFalse(self.watcher.rebuild(self.watcher.root_identity))
        self.assertEqual(self.watcher.fd, old_fd)
        self.assertTrue(self.watcher.topology)
        (site / 'still-watched').write_bytes(b'after retry request')
        self.assertTrue(self.watcher.wait(1))
        self.assertIn('site', self.watcher.take_changes())
        self.assertTrue(self.watcher.rebuild(self.watcher.root_identity))

    def test_cross_site_rename_marks_both_scopes(self):
        first, second = self.config.source / 'first', self.config.source / 'second'
        first.mkdir()
        second.mkdir()
        (first / 'asset.txt').write_bytes(b'moved')
        self.watcher.rebuild()
        self.watcher.wait(0)
        self.watcher.take_changes()
        (first / 'asset.txt').rename(second / 'asset.txt')
        self.assertTrue(self.watcher.wait(1))
        self.assertEqual(self.watcher.take_changes(), {'first', 'second'})

    def test_source_parent_noise_does_not_queue_a_full_reconciliation(self):
        (self.root / 'unrelated').write_bytes(b'not a site')
        self.watcher.wait(0.1)
        self.assertFalse(self.watcher.overflow)
        self.assertFalse(self.watcher.topology)
        self.assertEqual(self.watcher.take_changes(), set())

    def test_unknown_watch_descriptor_requests_recovery(self):
        self.watcher.decode(EVENT.pack(999999, IN_MODIFY, 0, 0))
        self.assertTrue(self.watcher.overflow)
        self.assertTrue(self.watcher.topology)

    def test_old_descriptor_events_keep_their_paths_during_rebuild(self):
        site = self.config.source / 'original'
        site.mkdir()
        self.watcher.rebuild()
        self.watcher.wait(0)
        self.watcher.take_changes()
        (site / 'queued-before-swap').write_bytes(b'queued')
        self.watcher.rebuild()
        self.assertIn('original', self.watcher.take_changes())

    def test_new_directory_rebuild_registers_immediate_descendant_writes(self):
        nested = self.config.source / 'new-site' / 'assets'
        nested.mkdir(parents=True)
        (nested / 'early.txt').write_bytes(b'before registration')
        self.assertTrue(self.watcher.wait(1))
        self.assertTrue(self.watcher.topology)
        self.watcher.rebuild()
        self.assertIn('new-site', self.watcher.take_changes())
        self.watcher.wait(0)
        self.watcher.take_changes()
        (nested / 'late.txt').write_bytes(b'after registration')
        self.assertTrue(self.watcher.wait(1))
        self.assertEqual(self.watcher.take_changes(), {'new-site'})

    def test_symlink_directory_is_not_followed_by_watcher(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.config.source / "alias").symlink_to(outside, target_is_directory=True)
        self.watcher.rebuild()
        self.watcher.wait(0)
        (outside / "ignored").write_bytes(b"synthetic")
        self.assertFalse(self.watcher.wait(0.02))
