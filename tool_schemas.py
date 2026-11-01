"""OpenAI-compatible tool schemas for Dame Curie native function calling.

Each entry maps a tool name to a JSON Schema ``parameters`` object. Descriptions
come from the live tool instances at request time so they stay in sync with
``get_description()``.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

logger = logging.getLogger(__name__)


def _obj(
    properties: dict[str, Any],
    required: list[str] | None = None,
    *,
    additional: bool = True,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": additional,
    }
    if required:
        schema["required"] = required
    return schema


def _str(desc: str = "", **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "string", "description": desc}
    out.update(extra)
    return out


def _bool(desc: str = "") -> dict[str, Any]:
    return {"type": "boolean", "description": desc}


def _int(desc: str = "") -> dict[str, Any]:
    return {"type": "integer", "description": desc}


def _num(desc: str = "") -> dict[str, Any]:
    return {"type": "number", "description": desc}


# parameter schemas only - descriptions are attached from tool.get_description()
CORE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "send_message", "react", "search_messages", "lookup_user", "web_search",
        "fetch_url", "shell", "image_generator", "see_image", "see_video",
        "youtube", "send_file", "wait", "no_response", "more_tools",
    }
)
TOOL_DISCOVERY_GROUPS: dict[str, frozenset[str]] = {
    "messaging": frozenset(
        {
            "edit_message", "delete_message", "create_poll", "create_invite",
            "forward_message", "typing", "pin_message", "inbox_list", "inbox_act",
        }
    ),
    "media": frozenset(
        {"change_avatar", "send_meme", "send_media", "tts"}
    ),
    "identity": frozenset(
        {"set_nickname", "set_member_nickname", "change_avatar", "change_presence"}
    ),
    "servers": frozenset(
        {
            "join_server", "server_setup", "leave_server", "list_servers",
            "list_admin_servers", "create_category", "create_channel", "edit_channel",
            "delete_channel", "set_channel_permissions", "edit_server", "manage_emoji",
        }
    ),
    "moderation": frozenset(
        {
            "kick_member", "ban_member", "unban_member", "list_bans", "timeout_member",
            "manage_role", "purge_messages", "set_member_nickname", "voice_mod",
            "lock_channel", "audit_log", "pin_message",
        }
    ),
    "voice": frozenset(
        {"join_vc", "vc_status", "vc_where", "leave_vc", "voice_mod", "tts"}
    ),
    "workflow": frozenset(
        {
            "set_activity", "sleep", "clear_sleep", "update_base_personality",
            "update_server_prompt", "guide", "spawn_background", "usage", "manage_plugin",
        }
    ),
    "games": frozenset(
        {"chess_start", "chess_move", "chess_state", "chess_resign"}
    ),
    "plugins": frozenset({"manage_plugin"}),
}

TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "image_generator": _obj(
        {
            "prompt": _str(
                "What to generate, or - with input images - the change to make"
            ),
            "image": _str(
                "Optional image URL, data URI, or local path Dame Curie wrote; for several, pass a "
                "JSON list or comma-separated refs (max 4). Omit to use message attachments. "
                "Pass an empty string or empty JSON list to generate from scratch without attachments."
            ),
            "auto_send": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Default false: generate/edit and save only; present with send_file(path=..., caption=...) "
                    "or a normal image-preview link. True: upload once immediately; __IMAGE_SENT__ "
                    "means already sent, do not resend its URL or add commentary."
                ),
            },
        },
        ["prompt"],
    ),
    "react": _obj({"emoji": _str("Emoji or custom emoji name")}, ["emoji"]),
    "edit_message": _obj(
        {
            "message_id": _str("Message ID to edit"),
            "content": _str("New message content"),
        },
        ["message_id", "content"],
    ),
    "delete_message": _obj(
        {
            "message_id": _str("Message ID to delete"),
            "channel_id": _str("Optional channel ID if not the current channel"),
        },
        ["message_id"],
    ),
    "change_presence": _obj(
        {"status": _str("online | idle | dnd | invisible")},
        ["status"],
    ),
    "set_activity": _obj(
        {
            "text": _str("Activity or custom status text"),
            "type": _str("playing | watching | listening | competing | custom"),
            "elapsed": _str("Optional elapsed time (for custom status)"),
        },
        ["text"],
    ),
    "create_poll": _obj(
        {
            "question": _str("Poll question"),
            "options": _str("Comma-separated options"),
            "duration_hours": _num("Optional poll duration in hours"),
        },
        ["question", "options"],
    ),
    "create_invite": _obj(
        {
            "max_uses": _int("Max uses (default 1)"),
            "max_age": _int("Max age in seconds"),
        }
    ),
    "join_server": _obj(
        {
            "invite": _str(
                "The exact invite the user provided: a full URL "
                "(https://discord.gg/xyz, https://discord.com/invite/xyz) "
                "or the bare code. Never substitute a different invite."
            )
        },
        ["invite"],
    ),
    "server_setup": _obj(
        {
            "server": _str(
                "Server name or numeric ID. Omit to set up the current server."
            ),
            "preferences": _str(
                "Optional steer for which options to take, e.g. "
                "'only AI and coding stuff, no ping roles'"
            ),
            "list_only": _bool(
                "True to list the available roles/channels without picking any"
            ),
        }
    ),
    "leave_server": _obj(
        {"server": _str("Server name or numeric ID to leave")},
        ["server"],
    ),
    "lookup_user": _obj(
        {
            "user_id": _str(
                "Numeric user ID or @mention. Returns bio/about me, banner, accent color, "
                "guild roles/nickname, account creation date, avatar, and voice status."
            )
        },
        ["user_id"],
    ),
    "manage_plugin": _obj(
        {
            "action": _str("Action to perform: 'list', 'enable', 'disable', 'status'"),
            "plugin": _str("Plugin name (e.g. 'checkers')"),
            "user_id": _str("Optional target user ID or @mention (defaults to caller)"),
            "is_global": _bool(
                "Whether to enable/disable plugin globally across all users (admin only)"
            ),
        },
        ["action"],
    ),
    "search_messages": _obj(
        {
            "query": _str("Search query"),
            "limit": _int("Max results (default 5)"),
        },
        ["query"],
    ),
    "set_nickname": _obj(
        {"nickname": _str("New nickname, or 'reset' to clear")},
        ["nickname"],
    ),
    "forward_message": _obj(
        {
            "message_id": _str("Message ID to forward"),
            "channel_id": _str("Destination channel ID"),
        },
        ["message_id", "channel_id"],
    ),
    "typing": _obj({}),
    "list_servers": _obj({}),
    "list_admin_servers": _obj(
        {
            "guild_id": _str("Optional server ID for one-server detail"),
        }
    ),
    "create_category": _obj(
        {
            "name": _str("Category name"),
            "position": _int("Optional position"),
        },
        ["name"],
    ),
    "create_channel": _obj(
        {
            "name": _str("Channel name"),
            "type": _str("text or voice"),
            "kind": _str("Alias for type: text or voice"),
            "category_id": _str("Optional parent category ID"),
            "topic": _str("Optional channel topic"),
        },
        ["name"],
    ),
    "edit_channel": _obj(
        {
            "channel_id": _str("Channel ID"),
            "name": _str("New name"),
            "category_id": _str("New parent category ID"),
            "category_name": _str("New parent category name"),
            "topic": _str("New topic"),
            "slowmode_seconds": _int("Slowmode delay in seconds (0 to disable)"),
            "nsfw": _bool("Whether the channel is NSFW"),
            "position": _int("New position"),
        },
        ["channel_id"],
    ),
    "delete_channel": _obj(
        {
            "channel_id": _str("Channel or category ID"),
            "confirm_name": _str("Exact name confirmation"),
        },
        ["channel_id", "confirm_name"],
    ),
    "kick_member": _obj(
        {
            "user_id": _str("User ID or @mention to kick"),
            "reason": _str("Optional audit-log reason"),
            "guild_id": _str("Optional server ID"),
        },
        ["user_id"],
    ),
    "ban_member": _obj(
        {
            "user_id": _str("User ID or @mention to ban"),
            "reason": _str("Optional audit-log reason"),
            "delete_message_seconds": _str(
                "Optional 0-604800 seconds of messages to delete"
            ),
            "guild_id": _str("Optional server ID"),
        },
        ["user_id"],
    ),
    "unban_member": _obj(
        {
            "user_id": _str("User ID to unban"),
            "reason": _str("Optional audit-log reason"),
            "guild_id": _str("Optional server ID"),
        },
        ["user_id"],
    ),
    "list_bans": _obj(
        {
            "guild_id": _str("Optional server ID"),
            "limit": _int("Max bans to list (default 20)"),
        }
    ),
    "timeout_member": _obj(
        {
            "user_id": _str("User ID or @mention"),
            "duration": _str("e.g. 10m, 1h, 1d; 0/clear to remove"),
            "reason": _str("Optional audit-log reason"),
            "guild_id": _str("Optional server ID"),
        },
        ["user_id", "duration"],
    ),
    "manage_role": _obj(
        {
            "action": _str("list | create | edit | delete | add | remove"),
            "guild_id": _str("Optional server ID"),
            "name": _str("Role name (create/edit/lookup)"),
            "role_id": _str("Role ID"),
            "user_id": _str("Member for add/remove"),
            "color": _str("Optional hex color"),
            "hoist": _bool("Display separately"),
            "mentionable": _bool("Allow @role mentions"),
            "permissions": _str("Comma-separated Discord permission names"),
            "confirm_name": _str("Exact role name required to delete"),
        },
        ["action"],
    ),
    "purge_messages": _obj(
        {
            "limit": _int("How many recent messages to delete (1-100, default 20)"),
            "channel_id": _str("Optional channel ID"),
            "user_id": _str("Optional author filter"),
        }
    ),
    "pin_message": _obj(
        {
            "message_id": _str("Message ID to pin or unpin"),
            "channel_id": _str("Optional channel ID"),
            "unpin": _bool("True to unpin instead of pin"),
        },
        ["message_id"],
    ),
    "set_member_nickname": _obj(
        {
            "user_id": _str("Member to nick"),
            "nickname": _str("New nickname, or reset to clear"),
            "guild_id": _str("Optional server ID"),
        },
        ["user_id", "nickname"],
    ),
    "voice_mod": _obj(
        {
            "action": _str("mute | unmute | deafen | undeafen | move | disconnect"),
            "user_id": _str("Member in voice"),
            "channel_id": _str("Voice channel ID for move"),
            "guild_id": _str("Optional server ID"),
        },
        ["action", "user_id"],
    ),
    "lock_channel": _obj(
        {
            "channel_id": _str("Optional channel ID (defaults to current)"),
            "unlock": _bool("True to unlock"),
        }
    ),
    "set_channel_permissions": _obj(
        {
            "channel_id": _str("Channel ID"),
            "target": _str("Role ID, user ID, or everyone"),
            "allow": _str("Comma pairs like send_messages=false,view_channel=true"),
            "reset": _bool("True to clear that overwrite"),
        },
        ["channel_id", "target"],
    ),
    "edit_server": _obj(
        {
            "name": _str("New server name"),
            "description": _str("New server description"),
            "guild_id": _str("Optional server ID"),
        }
    ),
    "audit_log": _obj(
        {
            "guild_id": _str("Optional server ID"),
            "limit": _int("Entries to read (default 10)"),
        }
    ),
    "manage_emoji": _obj(
        {
            "action": _str("list | create | delete"),
            "name": _str("Emoji name"),
            "url": _str("Public image URL for create"),
            "emoji_id": _str("Emoji ID for delete"),
            "guild_id": _str("Optional server ID"),
        },
        ["action"],
    ),
    "change_avatar": _obj(
        {"url": _str("Direct image URL (jpg/png/gif/webp)")},
        ["url"],
    ),
    "guide": _obj(
        {
            "goal": _str(
                "Short description of what the user wants built (e.g. 'coop neural worm maze with backend sync'). Used as thread title and to tailor the 5 clarifying questions."
            ),
        },
    ),
    "spawn_background": _obj(
        {
            "goal": _str(
                "What the background job should build/do. Required."
            ),
            "context": _str(
                "Extra spec for the job: requirements, style, constraints. Optional."
            ),
        },
        ["goal"],
        additional=False,
    ),
    "web_search": _obj(
        {
            "query": _str("Search query"),
            "max_results": _int("Optional result limit"),
            "engine": _str("Optional search engine hint"),
        },
        ["query"],
    ),
    "send_message": _obj(
        {
            "channel_id": _str(
                "Optional channel ID or DM recipient user ID to send to. If omitted, sends to current channel."
            ),
            "content": _str("Message text (Discord markdown OK)"),
            "reply": _bool(
                "Discord quote-reply (the quoted-parent UI). Default true. "
                "Pass false only for a standalone line with no quote. Keep it "
                "on when the room has moved on, several people are talking, "
                "or you are answering an older line."
            ),
            "reply_to": _str(
                "Optional short quote or who said it, like nah or alice. Not an id."
            ),
            "continue_turn": _bool(
                "Default false: this message is your answer and ends the turn. "
                "true: this message is a short update, not your final answer. It "
                "posts at once, before the other calls in this response, and you "
                "get another response to continue the work."
            ),
        },
        ["content"],
    ),
    # NOTE: no more `explanation_log` tool. Reasoning now rides inside every
    # tool call via the auto-injected `explanation` param (see build_openai_tools
    # above and tool_registry.record_explanation). Plain chat goes through
    # send_message, which itself carries a explanation field.
    "no_response": _obj({}),
    "more_tools": _obj(
        {
            "group": _str(
                "Optional tools to add for the next response turn.",
                enum=sorted(TOOL_DISCOVERY_GROUPS),
            )
        },
        ["group"],
        additional=False,
    ),
    "send_file": _obj(
        {
            "filename": _str("File name with extension"),
            "content": _str("File contents (text or base64)"),
            "encoding": _str("text or base64"),
            "path": _str("Optional existing on-disk path instead of content"),
            "caption": _str(
                "Optional text posted in the same message as the attachment, not separately "
                "(max 2000 characters on Discord)"
            ),
        }
    ),
    "shell": _obj(
        {
            "command": _str(
                "Bash command to run directly inside the bot container. Multiline "
                "scripts are allowed. To write a file: cat << 'EOF' > path/file.py "
                "then the body then a line containing only EOF. Put `> file` on "
                "the opener line, not after EOF."
            ),
            "files": _str("Optional comma-separated files to attach after the command"),
        },
        ["command"],
    ),
    "fetch_url": _obj(
        {
            "url": _str("URL to fetch"),
            "max_length": _int("Optional max characters of returned text"),
        },
        ["url"],
    ),
    "see_image": _obj(
        {
            "url": _str(
                "Image or GIF URL to look at: a direct jpg/png/gif/webp, "
                "a Discord CDN link, or a Tenor/Giphy/imgur GIF page"
            )
        },
        ["url"],
    ),
    "see_video": _obj(
        {
            "url": _str(
                "Direct mp4/webm/mov video URL to inspect with ffmpeg-derived "
                "frames; use youtube for YouTube links"
            )
        },
        ["url"],
    ),
    "youtube": _obj(
        {
            "url": _str(
                "YouTube video, channel, playlist, or search URL. "
                "Handles like @name also work."
            ),
            "query": _str("Optional YouTube search if url is omitted"),
            "limit": _int(
                "Optional max videos for channel/playlist/search (default 15)"
            ),
            "timestamps": _str("Optional comma-separated timestamps for frames"),
            "max_transcript_chars": _int("Optional transcript length cap"),
            "lang": _str("Optional caption language (default en)"),
        },
    ),
    "send_meme": _obj({"subreddit": _str("Optional subreddit name (e.g. me_irl)")}),
    "send_media": _obj(
        {
            "url": _str("Direct media URL to attach"),
            "caption": _str(
                "Optional text posted in the same message as the attachment, not separately "
                "(max 2000 characters on Discord)"
            ),
        },
        ["url"],
    ),
    "tts": _obj(
        {
            "text": _str("Text to speak"),
        },
        ["text"],
    ),
    "inbox_list": _obj({}),
    "inbox_act": _obj(
        {
            "action": _str(
                "accept, decline, dismiss, or read (read demotes a notice "
                "without clearing it)"
            ),
            "item_id": _str("Inbox item id, e.g. friend_123"),
            "user_id": _str("Requester Discord id if item_id is omitted"),
        },
        ["action"],
    ),
    "join_vc": _obj(
        {
            "voice_channel_id": _str(
                "Numeric Discord voice channel id (snowflake, not a planner channel number)"
            ),
            "channel_name": _str("Voice channel name in the current server"),
            "user_id": _str("Join this user's current voice channel"),
        },
    ),
    "vc_status": _obj({}),
    "vc_where": _obj(
        {"user_id": _str("Numeric user ID or @mention")},
        ["user_id"],
    ),
    "leave_vc": _obj({}),
    "wait": _obj(
        {"seconds": _num("Pause this tool batch (default 2, max 10)")},
    ),
    "sleep": _obj(
        {"duration_minutes": _int("Sleep window in minutes (1-60, default 30)")},
    ),
    "clear_sleep": _obj({}),
    "update_base_personality": _obj(
        {"text": _str("New base personality (100-2000 chars)")},
        ["text"],
    ),
    "update_server_prompt": _obj(
        {
            "text": _str("New per-server prompt"),
            "server_id": _str("Optional guild id; defaults to the current server"),
        },
        ["text"],
    ),
    # ---- Chess (Dame Curie plays real chess himself against a chosen opponent) --
    "chess_start": _obj(
        {
            "opponent": _str(
                "Who plays against this bot: a mention, Discord user id, or "
                "display name. Omit to play the person who asked, or the "
                "single @mentioned human in the message."
            ),
            "bot_side": _str(
                "white | black | auto (default white). The side this bot plays. "
                "The opponent gets the other colour."
            ),
        }
    ),
    "chess_move": _obj(
        {
            "move": _str(
                "The move to play, in SAN (e4, Nf3, O-O, exd5, Qh5) or UCI "
                "(e2e4, e7e8q). On the player's turn this is THEIR move. On "
                "this bot's turn this is the move YOU chose - pick it from the "
                "annotated legal-move list in the previous result. There is no "
                "engine playing for you; omitting move on your own turn just "
                "returns the position again."
            ),
        }
    ),
    "chess_state": _obj({}),
    "chess_resign": _obj(
        {
            "side": _str(
                "who resigns: this bot's name | player (optional; default player)"
            ),
        }
    ),
    "usage": _obj({}),
}


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------
# The model had no way to know whether a tool hands its output back. That
# ignorance cost us real turns: it would answer *before* web_search returned
# ("here's what I found: ...") because it assumed the call was fire-and-forget,
# and it would sit waiting for a second turn after `react`/`typing`, which
# never produce one, leaving the channel silent.
#
# These three sets are the single source of truth. build_openai_tools() stamps
# the matching one-line contract onto every tool description, the system prompt
# lists tools grouped by contract, and bot.py imports RESULT_TOOL_NAMES to
# decide whether a batch loops back for another model turn. Add a new tool to
# exactly one set - the prompt, the schema, and the dispatch loop all follow.

# Tools whose output is fed back to the model in a fresh turn.
RESULT_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "image_generator",
        "lookup_user",
        "manage_plugin",
        "search_messages",
        "create_invite",
        "join_server",
        "leave_server",
        "server_setup",
        "create_poll",
        "forward_message",
        "edit_message",
        # change_avatar returns a bare success ack ("Avatar changed
        # successfully"). Without a follow-up turn a model that calls only
        # this leaves the turn silent - the user sees the new avatar and no
        # text at all.
        "change_avatar",
        "list_servers",
        "guide",
        "web_search",
        "fetch_url",
        "see_image",
        "see_video",
        "youtube",
        "shell",
        "list_admin_servers",
        "create_category",
        "create_channel",
        "edit_channel",
        "delete_channel",
        "kick_member",
        "ban_member",
        "unban_member",
        "list_bans",
        "timeout_member",
        "manage_role",
        "purge_messages",
        "pin_message",
        "set_member_nickname",
        "voice_mod",
        "lock_channel",
        "set_channel_permissions",
        "edit_server",
        "audit_log",
        "manage_emoji",
        "send_file",
        "send_meme",
        "send_media",
        "inbox_list",
        "inbox_act",
        "join_vc",
        "vc_status",
        "vc_where",
        "leave_vc",
        # set_activity gets a follow-up so the model can react to its own
        # status change. change_presence deliberately does NOT - that one is
        # the online/idle/dnd dot the user just set, and a follow-up turn
        # would race to undo it.
        "set_activity",
        "update_base_personality",
        "update_server_prompt",
        # more_tools expands the selected group for the following model turn.
        "more_tools",
        # chess + usage return data the model needs a follow-up turn to react to.
        "chess_start",
        "chess_move",
        "chess_state",
        "chess_resign",
        "usage",
        # spawn_background hands the job id back so the live turn can ack it
        # by name, then ends (the detached job delivers the real answer later).
        "spawn_background",
    }
)

# Tools that end the turn outright. Nothing after them runs, and there is no
# follow-up turn unless a RESULT tool shared the same batch.
TURN_ENDING_TOOL_NAMES: frozenset[str] = frozenset(
    {"send_message", "no_response", "sleep"}
)

# Plugin tools that declared ``returns_result = True``. Plugin names cannot live
# in the static set above - they are discovered at import time - and without
# this every plugin tool got the "returns nothing" contract, so the dispatch
# loop ended the turn and the plugin's output was never read by the model.
# Populated by PluginManager on load.
_PLUGIN_RESULT_TOOL_NAMES: set[str] = set()


def set_plugin_result_tools(names: set[str] | frozenset[str] | None) -> None:
    """Register which plugin tools hand their output back to the model."""
    _PLUGIN_RESULT_TOOL_NAMES.clear()
    for name in names or ():
        text = str(name or "").strip()
        if text:
            _PLUGIN_RESULT_TOOL_NAMES.add(text)


def returns_result(name: str) -> bool:
    """Whether ``name`` hands its output back for a follow-up turn."""
    return name in RESULT_TOOL_NAMES or name in _PLUGIN_RESULT_TOOL_NAMES


# One line per contract class, appended to the tool's description so the model
# reads it in the same place it reads the parameters. Kept short on purpose -
# this text is paid for on every single request, for every single tool.
_CONTRACT_RESULT = " [returns output]"
_CONTRACT_ENDING = " [ends the turn]"
_CONTRACT_SILENT = " [returns nothing]"


def result_contract(name: str) -> str:
    """The one-line result contract appended to `name`'s description."""
    if returns_result(name):
        return (
            " [returns saved image by default; auto_send=true + __IMAGE_SENT__ means already delivered, no repeat]"
            if name == "image_generator" else _CONTRACT_RESULT
        )
    if name == "send_message":
        return " [ends the turn; with continue_turn=true it is an update and the turn continues]"
    if name in TURN_ENDING_TOOL_NAMES:
        return _CONTRACT_ENDING
    return _CONTRACT_SILENT


