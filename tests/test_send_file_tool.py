import asyncio
import base64
from types import SimpleNamespace

from bot_tools import SendFileTool
from bot_tools import ShellTool
from bot_tools import SendMessageTool
from bot_tools import ReasoningLogTool
from bot_tools import forget_shell_progress


class FakePosted:
    def __init__(self, content):
        self.content = content
        self.deleted = False
        self.edits = []

    async def edit(self, content=None, **kwargs):
        self.content = content
        self.edits.append(content)

    async def delete(self):
        self.deleted = True


class FakeMessage:
    def __init__(self):
        self.files = []
        self.replies = []

        class FakeChannel:
            def __init__(self, outer):
                self.outer = outer
                self.id = 99
                self.sent = []

            async def send(self, content=None, file=None, **kwargs):
                if file is not None:
                    self.outer.files.append(file)
                posted = FakePosted(content)
                self.sent.append(posted)
                self.outer.replies.append(content)
                return posted

        self.channel = FakeChannel(self)

        class FakeAuthor:
            id = "1325265045600600135"

        self.author = FakeAuthor()

    async def send(self, content=None, file=None, **kwargs):
        return await self.channel.send(content=content, file=file, **kwargs)

    async def reply(self, content=None, file=None, **kwargs):
        return await self.channel.send(content=content, file=file, **kwargs)


def test_send_file_tool_sends_text_file():
    tool = SendFileTool(bot=None)
    message = FakeMessage()

    async def run():
        result = await tool.execute(message, filename="hello.py", content="print('hi')\n")
        assert result == "__FILE_SENT__ Sent file: hello.py (12 bytes)"
        assert len(message.files) == 1
        sent = message.files[0]
        assert sent.filename == "hello.py"
        sent.fp.seek(0)
        assert sent.fp.read() == b"print('hi')\n"

    asyncio.run(run())


def test_send_file_tool_sends_base64_and_strips_path():
    tool = SendFileTool(bot=None)
    message = FakeMessage()
    payload = base64.b64encode(b"\x00\x01binary").decode("ascii")

    async def run():
        result = await tool.execute(message, filename="../data.bin", content=payload, encoding="base64")
        assert result == "__FILE_SENT__ Sent file: data.bin (8 bytes)"
        sent = message.files[0]
        assert sent.filename == "data.bin"
        sent.fp.seek(0)
        assert sent.fp.read() == b"\x00\x01binary"

    asyncio.run(run())


def test_shell_tool_runs_without_author_gate():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

    tool = ShellTool(bot=FakeBot())
    message = FakeMessage()

    async def run():
        async def fake_run_shell(command, on_progress=None):
            assert len(message.channel.sent) == 1
            assert "working on it…" in message.channel.sent[0].content
            return b"hi", b"", 0

        tool._run_shell_command = fake_run_shell

        result = await tool.execute(message, command="printf hi")
        assert result == "hi"
        assert len(message.files) == 0
        assert len(message.channel.sent) == 1
        assert "working on it…" in message.channel.sent[0].content

    asyncio.run(run())


def test_shell_tool_truncates_captured_output_to_max_output(monkeypatch):
    monkeypatch.setenv("MAXWELL_SHELL_MAX_OUTPUT", "100")
    class FakeBot:
        def _is_admin(self, user_id):
            return True

    tool = ShellTool(bot=FakeBot())
    message = FakeMessage()
    blob = ("line of shell output\n" * 80).encode()

    async def run():
        async def fake_run_shell(command, on_progress=None):
            return blob, b"", 0

        tool._run_shell_command = fake_run_shell
        result = await tool.execute(message, command="cat huge.log")
        assert "line of shell output" in result
        assert "... (truncated)" in result
        assert len(result) <= 150
        assert len(message.channel.sent) == 1
        posted = message.channel.sent[0]
        assert posted.content == "working on it…"

    asyncio.run(run())


def test_shell_progress_respects_shared_server_setting():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

        def _progress_enabled(self, server_id):
            return False

    tool = ShellTool(bot=FakeBot())
    message = FakeMessage()
    message.guild = SimpleNamespace(id=99)

    async def run():
        async def fake_run_shell(command, on_progress=None):
            return b"quiet", b"", 0

        tool._run_shell_command = fake_run_shell
        result = await tool.execute(message, command="printf quiet")
        assert result == "quiet"
        assert message.channel.sent == []

    asyncio.run(run())


