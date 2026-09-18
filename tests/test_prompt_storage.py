import ast
import asyncio
import json
import os
import re
import subprocess
import sys
import threading
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
    monkeypatch.setenv("MAXWELL_PROMPTS_DIR", str(prompts))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MAXWELL_ENV_FILE", "/dev/null")
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
    monkeypatch.setenv("MAXWELL_PROMPTS_DIR", str(tmp_path / "a"))
    a = get_prompt_store(tmp_path)
    monkeypatch.setenv("MAXWELL_PROMPTS_DIR", str(tmp_path / "b"))
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
        config=SimpleNamespace(DATA_DIR=str(tmp_path), MAXWELL_PROMPTS_DIR=str(external)),
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


class Request:
    def __init__(self, body=None, file="", query=None):
        self.body = body or {}
        self.match_info = {"file": file}
        self.query = query or {}

    async def json(self):
        return self.body


@pytest.mark.parametrize("reset", [False, True])
@pytest.mark.parametrize("external_mode", [False, True])
def test_control_write_lock_does_not_block_loop(tmp_path, external, monkeypatch, reset, external_mode):
    from api import api_server as api, state
    from utils import FileLock

    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "runtime")
    if not external_mode:
        monkeypatch.setenv("MAXWELL_PROMPTS_DIR", "")
    main_thread = threading.get_ident()

    async def run():
        monkeypatch.setattr(api, "_file_lock", asyncio.Lock())
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()

        def contended_lock(path):
            assert threading.get_ident() != main_thread
            loop.call_soon_threadsafe(entered.set)
            return FileLock(path, timeout=2.0)

        monkeypatch.setattr(state, "FileLock", contended_lock)
        with FileLock(api.DATA_DIR / "bot_control.json"):
            request = Request({"base_personality": "Nonblocking personality"})
            task = asyncio.create_task(api.control_reset(request) if reset else api.control_put(request))
            await asyncio.wait_for(entered.wait(), timeout=1.0)
            assert not task.done()
        response = await asyncio.wait_for(task, timeout=1.0)
        assert response.status == 200

    asyncio.run(run())


def test_api_runtime_compatibility(tmp_path, external, monkeypatch):
    from api import api_server as api
    from rag_memory import RAGMemoryManager

    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "runtime")
    runtime = RAGMemoryManager(str(api.DATA_DIR))
    personality = get_prompt_store(api.DATA_DIR)

    async def run():
        assert (await api.prompt_save(Request({"id": "123", "text": "API prompt"}))).status == 200
        assert runtime.get_server_prompt("123") == "API prompt"
        runtime.set_server_prompt("456", "Discord prompt")
        response = await api.data_file(Request(file="prompts.json"))
        assert json.loads(response.text) == {"123": "API prompt", "456": "Discord prompt"}
        response = await api.control_put(Request({"base_personality": "API personality"}))
        assert response.status == 200
        assert personality.read_personality() == "API personality"
        personality.set_personality("Tool personality")
        response = await api.control_get(Request())
        assert json.loads(response.text)["control"]["base_personality"] == "Tool personality"
        response = await api.data_file(Request(file="bot_control.json"))
        assert json.loads(response.text)["base_personality"] == "Tool personality"
        assert "base_personality" not in json.loads((api.DATA_DIR / "bot_control.json").read_text())
        (external / "servers.json").write_text("{broken", encoding="utf-8")
        assert runtime.get_server_prompt("456") == "Discord prompt"
        assert (await api.prompt_save(Request({"id": "123", "text": "bad"}))).status == 409
        assert (await api.data_file(Request(file="prompts.json"))).status == 409
        (external / "servers.json").write_text('{"DM": "external"}', encoding="utf-8")
        assert runtime.get_server_prompt("123") is None
        assert runtime.get_server_prompt("DM") == "external"
        assert (await api.prompt_delete(Request(query={"id": "DM"}))).status == 200
        assert runtime.get_server_prompt("DM") is None
        assert not (api.DATA_DIR / "prompts.json").exists()

    asyncio.run(run())
    runtime._db.close()


def test_prompt_tools_share_external_store(tmp_path, external):
    from bot_tools import UpdateBasePersonalityTool, UpdateServerPromptTool
    from rag_memory import RAGMemoryManager

    memory = RAGMemoryManager(str(tmp_path / "runtime"))
    bot = SimpleNamespace(config=SimpleNamespace(DATA_DIR=str(tmp_path / "runtime")), _control={}, memory=memory)
    message = SimpleNamespace(author=SimpleNamespace(id=100))

    async def run():
        result = await UpdateBasePersonalityTool(bot).execute(message, text="A personality written through the authorized tool path")
        assert "updated" in result
        assert (external / "personality.txt").read_text().startswith("A personality written")
        result = await UpdateServerPromptTool(bot).execute(message, server_id="DM", text="Tool prompt")
        assert "updated" in result
        assert json.loads((external / "servers.json").read_text()) == {"DM": "Tool prompt"}

    asyncio.run(run())
    memory._db.close()


@pytest.mark.parametrize("explicit,expected", [(None, "data_gf"), ("/tmp/custom-gf", "/tmp/custom-gf")])
def test_gf_data_dir(explicit, expected):
    env = dict(os.environ, MAXWELL_ENV_FILE="/dev/null", PYTHON_DOTENV_DISABLED="1", BOT_PERSONA_TYPE="mommy_gf")
    env.pop("DATA_DIR", None)
    if explicit is not None:
        env["DATA_DIR"] = explicit
    result = subprocess.run(
        [sys.executable, "-c", "from config import Config; print(Config.DATA_DIR)"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == expected
