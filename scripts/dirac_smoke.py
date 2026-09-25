#!/usr/bin/env python3
"""Submit and read Dirac smoke requests.

Submit on the host: the container sees the request mount read-only, so writing a
request is a host operation, while ``result`` and ``pending`` read the same two
mounts from either side. The same file works in both places because every path
comes from the config and resolves against the config's own directory. This tool
never talks to Discord and never touches the bot.

The record directory is the ledger, and eligibility to run is "no record exists",
so an operator who wipes that directory makes the requests still sitting in the
request directory runnable again. A missing record proves only that no record is
present, not that a request was never run or a worker is alive; the advisory health
snapshot may also be stale or unavailable.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smoke_protocol import (
    DEFAULT_DEADLINE_SECONDS,
    SmokeProtocolError,
    SmokeSettings,
    build_request,
    create_json_exclusive,
    iso_now,
    read_json_object,
    request_files,
    request_path,
    runtime_state_path,
    status_path,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dirac_smoke",
        description="Operator smoke requests for the live Dirac bot.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="smoke config JSON (default: $DAME_CURIE_DIRAC_SMOKE_CONFIG)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="publish one operator request")
    source = submit.add_mutually_exclusive_group(required=True)
    source.add_argument("--task", default="", help="the instruction, inline")
    source.add_argument("--task-file", default="", help="the instruction, from a file")
    submit.add_argument("--thread", default="", help="a bot-owned thread id")
    submit.add_argument(
        "--deadline",
        type=float,
        default=DEFAULT_DEADLINE_SECONDS,
        help="seconds to wait for the turn",
    )
    result = commands.add_parser("result", help="print the record for one request")
    result.add_argument("request_id")
    commands.add_parser(
        "pending", help="list requests with no record yet, oldest first"
    )
    commands.add_parser("health", help="show advisory last-observed worker state")
    return parser


def _submit(settings: SmokeSettings, args: argparse.Namespace) -> int:
    task = args.task
    if args.task_file:
        task = Path(args.task_file).read_text(encoding="utf-8")
    request = build_request(
        request_id=uuid4().hex,
        task=task,
        thread_id=args.thread,
        deadline_seconds=args.deadline,
    )
    path = request_path(settings, request.request_id)
    create_json_exclusive(path, request.as_json())
    print(
        json.dumps(
            {
                "request_id": request.request_id,
                "request": str(path),
                "record": str(status_path(settings, request.request_id)),
                "submitted_at": iso_now(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _health(settings: SmokeSettings) -> dict[str, object]:
    """Return last-observed state without claiming worker liveness."""
    try:
        state = read_json_object(runtime_state_path(settings), "runtime state")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SmokeProtocolError):
        state = None
    return {"worker_liveness": "unknown", "last_observed": state}


def _result(settings: SmokeSettings, request_id: str) -> int:
    path = status_path(settings, request_id)
    if not path.exists():
        print(
            json.dumps(
                {
                    "request_id": request_id,
                    "status": "pending",
                    "acceptance": "no_record",
                    "worker_liveness": "unknown",
                }
            )
        )
        return 0
    print(json.dumps(read_json_object(path, "record"), indent=2, sort_keys=True))
    return 0


def _pending(settings: SmokeSettings) -> int:
    """Requests the runtime has not accepted yet, in the order it will run them.

    The clock is the file's own modification time: request ids are random, so a
    name order is not an arrival order.
    """
    rows = []
    for path in request_files(settings):
        if status_path(settings, path.stem).exists():
            continue
        try:
            queued_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except FileNotFoundError:
            continue
        rows.append(
            {
                "request_id": path.stem,
                "queued_at": queued_at.isoformat(timespec="seconds"),
                "acceptance": "no_record",
                "worker_liveness": "unknown",
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.config:
        settings = SmokeSettings.load(Path(args.config))
    else:
        settings = SmokeSettings.from_env()
    if args.command == "submit":
        return _submit(settings, args)
    if args.command == "result":
        return _result(settings, args.request_id)
    if args.command == "health":
        print(json.dumps(_health(settings), indent=2, sort_keys=True))
        return 0
    return _pending(settings)


if __name__ == "__main__":
    raise SystemExit(main())
