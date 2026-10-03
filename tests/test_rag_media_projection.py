import asyncio
import hashlib
import json

import numpy as np
import pytest

import rag_memory as rag


CONTEXT_ERROR = {"error": "the input length exceeds the context length"}
VECTOR = [1.0, 0.0, 0.0, 0.0]


class Reply:
    def __init__(self, payload=None, status=200):
        self.payload = {"embeddings": [VECTOR]} if payload is None else payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class Transport:
    def __init__(self):
        self.calls = []
        self.opened = 0
        self.respond = lambda text: Reply()

    async def __aenter__(self):
        self.opened += 1
        return self

    async def __aexit__(self, *args):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.respond(kwargs["json"]["input"])


@pytest.fixture
def transport(monkeypatch):
    result = Transport()
    monkeypatch.setattr(rag.aiohttp, "ClientSession", lambda: result)
    return result


@pytest.fixture
def memory(tmp_path, monkeypatch, transport):
    monkeypatch.setattr(rag, "EMBED_DIM", len(VECTOR))
    monkeypatch.setattr(rag, "EMBED_MODEL", "synthetic-embedding-model")
    monkeypatch.setattr(rag, "EMBED_URL", "http://embedding.invalid/api/embed")
    monkeypatch.setattr(rag, "EMBED_HEADERS", {})
    monkeypatch.setattr(rag, "EMBEDDINGS_ENABLED", True)
    manager = rag.RAGMemoryManager(str(tmp_path))
    yield manager
    manager._db.close()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Before __IMAGE_B64__QUJDRA==__END_IMAGE_B64__ after.", "Before   after."),
        ("Before __AUDIO_B64__QUJD\nRA==__END_AUDIO_B64__ after.", "Before   after."),
        ("Before __IMAGE_B64__QUJDRA", "Before"),
        ("Before __AUDIO_B64__QUJD\nRA", "Before"),
        ("data:image/svg+xml;base64,PHN2Zz4=", ""),
        ("data:audio/wav;charset=utf-8;base64,UklGRg==", ""),
        ("data:;base64,QUJD", ""),
        ("DATA:application/octet-stream;BASE64,QUJD%2BRA%3D", ""),
        ('<img src="data:image/png;base64,QUJDRA=="> caption', '<img src=" "> caption'),
        ("before data:image/png;base64,QUJDRA== after", "before   after"),
        ("data:image/png;base64,QUJD", ""),
    ],
)
def test_embedding_projection_removes_only_explicit_media_payloads(text, expected):
    assert rag._embedding_projection(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Unicorn SVG source: <svg><path d=\"M 0 0 L 10 10\"/></svg>",
        'marker = "__IMAGE_B64__"\nend = "__END_IMAGE_B64__"',
        'pattern = r"__AUDIO_B64__([A-Za-z0-9+/=]+)__END_AUDIO_B64__"',
        "code = 'QUJDRA=='\nprint(code)",
        "A normal paragraph.\n\n    Indented code stays indented.",
        "data:text/plain,readable%20text",
        "https://example.invalid/image.svg",
        "Use image/svg+xml for XML; image/png for PNG.",
        "Explain the __IMAGE_B64__ marker",
        "Explain __AUDIO_B64__ markers in documentation",
        'header = "data:image/png;base64,"',
    ],
)
def test_legitimate_prose_code_and_plain_data_uris_are_unchanged(text):
    assert rag._embedding_projection(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "__IMAGE_B64__QUJDRA==__END_IMAGE_B64__",
        "__AUDIO_B64__QUJDRA==__END_AUDIO_B64__",
        "__IMAGE_B64__QUJDRA",
        "__AUDIO_B64__QUJD\nRA",
        "__IMAGE_B64__",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "data:audio/wav;base64,UklGRg==",
    ],
)
def test_pure_binary_inputs_open_no_http_session(memory, transport, text):
    assert asyncio.run(memory._embed(text)) is None
    assert transport.calls == []
    assert transport.opened == 0
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 0


def test_projection_precedes_cache_and_preserves_clean_cache_identity(memory, transport):
    clean = "Keep this useful sentence."
    old_key = hashlib.sha256(f"{memory.embedding_backend}\0{clean}".encode()).hexdigest()
    memory._db.execute(
        "INSERT INTO embed_cache (key, dim, backend, embedding, created_at, last_used_at, hits) "
        "VALUES (?, ?, ?, ?, 1, 1, 1)",
        (old_key, memory.embed_dim, memory.embedding_backend, np.asarray(VECTOR, dtype=np.float32).tobytes()),
    )
    text = clean + " __IMAGE_B64__" + "A" * 6904
    assert np.array_equal(asyncio.run(memory._embed(text)), VECTOR)
    assert transport.calls == []
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 1


def test_query_uses_projection_before_chunking(memory, transport):
    text = "Useful query. __IMAGE_B64__" + "A" * 6904
    assert asyncio.run(memory._embed_for_query(text)) is not None
    assert [call[1]["json"]["input"] for call in transport.calls] == ["Useful query."]


