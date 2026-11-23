"""The model can read the sync state of a site. It can never force or await a sync."""

import asyncio
import io
import json
import os
import shutil
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import site_status
from concurrency_safety import classify_tool
from control_defaults import KNOWN_TOOLS
from scripts.publisher.common import EXCLUDED, MARKER, PublisherError
from scripts.publisher.config import Config, load_config
from scripts.publisher.mirror import Mirror
from scripts.publisher.service import Publisher
from scripts.publisher.state import State
from scripts.publisher.watch import Watcher
from site_status import SiteStatusTool
from test_publisher_remote import LocalSSH
from tool_schemas import CORE_TOOL_NAMES, RESULT_TOOL_NAMES, TOOL_PARAMETERS

BASE = "https://sites.example.invalid/dame"


class Harness:
    """A real publisher with a synthetic remote, and the real tool that reads it."""

    def __init__(self, root: Path) -> None:
        for name in ("sites", "stage", "state", "status", "remote", "images"):
            (root / name).mkdir(mode=0o700)
        self.sites = root / "sites"
        self.file = root / "status/status.json"
        config = Config(
            source=self.sites,
            staging=root / "stage",
            state=root / "state",
            status=root / "status",
            key=root / "key",
            known_hosts=root / "known_hosts",
            host="synthetic.invalid",
            user="publisher",
            site_root=str(root / "remote"),
            image_root=str(root / "images"),
        )
        self.state = State(config)
        self.transport = LocalSSH(config)
        self.mirror = Mirror(config, self.state, self.transport)
        self.watcher = Watcher(config, self.mirror.scanner)
        self.publisher = Publisher(self.mirror, self.watcher)
        self.watcher.rebuild()
        self.state.source_identity = self.watcher.root_identity
        self.config = SimpleNamespace(
            DAME_CURIE_SITE_DIR=str(self.sites),
            DAME_CURIE_SITE_PUBLIC_BASE_URL=BASE,
            DAME_CURIE_PUBLISHER_STATUS=str(self.file),
        )
        self.tool = SiteStatusTool(SimpleNamespace(config=self.config))

    def put(self, relative: str, content: str = "synthetic") -> Path:
        """Write one local file, as the model does with the shell tool."""
        path = self.sites / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def job(self, name: str | None = None, force: bool = True) -> None:
        """Run one job of the publisher to its end. No name means a remote check."""
        time.sleep(0.1)
        self.publisher.job_started = time.time()
        if name is not None:
            # The scheduler takes a forced job out of the queue when it starts it.
            self.publisher.force.discard(name)
        future: Future = Future()
        try:
            if name is None:
                future.set_result(self.mirror.inventory())
            else:
                future.set_result(self.mirror.reconcile_site(name, force=force))
        except PublisherError as error:
            future.set_exception(error)
        with redirect_stderr(io.StringIO()):
            self.publisher.complete(future, name)

    def ask(self, site: str) -> str:
        """Call the tool as the model does."""
        return asyncio.run(self.tool.execute(SimpleNamespace(), site=site))


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    """Give one harness and close its descriptors."""
    value = Harness(tmp_path)
    yield value
    value.watcher.close()
    value.state.close()


