"""The read-only sync status of a site, for the model.

Root, 23 November 2026: the model may query the sync and can never force it. It must not
wait for the remote. It gives the URL and leaves the rest to the publisher. This module
reads local files only: it makes no request and starts nothing.
"""

import asyncio
import json
import os
import stat
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
# The publisher never publishes these names (EXCLUDED in scripts/publisher/common.py).
NEVER_PUBLISHED = frozenset({"_data", "_build", ".env", ".git", ".publisher-link"})
NOT_CHECKED = (
    "Not part of this check: hidden folders at the top of the site. Never published: "
    f"symlinks, and files or folders named {', '.join(sorted(NEVER_PUBLISHED))}."
)


def local_time(seconds: float) -> str:
    """Return a time of the status file in the process local zone."""
    return (
        datetime.fromtimestamp(seconds).astimezone().strftime("%H:%M:%S on %-d %B %Y")
    )


def raise_error(error: OSError) -> None:
    """Make os.walk raise. It skips a folder that it cannot read by default."""
    raise error


def newest_change(folder: Path, deadline: float) -> float:
    """Return the time of the newest change in a site, deletions included.

    The top-level hidden folders are not read: no remote check reads them either.
    """
    newest = 0.0
    for parent, directories, files in os.walk(folder, onerror=raise_error):
        top = Path(parent) == folder
        directories[:] = [
            name
            for name in directories
            if name not in NEVER_PUBLISHED and not (top and name.startswith("."))
        ]
        # "." is read after the listing, so a deletion before the listing is seen.
        for name in (".", *directories, *files):
            if time.monotonic() > deadline:
                raise TimeoutError(f"no answer in {READ_TIMEOUT_SECONDS} seconds")
            if name not in NEVER_PUBLISHED:
                newest = max(newest, os.lstat(os.path.join(parent, name)).st_ctime)
    return newest


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
        f"Site {name}: syncing in progress. It is created. Give the user the URL now. "
        f"It goes live by itself. Do not wait for it, test it or ask again. {link}"
    )


def unknown_text(name: str, link: str, cause: str) -> str:
    """Return the answer when the state is not readable: the URL and the cause."""
    return f"{waiting_text(name, link)}\nThe sync state is unknown: {cause}."


def site_report(
    name: str, root: Path, link: str, status_file: str, deadline: float
) -> str:
    """Return the sync state of one site as text for the model."""
    folder = root / name
    try:
        is_site = stat.S_ISDIR(folder.lstat().st_mode)
    except FileNotFoundError:
        is_site = False
    except (OSError, ValueError) as error:
        return unknown_text(name, link, f"{type(error).__name__}: {error}")
    if not is_site:
        return f"Error: there is no folder {name!r} in the authoring root {root}."
    if not status_file:
        return unknown_text(name, link, "DAME_CURIE_PUBLISHER_STATUS is not set")
    notes: list[str] = []
    try:
        status = json.loads(Path(status_file).read_text(encoding="utf-8"))
        site = status["sites"].get(name, {})
        notes = publisher_notes(status, site)
        synced = site.get("synced", 0.0)
        changed = newest_change(folder, deadline)
        if not notes and changed < synced - CLOCK_MARGIN_SECONDS:
            lines = [
                f"Site {name}: synced at {local_time(synced)}. {link}",
                NOT_CHECKED,
            ]
        else:
            lines = [waiting_text(name, link)]
    except (
        OSError,
        ValueError,
        LookupError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as error:
        lines = [unknown_text(name, link, f"{type(error).__name__}: {error}")]
    return "\n".join([*lines, *notes])


class SiteStatusTool(Tool):
    """Tell the model the URL of a site and whether the publisher has synced it."""

    # "site" in the name would give it the small budget of the removed site tools.
    concurrency_class = "default"

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
        name = str(site or "").rstrip("/")
        if (
            not name
            or Path(name).name != name
            or name.startswith(".")
            or name in NEVER_PUBLISHED | {"_images"}
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
        # The executor can start the walk late. The deadline counts from the call.
        deadline = time.monotonic() + READ_TIMEOUT_SECONDS
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    site_report,
                    name,
                    Path(config.DAME_CURIE_SITE_DIR),
                    link,
                    config.DAME_CURIE_PUBLISHER_STATUS,
                    deadline,
                ),
                READ_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            cause = f"no answer in {READ_TIMEOUT_SECONDS} seconds"
            return unknown_text(name, link, cause)
