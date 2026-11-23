import errno
import json
import os
import time
from pathlib import Path

from .common import PublisherError


class StatusFile:
    """The sync state of each site, for a reader that cannot reach the publisher.

    The publisher only writes this file. Nothing reads it back, so a reader of the file
    cannot change or start a sync. Times are seconds since the epoch.
    """

    def __init__(self, path: Path | None):
        self.path = path
        self.checked: float | None = None
        self.check_error = ""
        self.sites: dict[str, dict[str, float | str]] = {}

    def synced(self, name: str, started: float) -> None:
        """Record that the files of a site, as they were at `started`, are remote."""
        self.sites[name] = {"synced": started}

    def different(self, name: str) -> None:
        """Record that the remote differs. The cause of an earlier failure stays."""
        if name in self.sites:
            self.sites[name].pop("synced", None)

    def failed(self, name: str, error: str) -> None:
        """Record the cause of a failed attempt. The last successful sync stays."""
        self.sites.setdefault(name, {}).update(failed=time.time(), error=error)

    def write(self) -> None:
        """Replace the file. A failed write stops the publisher with its cause."""
        if self.path is None:
            return
        data = {
            "written": time.time(),
            "checked": self.checked,
            "check_error": self.check_error,
            "sites": self.sites,
        }
        temporary = self.path / ".status.json.tmp"
        try:
            temporary.write_text(json.dumps(data), encoding="utf-8")
            os.replace(temporary, self.path / "status.json")
        except OSError as error:
            name = errno.errorcode.get(error.errno, "UNKNOWN")
            raise PublisherError(f"status file not written: {name}") from error
