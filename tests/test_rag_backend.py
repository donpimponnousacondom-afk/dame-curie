"""Offline regressions for embedding identity, validation and resumable maintenance."""

import asyncio
import hashlib
import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

import doctor
import rag_maintenance
import rag_memory as rag


class UnmockedNetwork(BaseException):
    pass


class Reply:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload

    async def text(self):
        raise AssertionError("response bodies must not reach diagnostics")


class Transport:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.replies)


@pytest.fixture(autouse=True)
def embedding_config(monkeypatch):
    monkeypatch.setattr(rag, "EMBED_DIM", 8)
    monkeypatch.setattr(rag, "EMBED_MODEL", "test-model-a")
    monkeypatch.setattr(rag, "EMBED_URL", "http://embedding.invalid/api/embed")
    monkeypatch.setattr(rag, "EMBED_HEADERS", {})
    monkeypatch.setattr(rag, "EMBEDDINGS_ENABLED", True)
    monkeypatch.setattr(rag_maintenance, "EMBEDDINGS_ENABLED", True)

    def forbidden_http(*args, **kwargs):
        raise UnmockedNetwork("unmocked embedding network request")

    monkeypatch.setattr(rag.aiohttp, "ClientSession", forbidden_http)


@pytest.fixture
def memory(tmp_path):
    manager = rag.RAGMemoryManager(str(tmp_path))
    yield manager
    manager._db.close()


def vector(dimension=8, index=0):
    values = [0.0] * dimension
    values[index] = 1.0
    return values


def insert(
    manager,
    row_id="fact",
    text="a durable synthetic fact",
    kind="ltm",
    blob=None,
    backend="",
):
    manager._db.execute(
        "INSERT INTO vectors (id, kind, content, embedding, embedding_backend, timestamp, created_at) "
        "VALUES (?, ?, ?, ?, ?, '', 1)",
        (row_id, kind, text, blob, backend),
    )


def install_transport(monkeypatch, *replies):
    transport = Transport(replies)
    monkeypatch.setattr(rag.aiohttp, "ClientSession", lambda: transport)
    return transport


@pytest.mark.parametrize(
    "values",
    [
        [],
        [1.0] * 7,
        [[1.0]] * 8,
        [float("nan")] * 8,
        [float("inf")] * 8,
        [float("-inf")] * 8,
        [0.0] * 8,
        ["1"] * 8,
        [True] * 8,
        [True] + [1.0] * 7,
        [None] * 8,
        [1e100] * 8,
    ],
)
def test_response_rejects_invalid_vectors(values):
    with pytest.raises(ValueError):
        rag.validate_embedding_response({"embeddings": [values]}, 8)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"error": "private server detail", "embeddings": [vector()]},
        {"embeddings": [vector(), vector()]},
        {"data": [{"embedding": vector()}, {"ignored": True}]},
        {"data": [{"embedding": vector(), "index": 1}]},
        {"data": [{"embedding": vector(), "index": False}]},
    ],
)
def test_response_rejects_partial_or_ambiguous_wrappers(payload):
    with pytest.raises(ValueError):
        rag.validate_embedding_response(payload, 8)


def test_openai_indices_are_validated_and_reordered():
    result = rag.validate_embedding_response(
        {
            "data": [
                {"index": 1, "embedding": vector(index=1)},
                {"index": 0, "embedding": vector(index=0)},
            ]
        },
        8,
        count=2,
    )
    assert np.array_equal(result[0], vector(index=0))
    assert np.array_equal(result[1], vector(index=1))
    with pytest.raises(ValueError):
        rag.validate_embedding_response(
            {
                "data": [
                    {"index": 0, "embedding": vector()},
                    {"index": 0, "embedding": vector()},
                ]
            },
            8,
            count=2,
        )


