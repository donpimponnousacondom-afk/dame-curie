#!/usr/bin/env python3
"""Count or backfill embeddings, or remove old self copies, in one explicitly selected RAG database."""

import argparse
import asyncio
import contextlib
import json
import sqlite3
import sys
import time
from pathlib import Path

from rag_memory import EMBEDDINGS_ENABLED, RAGMemoryManager, embedding_status


def read_status(db_path: Path) -> dict:
    """Read counts without starting the manager, migrations, sidecar reads or HTTP."""
    with contextlib.closing(
        sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        return embedding_status(db)


async def backfill(
    db_path: Path, limit: int, batch_size: int, max_seconds: float
) -> dict:
    """Use the normal embedding client, restricted to the explicitly opened database."""
    memory = RAGMemoryManager(str(db_path.parent), db_path=db_path)
    try:
        return await memory.backfill_embeddings(
            limit=limit, batch_size=batch_size, max_seconds=max_seconds
        )
    finally:
        memory._db.close()


# Writers that stored a second copy of a message of the bot before #34. The
# gateway row under the Discord id holds the same text.
SELF_COPY_PREFIXES = ("bot_reply:", "bot_send_message:", "bot_update:", "rem_backfill:")


def dedupe_self_copies(db_path: Path, apply: bool) -> dict:
    """Remove bot-side copies whose text a gateway row of the same author holds.

    Root, 1 November 2026: one row per Discord message. A copy matches when
    a row with a numeric Discord id, in the same channel and by the same
    author, ends with the copy's text. Copies without such a row stay.
    ``apply`` writes a backup of the database next to it first.
    """
    mode = "rw" if apply else "ro"
    with contextlib.closing(
        sqlite3.connect(db_path.resolve().as_uri() + f"?mode={mode}", uri=True)
    ) as db:
        where = " OR ".join("id LIKE ?" for _ in SELF_COPY_PREFIXES)
        copies = db.execute(
            f"SELECT id, channel_id, author_id, content FROM vectors WHERE {where}",
            [prefix + "%" for prefix in SELF_COPY_PREFIXES],
        ).fetchall()
        counts = {prefix.rstrip(":"): {"matched": 0, "kept": 0} for prefix in SELF_COPY_PREFIXES}
        matched_ids = []
        for row_id, channel_id, author_id, content in copies:
            prefix = next(p for p in SELF_COPY_PREFIXES if row_id.startswith(p)).rstrip(":")
            text = str(content or "").strip()
            found = text and db.execute(
                "SELECT 1 FROM vectors WHERE channel_id=? AND author_id=? AND id GLOB '[0-9]*' "
                "AND substr(rtrim(content), -length(?)) = ? LIMIT 1",
                (channel_id, author_id, text, text),
            ).fetchone()
            if found:
                counts[prefix]["matched"] += 1
                matched_ids.append(row_id)
            else:
                counts[prefix]["kept"] += 1
        result: dict = {"apply": apply, "copies": counts, "deleted": 0}
        if apply and matched_ids:
            backup = db_path.with_name(
                f"{db_path.stem}.before-self-dedupe-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.db"
            )
            with contextlib.closing(sqlite3.connect(backup)) as target:
                db.backup(target)
            with db:
                db.executemany("DELETE FROM vectors WHERE id=?", [(i,) for i in matched_ids])
            result.update(deleted=len(matched_ids), backup=str(backup))
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "backfill", "dedupe-self-copies"))
    parser.add_argument(
        "--db", required=True, type=Path, help="existing configured RAG database"
    )
    parser.add_argument(
        "--limit", type=int, default=100, help="rows per pass, 1..10000"
    )
    parser.add_argument(
        "--batch-size", type=int, default=4, help="rows fetched at once, 1..64"
    )
    parser.add_argument(
        "--max-seconds", type=float, default=60, help="pass deadline, >0..600 seconds"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="dedupe-self-copies: delete the matched copies after a backup (default: count only)",
    )
    args = parser.parse_args(argv)
    try:
        if args.action == "dedupe-self-copies":
            print(json.dumps(dedupe_self_copies(args.db, args.apply), sort_keys=True))
            return 0
        counts = read_status(args.db)
        if args.action == "status":
            result = counts
        elif not EMBEDDINGS_ENABLED:
            result = {"stopped": "disabled", "attempted": 0, "counts": counts}
        else:
            result = asyncio.run(
                backfill(args.db, args.limit, args.batch_size, args.max_seconds)
            )
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(
            f"RAG maintenance failed ({type(exc).__name__}); check the database path/schema and bounds.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130
    print(json.dumps(result, sort_keys=True))
    return (
        2
        if result.get("failed")
        or result.get("stopped") in {"deadline", "endpoint_paused"}
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