def test_same_turn_shell_calls_update_one_progress_message():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

    tool = ShellTool(bot=FakeBot())
    message = FakeMessage()

    async def run():
        async def fake_run_shell(command, on_progress=None):
            return command.encode(), b"", 0

        tool._run_shell_command = fake_run_shell
        await tool.execute(message, command="date")
        await tool.execute(message, command="uname")
        assert len(message.channel.sent) == 1
        posted = message.channel.sent[0]
        assert "working on it…" in posted.content
        assert posted.edits
        assert not posted.deleted
        forget_shell_progress(tool.bot, message)
        assert not posted.deleted

    asyncio.run(run())


def test_shell_progress_edits_while_command_runs():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

    tool = ShellTool(bot=FakeBot())
    message = FakeMessage()

    async def run():
        async def fake_run_shell(command, on_progress=None):
            if on_progress is not None:
                await on_progress(b"", b"", 0.0)
                await on_progress(b"downloading 1/3\n", b"", 1.4)
                await on_progress(b"downloading 1/3\n2/3\n", b"", 2.6)
            return b"downloading 1/3\n2/3\ndone\n", b"", 0

        tool._run_shell_command = fake_run_shell
        result = await tool.execute(message, command="fetch.sh")
        assert len(message.channel.sent) == 1
        posted = message.channel.sent[0]
        assert "working on it…" in posted.content
        assert result.endswith("done")

    asyncio.run(run())


def test_new_user_message_gets_a_fresh_shell_progress_message():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

    tool = ShellTool(bot=FakeBot())
    first = FakeMessage()
    second = FakeMessage()
    second.channel = first.channel

    async def run():
        async def fake_run_shell(command, on_progress=None):
            return command.encode(), b"", 0

        tool._run_shell_command = fake_run_shell
        await tool.execute(first, command="date")
        await tool.execute(second, command="uname")
        assert len(first.channel.sent) == 2
        posted_first, posted_second = first.channel.sent
        assert "working on it…" in posted_first.content
        assert "working on it…" in posted_second.content
        assert posted_first is not posted_second
        assert not posted_first.deleted
        assert not posted_second.deleted

    asyncio.run(run())


def test_send_message_leaves_shell_progress():
    class FakeBot:
        def _is_admin(self, user_id):
            return True

        def _render_custom_emojis(self, text, guild):
            return text

        def _extract_stickers_from_text(self, text, guild):
            return text, []

    bot = FakeBot()
    shell = ShellTool(bot=bot)
    send = SendMessageTool(bot=bot)
    message = FakeMessage()

    async def run():
        async def fake_run_shell(command, on_progress=None):
            return b"ok", b"", 0

        shell._run_shell_command = fake_run_shell
        await shell.execute(message, command="pwd")
        posted = message.channel.sent[0]
        assert not posted.deleted
        result = await send.execute(message, content="done")
        assert result.startswith("__MESSAGE_SENT__")
        assert not posted.deleted
        assert len(message.channel.sent) == 2

    asyncio.run(run())


def test_reasoning_log_tool_records_verbose_payload():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    bot = FakeBot()
    tool = ReasoningLogTool(bot=bot)
    message = FakeMessage()

    async def run():
        result = await tool.execute(
            message,
            intent="reply",
            confidence=0.82,
            thoughts="Need answer directly.",
            data={"raw": [1, 2, 3]},
        )
        assert result == "__REASONING_RECORDED__"

    asyncio.run(run())

    assert bot.traces == [{
        "thoughts": "Need answer directly.",
        "intent": "reply",
        "confidence": 0.82,
        "data": {"raw": [1, 2, 3]},
    }]
    assert list(bot.traces[0])[:1] == ["thoughts"]


def test_reasoning_log_strips_nested_xml_from_thoughts():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    bot = FakeBot()
    tool = ReasoningLogTool(bot=bot)
    message = FakeMessage()

    async def run():
        result = await tool.execute(
            message,
            thoughts="<thoughts>User wants a site</thoughts><intent>create</intent><decision>build</decision> and some extra text",
        )
        assert result == "__REASONING_RECORDED__"

    asyncio.run(run())

    trace = bot.traces[0]
    assert "<thoughts>" not in trace["thoughts"]
    assert "<intent>" not in trace["thoughts"]
    assert "some extra text" in trace["thoughts"]
    assert trace["intent"] == "create"
    assert trace["decision"] == "build"