def test_large_finite_vectors_normalize_without_float32_overflow():
    result = rag.validate_embedding([1e30] * 8, 8)
    assert np.isfinite(result).all()
    assert np.linalg.norm(result) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "change,value",
    [
        ("EMBED_MODEL", "test-model-b"),
        ("EMBED_DIM", 16),
        ("EMBED_URL", "http://other-embedding.invalid/api/embed"),
    ],
)
def test_switch_quarantines_vectors_and_cache_without_losing_facts(
    tmp_path, monkeypatch, change, value
):
    first = rag.RAGMemoryManager(str(tmp_path))
    insert(first)
    install_transport(monkeypatch, Reply({"embeddings": [vector()]}))
    assert asyncio.run(first._embed_and_store("fact", "a durable synthetic fact"))
    old_identity = first.embedding_backend
    first._db.close()

    monkeypatch.setattr(rag, change, value)
    second = rag.RAGMemoryManager(str(tmp_path))
    assert second.embedding_backend != old_identity
    assert second.embedding_status()["stale"] == 1
    transport = install_transport(
        monkeypatch, Reply({"embeddings": [vector(second.embed_dim)]})
    )
    assert (
        asyncio.run(second.rag_search("a durable synthetic fact", kinds=["ltm"])) == []
    )
    assert len(transport.calls) == 1
    report = asyncio.run(second.backfill_embeddings())
    assert report["embedded"] == 1
    assert report["counts"]["pending"] == 0
    assert second.get_long_term_memory()[0]["content"] == "a durable synthetic fact"
    assert second._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 2
    assert (
        len(asyncio.run(second.rag_search("a durable synthetic fact", kinds=["ltm"])))
        == 1
    )
    second._db.close()


def test_manager_keeps_its_backend_when_another_configuration_loads(
    memory, monkeypatch
):
    original = memory.embedding_backend
    monkeypatch.setattr(rag, "EMBED_MODEL", "different-model")
    monkeypatch.setattr(rag, "EMBED_DIM", 16)
    transport = install_transport(monkeypatch, Reply({"embeddings": [vector()]}))
    result = asyncio.run(memory._embed("immutable backend settings"))
    assert result.shape == (8,)
    assert memory.embedding_backend == original
    assert transport.calls[0][1]["json"]["model"] == "test-model-a"


def test_legacy_vectors_and_cache_are_never_adopted(tmp_path, monkeypatch):
    memory = rag.RAGMemoryManager(str(tmp_path))
    content = "a durable synthetic fact"
    blob = rag._embedding_to_blob(np.array(vector(), dtype=np.float32))
    insert(memory, text=content, blob=blob)
    memory._db.execute("ALTER TABLE vectors DROP COLUMN embedding_backend")
    memory._db.execute("ALTER TABLE embed_cache DROP COLUMN backend")
    memory._db.execute(
        "INSERT INTO embed_cache VALUES (?, 8, ?, 0, 0, 0)",
        (hashlib.sha256(content.encode()).hexdigest(), blob),
    )
    memory._db.close()
    reopened = rag.RAGMemoryManager(str(tmp_path))
    assert reopened.embedding_status()["stale"] == 1
    assert reopened._db.execute("SELECT content, embedding FROM vectors").fetchone()[
        :
    ] == (content, blob)
    transport = install_transport(monkeypatch, Reply({"embeddings": [vector(index=1)]}))
    actual = asyncio.run(reopened._embed(content))
    assert np.array_equal(actual, vector(index=1))
    assert len(transport.calls) == 1
    reopened._db.close()


def test_current_cache_survives_restart_and_endpoint_outage(tmp_path, monkeypatch):
    first = rag.RAGMemoryManager(str(tmp_path))
    transport = install_transport(monkeypatch, Reply({"embeddings": [vector()]}))
    expected = asyncio.run(first._embed("cached synthetic text"))
    first._db.close()
    second = rag.RAGMemoryManager(str(tmp_path))
    second._embed_endpoint_down_until = float("inf")
    assert np.array_equal(asyncio.run(second._embed("cached synthetic text")), expected)
    assert len(transport.calls) == 1
    second._db.close()


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"embeddings": [[float("nan")] * 8]}, 200),
        ({"embeddings": [[1.0] * 7]}, 200),
        ({"data": []}, 200),
        (ValueError("private malformed payload"), 200),
        ({"error": "private server detail"}, 503),
    ],
)
def test_failure_breaker_recovers_and_clears_query_cooldown(
    memory, monkeypatch, caplog, payload, status
):
    clock = [100.0]
    monkeypatch.setattr(rag.time, "monotonic", lambda: clock[0])
    transport = install_transport(
        monkeypatch, Reply(payload, status), Reply({"embeddings": [vector()]})
    )
    assert asyncio.run(memory._embed("failed text")) is None
    assert asyncio.run(memory._embed("suppressed text")) is None
    assert len(transport.calls) == 1
    memory._query_embed_disabled_until = 1000
    clock[0] += rag.EMBED_ENDPOINT_COOLDOWN_SECONDS + 1
    assert asyncio.run(memory._embed("recovery text")) is not None
    assert memory._embed_endpoint_down_until == 0
    assert memory._query_embed_disabled_until == 0
    assert len(transport.calls) == 2
    assert "private" not in caplog.text
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 1


