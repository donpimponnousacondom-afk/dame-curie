import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import bot as bot_module
from bot import MaxwellBot
from prompt_storage import PromptStore


class RecordingChannel:
    def __init__(self):
        self.id = 23
        self.sent = []

    async def send(self, content, **kwargs):
        assert len(content) <= 2000
        payload = {"content": content, **kwargs}
        attachment = kwargs.get("file")
        if attachment is not None:
            payload["file_bytes"] = attachment.fp.read()
            payload["filename"] = attachment.filename
        self.sent.append(payload)


@pytest.fixture
def longprompt_case():
    memory = SimpleNamespace(
        get_server_prompt=Mock(return_value=None),
        set_server_prompt=Mock(),
        clear_server_prompt=Mock(),
    )
    bot = SimpleNamespace(
        command_prefix="?",
        _control={"disabled_commands": []},
        _is_admin=lambda user_id: user_id == 7,
        memory=memory,
    )
    channel = RecordingChannel()
    message = SimpleNamespace(
        content="?longprompt",
        author=SimpleNamespace(id=7),
        channel=channel,
        guild=SimpleNamespace(id=31, name="Synthetic Guild"),
        attachments=[],
    )
    return bot, message, memory


@pytest.fixture
def disk_prompt_memory(tmp_path):
    store = PromptStore(tmp_path)
    memory = SimpleNamespace(
        get_server_prompt=lambda server_id: store.read_servers(retain_valid=True).get(str(server_id)),
        set_server_prompt=store.set_server,
        clear_server_prompt=store.delete_server,
    )
    return store, memory


@pytest.mark.parametrize("prefix", ["!", "?"])
@pytest.mark.parametrize(
    ("guild", "scope"),
    [
        (SimpleNamespace(id=31, name="Guild name " + "g" * 180), "31"),
        (None, "DM"),
    ],
)
def test_longprompt_upload_preserves_exact_text_and_uses_guild_or_dm_scope(
    longprompt_case, prefix, guild, scope
):
    bot, message, memory = longprompt_case
    bot.command_prefix = prefix
    message.content = f"{prefix}longprompt"
    prompt = (
        "\ufeff \t1545541390392369165\r\n```🕊\r\n"
        + "<@111111111111111111> <@&222222222222222222> @everyone " * 80
        + "\r\n \t"
    )
    assert len(prompt) > 2000
    filename = "source-" + "x" * 180 + ".TXT"
    attachment = SimpleNamespace(
        filename=filename,
        size=len(prompt.encode("utf-8")),
        read=AsyncMock(return_value=prompt.encode("utf-8")),
    )
    message.attachments = [attachment]
    message.guild = guild

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.set_server_prompt.assert_called_once_with(scope, prompt)
    memory.get_server_prompt.assert_not_called()
    attachment.read.assert_awaited_once()
    assert len(message.channel.sent) == 1
    response = message.channel.sent[0]["content"]
    assert len(response) <= 120
    assert prompt not in response and "@everyone" not in response and "<@" not in response
    assert filename not in response
    assert guild is None or guild.name not in response
    allowed_mentions = message.channel.sent[0]["allowed_mentions"]
    assert not allowed_mentions.everyone
    assert not allowed_mentions.users
    assert not allowed_mentions.roles
    assert not allowed_mentions.replied_user


def test_longprompt_accepts_whitespace_only_text_without_trimming(longprompt_case):
    bot, message, memory = longprompt_case
    payload = b" \t\r\n  "
    attachment = SimpleNamespace(
        filename="prompt.txt", size=len(payload), read=AsyncMock(return_value=payload)
    )
    message.attachments = [attachment]

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.set_server_prompt.assert_called_once_with("31", payload.decode("utf-8"))
    attachment.read.assert_awaited_once()
    assert len(message.channel.sent[0]["content"]) <= 120


