#!/usr/bin/env python3
"""Submit and read Dirac smoke requests.

The same file works on the host and inside the bot container: every path comes
from the config and is resolved against the config's own directory. This tool
never talks to Discord and never touches the bot — it publishes one immutable
request that the bot's smoke runtime will pick up, and reads the record back.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smoke_protocol import (
    DEFAULT_DEADLINE_SECONDS,
    SmokeSettings,
    build_request,
    clock_of,
    create_json_exclusive,
    iso_now,
    new_request_id,
    read_json_object,
    request_files,
    request_path,
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
    return parser


def _submit(settings: SmokeSettings, args: argparse.Namespace) -> int:
    task = args.task
    if args.task_file:
        task = Path(args.task_file).read_text(encoding="utf-8")
    request = build_request(
        request_id=new_request_id(),
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


def _result(settings: SmokeSettings, request_id: str) -> int:
    path = status_path(settings, request_id)
    if not path.exists():
        print(json.dumps({"request_id": request_id, "status": "pending"}))
        return 0
    print(json.dumps(read_json_object(path, "record"), indent=2, sort_keys=True))
    return 0


def _pending(settings: SmokeSettings) -> int:
    """Requests the runtime has not accepted yet, in the order it will run them."""
    rows = []
    for path in request_files(settings):
        if not status_path(settings, path.stem).exists():
            rows.append({"request_id": path.stem, "queued_at": clock_of(path)})
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
    return _pending(settings)


if __name__ == "__main__":
    raise SystemExit(main())
