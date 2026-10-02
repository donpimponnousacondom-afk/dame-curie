import contextlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts.publisher.__main__ import main
from scripts.publisher.common import PublisherError
from scripts.publisher.config import load_config, validate
from scripts.publisher.state import State
from scripts.publisher.transport import Transport


class PublisherConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("public", "stage", "state"):
            (self.root / name).mkdir(mode=0o700)
        for name in ("key with spaces", "known hosts"):
            path = self.root / name
            path.write_bytes(b"synthetic fixture, not a credential")
            path.chmod(0o600)
        self.path = self.root / "publisher.toml"
        data = {
            "source": str(self.root / "public"), "staging": str(self.root / "stage"),
            "state": str(self.root / "state"), "key": str(self.root / "key with spaces"),
            "known_hosts": str(self.root / "known hosts"), "host": "static.example.invalid",
            "user": "publisher", "site_root": "/synthetic/sites", "image_root": "/synthetic/images",
        }
        self.path.write_text("\n".join(f"{name} = {json.dumps(value)}" for name, value in data.items()))
        self.path.chmod(0o600)
        self.config = load_config(self.path)

    def test_explicit_minimal_toml_has_no_application_configuration(self):
        self.assertEqual(self.config.source, self.root / "public")
        self.assertEqual(self.config.port, 22)
        self.assertEqual(self.config.rescan_seconds, 60)
        self.assertEqual(self.config.private_paths, ())
        self.assertEqual(self.config.marker_namespace, "dame-curie")
        self.path.write_text(self.path.read_text() + '\nmarker_namespace = "curie"\n')
        self.assertEqual(load_config(self.path).marker_namespace, "curie")

    def test_private_file_and_staging_permissions_are_required(self):
        self.path.chmod(0o644)
        with self.assertRaises(PublisherError):
            load_config(self.path)
        self.path.chmod(0o600)
        self.config.staging.chmod(0o755)
        with self.assertRaises(PublisherError):
            load_config(self.path)

    def test_source_staging_state_and_credentials_cannot_overlap(self):
        for changed in (
            replace(self.config, staging=self.config.source / "stage"),
            replace(self.config, source=self.root),
            replace(self.config, state=self.config.staging),
            replace(self.config, key=self.config.source / "key"),
            replace(self.config, private_paths=(self.root,)),
        ):
            with self.subTest(config=changed):
                with self.assertRaises(PublisherError):
                    validate(changed, self.path)

    def test_remote_root_overlap_and_host_option_injection_are_refused(self):
        for changed in (
            replace(self.config, site_root="/"),
            replace(self.config, image_root="/synthetic/sites/nested"),
            replace(self.config, site_root="/synthetic/../sites"),
            replace(self.config, host="-oProxyCommand=anything"),
            replace(self.config, user="publisher;exit"),
            replace(self.config, marker_namespace=""),
            replace(self.config, marker_namespace="../curie"),
            replace(self.config, marker_namespace="curie\n--anything"),
        ):
            with self.subTest(config=changed):
                with self.assertRaises(PublisherError):
                    validate(changed, self.path)

    def test_hardlinked_or_symlinked_credentials_are_refused(self):
        os.link(self.config.key, self.root / "alias")
        with self.assertRaises(PublisherError):
            validate(self.config, self.path)
        (self.root / "alias").unlink()
        original = self.config.key
        original.rename(self.root / "old-key")
        original.symlink_to(self.root / "old-key")
        with self.assertRaises(PublisherError):
            validate(self.config, self.path)

    def test_ownership_lock_and_binding_survive_reload(self):
        with contextlib.closing(State(self.config)) as state:
            with self.assertRaises(BlockingIOError):
                State(self.config)
            site = state.add_site("café '$;")
            token = site.token
            state.source_identity = (1, 2)
            state.roots = [[3, 4], [5, 6]]
            state.save()
        with contextlib.closing(State(self.config)) as state:
            self.assertEqual(state.sites["café '$;"].token, token)
            self.assertEqual(state.source_identity, (1, 2))
            self.assertEqual(state.roots, [[3, 4], [5, 6]])
            self.assertEqual(state.marker_namespace, "dame-curie")
        legacy = replace(self.config, marker_namespace="curie")
        for changed in (
            replace(self.config, host="other.example.invalid"),
            replace(self.config, source=self.root / "migrated-public"),
            legacy,
        ):
            with self.subTest(config=changed), self.assertRaisesRegex(PublisherError, "ownership configuration changed"):
                State(changed)
        data = json.loads(state.path.read_text())
        self.assertEqual(data.pop("marker_namespace"), "dame-curie")
        state.path.write_text(json.dumps(data))
        with contextlib.closing(State(self.config)) as reloaded:
            self.assertEqual(reloaded.sites["café '$;"].token, token)
        with self.assertRaisesRegex(PublisherError, "ownership configuration changed"):
            State(legacy)
        data["marker_namespace"] = "curie"
        state.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(PublisherError, "ownership configuration changed"):
            State(self.config)
        with contextlib.closing(State(legacy)) as reloaded:
            self.assertEqual(reloaded.marker_namespace, "curie")
            self.assertEqual(reloaded.sites["café '$;"].token, token)
            self.assertEqual(reloaded.roots, [[3, 4], [5, 6]])
            reloaded.save()
        self.assertEqual(json.loads(state.path.read_text())["marker_namespace"], "curie")

    def test_control_socket_state_path_cannot_expand_outside_private_directory(self):
        for name in ('state-${HOME}', 'state-%h', 'state\nother'):
            state = self.root / name
            state.mkdir(mode=0o700)
            with self.subTest(name=name), self.assertRaises(PublisherError):
                validate(replace(self.config, state=state), self.path)

    def test_known_hosts_uses_ssh_config_quoting_inside_argv(self):
        transport = Transport(self.config)
        self.assertIn(f'UserKnownHostsFile="{self.config.known_hosts}"', transport.ssh())
        self.assertIn(str(self.config.key), transport.ssh())

    def test_cli_failure_does_not_print_raw_exception_or_artifact_contents(self):
        output = io.StringIO()
        argv = ["publisher", "--config", str(self.path), "--once"]
        with patch("sys.argv", argv), contextlib.redirect_stderr(output):
            with patch("scripts.publisher.__main__.run", side_effect=OSError("SYNTHETIC PRIVATE PAYLOAD")):
                self.assertEqual(main(), 1)
        self.assertNotIn("SYNTHETIC PRIVATE PAYLOAD", output.getvalue())
        self.assertEqual(output.getvalue(), "publisher: configuration or filesystem operation failed\n")