def contract_groups(names: list[str]) -> dict[str, list[str]]:
    """Split `names` into the three contract buckets, order preserved."""
    groups: dict[str, list[str]] = {"result": [], "ending": [], "silent": []}
    for name in names:
        if returns_result(name):
            groups["result"].append(name)
        elif name in TURN_ENDING_TOOL_NAMES:
            groups["ending"].append(name)
        else:
            groups["silent"].append(name)
    return groups


# Each tool gets the `explanation` argument. It gives the reason for the call
# in one sentence. It is not the model's reasoning channel. Do not name it
# `reasoning`: that name made models write <reasoning> tags into content.
# See tool_registry.py.
EXPLANATION_PARAM: dict[str, Any] = {
    "type": "string",
    "description": (
        "The reason for this call. One sentence, plain text. The user sees it as a progress line."
    ),
}


def build_openai_tools(
    tools: dict[str, Any],
    *,
    allowed_names: set[str] | None = None,
    disabled_names: set[str] | None = None,
    max_description_chars: int = 1024,
) -> list[dict[str, Any]]:
    """Build OpenAI ``tools`` payload from live tool instances.

    Every tool gets an auto-injected `explanation` parameter on top of whatever
    it declared in TOOL_PARAMETERS. The explanation lives INSIDE the tool call now -
    there is no standalone explanation_log tool anymore. If you add a new tool,
    you do nothing special: it gets explanation for free. Stop forgetting.

    Every description also gets its result contract appended (see
    result_contract) so the model knows, per tool, whether the output comes
    back to it. The contract is added AFTER the description is truncated, so
    a long description can never eat the part that changes the model's plan.
    """
    try:
        max_description_chars = max(1, int(max_description_chars))
    except (TypeError, ValueError, OverflowError):
        max_description_chars = 1024
    disabled = disabled_names or set()
    out: list[dict[str, Any]] = []
    for name, tool in tools.items():
        if name in disabled:
            continue
        if allowed_names is not None and name not in allowed_names:
            continue
        try:
            desc = str(tool.get_description() or "").strip()
        except Exception:
            desc = name
        if len(desc) > max_description_chars:
            desc = desc[: max_description_chars - 1] + "…"
        desc = (desc or name) + result_contract(name)
        declared = TOOL_PARAMETERS.get(name)
        if declared is None:
            # Drop-in plugins are discovered at runtime, so their schemas
            # cannot live in this module's static registry. Let a plugin
            # provide the same get_parameters() contract as built-in tools;
            # otherwise retain a permissive empty object for legacy plugins.
            getter = getattr(tool, "get_parameters", None)
            try:
                declared = getter() if callable(getter) else None
            except Exception:
                declared = None
        if not isinstance(declared, dict) or declared.get("type") != "object":
            declared = {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }
        params = dict(declared)
        raw_props = params.get("properties")
        props = dict(raw_props) if isinstance(raw_props, dict) else {}
        # `explanation` is the first property and the first required name.
        # The prompt tells the model to write it first; the schema must agree.
        props = {"explanation": props.pop("explanation", EXPLANATION_PARAM), **props}
        params["properties"] = props
        # explanation is ALWAYS required - no exceptions, no "terse on a trivial
        # call" carve-out. If the model thinks before it acts, we want the
        # trace. If it skips explanation, the provider rejects the call instead
        # of silently dropping it (which is what bit us before).
        raw_required = params.get("required")
        required = (
            [r for r in raw_required if isinstance(r, str) and r != "explanation"]
            if isinstance(raw_required, (list, tuple))
            else []
        )
        params["required"] = ["explanation", *required]
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
        )
    return out