def test_reasoning_log_preserves_valid_compact_payload():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    bot = FakeBot()
    tool = ReasoningLogTool(bot=bot)
    message = FakeMessage()

    async def run():
        result = await tool.execute(
            message,
            thoughts="User asked for a site, so I should create one.",
            intent="create_site",
            decision="use_create_site",
            confidence="high",
        )
        assert result == "__REASONING_RECORDED__"

    asyncio.run(run())

    trace = bot.traces[0]
    assert trace["thoughts"] == "User asked for a site, so I should create one."
    assert trace["intent"] == "create_site"
    assert trace["decision"] == "use_create_site"
    assert trace["confidence"] == "high"


def test_reasoning_log_clamps_long_fields():
    class FakeBot:
        def __init__(self):
            self.traces = []

        async def _record_llm_trace(self, message, payload):
            self.traces.append(payload)

    bot = FakeBot()
    tool = ReasoningLogTool(bot=bot)
    message = FakeMessage()

    async def run():
        result = await tool.execute(
            message,
            thoughts="x" * 1000,
            intent="y" * 600,
        )
        assert result == "__REASONING_RECORDED__"

    asyncio.run(run())

    trace = bot.traces[0]
    assert len(trace["thoughts"]) <= 500
    assert len(trace["intent"]) <= 500


def test_send_file_works_for_non_admin_user():
    """Regression: send_file used to require MAXWELL_OWNER_IDS, which blocked
    any non-admin user from receiving a file back. The tool is an output
    channel, not a privileged action — it must work for everyone."""

    class NonAdminBot:
        def _is_admin(self, user_id):
            return False  # explicitly NOT admin

    tool = SendFileTool(bot=NonAdminBot())
    message = FakeMessage()

    async def run():
        result = await tool.execute(
            message, filename="hello.txt", content="hi from a non-admin"
        )
        assert result == "__FILE_SENT__ Sent file: hello.txt (19 bytes)"
        assert len(message.files) == 1
        sent = message.files[0]
        assert sent.filename == "hello.txt"
        sent.fp.seek(0)
        assert sent.fp.read() == b"hi from a non-admin"

    asyncio.run(run())


def test_shell_export_requires_registered_enabled_tool(tmp_path, monkeypatch):
    import bot_tools
    from unittest.mock import AsyncMock

    monkeypatch.setattr(bot_tools, "_shell_workspace", lambda: tmp_path)
    docker = AsyncMock(side_effect=AssertionError("Docker must not be called"))
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    (tmp_path / "generated.txt").write_text("generated")
    for tools, enabled in [({}, True), ({"shell": ShellTool(bot=None)}, False)]:
        bot = SimpleNamespace(tools=tools, config=SimpleNamespace(ENABLE_SHELL=enabled))
        message = FakeMessage()
        tool = SendFileTool(bot=bot)
        for path in ["/home/maxwell/generated.txt", str(tmp_path / "generated.txt")]:
            result = asyncio.run(tool.execute(message, path=path))
            assert "registered enabled" in result
        assert not message.files
    docker.assert_not_called()


def test_shell_export_generated_bound_file(tmp_path, monkeypatch):
    import bot_tools
    from unittest.mock import AsyncMock

    monkeypatch.setattr(bot_tools, "_shell_workspace", lambda: tmp_path)
    (tmp_path / "generated.txt").write_text("generated")
    bot = SimpleNamespace(tools={}, config=SimpleNamespace(ENABLE_SHELL=True))
    shell = ShellTool(bot=bot)
    bot.tools["shell"] = shell
    shell._verify_export_container = AsyncMock(return_value="verified-container-id")
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", AsyncMock(side_effect=AssertionError("no Docker copy")))
    message = FakeMessage()
    result = asyncio.run(SendFileTool(bot=bot).execute(message, path="/home/maxwell/generated.txt"))
    assert result == "__FILE_SENT__ Sent file: generated.txt (9 bytes)"
    assert message.files[0].fp.read() == b"generated"
    shell._verify_export_container.assert_awaited_once()
    assert asyncio.run(shell._send_container_file(message, "/home/maxwell/generated.txt")) == "generated.txt"
    assert message.files[1].fp.read() == b"generated"


