"""The publisher reports its progress to systemd, and a hang leaves its cause.

On 23 November 2026 the publisher had published nothing for at least 11 days, and
systemd still showed it as active. No log line named a cause.
"""

import contextlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from pathlib import Path
from threading import Event
from unittest.mock import patch

from scripts.publisher.common import PublisherError
from scripts.publisher.config import Config
from scripts.publisher.heartbeat import notify
from scripts.publisher.mirror import Mirror
from scripts.publisher.service import Publisher
from scripts.publisher.state import State
from scripts.publisher.watch import Watcher
from test_publisher_remote import LocalSSH

REPO = Path(__file__).resolve().parent.parent
UNIT = REPO / "scripts/publisher/dame-curie-publisher.service"


class HangingSSH(LocalSSH):
    """A transport whose remote calls hang while `hang` is set."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.hang = Event()
        self.hung = Event()
        self.release = Event()

    def execute(
        self,
        argv: list[str],
        capture: bool,
        operation: str = "remote",
        input_data: bytes | None = None,
    ) -> subprocess.CompletedProcess:
        if self.hang.is_set():
            self.hung.set()
            if not self.release.wait(10):
                raise RuntimeError("test did not release the hung call")
        return super().execute(argv, capture, operation, input_data)


class HeartbeatTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.address = str(self.root / "notify")
        self.receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.receiver.close)
        self.receiver.bind(self.address)
        environment = patch.dict(os.environ, {"NOTIFY_SOCKET": self.address})
        environment.start()
        self.addCleanup(environment.stop)

    def receive(self, timeout: float) -> str:
        """Return the next notification, or an empty string after `timeout` seconds."""
        self.receiver.settimeout(timeout)
        try:
            return self.receiver.recv(4096).decode()
        except TimeoutError:
            return ""

    def assert_reports_stop(self) -> None:
        """Fail when reports still arrive 2 seconds after the stall began."""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.receive(0.2)
        self.assertEqual(self.receive(1), "")

    def publisher(self) -> tuple[Publisher, HangingSSH]:
        """Build a publisher with a synthetic remote and a short check interval."""
        for name in ("public", "stage", "state", "remote", "images"):
            (self.root / name).mkdir(mode=0o700)
        config = Config(
            source=self.root / "public",
            staging=self.root / "stage",
            state=self.root / "state",
            key=self.root / "key",
            known_hosts=self.root / "known_hosts",
            host="synthetic.invalid",
            user="publisher",
            site_root=str(self.root / "remote"),
            image_root=str(self.root / "images"),
            settle_seconds=0.02,
            rescan_seconds=0.1,
        )
        state = State(config)
        self.addCleanup(state.close)
        transport = HangingSSH(config)
        mirror = Mirror(config, state, transport)
        watcher = Watcher(config, mirror.scanner)
        self.addCleanup(watcher.close)
        publisher = Publisher(mirror, watcher)
        executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown, wait=True)
        self.addCleanup(publisher.stopped.set)
        self.addCleanup(transport.release.set)
        self.task = executor.submit(publisher.run)
        return publisher, transport

    def test_a_finished_check_reports_progress_and_its_time(self) -> None:
        self.publisher()
        message = self.receive(5)
        self.assertTrue(message.startswith("WATCHDOG=1\nSTATUS="), message)
        self.assertRegex(
            message,
            r"last successful remote check: \d{4}-\d\d-\d\d \d\d:\d\d:\d\d[+-]\d\d:\d\d, "
            r"sites=0 local_errors=0$",
        )
        self.assertTrue(self.receive(5), "the next periodic check did not report")

    def test_a_hung_worker_stops_the_reports_until_it_continues(self) -> None:
        _, transport = self.publisher()
        self.assertTrue(self.receive(5))
        transport.hang.set()
        self.assertTrue(transport.hung.wait(5))
        self.assert_reports_stop()
        self.assertFalse(self.task.done())
        transport.hang.clear()
        transport.release.set()
        self.assertIn("WATCHDOG=1", self.receive(5))

    def test_a_hung_main_loop_stops_the_reports(self) -> None:
        publisher, _ = self.publisher()
        self.assertTrue(self.receive(5))
        release = Event()
        self.addCleanup(release.set)
        with patch.object(
            publisher, "observe", side_effect=lambda: release.wait(10)
        ) as observe:
            deadline = time.monotonic() + 5
            while not observe.called and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(observe.called)
            self.assert_reports_stop()
            release.set()

    def test_a_scheduler_that_starts_no_job_stops_the_reports(self) -> None:
        publisher, _ = self.publisher()
        self.assertTrue(self.receive(5))
        with patch.object(publisher, "inventory"):
            self.assert_reports_stop()
            self.assertFalse(self.task.done())

    def test_a_failed_check_reports_the_failure_and_the_last_success(self) -> None:
        _, transport = self.publisher()
        first = self.receive(5)
        self.assertIn("last successful remote check", first)
        with contextlib.redirect_stderr(io.StringIO()):
            transport.fail_action = "inventory"
            message = first
            deadline = time.monotonic() + 5
            while "FAILED" not in message and time.monotonic() < deadline:
                message = self.receive(1)
        self.assertRegex(
            message,
            r"^WATCHDOG=1\nSTATUS=remote check FAILED at \d{4}-\S+ \S+; "
            r"last success: \d{4}-\S+ \S+$",
        )

    def test_a_failed_report_stops_the_publisher_with_its_cause(self) -> None:
        self.publisher()
        self.assertTrue(self.receive(5))
        Path(self.address).unlink()
        with self.assertRaisesRegex(
            PublisherError, "systemd notification failed: ENOENT"
        ):
            self.task.result(timeout=5)

    def test_outside_systemd_nothing_is_sent(self) -> None:
        with patch.dict(os.environ):
            del os.environ["NOTIFY_SOCKET"]
            notify("WATCHDOG=1")
        self.assertEqual(self.receive(0.1), "")


class HangEvidenceTests(unittest.TestCase):
    def test_the_watchdog_signal_prints_the_stack_of_the_hung_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("public", "stage", "state"):
                (root / name).mkdir(mode=0o700)
            for name in ("key", "known_hosts"):
                (root / name).touch(mode=0o600)
            binaries = root / "bin"
            binaries.mkdir()
            started = root / "started"
            ssh = binaries / "ssh"
            ssh.write_text(f"#!/bin/sh\n: > '{started}'\nexec sleep 60\n")
            ssh.chmod(0o700)
            config = root / "publisher.toml"
            values = {name: str(root / name) for name in ("key", "known_hosts")}
            values |= {
                "source": str(root / "public"),
                "staging": str(root / "stage"),
                "state": str(root / "state"),
                "host": "synthetic.invalid",
                "user": "publisher",
                "site_root": "/synthetic/sites",
                "image_root": "/synthetic/images",
            }
            config.write_text(
                "\n".join(
                    f"{key} = {json.dumps(value)}" for key, value in values.items()
                )
            )
            config.chmod(0o600)
            environment = {"PATH": f"{binaries}:{os.environ['PATH']}"}
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "scripts.publisher", "--config", config],
                cwd=REPO,
                env=environment,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 20
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(started.exists(), "the publisher made no remote call")
                # systemd signals the whole control group, so ssh also receives it.
                os.killpg(process.pid, signal.SIGABRT)
                _, stderr = process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
        self.assertEqual(process.returncode, -signal.SIGABRT)
        self.assertIn("Fatal Python error: Aborted", stderr)
        self.assertRegex(stderr, r'transport\.py", line \d+ in execute')
        self.assertRegex(stderr, r'service\.py", line \d+ in run')


class UnitTests(unittest.TestCase):
    def test_the_unit_restarts_a_publisher_that_reports_no_progress(self) -> None:
        unit = ConfigParser(strict=False, interpolation=None)
        unit.optionxform = str
        unit.read(UNIT, encoding="utf-8")
        service = unit["Service"]
        self.assertEqual(service["WatchdogSec"], "30min")
        self.assertEqual(service["NotifyAccess"], "main")
        self.assertEqual(service["Restart"], "on-failure")
        self.assertNotIn("WatchdogSignal", service)


if __name__ == "__main__":
    unittest.main()