_NATIVE_MAX_CALLS = 10
_NATIVE_MAX_ID_BYTES = 128
_NATIVE_MAX_NAME_BYTES = 128
_NATIVE_MAX_ARGUMENT_BYTES = 16_000
_NATIVE_MAX_BATCH_ARGUMENT_BYTES = 32_000
_NATIVE_MAX_BATCH_ENVELOPE_BYTES = 40_000
_NATIVE_MAX_ARGUMENT_DEPTH = 32


_NATIVE_MAX_ARGUMENT_DECODES = 3
_MALFORMED = "Malformed native tool-call batch"
_OVERSIZED = "Oversized native tool-call batch"


def _native_argument_depth_problem(text: str) -> str:
    """Why JSON text is unbalanced or too deep; "" when it is neither."""
    depth = 0
    quoted = escaped = False
    for position, character in enumerate(text):
        if quoted and escaped:
            escaped = False
        elif quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character in "{[":
            depth += 1
            if depth > _NATIVE_MAX_ARGUMENT_DEPTH:
                return f"nest deeper than {_NATIVE_MAX_ARGUMENT_DEPTH} levels"
        elif not quoted and character in "}]":
            depth -= 1
            if depth < 0:
                return f"close an unopened bracket at character {position} (from 0)"
    if quoted:
        return "end inside a string"
    if depth:
        return f"leave {depth} open bracket{'s' if depth > 1 else ''}"
    return ""


