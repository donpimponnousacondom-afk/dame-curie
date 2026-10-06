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


@pytest.mark.parametrize(
    ("site_config", "site_root"),
    [
        ({"DAME_CURIE_SITE_DIR": "/state/sites"}, "/state/sites"),
        ({"DAME_CURIE_SITE_DIR": "/state/sites/authored"}, "/state/sites/authored"),
        ({"DAME_CURIE_SITE_DIR": "public/custom"}, "public/custom"),
        ({}, "public/bot"),
        ({"DAME_CURIE_SITE_DIR": ""}, "public/bot"),
    ],
    ids=["container", "configured", "relative", "default", "empty"],
)
def test_exec_uses_outer_bot_container(monkeypatch, tmp_path, site_config, site_root):
    monkeypatch.chdir(tmp_path)
    shell = ShellTool(bot=SimpleNamespace(config=SimpleNamespace(**site_config)))
    monkeypatch.setenv("DAME_CURIE_SITE_DIR", "/synthetic/unrelated-site-root")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-provider-secret")
    monkeypatch.setenv("DISCORD_TOKEN", "synthetic-discord-secret")
    monkeypatch.setenv("BASH_ENV", "/synthetic/must-not-source")
    monkeypatch.setenv("ENV", "/synthetic/must-not-source-either")
    monkeypatch.setenv("PYTHONPATH", "/synthetic/unrelated-python-path")
    monkeypatch.setenv("DATA_DIR", "/synthetic/private-data")
    monkeypatch.setenv("HOME", "/synthetic/unrelated-home")
    monkeypatch.setenv("PATH", "/synthetic/unrelated-bin")

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
        assert spawn.call_args.args == ("bash", "--noprofile", "--norc", "-c", "printf ok")
        assert spawn.call_args.kwargs["cwd"] == "/home/dame-curie"
        assert spawn.call_args.kwargs["start_new_session"] is True
        environment = spawn.call_args.kwargs["env"]
        assert environment == {
            "HOME": "/home/dame-curie",
            "PATH": "/home/dame-curie/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "DAME_CURIE_SITE_DIR": str(tmp_path / site_root),
        }
        assert "synthetic-provider-secret" not in environment.values()
        assert "synthetic-discord-secret" not in environment.values()

    asyncio.run(run())
