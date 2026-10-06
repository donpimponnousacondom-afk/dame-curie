import ast
import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from control_defaults import DEFAULT_CONTROL
from prompt_storage import PromptStorageError, PromptStore, get_prompt_store


@pytest.fixture
def external(tmp_path, monkeypatch):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "personality.txt").write_text("Original personality", encoding="utf-8")
    monkeypatch.setenv("DAME_CURIE_PROMPTS_DIR", str(prompts))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("DAME_CURIE_ENV_FILE", "/dev/null")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    return prompts


def test_store_isolation_and_external_reload(tmp_path):
    a = PromptStore(tmp_path / "a")
    b = PromptStore(tmp_path / "b")
    a.set_server("123", "a")
    b.set_server("123", "b")
    assert a.read_servers() == {"123": "a"}
    assert b.read_servers() == {"123": "b"}
    a.servers_path.write_text('{"123": "edited"}', encoding="utf-8")
    assert a.read_servers() == {"123": "edited"}
    assert a.read_personality() == DEFAULT_CONTROL["base_personality"]
    a.set_personality("Legacy personality")
    assert a.read_personality() == "Legacy personality"
    assert b.read_personality() == DEFAULT_CONTROL["base_personality"]


def test_factory_keys_external_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("DAME_CURIE_PROMPTS_DIR", str(tmp_path / "a"))
    a = get_prompt_store(tmp_path)
    monkeypatch.setenv("DAME_CURIE_PROMPTS_DIR", str(tmp_path / "b"))
    assert get_prompt_store(tmp_path) is not a


@pytest.mark.parametrize("bad", ["{ broken", "[]", '{"123": 9}', ""])
def test_bad_servers_retain_valid_and_refuse_writes(tmp_path, bad, caplog):
    store = PromptStore(tmp_path)
    store.set_server("123", "valid")
    store.servers_path.write_text(bad, encoding="utf-8")
    assert store.read_servers(retain_valid=True) == {"123": "valid"}
    assert "fix the file" in caplog.text
    with pytest.raises(PromptStorageError):
        store.set_server("456", "new")
    with pytest.raises(PromptStorageError):
        store.delete_server("123")
    assert store.servers_path.read_text(encoding="utf-8") == bad
    store.servers_path.write_text('{"456": "repaired"}', encoding="utf-8")
    assert store.read_servers() == {"456": "repaired"}


def test_personality_errors_and_last_valid(tmp_path, external, caplog):
    store = PromptStore(tmp_path, external)
    assert store.read_servers() == {}
    assert store.read_personality() == "Original personality"
    store.personality_path.write_text("\n ", encoding="utf-8")
    assert store.read_personality(retain_valid=True) == "Original personality"
    with pytest.raises(PromptStorageError, match="empty"):
        store.read_personality()
    store.personality_path.unlink()
    assert store.read_personality(retain_valid=True) == "Original personality"
    with pytest.raises(PromptStorageError, match="personality.txt"):
        PromptStore(tmp_path, external).read_personality(retain_valid=True)
    assert "fix the file" in caplog.text
    store.set_personality("Repaired personality")
    assert store.read_personality() == "Repaired personality"


def test_bot_personality_construction_reloads(tmp_path, external):
    source = Path(__file__).resolve().parents[1] / "bot.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_get_personality")
    namespace = {"datetime": datetime, "timezone": timezone, "re": re, "get_prompt_store": get_prompt_store}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    bot = SimpleNamespace(
        config=SimpleNamespace(DATA_DIR=str(tmp_path), DAME_CURIE_PROMPTS_DIR=str(external)),
        _BIRTHDAY=datetime(2026, 5, 21, tzinfo=timezone.utc),
    )
    construct = namespace["_get_personality"]
    assert construct(bot).startswith("Original personality")
    (external / "personality.txt").write_text("External edit", encoding="utf-8")
    assert construct(bot).startswith("External edit")
    (external / "personality.txt").write_text("", encoding="utf-8")
    assert construct(bot).startswith("External edit")


def test_locked_read_modify_write(tmp_path):
    def save(i):
        PromptStore(tmp_path).set_server(str(i), str(i))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(24)))
    assert len(PromptStore(tmp_path).read_servers()) == 24


def test_prompt_tools_share_external_store(tmp_path, external):
    from bot_tools import UpdateBasePersonalityTool, UpdateServerPromptTool
    from rag_memory import RAGMemoryManager

    memory = RAGMemoryManager(str(tmp_path / "runtime"))
    bot = SimpleNamespace(
        config=SimpleNamespace(DATA_DIR=str(tmp_path / "runtime")),
        _control={},
        memory=memory,
        _is_admin={100: True}.get,
    )
    message = SimpleNamespace(author=SimpleNamespace(id=100))

    async def run():
        result = await UpdateBasePersonalityTool(bot).execute(message, text="A personality written through the authorized tool path")
        assert "updated" in result
        assert (external / "personality.txt").read_text().startswith("A personality written")
        result = await UpdateServerPromptTool(bot).execute(message, server_id="DM", text="Tool prompt")
        assert "updated" in result
        assert json.loads((external / "servers.json").read_text()) == {"DM": "Tool prompt"}
        result = await UpdateServerPromptTool(bot).execute(
            message, server_id="DM", text="x" * 4001
        )
        assert "Error" in result and "4000" in result
        assert json.loads((external / "servers.json").read_text()) == {"DM": "Tool prompt"}

    asyncio.run(run())
    memory._db.close()
