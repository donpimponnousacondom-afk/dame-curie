import errno
import os
import socket
from datetime import datetime

from .common import PublisherError


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
