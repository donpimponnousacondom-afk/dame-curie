#!/usr/bin/env python3
"""Count or backfill embeddings in one explicitly selected, existing RAG database."""

import argparse
import asyncio
import contextlib
import json
import sqlite3
import sys
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "backfill"))
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
    args = parser.parse_args(argv)
    try:
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