def test_queued_requests_recheck_breaker_after_semaphore(memory, monkeypatch):
    transport = install_transport(monkeypatch, Reply({}, 503))

    async def run():
        await memory._embed_semaphore.acquire()
        tasks = [
            asyncio.create_task(memory._embed(f"queued text {index}"))
            for index in range(5)
        ]
        await asyncio.sleep(0)
        memory._embed_semaphore.release()
        return await asyncio.gather(*tasks)

    assert asyncio.run(run()) == [None] * 5
    assert len(transport.calls) == 1


def test_corrupt_vectors_and_cache_cannot_enter_search(memory, monkeypatch):
    content = "valid synthetic fact"
    corrupt = rag._embedding_to_blob(np.array([float("nan")] * 8, dtype=np.float32))
    insert(memory, text=content, blob=corrupt, backend=memory.embedding_backend)
    key = hashlib.sha256(f"{memory.embedding_backend}\0{content}".encode()).hexdigest()
    memory._db.execute(
        "INSERT INTO embed_cache VALUES (?, 8, ?, 0, 0, 0, ?)",
        (key, corrupt, memory.embedding_backend),
    )
    assert memory.embedding_status()["invalid"] == 1
    transport = install_transport(monkeypatch, Reply({"embeddings": [vector()]}))
    assert asyncio.run(memory.rag_search(content, kinds=["ltm"])) == []
    assert len(transport.calls) == 1
    report = asyncio.run(memory.backfill_embeddings())
    assert report["embedded"] == 1
    assert report["counts"]["invalid"] == 0


def test_negative_vectors_from_other_backends_do_not_suppress_matches(
    memory, monkeypatch
):
    blob = rag._embedding_to_blob(np.array(vector(), dtype=np.float32))
    insert(memory, blob=blob, backend=memory.embedding_backend)
    insert(
        memory,
        "negative",
        "a different fact",
        kind="negative",
        blob=blob,
        backend="other",
    )
    monkeypatch.setattr(
        memory, "_embed", AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    )
    hits = asyncio.run(
        memory.rag_search("a query", kinds=["ltm"], exclude_negatives=True)
    )
    assert len(hits) == 1


def test_backfill_moves_past_failed_prefix_and_resumes_after_restart(
    tmp_path, monkeypatch
):
    manager = rag.RAGMemoryManager(str(tmp_path))
    for index in range(12):
        insert(manager, str(index), f"synthetic row {index}")
    seen = []

    async def embed(text):
        seen.append(text)
        return (
            np.array(vector(), dtype=np.float32)
            if int(text.rsplit(" ", 1)[1]) >= 9
            else None
        )

    monkeypatch.setattr(manager, "_embed", embed)
    assert (
        asyncio.run(manager.backfill_embeddings(limit=4, batch_size=1))["attempted"]
        == 4
    )
    manager._db.close()
    manager = rag.RAGMemoryManager(str(tmp_path))
    monkeypatch.setattr(manager, "_embed", embed)
    assert asyncio.run(manager.backfill_embeddings(limit=4))["attempted"] == 4
    report = asyncio.run(manager.backfill_embeddings(limit=4))
    assert report["embedded"] == 3
    assert seen == [f"synthetic row {index}" for index in range(12)]
    report = asyncio.run(manager.backfill_embeddings())
    assert report["scan_complete"]
    assert report["attempted"] == 0
    monkeypatch.setattr(
        manager, "_embed", AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    )
    assert asyncio.run(manager.backfill_embeddings())["counts"]["pending"] == 0
    assert len(manager.get_long_term_memory()) == 12
    manager._db.close()


def test_negative_background_embedding_uses_the_stored_snapshot(memory, monkeypatch):
    embed = AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    monkeypatch.setattr(memory, "_embed", embed)
    content = "synthetic negative example " * 100

    async def run():
        negative_id = await memory.add_negative(content)
        await memory.flush()
        return negative_id

    negative_id = asyncio.run(run())
    row = memory._db.execute(
        "SELECT content, embedding_backend FROM vectors WHERE id=?", (negative_id,)
    ).fetchone()
    assert row["content"] == content[:1500]
    assert row["embedding_backend"] == memory.embedding_backend
    assert embed.call_args.args[0] == content[:1500]


