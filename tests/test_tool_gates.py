import asyncio
from types import SimpleNamespace

import pytest

import bot_tools
from bot import MaxwellBot
from bot_tools import FetchUrlTool, ShellTool


def test_dispatch_allows_shell_after_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: list[tuple[str, int]] = []
    shell_commands: list[str] = []

    async def fake_fetch(
        url: str, *, max_bytes: int
    ) -> tuple[str, str, bytes]:
        fetched.append((url, max_bytes))
        return url, "text/plain", b"synthetic page text"

    async def fake_shell(
        self: ShellTool, command: str, on_progress: object = None
    ) -> tuple[bytes, bytes, int]:
        shell_commands.append(command)
        return b"synthetic shell output", b"", 0

    async def record_trace(message: object, payload: dict[str, object]) -> None:
        return None

    monkeypatch.setattr(bot_tools, "_fetch_public_url", fake_fetch)
    monkeypatch.setattr(ShellTool, "_run_shell_command", fake_shell)
    bot = SimpleNamespace(
        tools={},
        _tool_breaker=SimpleNamespace(
            is_open=lambda _name: False,
            record_failure=lambda _name: None,
            record_success=lambda _name: None,
        ),
        _record_llm_trace=record_trace,
    )
    bot.tools.update({"fetch_url": FetchUrlTool(bot), "shell": ShellTool(bot)})
    message = SimpleNamespace(
        author=SimpleNamespace(id=17),
        guild=None,
        channel=SimpleNamespace(id=123),
    )
    compatible = set(bot.tools)

    async def dispatch() -> tuple[str, str]:
        fetched_result = await MaxwellBot._execute_tool_by_name(
            bot,
            message,
            "fetch_url",
            {"url": "https://example.test/reference"},
            disabled=set(),
            compatible=compatible,
        )
        shell_result = await MaxwellBot._execute_tool_by_name(
            bot,
            message,
            "shell",
            {"command": "printf synthetic"},
            disabled=set(),
            compatible=compatible,
        )
        return fetched_result, shell_result

    fetch_result, shell_result = asyncio.run(dispatch())
    assert fetch_result == "Tool fetch_url: synthetic page text"
    assert fetched == [("https://example.test/reference", FetchUrlTool.MAX_BYTES)]
    assert shell_result == "Tool shell: synthetic shell output"
    assert shell_commands == ["printf synthetic"]


def test_ordinary_chat_still_travels_light():
    assert not MaxwellBot._ACTION_TOOL_HINT_RE.search("lol yeah exactly")
