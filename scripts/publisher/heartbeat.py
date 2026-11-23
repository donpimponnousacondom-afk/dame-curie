import errno
import os
import socket
from datetime import datetime

from .common import PublisherError
from .config import Config

# The largest number of remote calls in one job: probe, remove, claim and transfer.
REMOTE_CALLS_PER_JOB = 4
LOCAL_WORK_SECONDS = 300


def check_watchdog(config: Config) -> None:
    """Refuse a watchdog limit that a healthy publisher can reach.

    The longest healthy time between two reports is two rescan periods and one full job:
    a site that changes just before a check is due can delay it by a second period.
    systemd sets WATCHDOG_USEC only when the unit has WatchdogSec.
    """
    limit = int(os.environ.get("WATCHDOG_USEC", "0")) / 1_000_000
    needed = (
        2 * config.rescan_seconds
        + REMOTE_CALLS_PER_JOB * config.timeout_seconds
        + LOCAL_WORK_SECONDS
    )
    if limit and limit < needed:
        raise PublisherError(
            f"WatchdogSec {limit:g}s is less than the {needed:g}s that rescan_seconds="
            f"{config.rescan_seconds:g} and timeout_seconds={config.timeout_seconds} need"
        )


def local_time() -> str:
    """Return the local time with its offset, for the status line."""
    return datetime.now().astimezone().isoformat(sep=" ", timespec="seconds")


def notify(message: str) -> None:
    """Send one message to systemd. Outside a systemd service there is no receiver.

    systemd sets NOTIFY_SOCKET when the unit has NotifyAccess. A failed send stops the
    publisher with its cause: a publisher that cannot report is not supervised.
    """
    address = os.environ.get("NOTIFY_SOCKET", "")
    if not address:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as channel:
            channel.sendto(message.encode(), address)
    except OSError as error:
        name = errno.errorcode.get(error.errno, "UNKNOWN")
        raise PublisherError(f"systemd notification failed: {name}") from error
