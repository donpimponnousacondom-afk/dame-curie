import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot import MaxwellBot


@pytest.fixture
def mention_bot():
    bot = SimpleNamespace(
        user=SimpleNamespace(id=100000000000000001),
        _control={
            "reply_to_bots": True,
            "store_memory": False,
            "process_images": False,
        },
        _blacklist=set(),
        _partner_ids=set(),
        _stop_until={},
        _cooldowns={},
        _active_requests={},
        _active_request_user={},
        command_prefix=",",
        _load_control=Mock(),
        clear_message_taint=Mock(),
        _is_admin=lambda _uid: False,
        _update_recent_users=Mock(),
        _get_channel_lock=lambda _cid: asyncio.Lock(),
        _channel_lock_timeout=lambda: 1,
        _conversation_watch_active=lambda _cid: False,
        _maybe_schedule_context_extraction=Mock(),
        _cancel_watch_debounce=Mock(),
        _touch_watch_debounce=Mock(),
        _dispatch_reply=Mock(),
        _arm_watch_from_own_message=AsyncMock(),
    )
    for name in (
        "_directly_addressed",
        "_is_partner_message",
        "_reset_partner_reply_budget_for_human",
        "_should_live_reply",
        "_maybe_live_reply",
        "_content_without_self_mention",
        "_solo_channel_for",
        "_solo_blocks",
    ):
        setattr(bot, name, getattr(MaxwellBot, name).__get__(bot))
    return bot


@pytest.fixture
def app_message(mention_bot):
    return SimpleNamespace(
        id=100000000000000004,
        author=SimpleNamespace(id=100000000000000002, bot=True),
        channel=SimpleNamespace(id=100000000000000003),
        guild=SimpleNamespace(id=100000000000000005),
        content=f"<@{mention_bot.user.id}> generate an image",
        mentions=[],
        reference=None,
        attachments=[],
        embeds=[],
        stickers=[],
    )


@pytest.mark.parametrize("marker", ["@", "@!"])
@pytest.mark.parametrize("author_is_bot", [False, True])
def test_raw_self_mention_dispatches_without_parsed_mentions(
    mention_bot, app_message, marker, author_is_bot
):
    app_message.author.bot = author_is_bot
    app_message.author.display_name = "test sender"
    app_message.content = f"<{marker}{mention_bot.user.id}> generate an image"
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_called_once_with(
        app_message, "generate an image", directed=True
    )


def test_raw_self_mention_with_another_parsed_user_dispatches(mention_bot, app_message):
    app_message.mentions = [SimpleNamespace(id=100000000000000006)]
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_called_once()


@pytest.mark.parametrize(
    "content",
    [
        "@Dame Curie hello",
        "<@100000000000000006> hello",
        "<@&100000000000000001> hello",
        "<#100000000000000001> hello",
        "<@1000000000000000010> hello",
        "<@100000000000000001 hello",
    ],
)
def test_non_user_or_nonself_tokens_do_not_dispatch(mention_bot, app_message, content):
    app_message.content = content
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_not_called()


@pytest.mark.parametrize(
    "control",
    [
        {"bot_enabled": False},
        {"reply_to_bots": False},
        {"reply_mentions": False},
        {"ignore_users": ["100000000000000002"]},
        {"blocked_channels": ["100000000000000003"]},
        {"allowed_channels": ["100000000000000006"]},
        {"guild_solo_channel": {"100000000000000005": "100000000000000006"}},
    ],
)
def test_raw_mentions_do_not_bypass_existing_controls(
    mention_bot, app_message, control
):
    mention_bot._control.update(control)
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_not_called()


def test_raw_mentions_do_not_bypass_blacklist(mention_bot, app_message):
    mention_bot._blacklist.add(str(app_message.author.id))
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_not_called()


def test_self_message_with_raw_self_mention_never_dispatches(mention_bot, app_message):
    app_message.author.id = mention_bot.user.id
    asyncio.run(MaxwellBot._on_message_impl(mention_bot, app_message))
    mention_bot._dispatch_reply.assert_not_called()


def test_forwarded_snapshot_mention_is_not_a_direct_ping(mention_bot, app_message):
    app_message.message_snapshots = [SimpleNamespace(content=app_message.content)]
    app_message.content = ""
    app_message.reference = SimpleNamespace(
        type=SimpleNamespace(name="forward", value=1),
        resolved=SimpleNamespace(author=mention_bot.user),
    )
    assert mention_bot._directly_addressed(app_message) is False
