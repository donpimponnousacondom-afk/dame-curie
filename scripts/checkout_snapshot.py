import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time


MAX_RESPONSE_BYTES = 64 * 1024
GIT_TIMEOUT_SECONDS = 10.0
GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C.UTF-8",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}
STATUS_ARGS = (
    "status", "--porcelain=v2", "--branch", "-z",
    "--untracked-files=normal", "--no-ahead-behind", "--no-renames",
)


def git_output(repository: Path, arguments: tuple[str, ...], deadline: float) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("checkout snapshot deadline exceeded")
    result = subprocess.run(
        [
            "/usr/bin/git", "--no-optional-locks", "--no-pager",
            "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
            "-c", "core.hooksPath=/dev/null", "-c", "i18n.logOutputEncoding=utf-8",
            "-C", str(repository), *arguments,
        ],
        env=GIT_ENV,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=remaining,
    )
    if result.returncode or result.stderr:
        raise ValueError("checkout Git read failed")
    return result.stdout


def parse_status(output: bytes) -> tuple[str, str, bool]:
    headers = {}
    dirty = False
    for record in output.split(b"\0"):
        if not record:
            continue
        if not record.startswith(b"# "):
            dirty = True
            break
        key, separator, value = record[2:].partition(b" ")
        if not separator or key in headers:
            raise ValueError("invalid checkout status")
        headers[key] = value
    commit = headers.get(b"branch.oid", b"").decode("ascii")
    branch = headers.get(b"branch.head", b"").decode("utf-8")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) or not branch:
        raise ValueError("checkout has no complete HEAD")
    return commit, branch, dirty


def capture_snapshot(repository: Path) -> dict[str, str | bool]:
    if not repository.is_absolute():
        raise ValueError("checkout path must be absolute")
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    initial = parse_status(git_output(repository, STATUS_ARGS, deadline))
    commit, branch, dirty = initial
    metadata = git_output(
        repository, ("log", "-1", "--format=%H%x00%cI%x00%s", commit, "--"), deadline
    ).rstrip(b"\n").decode("utf-8").split("\0")
    if len(metadata) != 3 or metadata[0] != commit:
        raise ValueError("invalid checkout commit metadata")
    date = datetime.fromisoformat(metadata[1])
    if date.tzinfo is None:
        raise ValueError("checkout commit date has no timezone")
    if parse_status(git_output(repository, STATUS_ARGS, deadline)) != initial:
        raise ValueError("checkout changed during capture")
    return {
        "commit": commit,
        "branch": branch,
        "date": date.astimezone(timezone.utc).isoformat(),
        "subject": metadata[2],
        "dirty": dirty,
    }


def snapshot_response(repository: Path) -> bytes:
    response = (json.dumps(capture_snapshot(repository), ensure_ascii=True) + "\n").encode("utf-8")
    if len(response) > MAX_RESPONSE_BYTES:
        raise ValueError("checkout snapshot response exceeds limit")
    return response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    arguments = parser.parse_args()
    try:
        response = snapshot_response(arguments.repository)
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
    except (OSError, subprocess.SubprocessError, ValueError):
        print("Checkout snapshot unavailable.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