def _native_argument_value_problem(value: dict) -> str:
    """Why an argument object is not plain JSON; "" when it is."""
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            if any(not isinstance(key, str) for key in current):
                return "hold a non-string key"
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
        elif isinstance(current, float) and not math.isfinite(current):
            return "hold a non-finite number"
    return ""


def _utf8_size(text: str, place: str, part: str = "the arguments") -> int:
    """UTF-8 byte size of call text; a lone surrogate is a malformed call."""
    try:
        return len(text.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ValueError(
            f"{_MALFORMED}: {place}: character {error.start} (from 0) of "
            f"{part} is not valid UTF-8"
        ) from None


def _parse_native_argument_json(
    text: str, decoder: json.JSONDecoder, place: str
) -> object:
    """Parse one complete nesting-bounded JSON argument value."""
    problem = (
        _native_argument_depth_problem(text) if text[:1] in {"{", "[", '"'} else ""
    )
    if problem:
        raise ValueError(f"{_MALFORMED}: {place}: the arguments {problem}")
    try:
        parsed, end = decoder.raw_decode(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{_MALFORMED}: {place}: the arguments are not valid JSON: "
            f"{error.msg} at character {error.pos} of the decoded text (from 0)"
        ) from None
    if text[end:].strip():
        raise ValueError(
            f"{_MALFORMED}: {place}: the arguments have text after the JSON "
            f"value, from character {end} of the decoded text (from 0)"
        )
    return parsed


def _decode_native_tool_arguments(
    raw_args: object, place: str, *, allow_oversized: bool = False
) -> tuple[dict[str, object], int, bool]:
    """Strictly decode one JSON-object argument payload within its mode's bound."""
    if raw_args is None:
        return {}, 0, False
    if isinstance(raw_args, dict):
        problem = _native_argument_value_problem(raw_args)
        if problem:
            raise ValueError(f"{_MALFORMED}: {place}: the arguments {problem}")
        encoded = json.dumps(
            raw_args, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        argument_bytes = _utf8_size(encoded, place)
        current = raw_args
    elif isinstance(raw_args, str):
        argument_bytes = _utf8_size(raw_args, place)
        current = raw_args.strip().lstrip("\ufeff")
    else:
        raise ValueError(
            f"{_MALFORMED}: {place}: the arguments have type "
            f"{type(raw_args).__name__}, not a JSON object or string"
        )
    oversized = argument_bytes > _NATIVE_MAX_ARGUMENT_BYTES
    if oversized and not allow_oversized:
        raise ValueError(
            f"{_OVERSIZED}: {place}: the arguments are {argument_bytes:,} bytes; "
            f"the limit is {_NATIVE_MAX_ARGUMENT_BYTES:,}"
        )
    if isinstance(raw_args, dict):
        problem = _native_argument_depth_problem(encoded)
        if problem:
            raise ValueError(f"{_MALFORMED}: {place}: the arguments {problem}")
    if isinstance(current, str) and not current:
        return {}, argument_bytes, oversized

    decoder = json.JSONDecoder()
    # Up to 3 decode or unwrap steps, then one more pass checks the object.
    for _ in range(_NATIVE_MAX_ARGUMENT_DECODES + 1):
        if isinstance(current, str):
            current = _parse_native_argument_json(current, decoder, place)
            continue
        if not isinstance(current, dict):
            raise ValueError(
                f"{_MALFORMED}: {place}: the arguments decode to type "
                f"{type(current).__name__}, not a JSON object"
            )
        wrapper = next(
            (
                key
                for key in ("arguments", "parameters")
                if len(current) == 1 and key in current and isinstance(current[key], (dict, str))
            ),
            None,
        )
        if wrapper is not None:
            current = current[wrapper]
            continue
        problem = _native_argument_value_problem(current)
        if problem:
            raise ValueError(f"{_MALFORMED}: {place}: the arguments {problem}")
        return dict(current), argument_bytes, oversized
    if not isinstance(current, (dict, str)):
        raise ValueError(
            f"{_MALFORMED}: {place}: the arguments decode to type "
            f"{type(current).__name__}, not a JSON object"
        )
    raise ValueError(
        f"{_MALFORMED}: {place}: the arguments need more than "
        f"{_NATIVE_MAX_ARGUMENT_DECODES} decode or unwrap steps"
    )


def normalize_native_tool_calls(
    raw_calls: list | None, *, allow_oversized_arguments: bool = False
) -> list[dict[str, Any]]:
    """Validate and normalize a complete provider tool-call batch."""
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list):
        raise ValueError(
            f"{_MALFORMED}: tool_calls has type {type(raw_calls).__name__}, "
            "not list"
        )
    if len(raw_calls) > _NATIVE_MAX_CALLS and not allow_oversized_arguments:
        raise ValueError(
            f"{_OVERSIZED}: the response has {len(raw_calls)} calls; the limit is "
            f"{_NATIVE_MAX_CALLS}"
        )
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    batch_argument_bytes = 0
    batch_envelope_bytes = 0
    for i, call in enumerate(raw_calls):
        place = f"call {i + 1} of {len(raw_calls)}"
        if not isinstance(call, dict) or call.get("type") not in (None, "function"):
            raise ValueError(f"{_MALFORMED}: {place} is not a function call")
        fn_value = call.get("function")
        if fn_value is not None and not isinstance(fn_value, dict):
            raise ValueError(f"{_MALFORMED}: the function of {place} is not an object")
        fn = fn_value if isinstance(fn_value, dict) else {}
        raw_name = fn.get("name")
        if raw_name is None or raw_name == "":
            raw_name = call.get("name")
        if raw_name is not None and not isinstance(raw_name, str):
            raise ValueError(
                f"{_MALFORMED}: the name of {place} has type "
                f"{type(raw_name).__name__}, not str"
            )
        if not raw_name or not raw_name.strip():
            raise ValueError(f"{_MALFORMED}: {place} has no function name")
        if _utf8_size(raw_name, place, "the name") > _NATIVE_MAX_NAME_BYTES:
            raise ValueError(
                f"{_OVERSIZED}: the name of {place} is longer than "
                f"{_NATIVE_MAX_NAME_BYTES} bytes"
            )
        original_name = raw_name.strip()
        name = original_name[5:] if original_name.lower().startswith("tool_") else original_name
        if not name:
            raise ValueError(
                f"{_MALFORMED}: the name of {place} is only the prefix tool_"
            )
        place = f"{place} ({original_name!r})"
        raw_args = fn.get("arguments", call.get("arguments", {}))
        args, argument_bytes, oversized_arguments = _decode_native_tool_arguments(
            raw_args, place, allow_oversized=allow_oversized_arguments
        )
        batch_argument_bytes += argument_bytes
        if (
            batch_argument_bytes > _NATIVE_MAX_BATCH_ARGUMENT_BYTES
            and not allow_oversized_arguments
        ):
            raise ValueError(
                f"{_OVERSIZED}: the batch reaches {batch_argument_bytes:,} bytes of "
                f"arguments at {place}; the limit is "
                f"{_NATIVE_MAX_BATCH_ARGUMENT_BYTES:,}"
            )
        raw_id = call.get("id")
        if raw_id in (None, ""):
            call_id = f"call_{i}"
        elif isinstance(raw_id, str):
            call_id = raw_id
        else:
            raise ValueError(
                f"{_MALFORMED}: the id of {place} has type "
                f"{type(raw_id).__name__}, not str"
            )
        if not call_id.strip():
            raise ValueError(f"{_MALFORMED}: the id of {place} is blank")
        if _utf8_size(call_id, place, "the id") > _NATIVE_MAX_ID_BYTES:
            raise ValueError(
                f"{_OVERSIZED}: the id of {place} is longer than "
                f"{_NATIVE_MAX_ID_BYTES} bytes"
            )
        if call_id in seen_ids:
            raise ValueError(f"{_MALFORMED}: {place} repeats the id {call_id!r}")
        seen_ids.add(call_id)
        batch_envelope_bytes += _utf8_size(
            json.dumps(call, ensure_ascii=False, separators=(",", ":")),
            place,
            "the call envelope",
        )
        if (
            batch_envelope_bytes > _NATIVE_MAX_BATCH_ENVELOPE_BYTES
            and not allow_oversized_arguments
        ):
            raise ValueError(
                f"{_OVERSIZED}: the batch envelope reaches {batch_envelope_bytes:,} "
                f"bytes at {place}; the limit is {_NATIVE_MAX_BATCH_ENVELOPE_BYTES:,}"
            )
        normalized.append(
            {
                "id": call_id,
                "name": name,
                "raw_name": original_name,
                "arguments": args if not oversized_arguments else {},
                "oversized_arguments": oversized_arguments,
                "raw": call if not oversized_arguments else None,
            }
        )
    batch_limit_error = ""
    if len(raw_calls) > _NATIVE_MAX_CALLS:
        batch_limit_error = (
            f"the response has {len(raw_calls)} calls; the limit is {_NATIVE_MAX_CALLS}"
        )
    elif batch_argument_bytes > _NATIVE_MAX_BATCH_ARGUMENT_BYTES:
        batch_limit_error = (
            f"the batch carries {batch_argument_bytes:,} bytes of arguments; "
            f"the limit is {_NATIVE_MAX_BATCH_ARGUMENT_BYTES:,}"
        )
    elif batch_envelope_bytes > _NATIVE_MAX_BATCH_ENVELOPE_BYTES:
        batch_limit_error = (
            f"the batch envelope is {batch_envelope_bytes:,} bytes; "
            f"the limit is {_NATIVE_MAX_BATCH_ENVELOPE_BYTES:,}"
        )
    for entry in normalized:
        entry["batch_limit_error"] = batch_limit_error
    return normalized


# ── tool-loop transcript bounds ──────────────────────────────────────────
# Every agent loop in this repo replays the
# whole assistant/tool transcript on every round, so an unbounded tail is how a
# turn walks off the end of the context window mid-loop. Per-result truncation
# is not enough on its own: 24 rounds of a 32k-capped result is still ~768k
# chars riding on top of an already-full prompt.
# The tail has its own allowance in the prompt budget (bot._apply_prompt_budget),
# so a tool turn keeps about 20 single-call rounds without growing chat prompts.
TOOL_TAIL_MAX_MESSAGES = 42
TOOL_TAIL_MAX_CHARS = 96_000
TOOL_TAIL_NEWEST_GROUP_CHARS = 24_000
TOOL_RESULT_COMPACT_CHARS = 8_000
_HISTORY_MARKER_RE = re.compile(
    r"\n… \[(\d+) chars truncated from (?:earlier tool result|tool result|tool history)\]$"
)


def message_chars(message: dict) -> int:
    """Prompt size of one chat message, tool_calls included.

    An assistant turn replayed in a tool loop carries its arguments (a
    file body, a shell script, a long send_message) and those are real
    prompt tokens - counting only ``content`` leaves a budget blind to the
    heaviest messages in the conversation.
    """
    extra = len(str(message.get("tool_call_id") or ""))
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        extra += len(str(call.get("id") or ""))
        fn = call.get("function")
        if isinstance(fn, dict):
            extra += len(str(fn.get("name") or "")) + len(
                str(fn.get("arguments") or "")
            )
    content = message.get("content", "")
    if isinstance(content, str):
        return len(content) + extra
    if isinstance(content, list):
        return (
            sum(
                len(str(part.get("text", "")))
                for part in content
                if isinstance(part, dict)
            )
            + extra
        )
    return len(str(content or "")) + extra


def tool_tail_groups(tail: list[dict]) -> list[list[dict]]:
    """Group complete native batches and assistant/synthetic-user result pairs.

    Reject orphan or mismatched native results rather than replaying a broken
    assistant/tool sequence or silently trimming half of a batch.
    """
    groups: list[list[dict]] = []
    for msg in tail:
        role = msg.get("role")
        if role == "tool":
            if not groups or not groups[-1][0].get("tool_calls"):
                raise ValueError("Orphan tool result in tool history")
            groups[-1].append(msg)
        elif (
            role == "user"
            and groups
            and groups[-1][0].get("role") == "assistant"
            and len(groups[-1]) == 1
            and str(msg.get("content") or "").startswith("=== TOOL RESULTS ===\n")
        ):
            groups[-1].append(msg)
        else:
            groups.append([msg])
    for group in groups:
        calls = group[0].get("tool_calls") or []
        if not calls:
            continue
        ids = [str(call.get("id") or "") for call in calls]
        results = [str(msg.get("tool_call_id") or "") for msg in group[1:]]
        if not all(ids) or len(set(ids)) != len(ids) or sorted(ids) != sorted(results):
            raise ValueError("Incomplete or mismatched native tool-call batch")
    return groups


def _truncate_history_text(content: str, limit: int, label: str) -> str:
    """Shorten a replay string without inventing new omission counts on retries."""
    if len(content) <= limit:
        return content
    match = _HISTORY_MARKER_RE.search(content)
    body = content[: match.start()] if match else content
    omitted = int(match.group(1)) if match else 0
    retained = min(len(body), limit)
    while retained:
        missing = omitted + len(body) - retained
        marker = f"\n… [{missing} chars truncated from {label}]"
        if retained + len(marker) <= limit:
            return body[:retained] + marker
        retained -= max(1, retained + len(marker) - limit)
    marker = f"\n… [{omitted + len(body)} chars truncated from {label}]"
    return marker if len(marker) <= limit else "…"[:limit]


def _fit_tool_group(group: list[dict], limit: int) -> None:
    """Share one strict char allowance across every result in a batch."""
    for msg in group:
        calls = msg.get("tool_calls") or []
        if calls:
            msg["tool_calls"] = elide_tool_calls_for_history(
                calls, max_args_chars=max(160, 4_000 // len(calls))
            )
    fixed = sum(message_chars(msg) for msg in group)
    contents = [msg for msg in group if isinstance(msg.get("content"), str)]
    fixed -= sum(len(msg["content"]) for msg in contents)
    if fixed > limit:
        raise ValueError("Tool-call IDs, names, or arguments exceed history budget")
    available = limit - fixed
    if sum(len(msg["content"]) for msg in contents) <= available:
        return
    low, high = 0, max(len(msg["content"]) for msg in contents)
    while low < high:
        mid = (low + high + 1) // 2
        if sum(min(len(msg["content"]), mid) for msg in contents) <= available:
            low = mid
        else:
            high = mid - 1
    for msg in contents:
        label = "tool result" if msg.get("role") == "tool" else "tool history"
        msg["content"] = _truncate_history_text(msg["content"], low, label)


_DROPPED_ROUNDS_RE = re.compile(
    r"\[Earlier in this turn (\d+) tool round\(s\) were dropped from context: ([^\]]*)\. "
    r"Their results are no longer visible\.\]\n"
)


def _round_marker_message(group: list[dict]) -> dict | None:
    """Return the first harness-written message of a group: a tool result."""
    return next((msg for msg in group if msg.get("role") in {"tool", "user"}), None)


_TEXT_RESULTS_HEADER = "=== TOOL RESULTS ===\n"


def _results_header(content: str) -> str:
    """The text-protocol header that must stay first so the group is recognised."""
    return _TEXT_RESULTS_HEADER if content.startswith(_TEXT_RESULTS_HEADER) else ""


def _take_dropped_marker(group: list[dict]) -> tuple[int, list[str], bool]:
    """Remove the dropped-rounds marker; return its round count, names and "and others"."""
    msg = _round_marker_message(group)
    content = msg.get("content") if msg else None
    if not isinstance(content, str):
        return 0, [], False
    header = _results_header(content)
    match = _DROPPED_ROUNDS_RE.match(content, len(header))
    if not match:
        return 0, [], False
    msg["content"] = header + content[match.end():]
    names = [name for name in match.group(2).split(", ") if name]
    others = "and others" in names
    return int(match.group(1)), [name for name in names if name != "and others"], others


def _round_tool_names(group: list[dict]) -> list[str]:
    calls = group[0].get("tool_calls") or [] if group else []
    names = [
        re.sub(r"[^A-Za-z0-9_.-]", "_", str((call.get("function") or {}).get("name") or "tool"))[:40]
        for call in calls
    ]
    return names or ["text tool round"]


def trim_tool_tail(
    tail: list[dict],
    *,
    max_messages: int = TOOL_TAIL_MAX_MESSAGES,
    max_chars: int = TOOL_TAIL_MAX_CHARS,
) -> list[dict]:
    """Compact before evicting; retain only complete groups under both caps.

    The newest whole batch receives at most 24k of the total 36k chars.
    Batches with more messages than the count cap or immutable overhead beyond
    the char cap must be rejected by the caller before executing their tools.
    """
    groups = tool_tail_groups(tail)
    dropped_groups = 0
    dropped_chars = 0
    marker_rounds, marker_names, marker_others = _take_dropped_marker(groups[0]) if groups else (0, [], False)
    while len(groups) > 1 and sum(map(len, groups)) > max_messages:
        dropped = groups.pop(0)
        dropped_chars += sum(message_chars(msg) for msg in dropped)
        dropped_groups += 1
        marker_names += _round_tool_names(dropped)
    if not groups:
        return []
    if len(groups[-1]) > max_messages:
        raise ValueError("Newest tool-call batch exceeds history message cap")
    _compact_old_tool_results(groups)
    group_limit = min(TOOL_TAIL_NEWEST_GROUP_CHARS, max_chars)
    _fit_tool_group(groups[-1], group_limit)
    for group in groups[:-1]:
        _fit_tool_group(group, group_limit)
    used = sum(message_chars(msg) for group in groups for msg in group)
    while len(groups) > 1 and used > max_chars:
        room = max_chars - sum(
            message_chars(msg) for group in groups[:-1] for msg in group
        )
        if room >= min(16_000, group_limit):
            _fit_tool_group(groups[-1], room)
            used = sum(message_chars(msg) for group in groups for msg in group)
            if used <= max_chars:
                break
        dropped = groups.pop(0)
        dropped_groups += 1
        dropped_chars += sum(message_chars(msg) for msg in dropped)
        marker_names += _round_tool_names(dropped)
        used -= sum(message_chars(msg) for msg in dropped)
    if dropped_groups:
        logger.info(
            "Tool history dropped %d older round(s), %d chars, to fit %d messages and %d chars",
            dropped_groups, dropped_chars, max_messages, max_chars,
        )
    marker_rounds += dropped_groups
    target = _round_marker_message(groups[0]) if marker_rounds else None
    if marker_rounds and (target is None or not isinstance(target.get("content"), str)):
        raise ValueError(
            f"Tool history dropped {marker_rounds} round(s), but the oldest kept group "
            "has no text tool result to carry the dropped-rounds marker"
        )
    if target is not None:
        names = list(dict.fromkeys(marker_names))
        # Names past the first 8 are not kept, so no count of them is claimed.
        others = marker_others or len(names) > 8
        names = names[:8] + (["and others"] if others else [])
        header = _results_header(target["content"])
        target["content"] = (
            header
            + f"[Earlier in this turn {marker_rounds} tool round(s) were dropped from context: "
            f"{', '.join(names)}. Their results are no longer visible.]\n"
            + target["content"][len(header):]
        )
    return [msg for group in groups for msg in group]


def _compact_old_tool_results(groups: list[list[dict]]) -> None:
    """Compact all older replay text before considering whole-group eviction."""
    for group in groups[:-1]:
        for msg in group:
            content = msg.get("content")
            if isinstance(content, str):
                label = (
                    "earlier tool result" if msg.get("role") == "tool" else "tool history"
                )
                msg["content"] = _truncate_history_text(
                    content, TOOL_RESULT_COMPACT_CHARS, label
                )


def elide_tool_calls_for_history(
    tool_calls: list[dict],
    *,
    max_chars: int = 2000,
    max_args_chars: int = 4000,
) -> list[dict]:
    """Copy calls with bounded public arguments; never edit executable calls."""
    import copy
    import json

    out = copy.deepcopy(tool_calls or [])
    for call in out:
        fn = call.get("function")
        if not isinstance(fn, dict):
            continue
        raw_args = fn.get("arguments")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args.strip() or "{}")
            except json.JSONDecodeError:
                fn["arguments"] = json.dumps({"_elided": f"[malformed arguments omitted, {len(raw_args)} chars]"})
                continue
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            continue
        if not isinstance(args, dict):
            fn["arguments"] = json.dumps({"_elided": f"[non-object arguments omitted, {len(str(raw_args))} chars]"})
            continue
        original_chars = len(raw_args) if isinstance(raw_args, str) else len(json.dumps(raw_args, ensure_ascii=False))
        changed = False
        for key, value in args.items():
            limit = 300 if key == "explanation" else max_chars
            if isinstance(value, str) and len(value) > limit:
                if key == "explanation":
                    marker = f"… [{len(value)} chars total; explanation shortened]"
                    args[key] = value[: limit - len(marker)] + marker
                else:
                    args[key] = f"[large {key} omitted, {len(value)} chars]"
                changed = True
        encoded = json.dumps(args, ensure_ascii=False)
        if len(encoded) > max_args_chars:
            fn["arguments"] = json.dumps(
                {"_elided": f"[large arguments omitted, {original_chars} chars]"}
            )
        elif changed or isinstance(raw_args, dict) or not raw_args.strip() or len(raw_args) > max_args_chars:
            fn["arguments"] = encoded
    return out
