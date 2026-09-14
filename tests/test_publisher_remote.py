import ctypes
import errno
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.publisher import guard
from scripts.publisher.common import MARKER, RemoteFailure, ScanIncomplete
from scripts.publisher.config import Config
from scripts.publisher.mirror import Mirror
from scripts.publisher.state import Site, State
from scripts.publisher.transport import Transport


class LocalSSH(Transport):
    def __init__(self, config):
        super().__init__(config)
        self.commands = []
        self.fail_action = ""
        self.after_transfer = lambda: None

    def execute(self, argv, capture):
        self.commands.append(argv)
        command = argv[-1] if capture else argv[argv.index("--rsync-path") + 1]
        request = json.loads(shlex.split(command)[-1])
        if request["action"] == self.fail_action:
            raise RemoteFailure("synthetic remote interruption")
        try:
            if capture:
                result = guard.run(request)
                return subprocess.CompletedProcess(argv, 0, json.dumps(result).encode())
            return self.local_rsync(argv, request)
        except (OSError, guard.Refused):
            raise RemoteFailure("synthetic remote refusal") from None

    def local_rsync(self, argv, request):
        local = []
        index = 0
        while index < len(argv) - 1:
            if argv[index] in {"-e", "--rsync-path"}:
                index += 2
            else:
                local.append(argv[index])
                index += 1
        local.append("./")
        results = []

        def execute(binary, arguments):
            self_test = binary == "rsync" and arguments == ["rsync"]
            if not self_test:
                raise AssertionError("unexpected remote execution")
            results.append(subprocess.run(local, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False))
            if results[-1].returncode:
                raise RemoteFailure("synthetic local rsync failed")

        cwd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        try:
            with patch.object(guard.os, "execvp", side_effect=execute):
                guard.run(request)
        finally:
            os.fchdir(cwd)
            os.close(cwd)
        self.after_transfer()
        return results[0]


class PublisherRemoteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("public", "stage", "state", "remote sites", "remote images"):
            (self.root / name).mkdir(mode=0o700)
        self.config = Config(
            source=self.root / "public", staging=self.root / "stage", state=self.root / "state",
            key=self.root / "key with ' spaces", known_hosts=self.root / "known hosts",
            host="static.example.invalid", user="publisher",
            site_root=str(self.root / "remote sites"), image_root=str(self.root / "remote images"),
        )
        self.state = State(self.config)
        self.addCleanup(lambda: self.state.close())
        self.transport = LocalSSH(self.config)
        self.mirror = Mirror(self.config, self.state, self.transport)
        self.sites = Path(self.config.site_root)
        self.images = Path(self.config.image_root)

    def put(self, name, content=b"synthetic"):
        path = self.config.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_remote_root_accepts_execute_only_hosting_ancestor(self):
        parent = self.root / "traverse-only"
        parent.mkdir()
        destination = parent / "public"
        destination.mkdir()
        expected = destination.stat()
        parent.chmod(0o111)
        try:
            with guard.root_directory(str(destination)) as fd:
                self.assertEqual(guard.identity(fd), [expected.st_dev, expected.st_ino])
                self.assertEqual(os.listdir(fd), [])
        finally:
            parent.chmod(0o700)

    def test_owned_site_updates_and_deletes_preserve_root_and_other_bots(self):
        (self.sites / "index.html").write_bytes(b"future root index")
        (self.sites / "other-bot").mkdir()
        (self.sites / "other-bot/sentinel").write_bytes(b"other")
        page = self.put("my site/index.html", b"one")
        removed = self.put("my site/old.js", b"old")
        self.mirror.reconcile()
        removed.unlink()
        page.write_bytes(b"two")
        self.mirror.reconcile()
        self.assertEqual((self.sites / "my site/index.html").read_bytes(), b"two")
        self.assertFalse((self.sites / "my site/old.js").exists())
        self.assertTrue((self.sites / "my site" / MARKER).exists())
        shutil.rmtree(page.parent)
        self.mirror.reconcile()
        self.assertFalse((self.sites / "my site").exists())
        self.assertEqual((self.sites / "index.html").read_bytes(), b"future root index")
        self.assertEqual((self.sites / "other-bot/sentinel").read_bytes(), b"other")
        self.assertEqual(self.state.sites, {})

    def test_unmanaged_collision_is_refused_even_when_empty(self):
        self.put("collision/index.html")
        (self.sites / "collision").mkdir()
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.assertEqual(list((self.sites / "collision").iterdir()), [])
        self.assertFalse(any(command[0] == "rsync" for command in self.transport.commands))

    def test_first_mkdir_cannot_claim_replacement_canonical_sentinel(self):
        self.put("site/index.html", b"publisher")
        sentinel = self.root / "unmanaged"
        sentinel.mkdir()
        (sentinel / "keep").write_bytes(b"unrelated")
        original = os.mkdir
        injected = False

        def replace_canonical(path, mode=0o777, *, dir_fd=None):
            nonlocal injected
            result = original(path, mode, dir_fd=dir_fd)
            if dir_fd is not None and not injected and os.path.samestat(os.fstat(dir_fd), self.sites.stat()):
                injected = True
                canonical = self.sites / "site"
                if canonical.exists():
                    canonical.rename(self.root / "detached-original")
                sentinel.rename(canonical)
            return result

        with patch.object(guard.os, "mkdir", side_effect=replace_canonical):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.assertTrue(injected)
        self.assertEqual((self.sites / "site/keep").read_bytes(), b"unrelated")
        self.assertFalse((self.sites / "site" / MARKER).exists())

    def test_first_mkdir_cannot_overwrite_empty_unmanaged_canonical(self):
        self.put("site/index.html")
        original = os.mkdir
        injected = False

        def create_canonical(path, mode=0o777, *, dir_fd=None):
            nonlocal injected
            result = original(path, mode, dir_fd=dir_fd)
            if dir_fd is not None and not injected and os.path.samestat(os.fstat(dir_fd), self.sites.stat()):
                injected = True
                canonical = self.sites / "site"
                if canonical.exists():
                    canonical.rename(self.root / "detached-original")
                original(canonical)
            return result

        with patch.object(guard.os, "mkdir", side_effect=create_canonical):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.assertTrue(injected)
        self.assertEqual(list((self.sites / "site").iterdir()), [])

    def test_canonical_swap_before_open_never_stamps_unowned_directory(self):
        self.put("site/index.html")
        sentinel = self.root / "replacement"
        sentinel.mkdir()
        (sentinel / "keep").write_bytes(b"unrelated")
        original = os.open
        injected = False

        def swap_before_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal injected
            canonical = self.sites / "site"
            if path == "site" and dir_fd is not None and canonical.exists() and not injected:
                injected = True
                canonical.rename(self.root / "detached-original")
                sentinel.rename(canonical)
            return original(path, flags, mode, dir_fd=dir_fd)

        with patch.object(guard.os, "open", side_effect=swap_before_open):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.assertTrue(injected)
        self.assertEqual((self.sites / "site/keep").read_bytes(), b"unrelated")
        self.assertFalse((self.sites / "site" / MARKER).exists())

    def test_pre_marker_interruption_recovers_after_restart(self):
        self.put("site/index.html", b"after restart")
        original = os.open

        def disk_full_before_marker(path, flags, mode=0o777, *, dir_fd=None):
            if path == MARKER and flags & os.O_CREAT:
                raise OSError(errno.ENOSPC, "synthetic disk full")
            return original(path, flags, mode, dir_fd=dir_fd)

        with patch.object(guard.os, "open", side_effect=disk_full_before_marker):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.state.close()
        self.state = State(self.config)
        self.mirror = Mirror(self.config, self.state, self.transport)
        self.mirror.reconcile()
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"after restart")
        self.assertFalse(any(path.name.startswith(".curie-publisher-claim-") for path in self.sites.iterdir()))

    def test_partial_marker_write_recovers_after_restart(self):
        self.put("site/index.html", b"after partial write")
        original = os.write

        def short_write(fd, payload):
            return original(fd, payload[:len(payload) // 2])

        with patch.object(guard.os, "write", side_effect=short_write):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.state.close()
        self.state = State(self.config)
        self.mirror = Mirror(self.config, self.state, self.transport)
        self.mirror.reconcile()
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"after partial write")
        self.assertFalse(any(path.name.startswith(".curie-publisher-claim-") for path in self.sites.iterdir()))

    def test_removed_source_cleans_partial_claim_not_unmanaged_canonical(self):
        page = self.put("site/index.html")
        self.put("_images/later.png", b"archive still reconciles")
        original = os.write

        def partial_then_disk_full(fd, payload):
            original(fd, payload[:len(payload) // 2])
            raise OSError(errno.ENOSPC, "synthetic disk full")

        with patch.object(guard.os, "write", side_effect=partial_then_disk_full):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        shutil.rmtree(page.parent)
        canonical = self.sites / "site"
        if canonical.exists():
            canonical.rename(self.root / "detached-partial")
        canonical.mkdir()
        (canonical / "keep").write_bytes(b"unmanaged")
        self.mirror.reconcile()
        self.assertEqual((canonical / "keep").read_bytes(), b"unmanaged")
        self.assertFalse((canonical / MARKER).exists())
        self.assertNotIn("site", self.state.sites)
        self.assertFalse(any(path.name.startswith(".curie-publisher-claim-") for path in self.sites.iterdir()))
        self.assertEqual((self.images / "later.png").read_bytes(), b"archive still reconciles")

    def test_overlapping_cleanup_refuses_publication_before_marker_unlink(self):
        self.put("site/index.html")
        (self.sites / "index.html").write_bytes(b"unrelated root index")
        with patch.object(guard, "rename_noreplace", side_effect=OSError(errno.EINTR, "synthetic interruption")):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        site = self.state.sites["site"]
        claim = self.transport.request("claim", self.state.roots, "site", site)
        remove = self.transport.request("remove", self.state.roots, "site", site)
        original = os.unlink
        blocked, errors = [], []
        injected = False

        def publish_before_unlink(path, *, dir_fd=None):
            nonlocal injected
            if path == MARKER and dir_fd is not None and not injected:
                injected = True
                try:
                    guard.run(claim)
                except BlockingIOError as error:
                    blocked.append(error.errno)
            return original(path, dir_fd=dir_fd)

        with patch.object(guard.os, "unlink", side_effect=publish_before_unlink):
            try:
                guard.run(remove)
            except OSError as error:
                errors.append(error.errno)
        self.assertTrue(injected)
        self.assertEqual(blocked, [errno.EAGAIN])
        self.assertEqual(errors, [])
        self.assertFalse((self.sites / "site").exists())
        self.assertFalse(any(path.name.startswith(".curie-publisher-claim-") for path in self.sites.iterdir()))
        self.assertEqual(len(guard.run(claim)["site_identity"]), 2)
        self.assertIn(site.token.encode(), (self.sites / "site" / MARKER).read_bytes())
        self.assertEqual((self.sites / "index.html").read_bytes(), b"unrelated root index")

    def test_overlapping_preparations_refuse_publication_before_marker_truncate(self):
        self.put("site/index.html")
        with patch.object(guard, "rename_noreplace", side_effect=OSError(errno.EINTR, "synthetic interruption")):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        site = self.state.sites["site"]
        claim = self.transport.request("claim", self.state.roots, "site", site)
        original = os.ftruncate
        blocked, errors, published_mutations = [], [], []
        injected = False

        def publish_before_truncate(fd, length):
            nonlocal injected
            if injected:
                return original(fd, length)
            injected = True
            try:
                guard.run(claim)
            except BlockingIOError as error:
                blocked.append(error.errno)
            original(fd, length)
            marker = self.sites / "site" / MARKER
            if marker.exists():
                published_mutations.append(marker.read_bytes())
                raise OSError(errno.ENOSPC, "synthetic interruption after truncate")

        with patch.object(guard.os, "ftruncate", side_effect=publish_before_truncate):
            try:
                guard.run(claim)
            except OSError as error:
                errors.append(error.errno)
        self.assertTrue(injected)
        self.assertEqual(blocked, [errno.EAGAIN])
        self.assertEqual(errors, [])
        self.assertEqual(published_mutations, [])
        self.assertIn(site.token.encode(), (self.sites / "site" / MARKER).read_bytes())
        self.assertEqual(len(guard.run(claim)["site_identity"]), 2)
        self.assertFalse(any(path.name.startswith(".curie-publisher-claim-") for path in self.sites.iterdir()))

    def test_unsupported_noreplace_has_no_ordinary_rename_fallback(self):
        self.put("site/index.html")

        def unsupported(*arguments):
            ctypes.set_errno(errno.ENOSYS)
            return -1

        library = type("SyntheticLibc", (), {})()
        library.renameat2 = unsupported
        with patch("ctypes.CDLL", return_value=library):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.assertFalse((self.sites / "site").exists())

    def test_archive_retains_removed_images_and_prompts_and_updates_names(self):
        image = self.put("_images/été '$;[].png", b"first-image")
        prompt = self.put("_images/été '$;[].txt", b"first prompt")
        orphan = self.put("_images/orphan.txt", b"not paired")
        self.mirror.reconcile()
        image.write_bytes(b"second-image")
        prompt.write_bytes(b"second prompt")
        self.mirror.reconcile()
        image.unlink()
        prompt.unlink()
        orphan.unlink()
        self.mirror.reconcile()
        self.assertEqual((self.images / image.name).read_bytes(), b"second-image")
        self.assertEqual((self.images / prompt.name).read_bytes(), b"second prompt")
        self.assertFalse((self.images / "orphan.txt").exists())
        self.assertTrue(all("--delete-delay" not in command for command in self.transport.commands if command[0] == "rsync"))

    def test_unicode_shell_names_are_data_not_shell_commands(self):
        name = "café '; $(touch SHOULD_NOT_EXIST) [x]"
        path = self.put(name + "/';$ unicode λ.js", b"unaltered")
        self.mirror.reconcile()
        self.assertEqual((self.sites / name / path.name).read_bytes(), b"unaltered")
        command = next(command for command in self.transport.commands if command[0] == "rsync")
        request = json.loads(shlex.split(command[command.index("--rsync-path") + 1])[-1])
        self.assertEqual(request["name"], name)
        self.assertEqual(command[-1], "publisher@static.example.invalid:./")
        self.assertFalse((self.sites / "SHOULD_NOT_EXIST").exists())

    def test_pending_transfer_recovers_after_state_reload(self):
        self.put("site/index.html", b"first")
        self.transport.fail_action = "site"
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        token = self.state.sites["site"].token
        self.state.close()
        self.state = State(self.config)
        self.transport.fail_action = ""
        self.mirror = Mirror(self.config, self.state, self.transport)
        self.mirror.reconcile()
        self.assertEqual(self.state.sites["site"].token, token)
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"first")

    def test_lost_first_claim_acknowledgement_recovers_own_marker(self):
        self.put("site/index.html", b"survives lost acknowledgement")
        original = self.transport.control

        def lose_acknowledgement(request):
            response = original(request)
            if request["action"] == "claim":
                raise RemoteFailure("synthetic lost acknowledgement")
            return response

        with patch.object(self.transport, "control", side_effect=lose_acknowledgement):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        site = self.state.sites["site"]
        self.assertEqual(site.identity, [])
        self.assertIn(site.token.encode(), (self.sites / "site" / MARKER).read_bytes())
        self.mirror.reconcile()
        self.assertEqual(len(site.identity), 2)
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"survives lost acknowledgement")

    def test_lost_ack_copied_marker_cannot_claim_replacement_inode(self):
        self.put("site/index.html", b"publisher")
        original = self.transport.control

        def lose_acknowledgement(request):
            response = original(request)
            if request["action"] == "claim":
                raise RemoteFailure("synthetic lost acknowledgement")
            return response

        with patch.object(self.transport, "control", side_effect=lose_acknowledgement):
            with self.assertRaises(RemoteFailure):
                self.mirror.reconcile()
        self.assertEqual(self.state.sites["site"].identity, [])
        canonical = self.sites / "site"
        marker_bytes = (canonical / MARKER).read_bytes()
        canonical.rename(self.sites / "detached-owned-site")
        canonical.mkdir()
        (canonical / MARKER).write_bytes(marker_bytes)
        (canonical / MARKER).chmod(0o600)
        (canonical / "keep").write_bytes(b"unrelated replacement")
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.assertEqual((canonical / "keep").read_bytes(), b"unrelated replacement")
        self.assertEqual((canonical / MARKER).read_bytes(), marker_bytes)
        self.assertEqual(self.state.sites["site"].identity, [])

    def test_reconnect_and_change_during_transfer_reconcile_later(self):
        path = self.put("site/index.html", b"before")
        self.transport.fail_action = "probe"
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.transport.fail_action = ""
        self.transport.after_transfer = lambda: path.write_bytes(b"after")
        self.mirror.reconcile()
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"before")
        self.transport.after_transfer = lambda: None
        self.mirror.reconcile()
        self.assertEqual((self.sites / "site/index.html").read_bytes(), b"after")

    def test_incomplete_scan_never_contacts_remote_or_deletes(self):
        page = self.put("site/index.html")
        self.mirror.reconcile()
        self.transport.commands.clear()
        page.unlink()
        with patch.object(self.mirror.scanner, "collect", side_effect=PermissionError):
            with self.assertRaises(ScanIncomplete):
                self.mirror.reconcile()
        self.assertEqual(self.transport.commands, [])
        self.assertTrue((self.sites / "site/index.html").exists())

    def test_source_site_symlink_replacement_is_not_site_removal(self):
        page = self.put("site/index.html")
        self.mirror.reconcile()
        shutil.rmtree(page.parent)
        (self.config.source / "site").symlink_to(self.root, target_is_directory=True)
        self.mirror.reconcile()
        self.assertTrue((self.sites / "site/index.html").exists())
        self.assertIn("site", self.state.sites)

    def test_remote_root_replacement_refuses_any_further_transfer(self):
        self.put("site/index.html")
        self.mirror.reconcile()
        self.sites.rename(self.root / "old remote")
        self.sites.mkdir()
        self.transport.commands.clear()
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.assertFalse(any(command[0] == "rsync" for command in self.transport.commands))

    def test_symlink_remote_root_and_symlink_parent_are_refused(self):
        self.put("site/index.html")
        self.sites.rmdir()
        self.sites.symlink_to(self.images, target_is_directory=True)
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.sites.unlink()
        self.sites.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        request = self.transport.request("probe", [], "", Site(""))
        request["site_root"] = str(alias / "remote sites")
        with self.assertRaises(OSError):
            guard.run(request)

    def test_remote_child_replacement_with_copied_marker_is_refused(self):
        self.put("site/index.html")
        self.mirror.reconcile()
        original = self.sites / "site"
        marker_bytes = (original / MARKER).read_bytes()
        original.rename(self.sites / "old-site")
        original.mkdir()
        marker = original / MARKER
        marker.write_bytes(marker_bytes)
        marker.chmod(0o600)
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()

    def test_interrupted_deletion_recovers_without_touching_symlink_target(self):
        page = self.put("site/index.html")
        self.mirror.reconcile()
        outside = self.root / "sentinel"
        outside.mkdir()
        (outside / "keep").write_bytes(b"keep")
        (self.sites / "site/link").symlink_to(outside, target_is_directory=True)
        shutil.rmtree(page.parent)
        self.transport.fail_action = "remove"
        with self.assertRaises(RemoteFailure):
            self.mirror.reconcile()
        self.assertTrue(self.state.sites["site"].deleting)
        self.transport.fail_action = ""
        self.mirror.reconcile()
        self.assertEqual((outside / "keep").read_bytes(), b"keep")
        self.assertFalse((self.sites / "site").exists())

    def test_final_marker_removal_interruption_is_recoverable(self):
        page = self.put("site/index.html")
        self.mirror.reconcile()
        shutil.rmtree(page.parent)
        remote = self.sites / "site"
        (remote / "index.html").unlink()
        (remote / MARKER).unlink()
        self.state.sites["site"].deleting = True
        self.state.save()
        self.mirror.reconcile()
        self.assertFalse(remote.exists())

    def test_archive_and_shared_root_deletion_requests_are_refused(self):
        for action in ("archive", "probe"):
            request = self.transport.request(action, [], "", Site(""))
            with self.assertRaises(RemoteFailure):
                self.transport.sync(self.mirror.staging.tree, request, delete=True)
        request = self.transport.request("remove", [], "..", Site("token"))
        with self.assertRaises(guard.Refused):
            guard.run(request)

    def test_guard_command_uses_isolated_no_site_python(self):
        request = self.transport.request("probe", [], "", Site(""))
        arguments = shlex.split(self.transport.command(request))
        self.assertEqual(arguments[:4], ["python3", "-I", "-S", "-c"])
        self.assertEqual(json.loads(arguments[-1]), request)

    def test_guard_subprocess_ignores_poisoned_cwd_pythonpath_and_sitecustomize(self):
        poison = self.root / "unrelated-python"
        poison.mkdir()
        sentinel = self.root / "unrelated-import-ran"
        payload = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unrelated code')\n"
        for name in ("json.py", "ctypes.py", "sitecustomize.py", "usercustomize.py"):
            (poison / name).write_text(payload)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(poison)
        environment["PYTHONUSERBASE"] = str(poison)
        request = self.transport.request("probe", [], "", Site(""))
        arguments = shlex.split(self.transport.command(request))
        result = subprocess.run(
            [sys.executable, *arguments[1:]], cwd=poison, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(json.loads(result.stdout)["roots"]), 2)
        self.assertFalse(sentinel.exists())

    def test_ssh_options_are_explicit_and_remote_errors_are_not_exposed(self):
        transport = Transport(self.config)
        argv = transport.ssh()
        self.assertEqual(argv[:3], ["ssh", "-F", "/dev/null"])
        for option in (
            "IdentityAgent=none", "IdentityFile=none", "IdentitiesOnly=yes", "BatchMode=yes",
            "StrictHostKeyChecking=yes", "GlobalKnownHostsFile=/dev/null",
            "ClearAllForwardings=yes", "ForwardAgent=no", "ConnectTimeout=15",
        ):
            self.assertIn(option, argv)
        self.assertEqual(argv[argv.index("-i") + 1], str(self.config.key))
        result = subprocess.CompletedProcess(argv, 255, b"private remote text", b"private remote error")
        with patch("scripts.publisher.transport.subprocess.run", return_value=result):
            with self.assertRaisesRegex(RemoteFailure, "^remote operation refused or failed$"):
                transport.execute(argv, capture=True)