def test_shell_export_rejects_traversal_symlink_and_arbitrary_copy(tmp_path, monkeypatch):
    import bot_tools
    from unittest.mock import AsyncMock

    workspace = tmp_path / "shell"
    workspace.mkdir()
    (tmp_path / "outside.txt").write_text("outside")
    (workspace / "escape.txt").symlink_to(tmp_path / "outside.txt")
    (workspace / "parent").symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(bot_tools, "_shell_workspace", lambda: workspace)
    bot = SimpleNamespace(tools={}, config=SimpleNamespace(ENABLE_SHELL=True, DATA_DIR=str(tmp_path / "unused")))
    shell = ShellTool(bot=bot)
    bot.tools["shell"] = shell
    shell._verify_export_container = AsyncMock(return_value="verified-container-id")
    docker = AsyncMock(side_effect=AssertionError("arbitrary docker cp forbidden"))
    monkeypatch.setattr(bot_tools, "_run_docker_cmd", docker)
    tool = SendFileTool(bot=bot)
    for path in ["/host/etc/shadow", "/etc/passwd", "/tmp/generated.txt", "/home/maxwellish/outside.txt", "/home/maxwell/../outside.txt", "/home/maxwell//etc/passwd", "/home/maxwell/escape.txt", "/home/maxwell/parent/outside.txt"]:
        message = FakeMessage()
        assert asyncio.run(tool.execute(message, path=path)).startswith("Error")
        assert asyncio.run(shell._send_container_file(message, path)) is None
        assert not message.files
    docker.assert_not_called()


def test_shell_export_rejects_stale_wrong_mode(tmp_path, monkeypatch):
    import bot_tools
    from unittest.mock import AsyncMock

    monkeypatch.setattr(bot_tools, "_shell_workspace", lambda: tmp_path)
    (tmp_path / "generated.txt").write_text("generated")
    bot = SimpleNamespace(tools={}, config=SimpleNamespace(ENABLE_SHELL=True))
    shell = ShellTool(bot=bot)
    bot.tools["shell"] = shell
    shell._verify_export_container = AsyncMock(side_effect=ValueError("shell container mode does not match configuration"))
    message = FakeMessage()
    result = asyncio.run(SendFileTool(bot=bot).execute(message, path="/home/maxwell/generated.txt"))
    assert "mode does not match" in result
    assert not message.files


def test_generated_host_exports_do_not_require_shell(tmp_path):
    export = tmp_path / "exports"
    export.mkdir()
    (export / "report.txt").write_text("report")
    bot = SimpleNamespace(tools={}, config=SimpleNamespace(ENABLE_SHELL=False, DATA_DIR=str(tmp_path)))
    message = FakeMessage()
    result = asyncio.run(SendFileTool(bot=bot).execute(message, path=str(export / "report.txt")))
    assert result == "__FILE_SENT__ Sent file: report.txt (6 bytes)"


def test_shell_export_rejects_symlink_swapped_after_resolve(tmp_path, monkeypatch):
    import os
    import bot_tools
    from unittest.mock import AsyncMock

    workspace = tmp_path / "shell"
    workspace.mkdir()
    nested = workspace / "nested"
    nested.mkdir()
    (nested / "file.txt").write_text("safe")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("outside")
    monkeypatch.setattr(bot_tools, "_shell_workspace", lambda: workspace)
    bot = SimpleNamespace(tools={}, config=SimpleNamespace(ENABLE_SHELL=True))
    shell = ShellTool(bot=bot)
    bot.tools["shell"] = shell
    shell._verify_export_container = AsyncMock(return_value="verified")
    real_open = os.open

    def swap_open(path, flags, *args, **kwargs):
        if path == workspace and nested.is_dir() and not nested.is_symlink():
            nested.rename(workspace / "original")
            nested.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_open)
    message = FakeMessage()
    result = asyncio.run(SendFileTool(bot=bot).execute(message, path="/home/maxwell/nested/file.txt"))
    assert result.startswith("Error")
    assert not message.files
