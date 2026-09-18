"""Regression tests for Discord MESSAGE_UPDATE context refreshes."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from bot import MaxwellBot


class _Memory:
    def __init__(self):
        self.rows = []

    async def add_to_channel_memory(self, channel_id, row):
        self.rows.append((str(channel_id), dict(row)))


def _message(message_id, content, *, embeds=None):
    author = SimpleNamespace(id=11, display_name="Alice", bot=False)
    channel = SimpleNamespace(id=22, name="chat", guild=None)
    return SimpleNamespace(
        id=message_id,
        content=content,
        author=author,
        channel=channel,
        guild=None,
        embeds=list(embeds or []),
        attachments=[],
        stickers=[],
        components=[],
        poll=None,
        mentions=[],
        channel_mentions=[],
        role_mentions=[],
        mention_everyone=False,
        reference=None,
        created_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        type=SimpleNamespace(name="default"),
    )


class _ReplyChannel:
    id = 22
    name = "chat"
    guild = None
    type = discord.ChannelType.private

    def __init__(self):
        self._state = SimpleNamespace()
        self.send = AsyncMock(return_value=SimpleNamespace(id=900, channel=self))

    def get_partial_message(self, message_id):
        return discord.PartialMessage(channel=self, id=int(message_id))


def _delivery_message(message_id, content):
    message = _message(message_id, content)
    message.channel = _ReplyChannel()
    message.reply = message.channel.get_partial_message(message_id).reply
    return message


def _bot():
    bot = object.__new__(MaxwellBot)
    bot._control = {
        "store_memory": True,
        "process_images": True,
        "process_audio": False,
        "ignore_users": [],
        "allowed_channels": [],
        "blocked_channels": [],
    }
    bot._blacklist = set()
    bot._message_snapshots = {}
    bot._message_update_state = {}
    bot._inflight_context = {}
    bot._media_context = {}
    bot._recent_users = {}
    bot.memory = _Memory()
    bot._is_admin = lambda _user_id: False
    bot._update_recent_users = lambda *_args: None

    async def add_message_to_memory(channel_id, row, _message=None):
        await bot.memory.add_to_channel_memory(channel_id, row)

    bot.add_message_to_memory = add_message_to_memory
    bot._cache_media_context = MaxwellBot._cache_media_context.__get__(bot)
    return bot


def test_message_edit_replaces_memory_text_and_visual_cache():
    bot = _bot()
    old = _message(77, "old text")
    new_embed = SimpleNamespace(
        title="new preview",
        description="updated embed description",
        url="https://example.com/post",
        image=SimpleNamespace(url="https://cdn.example/image.png"),
        thumbnail=None,
        video=None,
        author=None,
        provider=None,
        fields=[],
        footer=None,
    )
    after = _message(77, "new text", embeds=[new_embed])
    bot._media_context["22"] = [
        {
            "b64": "b2xk",
            "mime_type": "image/jpeg",
            "filename": "old.jpg",
            "message_id": 77,
            "uses_left": 1,
        }
    ]

    async def extract(message):
        return [
            {
                "b64": "bmV3",
                "mime_type": "image/png",
                "filename": "new.png",
                "is_image": True,
                "message_id": message.id,
                "url": "https://cdn.example/image.png",
            }
        ]

    bot._extract_context_media = extract
    asyncio.run(MaxwellBot.on_message_edit(bot, old, after))

    assert "new text" in bot.memory.rows[-1][1]["content"]
    assert "old text" not in bot.memory.rows[-1][1]["content"]
    cached = bot._media_context["22"]
    assert [item["filename"] for item in cached] == ["new.png"]


def test_embed_mutation_refreshes_text_without_redownloading_same_media():
    bot = _bot()
    calls = []

    def embed(description):
        return SimpleNamespace(
            title="preview",
            description=description,
            url="https://example.com/post",
            image=SimpleNamespace(url="https://cdn.example/image.png"),
            thumbnail=None,
            video=None,
            author=None,
            provider=None,
            fields=[],
            footer=None,
        )

    first = _message(88, "look", embeds=[embed("first")])
    second = _message(88, "look", embeds=[embed("second")])

    async def extract(message):
        calls.append(message.embeds[0].description)
        return [
            {
                "b64": "aW1hZ2U=",
                "mime_type": "image/png",
                "filename": "preview.png",
                "is_image": True,
                "message_id": message.id,
                "url": "https://cdn.example/image.png",
            }
        ]

    bot._extract_context_media = extract
    assert asyncio.run(MaxwellBot._refresh_edited_message(bot, first)) is True
    assert asyncio.run(MaxwellBot._refresh_edited_message(bot, second)) is True

    assert calls == ["first"]
    assert "second" in bot.memory.rows[-1][1]["content"]
    assert len(bot._media_context["22"]) == 1


def test_text_edit_notifies_inflight_turn_without_dispatching_reply():
    bot = _bot()
    before = _message(99, "before")
    after = _message(99, "after")
    state = MaxwellBot._begin_inflight_context(bot, before, before.content)
    state["media"] = [
        {
            "b64": "aW1hZ2U=",
            "mime_type": "image/png",
            "filename": "current.png",
            "is_image": True,
            "message_id": 99,
        }
    ]
    bot._message_update_state["99"] = (
        MaxwellBot._message_update_fingerprint(before),
        MaxwellBot._message_media_fingerprint(before),
        0.0,
    )
    bot._extract_context_media = lambda _message: None

    async def no_media(_message):
        raise AssertionError("text-only edit should not download media")

    bot._extract_context_media = no_media
    assert asyncio.run(
        MaxwellBot._refresh_edited_message(bot, after, before=before)
    ) is True
    assert state["latest_content"] == "after"
    assert state["latest_media"] == state["media"]
    assert state["version"] == 1


def test_raw_partial_update_merges_with_cached_message():
    bot = _bot()
    cached = _message(101, "keep this text")
    payload = SimpleNamespace(
        cached_message=cached,
        message_id=101,
        channel_id=22,
        data={
            "id": "101",
            "channel_id": "22",
            "embeds": [
                {
                    "title": "late preview",
                    "description": "unfurled",
                    "url": "https://example.com/post",
                }
            ],
        },
    )

    merged = asyncio.run(MaxwellBot._message_from_raw_update(bot, payload))

    assert merged.content == "keep this text"
    assert merged.embeds[0].title == "late preview"
    assert merged.author.id == 11
    assert merged.author.bot is False


def test_raw_author_without_bot_flag_is_human():
    bot = _bot()
    payload = SimpleNamespace(
        cached_message=None,
        message_id=202,
        channel_id=22,
        data={
            "id": "202",
            "channel_id": "22",
            "content": "hello",
            "author": {"id": "11", "username": "alice"},
        },
    )
    merged = asyncio.run(MaxwellBot._message_from_raw_update(bot, payload))
    assert merged.author.bot is False
    assert merged.author.display_name == "alice"


def test_raw_cached_update_preserves_reply_delivery():
    async def scenario():
        bot = _bot()
        cached = _delivery_message(303, "original text")
        payload = SimpleNamespace(
            cached_message=cached, message_id=303, channel_id=22,
            data={"content": "edited text", "embeds": [{"title": "late preview"}]},
        )

        merged = await bot._message_from_raw_update(payload)
        sent = await merged.reply("finished answer", mention_author=False)

        assert merged.content == "edited text"
        assert merged.embeds[0].title == "late preview"
        assert merged.author.id == cached.author.id
        assert merged.author.bot is False
        assert cached.content == "original text"
        assert cached.embeds == []
        assert sent is cached.channel.send.return_value
        call = cached.channel.send.call_args
        assert call.args == ("finished answer",)
        assert call.kwargs["mention_author"] is False
        reference = call.kwargs["reference"].to_message_reference_dict()
        assert str(reference["message_id"]) == "303"
        assert str(reference["channel_id"]) == "22"

    asyncio.run(scenario())


def test_repeated_raw_partial_updates_preserve_latest_data_and_reply():
    async def scenario():
        bot = _bot()
        original = _delivery_message(404, "original text")
        payload = SimpleNamespace(
            cached_message=original, message_id=404, channel_id=22,
            data={"content": "fresh text", "embeds": [{"title": "first preview"}]},
        )
        first = await bot._message_from_raw_update(payload)
        bot._message_snapshots["404"] = first
        payload.cached_message = None
        payload.data = {"embeds": [{"title": "second preview"}]}
        second = await bot._message_from_raw_update(payload)
        bot._message_snapshots["404"] = second
        payload.data = {"content": "newest text"}
        latest = await bot._message_from_raw_update(payload)

        assert second.content == "fresh text"
        assert latest.content == "newest text"
        assert latest.embeds[0].title == "second preview"
        assert latest.author.bot is False
        await second.reply("second answer")
        await latest.reply("latest answer")
        assert original.channel.send.await_count == 2
        assert [call.args[0] for call in original.channel.send.call_args_list] == [
            "second answer", "latest answer",
        ]
        for call in original.channel.send.call_args_list:
            reference = call.kwargs["reference"].to_message_reference_dict()
            assert str(reference["message_id"]) == "404"
            assert str(reference["channel_id"]) == "22"

    asyncio.run(scenario())


def test_raw_uncached_fetch_failure_can_reply_via_channel():
    async def scenario():
        bot = _bot()
        channel = _ReplyChannel()
        channel.fetch_message = AsyncMock(side_effect=RuntimeError("fetch unavailable"))
        bot.get_channel = lambda channel_id: channel if int(channel_id) == 22 else None
        payload = SimpleNamespace(
            cached_message=None, message_id=505, channel_id=22,
            data={
                "content": "fresh uncached text",
                "embeds": [{"title": "uncached preview"}],
                "author": {"id": "11", "username": "alice"},
            },
        )

        merged = await bot._message_from_raw_update(payload)
        sent = await merged.reply("uncached answer")

        channel.fetch_message.assert_awaited_once_with(505)
        assert merged.content == "fresh uncached text"
        assert merged.embeds[0].title == "uncached preview"
        assert merged.author.bot is False
        assert sent is channel.send.return_value
        assert channel.send.call_args.args == ("uncached answer",)
        reference = channel.send.call_args.kwargs["reference"].to_message_reference_dict()
        assert str(reference["message_id"]) == "505"
        assert str(reference["channel_id"]) == "22"

    asyncio.run(scenario())
