import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.publisher.common import ScanIncomplete
from scripts.publisher.scan import CHUNK_SIZE, Scanner
from scripts.publisher.staging import Staging


class PublisherScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "public"
        self.source.mkdir()
        stage = self.root / "stage"
        stage.mkdir(mode=0o700)
        self.staging = Staging(stage)
        self.scanner = Scanner(self.source, self.staging.blobs)

    def put(self, name, content=b"synthetic"):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_recursive_sites_and_flat_archive_keep_exact_bytes(self):
        self.put("café ' $;[]/index.html", b"<script src='/unchanged.js'></script>")
        self.put("café ' $;[]/backend.py", b"print('static download only')")
        self.put("café ' $;[]/assets/image.png", b"bundled")
        self.put("_images/été $';.png", b"original-image")
        self.put("_images/été $';.txt", "exact prompt\n下一行".encode())
        self.put("_images/orphan.txt")
        self.put("_images/nested/no.png")
        self.put("index.html", b"root is not a site")
        snapshot = self.scanner.scan()
        self.staging.materialize(snapshot)
        self.assertEqual(snapshot.sites, {"café ' $;[]"})
        self.assertEqual(len(snapshot.files), 5)
        for relative in snapshot.files:
            self.assertEqual((self.staging.tree / relative).read_bytes(), (self.source / relative).read_bytes())
        self.assertFalse((self.staging.tree / "_images/orphan.txt").exists())
        self.assertFalse((self.staging.tree / "_images/nested").exists())

    def test_exclusions_do_not_open_private_or_special_entries(self):
        self.put("site/index.html")
        files = (".env", ".dame-curie-publisher-owner", ".publisher-link")
        directories = ("_data", "_build", ".git", ".dame-curie-publisher-claim-synthetic")
        for name in files:
            self.put("site/" + name, b"excluded file")
        for name in directories:
            self.put(f"site/{name}/blocked", b"excluded subtree")
        private = self.root / "outside"
        private.write_bytes(b"symlink target")
        (self.source / "site/link").symlink_to(private)
        (self.source / "site/linkdir").symlink_to(self.root, target_is_directory=True)
        os.mkfifo(self.source / "site/pipe")
        legacy_files = {Path("site/.curie-publisher-owner"), Path("site/.curie-publisher-claim-synthetic/legacy-child")}
        for path in legacy_files:
            self.put(str(path), b"legacy internal name")
        for namespace in ("dame-curie", "curie"):
            self.scanner.marker_namespace = namespace
            expected = {Path("site/index.html")}
            excluded = {*files, *directories, "blocked", "outside", "link", "linkdir", "pipe"}
            if namespace == "dame-curie":
                expected.update(legacy_files)
            else:
                excluded.update({".curie-publisher-owner", ".curie-publisher-claim-synthetic", "legacy-child"})
            with self.subTest(namespace=namespace), patch("scripts.publisher.scan.os.open", wraps=os.open) as opened:
                self.assertEqual(set(self.scanner.scan().files), expected)
                self.assertTrue(excluded.isdisjoint(Path(call.args[0]).name for call in opened.call_args_list))

    def test_public_data_config_and_other_ordinary_site_names_are_mirrored(self):
        names = {"data", "config", "credentials", "secrets", "node_modules", "venv", "registry.json", "public.db", "public.key"}
        for name in names:
            self.put(f"{name}/index.html", f"<h1>{name}</h1>".encode())
        snapshot = self.scanner.scan()
        self.staging.materialize(snapshot)
        self.assertEqual(snapshot.sites, names)
        for name in names:
            relative = Path(name) / "index.html"
            self.assertEqual((self.staging.tree / relative).read_bytes(), (self.source / relative).read_bytes())

    def test_nested_public_config_source_data_and_dot_assets_keep_exact_bytes(self):
        files = {
            "config.py": b'THEME = "dark"\n',
            "config.json": b'{"theme":"dark"}\n',
            "config.toml": b'theme = "dark"\n',
            "settings.json": b'{"enabled":true}\n',
            "data/catalog.sqlite": b"public database download\x00\x01",
            "data/catalog.db": b"public data bytes",
            "data/values.json": b"[1,2,3]",
            "credentials.json": b'{"requires_login":false}',
            "registry.json": b'{"public":[]}',
            "server_registry.json": b'{"examples":[]}',
            "site_servers.json": b'{"public_catalog":[]}',
            "node_modules/demo/index.js": b"export const value = 1;",
            "venv/readme.txt": b"public source bundle",
            "__pycache__/sample.bin": b"public binary download",
            "compose.yaml": b"services: {}\n",
            "docker-compose.yml": b"services: {}\n",
            "downloads/public.key": b"public key-shaped download",
            "downloads/certificate.pem": b"public certificate download",
            "public.env": b"THEME=dark\n",
            ".well-known/example.json": b'{"public":true}',
            ".assets/module.js": b"export default 1;",
            ".gitignore": b"*.tmp\n",
            ".env.example": b"THEME=dark\n",
        }
        for name, content in files.items():
            self.put("site/" + name, content)
        self.put(".not-a-site/index.html", b"top-level hidden artifact")
        snapshot = self.scanner.scan()
        self.staging.materialize(snapshot)
        self.assertEqual(snapshot.sites, {"site"})
        self.assertEqual(set(snapshot.files), {Path("site") / name for name in files})
        for name, content in files.items():
            self.assertEqual((self.staging.tree / "site" / name).read_bytes(), content)

    def test_explicit_private_subtree_never_recurses(self):
        self.put("site/index.html")
        private = self.put("site/operator-only/unknown.bin", b"private subtree").parent
        self.scanner.private_paths = (private,)
        with patch("scripts.publisher.scan.os.open", wraps=os.open) as opened:
            self.assertEqual(set(self.scanner.scan().files), {Path("site/index.html")})
        self.assertTrue({"operator-only", "unknown.bin"}.isdisjoint(Path(call.args[0]).name for call in opened.call_args_list))

    def test_hardlink_is_rejected_before_content_read(self):
        private = self.root / "synthetic-private"
        private.write_bytes(b"must not be read")
        (self.source / "site").mkdir()
        os.link(private, self.source / "site/alias.txt")
        with patch.object(self.staging.blobs, "capture", side_effect=AssertionError("read reached")):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()

    def test_fixed_marker_across_chunk_boundary_keeps_exact_bytes(self):
        marker = b"-----BEGIN PRIVATE KEY-----"
        content = b"x" * (CHUNK_SIZE - 5) + marker
        self.put("site/download.bin", content)
        self.staging.materialize(self.scanner.scan())
        self.assertEqual((self.staging.tree / "site/download.bin").read_bytes(), content)

    def test_redacted_labels_and_environment_references_are_publishable(self):
        self.put("site/backend.py", b'api_key=os.getenv("OPENAI_API_KEY")\nDISCORD_TOKEN=os.environ["DISCORD_TOKEN"]\n')
        self.put("_images/image.png", b"synthetic image")
        self.put("_images/image.txt", b'Authorization: [REDACTED]\napi_key=[REDACTED]\n"private_key": "[REDACTED]"\n')
        self.assertEqual(len(self.scanner.scan().files), 3)

    def test_credential_shaped_content_keeps_exact_bytes(self):
        path = self.put("site/file.txt")
        for content in (
            b"x" * (CHUNK_SIZE - 20) + b"Authorization: Bearer [REDACTED]",
            b"DISCORD_TOKEN=synthetic-real-token",
            b'api_key="sk-synthetic-literal"',
            b"Authorization: Bearer synthetic-literal",
            b"Authorization: Bearer $OPENROUTER_API_KEY",
            b"Authorization: Bearer ${OPENROUTER_API_KEY}",
        ):
            with self.subTest(content=content):
                path.write_bytes(content)
                self.staging.materialize(self.scanner.scan())
                self.assertEqual((self.staging.tree / "site/file.txt").read_bytes(), content)

    def test_symlink_swap_between_stat_and_open_is_refused(self):
        path = self.put("site/file.txt")
        private = self.root / "outside"
        private.write_bytes(b"never read")
        original = self.scanner.file

        def swap(parent, relative, value, result, copy):
            path.unlink()
            path.symlink_to(private)
            original(parent, relative, value, result, copy)

        with patch.object(self.scanner, "file", side_effect=swap):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()

    def test_file_changed_during_hash_does_not_materialize(self):
        path = self.put("site/file.txt", b"before")
        self.staging.materialize(self.scanner.scan())
        original = self.staging.blobs.capture

        def mutate(fd, before):
            path.write_bytes(b"after")
            return original(fd, before)

        with patch.object(self.staging.blobs, "capture", side_effect=mutate):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()
        self.assertEqual((self.staging.tree / "site/file.txt").read_bytes(), b"before")

    def test_missing_entry_and_unreadable_directory_refuse_complete_scan(self):
        path = self.put("site/file.txt")
        original = self.scanner.file

        def remove(parent, relative, value, result, copy):
            path.unlink()
            original(parent, relative, value, result, copy)

        with patch.object(self.scanner, "file", side_effect=remove):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()
        with patch.object(self.scanner, "descend", side_effect=PermissionError):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()

    def test_change_after_first_walk_is_caught_by_validation_walk(self):
        path = self.put("site/file.txt")
        original = self.scanner.collect

        def collect(copy, expected):
            snapshot = original(copy, expected)
            if copy:
                path.unlink()
            return snapshot

        with patch.object(self.scanner, "collect", side_effect=collect):
            with self.assertRaises(ScanIncomplete):
                self.scanner.scan()

    def test_source_replacement_is_refused_before_artifact_reads(self):
        self.put("site/file.txt")
        identity = self.scanner.scan().root_identity
        self.source.rename(self.root / "old-public")
        self.source.mkdir()
        self.put("site/replacement.txt")
        with patch.object(self.staging.blobs, "capture", side_effect=AssertionError("read reached")):
            with self.assertRaisesRegex(ScanIncomplete, "replacement"):
                self.scanner.scan(identity)

    def test_missing_root_and_symlinked_ancestor_are_refused(self):
        self.source.rmdir()
        with self.assertRaises(ScanIncomplete):
            self.scanner.scan()
        other = self.root / "other"
        other.mkdir()
        self.source.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ScanIncomplete):
            self.scanner.scan()

    def test_unchanged_archive_does_not_copy_or_replace_staged_files(self):
        self.put("_images/file.png", b"same bytes")
        self.put("_images/file.txt", b"same prompt")
        self.staging.materialize(self.scanner.scan())
        before = {path.name: path.stat() for path in (self.staging.tree / "_images").iterdir()}
        with patch.object(self.staging.blobs, "copy", side_effect=AssertionError("duplicate copy")):
            self.staging.materialize(self.scanner.scan())
        after = {path.name: path.stat() for path in (self.staging.tree / "_images").iterdir()}
        for name in before:
            self.assertEqual(before[name].st_ino, after[name].st_ino)
            self.assertEqual(before[name].st_mtime_ns, after[name].st_mtime_ns)

    def test_current_staging_prunes_old_versions_and_type_changes(self):
        path = self.put("site/name", b"first")
        self.staging.materialize(self.scanner.scan())
        path.write_bytes(b"second")
        self.staging.materialize(self.scanner.scan())
        self.assertEqual(len(list(self.staging.blobs.path.iterdir())), 1)
        path.unlink()
        path.mkdir()
        self.put("site/name/child", b"third")
        self.staging.materialize(self.scanner.scan())
        self.assertEqual((self.staging.tree / "site/name/child").read_bytes(), b"third")
        self.assertEqual(len(list(self.staging.blobs.path.iterdir())), 1)

    def test_orphan_or_symlink_image_cannot_authorize_prompt(self):
        outside = self.root / "outside.png"
        outside.write_bytes(b"synthetic")
        self.put("_images/file.txt", b"orphan")
        (self.source / "_images/file.png").symlink_to(outside)
        self.assertEqual(self.scanner.scan().files, {})
