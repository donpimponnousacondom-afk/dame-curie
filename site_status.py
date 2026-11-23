"""The read-only sync status of a site, for the model.

Root, 23 November 2026: the model may query the sync and can never force it. It must not
wait for the remote. It gives the URL and leaves the rest to the publisher. This module
reads local files only: it makes no request and starts nothing.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from discord import Message

from tools import Tool

# A local walk that takes longer than this must not hold a reply.
READ_TIMEOUT_SECONDS = 5
# systemd restarts a publisher that reports nothing for this time (WatchdogSec).
SILENT_PUBLISHER_SECONDS = 30 * 60
# The kernel stamps files with a coarse clock that can lag the clock of the publisher.
CLOCK_MARGIN_SECONDS = 0.05
# Folders of the authoring root that are not sites: images and the publisher exclusions.
UNPUBLISHED_NAMES = frozenset({"_images", "_data", "_build"})


def local_time(seconds: float) -> str:
    """Return a time of the status file in the process local zone."""
    return (
        datetime.fromtimestamp(seconds).astimezone().strftime("%H:%M:%S on %-d %B %Y")
    )


def hidden_folders(folder: Path) -> list[str]:
    """Return the top-level hidden folders. The remote keeps them and no check reads them."""
    return sorted(
        entry.name
        for entry in os.scandir(folder)
        if entry.name.startswith(".") and entry.is_dir(follow_symlinks=False)
    )


def newest_change(folder: Path, deadline: float) -> float:
    """Return the time of the newest change in a site, deletions included.

    A file that disappears during the walk is a change that happens now.
    """
    try:
        newest = folder.stat().st_ctime
        skipped = hidden_folders(folder)
        for parent, directories, files in os.walk(folder):
            if time.monotonic() > deadline:
                raise TimeoutError
            if Path(parent) == folder:
                directories[:] = [name for name in directories if name not in skipped]
            for name in (*directories, *files):
                newest = max(newest, os.lstat(os.path.join(parent, name)).st_ctime)
    except FileNotFoundError:
        return time.time()
    return newest


def read_status(status_file: str) -> dict:
    """Return the content of the status file. A wrong shape is an error with its cause."""
    status = json.loads(Path(status_file).read_text(encoding="utf-8"))
    if not isinstance(status, dict) or not (
        isinstance(status.get("sites"), dict)
        and isinstance(status.get("written"), int | float)
        and isinstance(status.get("check_error"), str)
        and all(isinstance(site, dict) for site in status["sites"].values())
    ):
        raise ValueError("the status file has an unexpected shape")
    return status


def publisher_notes(status: dict, site: dict) -> list[str]:
    """Return what the publisher reported about itself, when it is not healthy."""
    notes = []
    if site.get("error"):
        notes.append(
            f"The last sync attempt failed at {local_time(site['failed'])}: "
            f"{site['error']}. It is retried by itself."
        )
    if status["check_error"]:
        notes.append(
            f"The last check of the remote failed: {status['check_error']}. "
            "It is retried by itself."
        )
    silent = time.time() - status["written"]
    if silent > SILENT_PUBLISHER_SECONDS:
        notes.append(
            f"The publisher has not reported since {local_time(status['written'])}. "
            "The operator must check it. Tell the user once."
        )
    return notes


def waiting_text(name: str, link: str) -> str:
    """Return the answer for every site that is not known to be synced."""
    return (
        f"{name}: syncing in progress. The site is created. Give the user the URL now. "
        f"It goes live by itself. Do not wait for it, test it or ask again. {link}"
    )


def site_report(name: str, root: Path, link: str, status_file: str) -> str:
    """Return the sync state of one site as text for the model."""
    deadline = time.monotonic() + READ_TIMEOUT_SECONDS
    folder = root / name
    if folder.is_symlink() or not folder.is_dir():
        return f"Error: there is no folder {name!r} in the authoring root {root}."
    waiting = waiting_text(name, link)
    if not status_file:
        return f"{waiting}\nThe sync state is unknown: DAME_CURIE_PUBLISHER_STATUS is not set."
    try:
        status = read_status(status_file)
    except (OSError, ValueError) as error:
        return f"{waiting}\nThe sync state is unknown: {error}."
    site = status["sites"].get(name, {})
    synced = site.get("synced")
    lines = [waiting]
    if synced and newest_change(folder, deadline) < synced - CLOCK_MARGIN_SECONDS:
        lines = [f"{name}: synced at {local_time(synced)}. {link}"]
        if hidden := hidden_folders(folder):
            lines.append(f"Not part of this check: {', '.join(hidden)}.")
    return "\n".join([*lines, *publisher_notes(status, site)])


class SiteStatusTool(Tool):
    """Tell the model the URL of a site and whether the publisher has synced it."""

    def get_description(self) -> str:
        """Return the tool description that the model reads."""
        return (
            "Show the public URL of one of your sites and whether its files are synced to "
            "the remote. It only reads: it cannot start, speed up or repair a sync. "
            "'syncing in progress' is a good result: give the user the URL and stop. "
            "Never poll it. Params: site (required, the folder name in the authoring root)."
        )

    async def execute(self, message: Message, site: str = "", **kwargs: object) -> str:
        """Return the sync state of the site at once."""
        name = str(site or "").strip().strip("/")
        if (
            not name
            or Path(name).name != name
            or name.startswith(".")
            or name in UNPUBLISHED_NAMES
        ):
            return (
                "Error: site must be the name of one site folder in the authoring root."
            )
        config = self.bot.config
        base = config.DAME_CURIE_SITE_PUBLIC_BASE_URL.rstrip("/")
        link = (
            f"URL: {base}/{quote(name)}/"
            if base
            else "URL: the operator configured no public site base."
        )
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    site_report,
                    name,
                    Path(config.DAME_CURIE_SITE_DIR),
                    link,
                    config.DAME_CURIE_PUBLISHER_STATUS,
                ),
                READ_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            return (
                f"{waiting_text(name, link)}\nThe sync state is unknown: the local files "
                f"were not read in {READ_TIMEOUT_SECONDS} seconds."
            )
