#!/usr/bin/env python3
"""Count or backfill embeddings, or remove old self copies, in one explicitly selected RAG database."""

import argparse
import asyncio
import contextlib
import json
import re
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


# The time prefix the gateway puts in front of a stored message.
_GATEWAY_PREFIX = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [^\]]+\] ")


def dedupe_self_copies(db_path: Path, apply: bool) -> dict:
    """Remove bot-side copies of messages that a gateway row already holds.

    Root, 1 November 2026: one row per Discord message. A copy matches when
    it is bot_reply:<id> or bot_update:<id> and the gateway row <id> of the
    same author exists, or when a gateway row
    (a digit-only Discord id) of the same author in the same channel holds
    exactly the copy's text after its time prefix. The content-hash
    deduplication keeps one row per identical text in a channel. Other
    copies stay.
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
        gateway_authors: dict[str, str] = {}
        gateway_texts: dict[tuple[str, str], set[str]] = {}
        for row_id, channel_id, author_id, content in db.execute(
            "SELECT id, channel_id, author_id, content FROM vectors "
            "WHERE id != '' AND id NOT GLOB '*[^0-9]*'"
        ):
            gateway_authors[row_id] = author_id
            text = _GATEWAY_PREFIX.sub("", str(content or ""), count=1).strip()
            gateway_texts.setdefault((channel_id, author_id), set()).add(text)
        counts = {prefix.rstrip(":"): {"matched": 0, "kept": 0} for prefix in SELF_COPY_PREFIXES}
        matched_ids = []
        for row_id, channel_id, author_id, content in copies:
            prefix = next(p for p in SELF_COPY_PREFIXES if row_id.startswith(p))
            suffix = row_id[len(prefix):]
            text = str(content or "").strip()
            # Only bot_reply:<sent id> and bot_update:<sent id> carry the id
            # of her own sent message. bot_send_message:<id> carries the id of
            # the message she answered, and a chunk fallback carries that id
            # too, so those match by text only.
            same_id = (
                prefix in ("bot_reply:", "bot_update:")
                and ":" not in suffix
                and gateway_authors.get(suffix) == author_id
            )
            found = same_id or (
                bool(text) and text in gateway_texts.get((channel_id, author_id), set())
            )
            counts[prefix.rstrip(":")]["matched" if found else "kept"] += 1
            if found:
                matched_ids.append(row_id)
        result: dict = {"apply": apply, "copies": counts, "deleted": 0}
        if apply and matched_ids:
            backup = db_path.with_name(
                f"{db_path.stem}.before-self-dedupe-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.db"
            )
            try:
                # The backup holds private chat data: owner access only.
                backup.touch(mode=0o600, exist_ok=False)
                with contextlib.closing(sqlite3.connect(backup)) as target:
                    db.backup(target)
            except (OSError, sqlite3.Error) as exc:
                raise RuntimeError(
                    f"backup to {backup} failed ({type(exc).__name__}: {exc}); nothing was deleted"
                ) from exc
            try:
                with db:
                    db.executemany("DELETE FROM vectors WHERE id=?", [(i,) for i in matched_ids])
            except sqlite3.Error as exc:
                raise RuntimeError(
                    f"delete failed ({type(exc).__name__}: {exc}); the transaction was rolled "
                    f"back; the backup is {backup}"
                ) from exc
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
            try:
                print(json.dumps(dedupe_self_copies(args.db, args.apply), sort_keys=True))
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                print(f"dedupe-self-copies failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 1
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