def test_backfill_includes_system_authored_negative_and_entity_facts(
    memory, monkeypatch
):
    monkeypatch.setattr(rag, "EMBEDDINGS_ENABLED", False)

    async def populate():
        await memory.add_negative("synthetic negative example")
        await memory.add_entity_fact("123", "synthetic entity fact")

    asyncio.run(populate())
    monkeypatch.setattr(rag, "EMBEDDINGS_ENABLED", True)
    counts = memory.embedding_status()
    assert counts["eligible_pending"] == 2
    assert counts["excluded"] == 0
    monkeypatch.setattr(
        memory, "_embed", AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    )
    report = asyncio.run(memory.backfill_embeddings())
    assert report["embedded"] == 2
    assert report["skipped"] == 0
    assert report["counts"]["eligible_pending"] == 0
    assert memory.entity_stats()["facts_embedded"] == 1


def test_backfill_skips_malformed_web_metadata_without_starving_later_rows(
    memory, monkeypatch
):
    insert(memory, "broken", "synthetic web content", kind="web_result")
    memory._db.execute("UPDATE vectors SET metadata='[]' WHERE id='broken'")
    insert(memory)
    monkeypatch.setattr(
        memory, "_embed", AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    )
    report = asyncio.run(memory.backfill_embeddings())
    assert report["failed"] == 1
    assert report["embedded"] == 1
    assert report["counts"]["total"] == 2


def test_backfill_deadline_leaves_interrupted_row_resumable(memory, monkeypatch):
    insert(memory)

    async def slow_embed(text):
        await asyncio.Event().wait()

    monkeypatch.setattr(memory, "_embed", slow_embed)
    report = asyncio.run(memory.backfill_embeddings(max_seconds=0.01))
    assert report["stopped"] == "deadline"
    assert report["cursor"] == 0
    assert report["counts"]["pending"] == 1
    monkeypatch.setattr(
        memory, "_embed", AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    )
    assert asyncio.run(memory.backfill_embeddings())["embedded"] == 1


def test_cached_backfill_honors_deadline_and_cooperative_cancellation(
    memory, monkeypatch
):
    content = "synthetic cached fact"
    memory._db.execute("BEGIN")
    memory._db.executemany(
        "INSERT INTO vectors (id, kind, content, timestamp, created_at) VALUES (?, 'ltm', ?, '', 0)",
        [(str(index), content) for index in range(5000)],
    )
    memory._db.execute("COMMIT")
    transport = install_transport(monkeypatch, Reply({"embeddings": [vector()]}))
    asyncio.run(memory._embed(content))
    report = asyncio.run(
        memory.backfill_embeddings(limit=5000, batch_size=64, max_seconds=0.01)
    )
    assert report["stopped"] == "deadline"
    assert report["embedded"] < 5000
    pending = report["counts"]["eligible_pending"]
    assert pending > 0
    assert len(transport.calls) == 1

    async def cancel_cached_pass():
        task = asyncio.create_task(memory.backfill_embeddings(limit=5000))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_cached_pass())
    assert memory.embedding_status()["eligible_pending"] == pending
    assert asyncio.run(memory.backfill_embeddings(limit=1))["embedded"] == 1


def test_cancellation_does_not_mark_a_row_done(memory, monkeypatch):
    insert(memory)

    async def run():
        started = asyncio.Event()

        async def embed(text):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(memory, "_embed", embed)
        task = asyncio.create_task(memory.backfill_embeddings())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert memory.embedding_status()["pending"] == 1
    assert memory._db.execute("SELECT COUNT(*) FROM embed_backfill").fetchone()[0] == 0


@pytest.mark.parametrize("delete", [False, True])
def test_concurrent_edit_or_delete_wins_over_embedding(memory, monkeypatch, delete):
    text = "fact https://example.invalid/old"
    insert(memory, text=text)

    async def embed(snapshot):
        if delete:
            memory._db.execute("DELETE FROM vectors WHERE id='fact'")
        else:
            memory._db.execute(
                "UPDATE vectors SET content=? WHERE id='fact'",
                ("fact https://example.invalid/new",),
            )
        return np.array(vector(), dtype=np.float32)

    monkeypatch.setattr(memory, "_embed", embed)
    assert not asyncio.run(memory._embed_and_store("fact", text))
    assert (
        memory._db.execute(
            "SELECT COUNT(*) FROM vectors WHERE embedding IS NOT NULL"
        ).fetchone()[0]
        == 0
    )