def test_a_new_site_is_syncing_until_the_publisher_synced_it(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job()
    first = harness.ask("page")
    assert first.startswith("Site page: syncing in progress. It is created.")
    assert "Give the user the URL now" in first
    assert "Do not wait for it, test it or ask again" in first
    assert f"URL: {BASE}/page/" in first
    harness.job("page")
    second = harness.ask("page")
    assert second.startswith("Site page: synced at ")
    assert f"URL: {BASE}/page/" in second


@pytest.mark.parametrize("change", ["edit", "add", "nested", "delete", "replace"])
def test_every_local_change_is_syncing_until_the_next_sync(
    harness: Harness, change: str
) -> None:
    page = harness.put("page/index.html")
    harness.put("page/assets/a.txt")
    harness.job("page")
    assert harness.ask("page").startswith("Site page: synced at ")
    time.sleep(0.1)
    if change == "edit":
        page.write_text("changed")
        os.utime(page, (1, 1))
    elif change == "add":
        harness.put("page/new.html")
    elif change == "nested":
        harness.put("page/assets/b.txt")
    elif change == "delete":
        (harness.sites / "page/assets/a.txt").unlink()
    else:
        other = harness.put("other/index.html", "replacement")
        os.replace(other, page)
    assert harness.ask("page").startswith("Site page: syncing in progress.")
    harness.job("page")
    assert harness.ask("page").startswith("Site page: synced at ")


def test_a_remote_check_confirms_an_unchanged_site(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    before = json.loads(harness.file.read_text())["sites"]["page"]["synced"]
    harness.job()
    assert json.loads(harness.file.read_text())["sites"]["page"]["synced"] > before
    assert harness.ask("page").startswith("Site page: synced at ")


def test_a_remote_difference_is_syncing_again(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    (Path(harness.mirror.config.site_root) / "page/index.html").write_text("damaged")
    harness.job()
    assert harness.ask("page").startswith("Site page: syncing in progress.")


def test_the_running_publisher_reports_a_new_site_as_synced(harness: Harness) -> None:
    executor = ThreadPoolExecutor(max_workers=1)
    with redirect_stderr(io.StringIO()):
        task = executor.submit(harness.publisher.run)
        harness.put("page/index.html")
        deadline = time.monotonic() + 10
        while "synced at" not in harness.ask("page") and time.monotonic() < deadline:
            time.sleep(0.05)
        harness.publisher.stopped.set()
        task.result(timeout=5)
    executor.shutdown()
    assert harness.ask("page").startswith("Site page: synced at ")
    assert (Path(harness.mirror.config.site_root) / "page/index.html").is_file()


def test_a_file_that_disappears_during_the_walk_is_a_change(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    original = os.lstat

    def lstat(path: str) -> os.stat_result:
        if str(path).endswith("index.html"):
            raise FileNotFoundError(2, "synthetic removal")
        return original(path)

    with patch.object(site_status.os, "lstat", side_effect=lstat):
        text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert f"URL: {BASE}/page/" in text
    assert "The sync state is unknown: FileNotFoundError" in text


def test_a_folder_that_cannot_be_read_is_named(harness: Harness) -> None:
    harness.put("page/assets/a.txt")
    harness.job("page")
    original = os.scandir

    def scandir(path: str) -> object:
        if str(path).endswith("assets"):
            raise PermissionError(13, "synthetic refusal")
        return original(path)

    with patch.object(os, "scandir", side_effect=scandir):
        text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert f"URL: {BASE}/page/" in text
    assert "The sync state is unknown: PermissionError" in text


def test_a_failed_sync_names_its_cause_and_does_not_hide_the_url(
    harness: Harness,
) -> None:
    harness.put("page/index.html")
    harness.transport.fail_action = "site"
    harness.job("page")
    text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert f"URL: {BASE}/page/" in text
    assert "synthetic remote interruption. It is retried by itself." in text
    harness.transport.fail_action = ""
    harness.job("page")
    assert "failed" not in harness.ask("page")


def test_a_failed_hidden_folder_is_not_synced_by_a_clean_check(
    harness: Harness,
) -> None:
    """The check skips top-level hidden folders, so only a transfer ends the failure."""
    harness.put("page/index.html")
    harness.put("page/.data/x")
    harness.job("page")
    harness.put("page/.data/x", "changed inside a folder that the walk skips")
    harness.transport.fail_action = "site"
    harness.job("page")
    assert harness.ask("page").startswith("Site page: syncing in progress.")
    for checks in (1, 2, 3):
        for _ in range(checks):
            harness.job()
        text = harness.ask("page")
        assert text.startswith("Site page: syncing in progress.")
        assert "synthetic remote interruption" in text
        harness.job("page")
    harness.transport.fail_action = ""
    harness.job("page")
    text = harness.ask("page")
    assert text.startswith("Site page: synced at ")
    assert "Not part of this check: hidden folders at the top of the site." in text
    harness.job()
    assert harness.ask("page").startswith("Site page: synced at ")


def test_a_job_without_a_transfer_is_not_a_confirmation(harness: Harness) -> None:
    page = harness.put("page/index.html")
    harness.job("page")
    time.sleep(0.1)
    page.touch()
    harness.job("page", force=False)
    assert harness.ask("page").startswith("Site page: syncing in progress.")
    harness.job()
    assert harness.ask("page").startswith("Site page: synced at ")


def test_a_symlink_is_not_a_site(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    (harness.sites / "latest").symlink_to("page")
    harness.job("latest", force=False)
    assert harness.ask("latest").startswith("Error: there is no folder 'latest'")
    shutil.rmtree(harness.sites / "page")
    harness.put("older/index.html")
    (harness.sites / "page").symlink_to("older")
    assert harness.ask("page").startswith("Error: there is no folder 'page'")


def test_an_excluded_folder_does_not_hold_a_site(harness: Harness) -> None:
    harness.put("page/assets/_data/a.txt")
    harness.put("page/assets/.env")
    harness.job("page")
    time.sleep(0.1)
    harness.put("page/assets/_data/a.txt", "changed and never published")
    harness.put("page/assets/.env", "changed and never published")
    text = harness.ask("page")
    assert text.startswith("Site page: synced at ")
    assert "_build, _data." in text


def test_the_exclusions_are_those_of_the_publisher() -> None:
    assert site_status.NEVER_PUBLISHED == EXCLUDED - {MARKER}


def test_no_site_name_makes_an_answer_look_like_an_error(harness: Harness) -> None:
    harness.put("ErrorPages/index.html")
    assert harness.ask("ErrorPages").startswith("Site ErrorPages: syncing in progress.")


def test_a_folder_replaced_during_the_walk_is_a_change(harness: Harness) -> None:
    harness.put("page/assets/a.txt")
    harness.put("page/zz/b.txt")
    harness.put("other/a.txt")
    harness.job("page")
    time.sleep(0.1)
    original = os.scandir
    other = harness.sites / "other"
    walked: list[Path] = []

    def scandir(path: object) -> object:
        # When the walk lists its second subfolder, it has read the first one.
        if str(path) != str(harness.sites / "page"):
            walked.append(Path(str(path)))
        if len(walked) == 2 and other.exists():
            walked[0].rename(harness.sites / "old")
            other.rename(walked[0])
        return original(path)

    with patch.object(os, "scandir", side_effect=scandir):
        assert harness.ask("page").startswith("Site page: syncing in progress.")
    assert not other.exists()


def test_a_deletion_before_the_listing_is_seen(harness: Harness) -> None:
    page = harness.put("page/index.html")
    harness.job("page")
    time.sleep(0.1)
    original = os.scandir

    def scandir(path: object) -> object:
        page.unlink(missing_ok=True)
        return original(path)

    with patch.object(os, "scandir", side_effect=scandir):
        assert harness.ask("page").startswith("Site page: syncing in progress.")


def test_an_unreadable_new_site_names_its_cause(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    harness.put("new/index.html")
    with patch.object(os, "scandir", side_effect=PermissionError(13, "synthetic")):
        text = harness.ask("new")
    assert text.startswith("Site new: syncing in progress.")
    assert "The sync state is unknown: PermissionError" in text


def test_an_unreadable_root_is_not_a_missing_site(harness: Harness) -> None:
    harness.put("page/index.html")
    with patch.object(Path, "lstat", side_effect=PermissionError(13, "synthetic")):
        text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert "The sync state is unknown: PermissionError" in text


def test_the_tool_does_not_wait_in_the_site_budget() -> None:
    tool = SiteStatusTool(SimpleNamespace())
    assert classify_tool("site_status", tool) == "default"


def test_a_folder_name_is_exact(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.put("page /index.html")
    harness.job("page")
    assert harness.ask("page").startswith("Site page: synced at ")
    assert harness.ask("page ").startswith("Site page : syncing in progress.")
    assert f"URL: {BASE}/page%20/" in harness.ask("page ")


def test_the_url_is_quoted_and_a_leading_underscore_is_a_site(harness: Harness) -> None:
    harness.put("demo#2/index.html")
    harness.put("_demo/index.html")
    assert f"URL: {BASE}/demo%232/" in harness.ask("demo#2")
    assert f"URL: {BASE}/_demo/" in harness.ask("_demo")


def test_the_outer_timeout_keeps_what_was_read(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.transport.fail_action = "site"
    harness.job("page")

    def slow(*_: object) -> float:
        time.sleep(0.6)
        return 0.0

    with (
        patch.object(site_status, "READ_TIMEOUT_SECONDS", 0.2),
        patch.object(site_status, "newest_change", side_effect=slow),
    ):
        text = harness.ask("page")
    assert "The sync state is unknown: no answer in 0.2 seconds." in text
    assert "synthetic remote interruption" in text


def test_a_blank_site_folder_is_the_default_of_the_shell(harness: Harness) -> None:
    harness.config.DAME_CURIE_SITE_DIR = ""
    assert "in the authoring root public/bot." in harness.ask("page")


def test_a_slow_walk_still_names_a_failed_sync(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    data = json.loads(harness.file.read_text())
    data["check_error"] = "synthetic check failure"
    harness.file.write_text(json.dumps(data))
    with patch.object(site_status, "newest_change", side_effect=TimeoutError("late")):
        text = harness.ask("page")
    assert "The sync state is unknown: TimeoutError: late." in text
    assert "synthetic check failure" in text


def test_a_large_tree_stops_its_own_walk(harness: Harness) -> None:
    harness.put("page/index.html")
    with pytest.raises(TimeoutError):
        site_status.newest_change(harness.sites / "page", time.monotonic() - 1)


def test_a_refused_local_file_names_its_cause(harness: Harness) -> None:
    page = harness.put("page/index.html")
    os.link(page, harness.sites / "page/link.html")
    harness.job()
    text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert "hardlinked source refused" in text


def test_a_failed_remote_check_is_named(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.transport.fail_action = "inventory"
    harness.job()
    assert (
        "The last check of the remote failed: synthetic remote interruption."
        in harness.ask("page")
    )
    harness.transport.fail_action = ""
    harness.job()
    harness.job("page")
    assert harness.ask("page").startswith("Site page: synced at ")
    harness.transport.fail_action = "inventory"
    harness.job()
    text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert "The last check of the remote failed" in text


def test_a_silent_publisher_is_named(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    data = json.loads(harness.file.read_text())
    data["written"] -= 31 * 60
    harness.file.write_text(json.dumps(data))
    text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert "The publisher has not reported since" in text
    assert "The operator must check it. Tell the user once." in text


def test_a_removed_site_leaves_the_status(harness: Harness) -> None:
    page = harness.put("page/index.html")
    harness.job("page")
    page.unlink()
    page.parent.rmdir()
    harness.job()
    assert "page" not in json.loads(harness.file.read_text())["sites"]
    assert harness.ask("page").startswith("Error: there is no folder 'page'")


@pytest.mark.parametrize(
    "missing",
    ["unset", "absent", "invalid", "shape", "list", "text", "no-time", "huge", "null"],
)
def test_an_unreadable_status_still_gives_the_url_and_names_the_cause(
    harness: Harness, missing: str
) -> None:
    harness.put("page/index.html")
    if missing == "unset":
        harness.config.DAME_CURIE_PUBLISHER_STATUS = ""
    elif missing != "absent":
        page = {
            "text": {"synced": "x"},
            "no-time": {"error": "x"},
            "huge": {"synced": 1e999},
            "null": {"synced": None},
        }.get(missing)
        status = {"written": time.time(), "check_error": "", "sites": {"page": page}}
        content = {"invalid": "{", "shape": "{}", "list": "[]"}.get(missing)
        content = content or json.dumps(status)
        harness.file.write_text(content)
    text = harness.ask("page")
    assert text.startswith("Site page: syncing in progress.")
    assert f"URL: {BASE}/page/" in text
    assert "The sync state is unknown: " in text


@pytest.mark.parametrize("name", ["", "  ", "..", ".hidden", "_images", "_data", "a/b"])
def test_only_one_site_folder_is_accepted(harness: Harness, name: str) -> None:
    text = harness.ask(name)
    assert text.startswith("Error: ")


def test_a_slow_read_does_not_hold_the_reply(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")

    async def ask() -> tuple[str, float]:
        started = time.monotonic()
        text = await harness.tool.execute(SimpleNamespace(), site="page")
        return text, time.monotonic() - started

    with (
        patch.object(site_status, "READ_TIMEOUT_SECONDS", 0.1),
        patch.object(
            site_status, "newest_change", side_effect=lambda *_: time.sleep(1)
        ),
    ):
        loop = asyncio.new_event_loop()
        text, elapsed = loop.run_until_complete(ask())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
    assert elapsed < 0.8
    assert text.startswith("Site page: syncing in progress.")
    assert f"URL: {BASE}/page/" in text
    assert "The sync state is unknown: no answer in 0.1 seconds." in text


def test_the_tool_changes_no_file_and_makes_no_request(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.job("page")
    before = sorted((p, p.lstat().st_ctime_ns) for p in harness.sites.rglob("*"))
    requests = len(harness.transport.requests)
    harness.watcher.drain()
    harness.watcher.take_changes()
    harness.ask("page")
    harness.watcher.drain()
    assert harness.watcher.take_changes() == set()
    assert len(harness.transport.requests) == requests
    assert before == sorted(
        (p, p.lstat().st_ctime_ns) for p in harness.sites.rglob("*")
    )


def test_a_status_that_cannot_be_written_stops_the_publisher(harness: Harness) -> None:
    harness.put("page/index.html")
    harness.file.parent.rmdir()
    with pytest.raises(PublisherError, match="status file not written: ENOENT"):
        harness.job()


def test_the_status_folder_is_private_and_separate(tmp_path: Path) -> None:
    for name in ("public", "stage", "state", "status"):
        (tmp_path / name).mkdir(mode=0o700)
    for name in ("key", "known_hosts"):
        (tmp_path / name).touch(mode=0o600)
    values = {
        name: str(tmp_path / target)
        for name, target in (
            ("source", "public"),
            ("staging", "stage"),
            ("state", "state"),
            ("status", "status"),
            ("key", "key"),
            ("known_hosts", "known_hosts"),
        )
    }
    values |= {"host": "a.invalid", "user": "p", "site_root": "/a", "image_root": "/b"}
    path = tmp_path / "publisher.toml"

    def load(**changes: str) -> Config:
        rows = (f"{k} = {json.dumps(v)}" for k, v in (values | changes).items())
        path.write_text("\n".join(rows))
        path.chmod(0o600)
        return load_config(path)

    config = load()
    assert config.status == tmp_path / "status"
    assert replace(config, status=None).status is None
    with pytest.raises(PublisherError, match="local roots overlap"):
        load(status=str(tmp_path / "public/status"))
    (tmp_path / "status").chmod(0o755)
    with pytest.raises(PublisherError, match="private directory permissions refused"):
        load()


def test_the_tool_is_registered_and_returns_its_result() -> None:
    assert "site_status" in CORE_TOOL_NAMES
    assert "site_status" in RESULT_TOOL_NAMES
    assert TOOL_PARAMETERS["site_status"]["required"] == ["site"]
    assert "site_status" in KNOWN_TOOLS
    description = SiteStatusTool(SimpleNamespace()).get_description()
    assert "cannot start, speed up or repair a sync" in description
    assert "Never poll it" in description


def test_the_tool_does_not_depend_on_the_shell() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "bot.py").read_text()
    assert '\n        self.tools["site_status"] = SiteStatusTool(self)\n' in source


def test_the_unit_starts_without_the_optional_folder() -> None:
    root = Path(__file__).resolve().parents[1]
    unit = (root / "scripts/publisher/dame-curie-publisher.service").read_text()
    assert " -/srv/dame-curie/publisher-status\n" in unit


def test_the_image_ships_the_module() -> None:
    root = Path(__file__).resolve().parents[1]
    assert " site_status.py " in (root / "docker/app.Dockerfile").read_text()
    allowed = (root / "docker/app.Dockerfile.dockerignore").read_text().splitlines()
    assert "!site_status.py" in allowed
