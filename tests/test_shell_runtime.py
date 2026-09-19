import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot_tools
from bot_tools import ShellTool


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setenv("DAME_CURIE_CONTAINER_MODE", "true")
    monkeypatch.setenv("DAME_CURIE_SHELL_DIR", "/state/shell")
    is_file = bot_tools.os.path.isfile
    monkeypatch.setattr(bot_tools.os.path, "isfile", lambda path: path == "/.dockerenv" or is_file(path))
    monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", AsyncMock(side_effect=AssertionError("live subprocess forbidden")))


def test_exec_uses_outer_bot_container(monkeypatch):
    shell = ShellTool(bot=None)

    async def run():
        stdout = asyncio.StreamReader()
        stdout.feed_data(b"ok")
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_eof()
        process = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0, wait=AsyncMock(return_value=0))
        spawn = AsyncMock(return_value=process)
        monkeypatch.setattr(bot_tools.asyncio, "create_subprocess_exec", spawn)
        assert await shell._run_shell_command("printf ok") == (b"ok", b"", 0)
        assert spawn.call_args.args == ("bash", "-lc", "printf ok")
        assert spawn.call_args.kwargs["cwd"] == "/home/dame-curie"
        assert spawn.call_args.kwargs["start_new_session"] is True

    asyncio.run(run())