def test_disabled_rag_never_starts_network_and_keeps_raw_memory(memory, monkeypatch):
    monkeypatch.setattr(rag, "EMBEDDINGS_ENABLED", False)
    insert(memory)

    async def run():
        coroutine = memory._embed("do not run")
        assert memory._spawn(coroutine) is None
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
        assert await memory._embed("do not embed") is None
        assert await memory._embed_for_query("do not query") is None
        assert not await memory._embed_and_store("fact", "a durable synthetic fact")
        assert (await memory._embed_pending_all())["stopped"] == "disabled"
        assert (await memory._embed_pending("ltm"))["stopped"] == "disabled"
        assert (await memory.backfill_embeddings())["attempted"] == 0
        await memory.add_to_channel_memory("channel", {"content": "preserved message"})
        assert (
            await memory.store_web_results(
                "query",
                [
                    {
                        "href": "https://example.invalid",
                        "title": "Synthetic title",
                        "body": "Synthetic body",
                    }
                ],
            )
            == 1
        )

    asyncio.run(run())
    assert memory.embedding_status()["total"] == 3
    assert memory.embedding_status()["unembedded"] == 3
    assert not memory._embed_tasks


def test_web_failure_is_preserved_and_backfill_uses_the_same_input(memory, monkeypatch):
    embed = AsyncMock(return_value=None)
    monkeypatch.setattr(memory, "_embed", embed)
    asyncio.run(
        memory.store_web_results(
            "query",
            [
                {
                    "href": "https://example.invalid",
                    "title": "Synthetic title",
                    "body": "Synthetic body",
                }
            ],
        )
    )
    assert memory.embedding_status()["unembedded"] == 1
    initial_input = embed.call_args.args[0]
    embed.return_value = np.array(vector(), dtype=np.float32)
    report = asyncio.run(memory.backfill_embeddings())
    assert report["embedded"] == 1
    assert (
        embed.call_args.args[0]
        == initial_input
        == "Synthetic title\nSynthetic title\nSynthetic body"
    )
    assert (
        memory._db.execute("SELECT content FROM vectors").fetchone()[0]
        == "Synthetic title\nSynthetic body"
    )


def test_backfill_skips_low_signal_and_separates_kind_cursors(memory, monkeypatch):
    insert(memory, "short", "ok", kind="message")
    insert(memory, "message", "synthetic message", kind="message")
    insert(memory)
    embed = AsyncMock(return_value=np.array(vector(), dtype=np.float32))
    monkeypatch.setattr(memory, "_embed", embed)
    report = asyncio.run(memory.backfill_embeddings(kind="message", limit=1))
    assert report["skipped"] == 1
    assert embed.await_count == 0
    assert asyncio.run(memory.backfill_embeddings(kind="ltm"))["embedded"] == 1
    final = asyncio.run(memory.backfill_embeddings(kind="message"))
    assert final["embedded"] == 1
    assert final["counts"]["pending"] == 1
    assert final["counts"]["excluded_pending"] == 1
    assert final["counts"]["eligible_pending"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": 10001},
        {"batch_size": 0},
        {"batch_size": 65},
        {"max_seconds": 0},
        {"max_seconds": 601},
        {"max_seconds": float("nan")},
    ],
)
def test_backfill_bounds_are_enforced(memory, kwargs):
    with pytest.raises(ValueError):
        asyncio.run(memory.backfill_embeddings(**kwargs))


def test_explicit_maintenance_database_never_reads_or_migrates_siblings(
    tmp_path, monkeypatch
):
    original = rag.RAGMemoryManager(str(tmp_path))
    insert(original)
    original._db.close()
    target = tmp_path / "selected.db"
    (tmp_path / "maxwell_rag.db").rename(target)
    (tmp_path / "long_term_memory.txt").write_text("do not import this fact")
    (tmp_path / "prompts.json").write_text("malformed sidecar")

    def unexpected_read(*args, **kwargs):
        raise AssertionError("maintenance ran an unrelated migration")

    monkeypatch.setattr(rag.RAGMemoryManager, "_migrate_ltm", unexpected_read)
    monkeypatch.setattr(
        rag.RAGMemoryManager, "_migrate_shared_context", unexpected_read
    )
    manager = rag.RAGMemoryManager(str(tmp_path / "unused"), db_path=target)
    assert manager.embedding_status()["total"] == 1
    assert not (tmp_path / "unused").exists()
    assert not (tmp_path / "maxwell_rag.db").exists()
    manager._db.close()