@pytest.mark.parametrize(
    ("declared_size", "payload", "accepted"),
    [
        (bot_module.TEXT_ATTACHMENT_MAX_BYTES, b"x" * bot_module.TEXT_ATTACHMENT_MAX_BYTES, True),
        (bot_module.TEXT_ATTACHMENT_MAX_BYTES + 1, b"x", False),
        (
            1,
            ("é" * (bot_module.TEXT_ATTACHMENT_MAX_BYTES // 2 + 1)).encode("utf-8"),
            False,
        ),
    ],
)
def test_longprompt_upload_enforces_declared_and_actual_byte_limits(
    longprompt_case, declared_size, payload, accepted
):
    bot, message, memory = longprompt_case
    attachment = SimpleNamespace(
        filename="prompt.txt", size=declared_size, read=AsyncMock(return_value=payload)
    )
    message.attachments = [attachment]

    asyncio.run(MaxwellBot._handle_command(bot, message))

    if accepted:
        memory.set_server_prompt.assert_called_once_with("31", payload.decode("utf-8"))
        attachment.read.assert_awaited_once()
        assert len(message.channel.sent[0]["content"]) <= 120
        assert "x" * 100 not in message.channel.sent[0]["content"]
    else:
        memory.set_server_prompt.assert_not_called()
        response = message.channel.sent[0]["content"].lower()
        assert any(term in response for term in ("size", "limit", "large", "512"))
        if declared_size > bot_module.TEXT_ATTACHMENT_MAX_BYTES:
            attachment.read.assert_not_awaited()
        else:
            attachment.read.assert_awaited_once()


@pytest.mark.parametrize(
    ("payload", "reason"),
    [(b"", "empty"), (b"\xff", "utf-8")],
)
def test_longprompt_rejects_empty_or_malformed_utf8_without_mutating(
    longprompt_case, payload, reason
):
    bot, message, memory = longprompt_case
    previous = "existing prompt remains"
    memory.get_server_prompt.return_value = previous
    attachment = SimpleNamespace(
        filename="prompt.txt", size=len(payload), read=AsyncMock(return_value=payload)
    )
    message.attachments = [attachment]

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.set_server_prompt.assert_not_called()
    assert memory.get_server_prompt.return_value == previous
    attachment.read.assert_awaited_once()
    response = message.channel.sent[0]["content"].lower()
    assert reason in response or (reason == "utf-8" and "decode" in response)
    assert previous not in response


@pytest.mark.parametrize(
    ("arguments", "filenames", "reason"),
    [
        ("", ["prompt.pdf"], ".txt"),
        ("inline text", ["prompt.txt"], "argument"),
        ("inline text", [], "argument"),
        ("", ["one.txt", "two.txt"], "one"),
    ],
)
def test_longprompt_rejects_wrong_extension_inline_args_and_multiple_files(
    longprompt_case, arguments, filenames, reason
):
    bot, message, memory = longprompt_case
    attachments = [
        SimpleNamespace(filename=filename, size=4, read=AsyncMock(return_value=b"text"))
        for filename in filenames
    ]
    message.content = "?longprompt" + (f" {arguments}" if arguments else "")
    message.attachments = attachments

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.set_server_prompt.assert_not_called()
    memory.get_server_prompt.assert_not_called()
    for attachment in attachments:
        attachment.read.assert_not_awaited()
    response = message.channel.sent[0]["content"].lower()
    assert reason in response or (reason == "argument" and "inline" in response)


@pytest.mark.parametrize("upload", [False, True])
def test_longprompt_admin_gate_precedes_prompt_access_and_attachment_read(longprompt_case, upload):
    bot, message, memory = longprompt_case
    attachment = SimpleNamespace(
        filename="prompt.txt", size=4, read=AsyncMock(return_value=b"text")
    )
    message.attachments = [attachment] if upload else []
    bot._is_admin = lambda user_id: False

    asyncio.run(MaxwellBot._handle_command(bot, message))

    assert [item["content"] for item in message.channel.sent] == ["not authorized"]
    memory.get_server_prompt.assert_not_called()
    memory.set_server_prompt.assert_not_called()
    attachment.read.assert_not_awaited()


@pytest.mark.parametrize("upload", [False, True])
def test_longprompt_obeys_disabled_commands_before_prompt_access(longprompt_case, upload):
    bot, message, memory = longprompt_case
    attachment = SimpleNamespace(
        filename="prompt.txt", size=4, read=AsyncMock(return_value=b"text")
    )
    message.attachments = [attachment] if upload else []
    bot._control["disabled_commands"] = ["longprompt"]

    asyncio.run(MaxwellBot._handle_command(bot, message))

    assert not message.channel.sent
    memory.get_server_prompt.assert_not_called()
    memory.set_server_prompt.assert_not_called()
    attachment.read.assert_not_awaited()


@pytest.mark.parametrize(
    ("guild", "scope"), [(SimpleNamespace(id=31, name="Guild"), "31"), (None, "DM")]
)
def test_longprompt_export_is_utf8_byte_exact_short_and_mention_safe(longprompt_case, guild, scope):
    bot, message, memory = longprompt_case
    prompt = (
        "\ufeff 1545541390392369165\r\n```🕊\r\n"
        + "<@111111111111111111> <@&222222222222222222> @everyone " * 80
        + "\t \n"
    )
    assert len(prompt) > 2000
    memory.get_server_prompt.return_value = prompt
    message.guild = guild

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.get_server_prompt.assert_called_once_with(scope)
    memory.set_server_prompt.assert_not_called()
    assert len(message.channel.sent) == 1
    response = message.channel.sent[0]["content"]
    assert len(response) <= 120
    assert prompt not in response and "@everyone" not in response and "<@" not in response
    assert message.channel.sent[0]["filename"] == "prompt.txt"
    assert message.channel.sent[0]["file_bytes"] == prompt.encode("utf-8")
    assert message.channel.sent[0]["file"].fp.closed
    allowed_mentions = message.channel.sent[0]["allowed_mentions"]
    assert not allowed_mentions.everyone
    assert not allowed_mentions.users
    assert not allowed_mentions.roles
    assert not allowed_mentions.replied_user


@pytest.mark.parametrize(
    ("prompt", "exported"),
    [
        ("x" * bot_module.TEXT_ATTACHMENT_MAX_BYTES, True),
        ("é" * (bot_module.TEXT_ATTACHMENT_MAX_BYTES // 2 + 1), False),
    ],
)
def test_longprompt_export_enforces_utf8_byte_limit_without_truncation(
    longprompt_case, prompt, exported
):
    bot, message, memory = longprompt_case
    memory.get_server_prompt.return_value = prompt

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.get_server_prompt.assert_called_once_with("31")
    memory.set_server_prompt.assert_not_called()
    if exported:
        assert message.channel.sent[0]["filename"] == "prompt.txt"
        assert message.channel.sent[0]["file_bytes"] == prompt.encode("utf-8")
        assert len(message.channel.sent[0]["content"]) <= 120
    else:
        assert len(message.channel.sent) == 1
        response = message.channel.sent[0]["content"].lower()
        assert any(term in response for term in ("size", "limit", "large", "512"))
        assert "file_bytes" not in message.channel.sent[0]
        assert len(response) <= 120


def test_longprompt_round_trips_exact_text_through_prompt_store(longprompt_case, disk_prompt_memory):
    bot, message, _ = longprompt_case
    store, memory = disk_prompt_memory
    bot.memory = memory
    prompt = "\ufeff \t1545541390392369165\r\n```🕊\r\n@everyone\r\n  "
    payload = prompt.encode("utf-8")
    message.attachments = [
        SimpleNamespace(
            filename="prompt.txt", size=len(payload), read=AsyncMock(return_value=payload)
        )
    ]

    asyncio.run(MaxwellBot._handle_command(bot, message))

    assert store.read_servers() == {"31": prompt}
    message.channel.sent.clear()
    message.attachments = []
    asyncio.run(MaxwellBot._handle_command(bot, message))
    assert message.channel.sent[0]["file_bytes"] == payload


def test_longprompt_attachment_read_failure_leaves_prompt_unchanged(longprompt_case, monkeypatch):
    bot, message, memory = longprompt_case
    attachment = SimpleNamespace(
        filename="prompt.txt", size=4, read=AsyncMock(side_effect=RuntimeError("synthetic read failure"))
    )
    message.attachments = [attachment]
    public_error = AsyncMock()
    monkeypatch.setattr(bot_module, "send_public_error", public_error)

    asyncio.run(MaxwellBot._handle_command(bot, message))

    attachment.read.assert_awaited_once()
    memory.set_server_prompt.assert_not_called()
    public_error.assert_awaited_once_with(bot, message.channel)


def test_longprompt_ack_failure_does_not_roll_back_saved_prompt(
    longprompt_case, disk_prompt_memory, monkeypatch
):
    bot, message, _ = longprompt_case
    store, memory = disk_prompt_memory
    bot.memory = memory
    prompt = "\ufeff preserve\r\n  ```"
    payload = prompt.encode("utf-8")
    attachment = SimpleNamespace(
        filename="prompt.txt", size=len(payload), read=AsyncMock(return_value=payload)
    )
    message.attachments = [attachment]
    message.channel.send = AsyncMock(side_effect=RuntimeError("synthetic ack failure"))
    public_error = AsyncMock()
    monkeypatch.setattr(bot_module, "send_public_error", public_error)

    asyncio.run(MaxwellBot._handle_command(bot, message))

    attachment.read.assert_awaited_once()
    assert store.read_servers() == {"31": prompt}
    public_error.assert_awaited_once_with(bot, message.channel)


def test_longprompt_export_send_failure_closes_file_buffer(longprompt_case, monkeypatch):
    bot, message, memory = longprompt_case
    memory.get_server_prompt.return_value = "export body"
    message.channel.send = AsyncMock(side_effect=RuntimeError("synthetic export failure"))
    public_error = AsyncMock()
    monkeypatch.setattr(bot_module, "send_public_error", public_error)

    asyncio.run(MaxwellBot._handle_command(bot, message))

    prompt_file = message.channel.send.await_args.kwargs["file"]
    assert prompt_file.fp.closed
    memory.set_server_prompt.assert_not_called()
    public_error.assert_awaited_once_with(bot, message.channel)


def test_longprompt_without_stored_prompt_returns_a_short_upload_hint(longprompt_case):
    bot, message, memory = longprompt_case

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.get_server_prompt.assert_called_once_with("31")
    memory.set_server_prompt.assert_not_called()
    assert len(message.channel.sent) == 1
    hint = message.channel.sent[0]["content"].lower()
    assert len(hint) <= 2000
    assert "prompt" in hint
    assert any(term in hint for term in ("attach", "upload", ".txt"))
    assert "file" not in message.channel.sent[0]


def test_prompt_and_clearprompt_retain_their_existing_command_behavior(longprompt_case):
    bot, message, memory = longprompt_case
    prompt = "legacy inline @everyone\r\n```"
    message.content = "?prompt " + prompt

    asyncio.run(MaxwellBot._handle_command(bot, message))

    memory.set_server_prompt.assert_called_once_with("31", prompt)
    assert message.channel.sent[0]["content"] == (
        f"Prompt updated for {message.guild.name}:\n```\n{prompt}\n```"
    )

    message.channel.sent.clear()
    message.content = "?clearprompt"
    asyncio.run(MaxwellBot._handle_command(bot, message))
    memory.clear_server_prompt.assert_called_once_with("31")
    assert [item["content"] for item in message.channel.sent] == ["Server prompt cleared."]
