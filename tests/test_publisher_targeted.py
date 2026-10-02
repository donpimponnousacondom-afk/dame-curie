import json
import os
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.publisher.common import PublisherError, RemoteFailure, ScanIncomplete
from scripts.publisher.config import Config
from scripts.publisher.mirror import Mirror
from scripts.publisher.state import State
from test_publisher_remote import LocalSSH


class PublisherTargetedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("public", "stage", "state", "remote sites", "remote images"):
            (self.root / name).mkdir(mode=0o700)
        self.config = Config(
            source=self.root / "public", staging=self.root / "stage", state=self.root / "state",
            key=self.root / "key", known_hosts=self.root / "known_hosts",
            host="static.example.invalid", user="publisher",
            site_root=str(self.root / "remote sites"), image_root=str(self.root / "remote images"),
        )
        self.state = State(self.config)
        self.addCleanup(self.state.close)
        self.transport = LocalSSH(self.config)
        self.mirror = Mirror(self.config, self.state, self.transport)
        self.remote = Path(self.config.site_root)

    def put(self, name, content=b"synthetic"):
        path = self.config.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def actions(self):
        commands = self.transport.commands
        return [json.loads(shlex.split(argv[-1] if argv[0] == "ssh" else argv[argv.index("--rsync-path") + 1])[-1])["action"] for argv in commands]

    def test_selected_scope_does_not_read_other_sites(self):
        self.put("site/index.html", b"publishable")
        self.put("other/private.txt", b"outside selected scope")
        with patch("scripts.publisher.scan.os.open", wraps=os.open) as opened:
            self.mirror.reconcile_site("site")
        self.assertTrue({"other", "private.txt"}.isdisjoint(Path(call.args[0]).name for call in opened.call_args_list))
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"publishable")
        self.assertFalse((self.remote / "other").exists())
        self.assertEqual(self.actions(), ["probe", "claim", "site"])

    def test_unchanged_scope_skips_hashing_and_transport(self):
        self.put("site/index.html")
        self.mirror.reconcile_site("site")
        self.transport.commands.clear()
        with patch.object(self.mirror.staging.blobs, "capture", side_effect=AssertionError("unneeded read")):
            self.mirror.reconcile_site("site")
        self.assertEqual(self.transport.commands, [])

    def test_same_content_updates_metadata_cache_without_transfer(self):
        page = self.put("site/index.html", b"unchanged")
        self.mirror.reconcile_site("site")
        before = page.stat()
        os.utime(page, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
        self.transport.commands.clear()
        self.mirror.reconcile_site("site")
        self.assertEqual(self.transport.commands, [])
        with patch.object(self.mirror.staging.blobs, "capture", side_effect=AssertionError("unneeded read")):
            self.mirror.reconcile_site("site")

    def test_known_site_reuses_binding_without_probe_or_claim(self):
        page = self.put("site/index.html", b"before")
        self.mirror.reconcile_site("site")
        page.write_bytes(b"after")
        self.transport.commands.clear()
        self.mirror.reconcile_site("site")
        self.assertEqual(self.actions(), ["site"])
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"after")

    def test_restored_mtime_does_not_hide_changed_bytes(self):
        page = self.put("site/index.html", b"before")
        self.mirror.reconcile_site("site")
        before = page.stat()
        page.write_bytes(b"after!")
        os.utime(page, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"after!")

    def test_targeted_staging_preserves_other_sites_and_shared_blobs(self):
        page = self.put("a/index.html", b"shared")
        self.put("b/index.html", b"shared")
        self.mirror.reconcile_site("a")
        self.mirror.reconcile_site("b")
        staged = self.mirror.staging.tree / "b/index.html"
        before = staged.stat().st_ino
        page.write_bytes(b"new a")
        self.mirror.reconcile_site("a")
        self.assertEqual(staged.read_bytes(), b"shared")
        self.assertEqual(staged.stat().st_ino, before)
        self.assertEqual(len(list(self.mirror.staging.blobs.path.iterdir())), 2)
        shutil.rmtree(page.parent)
        self.mirror.reconcile_site("a")
        self.assertEqual(staged.read_bytes(), b"shared")
        self.assertEqual(len(list(self.mirror.staging.blobs.path.iterdir())), 1)
        self.assertFalse((self.remote / "a").exists())
        self.assertEqual((self.remote / "b/index.html").read_bytes(), b"shared")

    def test_empty_directory_change_is_not_skipped(self):
        self.put("site/index.html")
        self.mirror.reconcile_site("site")
        empty = self.config.source / "site/empty"
        empty.mkdir()
        self.mirror.reconcile_site("site")
        self.assertTrue((self.remote / "site/empty").is_dir())
        empty.rmdir()
        self.mirror.reconcile_site("site")
        self.assertFalse((self.remote / "site/empty").exists())

    def test_targeted_staging_handles_file_directory_type_changes(self):
        path = self.put("site/item", b"file")
        self.mirror.reconcile_site("site")
        path.unlink()
        self.put("site/item/child", b"nested")
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/item/child").read_bytes(), b"nested")
        shutil.rmtree(path)
        path.write_bytes(b"file again")
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/item").read_bytes(), b"file again")

    def test_symlink_replacement_is_present_not_deletion(self):
        page = self.put("site/index.html")
        self.mirror.reconcile_site("site")
        shutil.rmtree(page.parent)
        page.parent.symlink_to(self.root, target_is_directory=True)
        self.transport.commands.clear()
        self.mirror.reconcile_site("site")
        self.assertEqual(self.transport.commands, [])
        self.assertTrue((self.remote / "site/index.html").exists())
        self.assertIn("site", self.state.sites)

    def test_regular_file_replacement_is_present_not_deletion(self):
        page = self.put("site/index.html")
        self.mirror.reconcile_site("site")
        shutil.rmtree(page.parent)
        page.parent.write_bytes(b"top-level file is not a site")
        self.transport.commands.clear()
        with patch("scripts.publisher.scan.os.read", side_effect=AssertionError("replacement read")) as read:
            self.mirror.reconcile_site("site")
        read.assert_not_called()
        self.assertEqual(self.transport.commands, [])
        self.assertTrue((self.remote / "site/index.html").exists())

    def test_failed_partial_transfer_cannot_leave_previous_success_cache(self):
        page = self.put("site/index.html", b"old")
        self.mirror.reconcile_site("site")
        page.write_bytes(b"new")
        self.transport.fail_action = "site"
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile_site("site")
        (self.remote / "site/index.html").write_bytes(b"partial remote result")
        self.assertNotIn("site", self.mirror.published)
        page.write_bytes(b"old")
        self.transport.fail_action = ""
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"old")

    def test_transfer_mutation_is_not_cached_as_published(self):
        page = self.put("site/index.html", b"before")
        self.transport.after_transfer = lambda: page.write_bytes(b"after")
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"before")
        self.transport.after_transfer = lambda: None
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"after")

    def test_pending_delete_then_recreation_gets_fresh_binding(self):
        page = self.put("site/index.html", b"old")
        self.mirror.reconcile_site("site")
        token = self.state.sites["site"].token
        shutil.rmtree(page.parent)
        self.transport.fail_action = "remove"
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile_site("site")
        self.assertTrue(self.state.sites["site"].deleting)
        self.put("site/index.html", b"recreated")
        self.transport.fail_action = ""
        self.mirror.reconcile_site("site")
        self.assertNotEqual(self.state.sites["site"].token, token)
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"recreated")

    def test_archive_scope_never_deletes_remote_images(self):
        image = self.put("_images/image.png", b"image")
        prompt = self.put("_images/image.txt", b"prompt")
        self.put("_images/orphan.txt", b"not paired")
        self.mirror.reconcile_site("_images")
        image.unlink()
        prompt.unlink()
        self.mirror.reconcile_site("_images")
        images = Path(self.config.image_root)
        self.assertEqual((images / "image.png").read_bytes(), b"image")
        self.assertEqual((images / "image.txt").read_bytes(), b"prompt")
        self.assertFalse((images / "orphan.txt").exists())
        self.assertTrue(all("--delete-delay" not in argv for argv in self.transport.commands))

    def test_selected_scan_keeps_exact_bytes_and_refuses_hardlinks_before_read(self):
        content = b"DISCORD_TOKEN=synthetic-literal\nAuthorization: Bearer $OPENROUTER_API_KEY\n"
        path = self.put("site/file.txt", content)
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/file.txt").read_bytes(), content)
        path.write_bytes(b"ordinary")
        os.link(path, self.root / "alias")
        self.transport.commands.clear()
        with patch.object(self.mirror.staging.blobs, "capture", side_effect=AssertionError("hardlink read")) as capture:
            with self.assertRaisesRegex(ScanIncomplete, "hardlinked source refused"):
                self.mirror.reconcile_site("site")
        capture.assert_not_called()
        self.assertEqual(self.transport.commands, [])
        self.assertEqual((self.remote / "site/file.txt").read_bytes(), content)

    def test_selected_scan_validates_second_pass(self):
        page = self.put("site/index.html", b"before")
        original = self.mirror.scanner.collect_site

        def mutate(name, copy, expected):
            snapshot = original(name, copy, expected)
            if copy:
                page.write_bytes(b"after")
            return snapshot

        with patch.object(self.mirror.scanner, "collect_site", side_effect=mutate):
            with self.assertRaises(ScanIncomplete):
                self.mirror.scanner.scan_site("site")
        self.assertEqual(self.transport.commands, [])

    def test_scoped_scan_rejects_root_replacement_before_content_read(self):
        self.put("site/index.html")
        self.mirror.reconcile_site("site")
        self.config.source.rename(self.root / "old-public")
        self.put("site/index.html", b"replacement")
        with patch.object(self.mirror.staging.blobs, "capture", side_effect=AssertionError("unsafe read")):
            with self.assertRaises(ScanIncomplete):
                self.mirror.reconcile_site("site")

    def test_changed_site_still_refuses_replaced_remote_root(self):
        page = self.put("site/index.html", b"before")
        self.mirror.reconcile_site("site")
        self.remote.rename(self.root / "old-remote")
        self.remote.mkdir()
        page.write_bytes(b"after")
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile_site("site")
        self.assertEqual(list(self.remote.iterdir()), [])

    def test_new_mirror_does_not_trust_previous_success_cache(self):
        self.put("site/index.html")
        self.mirror.reconcile_site("site")
        self.transport.commands.clear()
        replacement = Mirror(self.config, self.state, self.transport)
        replacement.reconcile_site("site")
        self.assertEqual(self.actions(), ["site"])

    def test_full_reconcile_invalidates_targeted_cache(self):
        page = self.put("site/index.html", b"old")
        self.mirror.reconcile_site("site")
        page.write_bytes(b"new")
        self.mirror.reconcile()
        self.assertEqual(self.mirror.published, {})
        page.write_bytes(b"old")
        self.mirror.reconcile_site("site")
        self.assertEqual((self.remote / "site/index.html").read_bytes(), b"old")

    def test_partial_materialize_refuses_cross_scope_snapshot(self):
        self.put("a/index.html")
        self.put("b/index.html")
        snapshot = self.mirror.scanner.scan()
        with self.assertRaises(PublisherError):
            self.mirror.staging.materialize_site("a", snapshot)

    def test_scope_names_cannot_escape_or_select_excluded_paths(self):
        for name in ("", ".", "..", "../outside", "/outside", "_data", ".git"):
            with self.subTest(name=name), self.assertRaises(ScanIncomplete):
                self.mirror.scanner.scan_site(name)
        snapshot = self.mirror.scanner.scan_site("missing")
        for name in ("", ".", "..", "../outside", "/outside"):
            with self.subTest(staging_name=name), self.assertRaises(PublisherError):
                self.mirror.staging.materialize_site(name, snapshot)
        self.assertEqual(self.transport.commands, [])