def test_cli_status_is_read_only_secret_free_and_requires_explicit_db(
    memory, capsys, tmp_path
):
    insert(memory, text="PRIVATE SYNTHETIC FACT MUST NEVER APPEAR")
    memory._db.execute("ALTER TABLE vectors DROP COLUMN embedding_backend")
    columns_before = list(memory._db.execute("PRAGMA table_info(vectors)"))
    assert rag_maintenance.main(["status", "--db", str(memory.db_path)]) == 0
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    assert json.loads(output)["pending"] == 1
    assert list(memory._db.execute("PRAGMA table_info(vectors)")) == columns_before
    with pytest.raises(SystemExit) as error:
        rag_maintenance.main(["status"])
    assert error.value.code == 2
    missing = tmp_path / "missing.db"
    assert rag_maintenance.main(["status", "--db", str(missing)]) == 1
    assert not missing.exists()


def test_disabled_cli_backfill_does_not_even_migrate_schema(
    memory, monkeypatch, capsys
):
    insert(memory)
    memory._db.execute("ALTER TABLE vectors DROP COLUMN embedding_backend")
    monkeypatch.setattr(rag_maintenance, "EMBEDDINGS_ENABLED", False)
    assert rag_maintenance.main(["backfill", "--db", str(memory.db_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["stopped"] == "disabled"
    assert "embedding_backend" not in {
        row[1] for row in memory._db.execute("PRAGMA table_info(vectors)")
    }


def test_cli_backfill_respects_explicit_db_and_reports_partial_failure(
    memory, monkeypatch, capsys
):
    insert(memory)
    install_transport(monkeypatch, Reply({}, 503))
    result = rag_maintenance.main(
        ["backfill", "--db", str(memory.db_path), "--limit", "1"]
    )
    assert result == 2
    report = json.loads(capsys.readouterr().out)
    assert report["failed"] == 1
    assert report["counts"]["pending"] == 1


def doctor_config(enabled=True):
    return SimpleNamespace(
        ENABLE_RAG=enabled,
        EMBED_BASE_URL="http://configured.invalid/v1",
        EMBED_MODEL="configured-model",
        EMBED_API_KEY="synthetic-key",
        EMBED_DIM=8,
    )


@pytest.mark.parametrize(
    "payload,status,expected",
    [
        ({"embeddings": [vector()]}, 200, "ok"),
        ({"data": [{"index": 0, "embedding": vector()}]}, 200, "ok"),
        ({"embeddings": [[1.0] * 7]}, 200, "warn"),
        ({"embeddings": [[float("nan")] * 8]}, 200, "warn"),
        ({"embeddings": [[0.0] * 8]}, 200, "warn"),
        ({"secret": "private error text"}, 503, "warn"),
        (ValueError("private error text"), 200, "warn"),
    ],
)
def test_doctor_checks_real_vectors_and_configured_backend(
    monkeypatch, payload, status, expected
):
    transport = install_transport(monkeypatch, Reply(payload, status))
    state, detail = asyncio.run(doctor._probe_embeddings(doctor_config()))
    assert state == expected
    assert "private" not in detail
    assert "synthetic-key" not in detail
    url, kwargs = transport.calls[0]
    assert url == "http://configured.invalid/v1/embeddings"
    assert kwargs["json"]["model"] == "configured-model"
    assert kwargs["headers"]["Authorization"] == "Bearer synthetic-key"


def test_doctor_disabled_rag_does_not_probe():
    state, detail = asyncio.run(doctor._probe_embeddings(doctor_config(enabled=False)))
    assert state == "warn"
    assert "no request" in detail


@pytest.mark.parametrize(
    "stdout,stderr,returncode,reachable",
    [
        ("\n", "permission denied while trying to connect", 0, False),
        ("", "", 0, False),
        ("26.1.5", "permission denied", 0, False),
        ("26.1.5\n", "", 0, True),
        ("26.1.5", "", 1, False),
    ],
)
def test_doctor_does_not_trust_formatted_docker_exit_zero(
    monkeypatch, capsys, stdout, stderr, returncode, reachable
):
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda binary: "/usr/bin/docker")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        ),
    )
    doctor.check_docker(SimpleNamespace(ENABLE_SHELL=True))
    assert ("daemon reachable" in capsys.readouterr().out) is reachable