@pytest.mark.parametrize("path", ["store", "backfill"])
def test_store_and_backfill_preserve_raw_history_and_metadata(memory, transport, path):
    text = "Useful result. __AUDIO_B64__" + "A" * 6904
    metadata = json.dumps({"tool_result": text, "tool_name": "synthetic_tool"})
    memory._db.execute(
        "INSERT INTO vectors (id, kind, source, content, metadata, timestamp, created_at) "
        "VALUES ('synthetic', 'ltm', 'bot', ?, ?, '', 1)",
        (text, metadata),
    )
    if path == "store":
        assert asyncio.run(memory._embed_and_store("synthetic", text))
    else:
        assert asyncio.run(memory.backfill_embeddings())["embedded"] == 1
    row = memory._db.execute("SELECT content, metadata, embedding FROM vectors WHERE id='synthetic'").fetchone()
    assert row["content"] == text
    assert row["metadata"] == metadata
    assert row["embedding"] is not None
    assert [call[1]["json"]["input"] for call in transport.calls] == ["Useful result."]


def test_existing_contaminated_vectors_are_not_invalidated_or_reembedded(memory, transport):
    text = "Historical record. __IMAGE_B64__QUJDRA==__END_IMAGE_B64__"
    blob = np.asarray(VECTOR, dtype=np.float32).tobytes()
    memory._db.execute(
        "INSERT INTO vectors (id, kind, content, embedding, embedding_backend, timestamp, created_at) "
        "VALUES ('historical', 'ltm', ?, ?, ?, '', 1)",
        (text, blob, memory.embedding_backend),
    )
    report = asyncio.run(memory.backfill_embeddings())
    assert report["attempted"] == 0
    assert transport.calls == []
    row = memory._db.execute("SELECT content, embedding FROM vectors WHERE id='historical'").fetchone()
    assert tuple(row) == (text, blob)


def test_context_rejection_splits_only_offending_chunk_without_losing_unicode(memory, transport):
    text = "😀漢字" * 2000 + "tail"
    accepted = []

    def respond(chunk):
        if len(chunk.encode()) > 5000:
            return Reply(CONTEXT_ERROR, 400)
        accepted.append(chunk)
        return Reply()

    transport.respond = respond
    assert asyncio.run(memory._embed(text)) is None
    original_chunks = rag._split_embed_chunks(text)
    assert accepted == []
    assert len(transport.calls) == 1
    assert transport.calls[0][1]["json"] == {
        "model": memory.embed_model, "input": original_chunks[0],
    }
    assert memory._embed_endpoint_down_until > 0.0
    assert transport.calls[0][1]["timeout"].total == rag.EMBED_HTTP_TIMEOUT_SECONDS
    assert asyncio.run(memory._embed(text)) is None
    assert len(transport.calls) == 1


@pytest.mark.parametrize("text", ["x", "x" * 6000])
def test_repeated_context_rejections_stop_without_cache_or_global_outage(memory, transport, text):
    transport.respond = lambda chunk: Reply(CONTEXT_ERROR, 400)
    assert asyncio.run(memory._embed(text)) is None
    assert len(transport.calls) == 1
    assert memory._embed_endpoint_down_until > 0.0
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 0


def test_partial_success_is_not_cached_when_later_chunk_cannot_fit(memory, transport):
    text = "a" * 6000 + "b" * 6000
    transport.respond = lambda chunk: Reply(CONTEXT_ERROR, 400) if "b" in chunk else Reply()
    assert asyncio.run(memory._embed(text)) is None
    assert transport.calls[0][1]["json"]["input"] == "a" * 6000
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 0
    assert memory._embed_endpoint_down_until > 0.0


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "another input error"},
        ["the input length exceeds the context length"],
        "the input length exceeds the context length",
        json.JSONDecodeError("invalid JSON", "invalid", 0),
    ],
)
def test_unrecognized_400_does_not_trigger_split_retries(memory, transport, payload):
    transport.respond = lambda chunk: Reply(payload, 400)
    assert asyncio.run(memory._embed("Synthetic text.")) is None
    assert len(transport.calls) == 1
    assert memory._embed_endpoint_down_until > 0.0
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 0


def test_context_message_from_non_ollama_endpoint_is_not_retried(memory, transport):
    memory.embed_url = "http://embedding.invalid/v1/embeddings"
    transport.respond = lambda chunk: Reply(CONTEXT_ERROR, 400)
    assert asyncio.run(memory._embed("Synthetic text.")) is None
    assert len(transport.calls) == 1
    assert memory._embed_endpoint_down_until > 0.0


def test_cancellation_during_context_recovery_propagates(memory, transport):
    replies = iter([Reply(asyncio.CancelledError())])
    transport.respond = lambda chunk: next(replies)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(memory._embed("Synthetic text."))
    assert len(transport.calls) == 1
    assert memory._embed_endpoint_down_until == 0.0
    assert memory._db.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0] == 0
