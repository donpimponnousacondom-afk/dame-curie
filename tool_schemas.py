"""OpenAI-compatible tool schemas for Dame Curie native function calling.

Each entry maps a tool name to a JSON Schema ``parameters`` object. Descriptions
come from the live tool instances at request time so they stay in sync with
``get_description()``.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


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


# parameter schemas only — descriptions are attached from tool.get_description()
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
                "What to generate, or — with input images — the change to make"
            ),
            "image": _str(
                "Optional image URL, data URI, or local path Dame Curie wrote; for several, pass a "
                "JSON list or comma-separated refs (max 4). Omit to use message attachments. "
                "Pass an empty string or empty JSON list to generate from scratch without attachments."
            ),
            "model": _str(
                "Optional exact configured model ID; defaults to IMAGE_GEN_MODEL."
            ),
            "quality": _str(
                "Optional quality override; defaults to IMAGE_GEN_QUALITY."
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
            "provider": _str(
                "Trusted configured provider profile; aux/autonomy require their own endpoint and model. Defaults to main.",
                enum=["main", "autonomy", "aux"], default="main",
            ),
            "model": _str(
                "Optional primary-model override; configured fallback models remain unchanged and may answer instead. No endpoint or credentials.",
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
        },
        ["content"],
    ),
    # NOTE: no more `reasoning_log` tool. Reasoning now rides inside every
    # tool call via the auto-injected `reasoning` param (see build_openai_tools
    # above and tool_registry.record_reasoning). Plain chat goes through
    # send_message, which itself carries a reasoning field.
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
            "language": _str("Language name or code (e.g. english, spanish)"),
            "voice": _str(
                "TTS voice name (tiktok, mommy, or espanol/spanish). Omit for the default voice."
            ),
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
                "this bot's turn this is the move YOU chose — pick it from the "
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
# exactly one set — the prompt, the schema, and the dispatch loop all follow.

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
        # this leaves the turn silent — the user sees the new avatar and no
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
        # status change. change_presence deliberately does NOT — that one is
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
# in the static set above — they are discovered at import time — and without
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
# reads it in the same place it reads the parameters. Kept short on purpose —
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


# The reasoning parameter is stamped onto EVERY tool so the model does its
# real reasoning *inside the tool call it wants to use* instead of a separate,
# pointless `reasoning_log` tool. Same shape everywhere — see tool_registry.py.
REASONING_PARAM: dict[str, Any] = {
    "type": "string",
    "description": (
        "Why this call, one sentence, first argument. Plain text only."
    ),
}


def _image_generator_properties(
    tool: object, properties: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    """Copy the image model and quality fields with live configuration values."""
    cfg = getattr(getattr(tool, "bot", None), "config", None)
    model_map = getattr(cfg, "IMAGE_GEN_MODELS", {}) or {}
    default_model = getattr(cfg, "IMAGE_GEN_MODEL", "")
    model_property = dict(properties["model"])
    if isinstance(model_map, dict) and model_map:
        model_property["enum"] = list(model_map)
        model_property["description"] = (
            "Select an exact configured model ID. Omit to use IMAGE_GEN_MODEL. "
            "Configured models and operator descriptions:\n"
            + "\n".join(
                f"- {model_id}: {description}"
                for model_id, description in model_map.items()
            )
        )
        if default_model in model_map:
            model_property["default"] = default_model
    else:
        model_property["description"] = (
            "No image models are configured; set IMAGE_GEN_MODELS and IMAGE_GEN_MODEL."
        )
    properties["model"] = model_property
    quality_property = dict(properties["quality"])
    quality_property["default"] = getattr(cfg, "IMAGE_GEN_QUALITY", "low")
    properties["quality"] = quality_property
    return properties


def build_openai_tools(
    tools: dict[str, Any],
    *,
    allowed_names: set[str] | None = None,
    disabled_names: set[str] | None = None,
    max_description_chars: int = 1024,
) -> list[dict[str, Any]]:
    """Build OpenAI ``tools`` payload from live tool instances.

    Every tool gets an auto-injected `reasoning` parameter on top of whatever
    it declared in TOOL_PARAMETERS. Reasoning lives INSIDE the tool call now —
    there is no standalone reasoning_log tool anymore. If you add a new tool,
    you do nothing special: it gets reasoning for free. Stop forgetting.

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
        # Extend a per-call copy so dynamic model choices never mutate TOOL_PARAMETERS.
        raw_props = params.get("properties")
        props = dict(raw_props) if isinstance(raw_props, dict) else {}
        if name == "image_generator":
            props = _image_generator_properties(tool, props)
        props.setdefault("reasoning", REASONING_PARAM)
        params["properties"] = props
        # reasoning is ALWAYS required — no exceptions, no "terse on a trivial
        # call" carve-out. If the model thinks before it acts, we want the
        # trace. If it skips reasoning, the provider rejects the call instead
        # of silently dropping it (which is what bit us before).
        raw_required = params.get("required")
        required = (
            [r for r in raw_required if isinstance(r, str) and r != "reasoning"]
            if isinstance(raw_required, (list, tuple))
            else []
        )
        if "reasoning" not in required:
            required.append("reasoning")
        params["required"] = required
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


def _decode_tool_arguments(raw_args: Any) -> dict[str, Any]:
    """Decode the argument shapes used by OpenAI-compatible providers.

    Providers are not consistent here: most send a JSON object string, some
    send an object directly, and a few double-encode the object or append
    harmless trailing markup. Keep that tolerance in one place so every
    native tool call reaches dispatch with the same ``dict`` shape.
    """
    import json

    if isinstance(raw_args, dict):
        return dict(raw_args)
    if not isinstance(raw_args, str):
        return {}

    text = raw_args.strip().lstrip("\ufeff")
    if not text:
        return {}

    # Unwrap at most two layers. This handles both:
    #   arguments='{"content":"hi"}'
    #   arguments='"{\\"content\\": \\"hi\\"}"'
    # and provider wrappers such as {"arguments": {...}}.
    current: Any = text
    parsed_json = False
    for _ in range(3):
        if isinstance(current, dict):
            if len(current) == 1:
                for wrapper in ("arguments", "parameters"):
                    if wrapper in current and isinstance(current[wrapper], (dict, str)):
                        current = current[wrapper]
                        break
                else:
                    return dict(current)
            else:
                return dict(current)
            continue
        if not isinstance(current, str):
            return {"_": current} if parsed_json else {}
        candidate = current.strip()
        try:
            current = json.loads(candidate)
            parsed_json = True
            continue
        except (json.JSONDecodeError, TypeError, ValueError):
            # raw_decode accepts a valid JSON object followed by provider
            # garbage, which has appeared in a few OpenAI-compatible streams.
            try:
                current, _end = json.JSONDecoder().raw_decode(candidate)
                parsed_json = True
                continue
            except (json.JSONDecodeError, TypeError, ValueError):
                break

    if isinstance(current, dict):
        return dict(current)
    if parsed_json:
        # Preserve the previous compatibility shape for valid JSON scalars.
        return {"_": current}

    # Last-resort compatibility for providers that emit a simple
    # ``key=value`` string instead of JSON. This is intentionally limited to
    # the old fallback behavior; it is never used for valid JSON.
    args: dict[str, Any] = {}
    for part in text.split():
        if "=" in part:
            key, value = part.split("=", 1)
            args[key.strip()] = value.strip().strip("\"'")
    if args:
        return args
    return {"content": text}


_NATIVE_MAX_CALLS = 8
_NATIVE_MAX_ID_BYTES = 128
_NATIVE_MAX_NAME_BYTES = 128
_NATIVE_MAX_ARGUMENT_BYTES = 16_000
_NATIVE_MAX_BATCH_ARGUMENT_BYTES = 32_000
_NATIVE_MAX_BATCH_ENVELOPE_BYTES = 40_000
_NATIVE_MAX_ARGUMENT_DEPTH = 32


def _native_argument_depth_is_bounded(text: str) -> bool:
    """Reject malformed or over-nested JSON before decoding."""
    depth = 0
    quoted = escaped = False
    for character in text:
        if quoted and escaped:
            escaped = False
        elif quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character in "{[":
            depth += 1
            if depth > _NATIVE_MAX_ARGUMENT_DEPTH:
                return False
        elif not quoted and character in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quoted


def _native_argument_values_are_json_safe(value: dict) -> bool:
    """Reject non-string keys and non-finite numbers in argument objects."""
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            if any(not isinstance(key, str) for key in current):
                return False
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
        elif isinstance(current, float) and not math.isfinite(current):
            return False
    return True


def _parse_native_argument_json(
    text: str, decoder: json.JSONDecoder
) -> object:
    """Parse one complete nesting-bounded JSON argument value."""
    if text[:1] in {"{", "[", '"'} and not _native_argument_depth_is_bounded(
        text
    ):
        raise ValueError("Malformed or oversized native tool-call batch")
    try:
        parsed, end = decoder.raw_decode(text)
    except json.JSONDecodeError:
        raise ValueError("Malformed native tool-call batch") from None
    if text[end:].strip():
        raise ValueError("Malformed native tool-call batch")
    return parsed


def _decode_native_tool_arguments(raw_args: object) -> tuple[dict[str, object], int]:
    """Strictly decode one bounded JSON-object argument payload."""
    if raw_args is None:
        return {}, 0
    if isinstance(raw_args, dict):
        if not _native_argument_values_are_json_safe(raw_args):
            raise ValueError("Malformed native tool-call batch")
        encoded = json.dumps(
            raw_args, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        argument_bytes = len(encoded.encode("utf-8"))
        current = raw_args
    elif isinstance(raw_args, str):
        argument_bytes = len(raw_args.encode("utf-8"))
        current = raw_args.strip().lstrip("\ufeff")
    else:
        raise ValueError("Malformed native tool-call batch")
    if argument_bytes > _NATIVE_MAX_ARGUMENT_BYTES or (
        isinstance(raw_args, dict)
        and not _native_argument_depth_is_bounded(encoded)
    ):
        raise ValueError("Malformed or oversized native tool-call batch")
    if isinstance(current, str) and not current:
        return {}, argument_bytes

    decoder = json.JSONDecoder()
    for _ in range(3):
        if isinstance(current, str):
            current = _parse_native_argument_json(current, decoder)
            continue
        if not isinstance(current, dict):
            raise ValueError("Malformed native tool-call batch")
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
        if not _native_argument_values_are_json_safe(current):
            raise ValueError("Malformed native tool-call batch")
        return dict(current), argument_bytes
    raise ValueError("Malformed or oversized native tool-call batch")


def normalize_native_tool_calls(raw_calls: list | None) -> list[dict[str, Any]]:
    """Validate and normalize a complete bounded provider tool-call batch."""
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list) or len(raw_calls) > _NATIVE_MAX_CALLS:
        raise ValueError("Malformed or oversized native tool-call batch")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    batch_argument_bytes = 0
    batch_envelope_bytes = 0
    for i, call in enumerate(raw_calls):
        if not isinstance(call, dict) or call.get("type") not in (None, "function"):
            raise ValueError("Malformed native tool-call batch")
        fn_value = call.get("function")
        if fn_value is not None and not isinstance(fn_value, dict):
            raise ValueError("Malformed native tool-call batch")
        fn = fn_value if isinstance(fn_value, dict) else {}
        raw_name = fn.get("name") or call.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("Malformed native tool-call batch")
        if len(raw_name.encode("utf-8")) > _NATIVE_MAX_NAME_BYTES:
            raise ValueError("Oversized native tool-call batch")
        original_name = raw_name.strip()
        name = original_name[5:] if original_name.lower().startswith("tool_") else original_name
        if not name:
            raise ValueError("Malformed native tool-call batch")
        raw_args = fn.get("arguments", call.get("arguments", {}))
        args, argument_bytes = _decode_native_tool_arguments(raw_args)
        batch_argument_bytes += argument_bytes
        if batch_argument_bytes > _NATIVE_MAX_BATCH_ARGUMENT_BYTES:
            raise ValueError("Oversized native tool-call batch")
        raw_id = call.get("id")
        if raw_id in (None, ""):
            call_id = f"call_{i}"
        elif isinstance(raw_id, str):
            call_id = raw_id
        else:
            raise ValueError("Malformed native tool-call batch")
        if (
            not call_id.strip()
            or len(call_id.encode("utf-8")) > _NATIVE_MAX_ID_BYTES
            or call_id in seen_ids
        ):
            raise ValueError("Malformed or oversized native tool-call batch")
        seen_ids.add(call_id)
        batch_envelope_bytes += len(
            json.dumps(call, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if batch_envelope_bytes > _NATIVE_MAX_BATCH_ENVELOPE_BYTES:
            raise ValueError("Oversized native tool-call batch")
        normalized.append(
            {
                "id": call_id,
                "name": name,
                "raw_name": original_name,
                "arguments": args,
                "raw": call,
            }
        )
    return normalized


# ── text-form tool-call recovery ─────────────────────────────────────────
# Native `tools=` is the only dispatch protocol we ask for, but models still
# hand the call back as ORDINARY TEXT instead of a tool_calls entry. Every
# family does it in its own dialect:
#
#   GLM / Kimi     <tool_call>send_message
#                  <arg_key>content</arg_key><arg_value>hola</arg_value>
#   Qwen / vLLM    <function=send_message><parameter=content>hola</parameter>
#   DeepSeek DSML  <invoke name="send_message"><parameter name="content">…
#   gpt-oss        to=functions.send_message …{"content": "hola"}
#   bare JSON      {"name": "send_message", "arguments": {"content": "hola"}}
#
# Before this module the only handling was defensive scrubbing, and both of
# its outcomes were bad: a dialect the scrubber knew got deleted (the reply
# vanished and the turn went silent), and a dialect it did not know got
# posted to the channel verbatim — the user reading a raw parameter dump
# ("reasoning … content … reply true") instead of the message.
#
# Recovery beats scrubbing: parse the leaked markup back into a real tool
# call so it EXECUTES. send_message actually sends, shell actually runs, and
# whatever prose surrounded the markup survives as the leftover text.

_RECOVERY_MAX_CALLS = 8
_RECOVERY_MAX_INPUT_CHARS = 16_000
_RECOVERY_MAX_ARGUMENT_CHARS = 4_000

_FENCE_RE = re.compile(r"```.*?(?:```|$)|~~~.*?(?:~~~|$)", re.DOTALL)

# One (key, value) pair inside a leaked call body, per dialect.
_PAIR_PATTERNS: tuple[re.Pattern, ...] = (
    # GLM-4.x / Kimi K2
    re.compile(
        r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>(.*?)(?:</arg_value>|$)",
        re.DOTALL | re.IGNORECASE,
    ),
    # Qwen / vLLM "<parameter=key>"
    re.compile(
        r"<parameter\s*=\s*([A-Za-z_]\w*)\s*>(.*?)(?:</parameter\s*>|$)",
        re.DOTALL | re.IGNORECASE,
    ),
    # Anthropic-style and DeepSeek DSML '<…parameter name="key" …>'
    re.compile(
        r"<[^<>]*parameter[^<>]*\bname\s*=\s*[\"']([^\"']+)[\"'][^<>]*>"
        r"(.*?)(?:</[^<>]*parameter[^<>]*>|$)",
        re.DOTALL | re.IGNORECASE,
    ),
    # '<arg>key</arg>value</arg>'
    re.compile(
        r"<arg>\s*([A-Za-z_]\w*)\s*</arg>(.*?)(?:</arg>|$)",
        re.DOTALL | re.IGNORECASE,
    ),
)

_TOOL_CALL_BLOCK_RE = re.compile(
    r"<tool_call\b[^>]*>(.*?)(?:</tool_call\s*>|$)", re.DOTALL | re.IGNORECASE
)
_FUNCTION_EQ_RE = re.compile(
    r"<function\s*=\s*([A-Za-z_][\w.]*)\s*>(.*?)(?:</function\s*>|$)",
    re.DOTALL | re.IGNORECASE,
)
_INVOKE_RE = re.compile(
    r"<[^<>]*invoke\b[^<>]*\bname\s*=\s*[\"']([^\"']+)[\"'][^<>]*>"
    r"(.*?)(?:</[^<>]*invoke[^<>]*>|$)",
    re.DOTALL | re.IGNORECASE,
)
# gpt-oss / harmony. Kept deliberately flat: the obvious pattern (an optional
# repeated "<|token|>" prefix glued to the name) nests quantifiers and takes
# seconds to fail on a reply that is mostly pipes. The header before the name
# is walked back separately, over a bounded window, so the leftover text is
# not a stray "<|channel|>commentary".
_HARMONY_RE = re.compile(r"\bto\s*=\s*functions?\.([A-Za-z_]\w*)", re.IGNORECASE)
_HARMONY_LEAD_RE = re.compile(r"<\|[^|<>]{0,32}\|>[^<>|]{0,32}$")
_HARMONY_LEAD_WINDOW = 96


def _harmony_call_start(text: str, pos: int) -> int:
    """Start of the "<|start|>assistant<|channel|>commentary " header at pos."""
    start = pos
    for _ in range(6):
        window = max(0, start - _HARMONY_LEAD_WINDOW)
        match = _HARMONY_LEAD_RE.search(text, window, start)
        if match is None or match.end() != start:
            break
        start = match.start()
    return start


# "send_message<arg>content</arg>hola</arg>" — a bare tool name glued to
# <arg> pairs, with no wrapper tag to find it by. Built per known-name set.
_BARE_ARG_BODY = r"((?:<arg>\s*[A-Za-z_]\w*\s*</arg>.*?</arg>)+)"
_bare_arg_cache: dict[frozenset, re.Pattern] = {}


def _bare_arg_call_re(names: frozenset) -> re.Pattern:
    cached = _bare_arg_cache.get(names)
    if cached is None:
        alt = (
            "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
            or r"(?!x)x"
        )
        cached = re.compile(
            rf"(?<![A-Za-z0-9_])({alt})\s*{_BARE_ARG_BODY}",
            re.DOTALL | re.IGNORECASE,
        )
        _bare_arg_cache[names] = cached
    return cached


_NAME_ATTR_RE = re.compile(r"""\bname\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
_BARE_NAME_LINE_RE = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*$")
# `type` is first on OpenAI-shaped dumps (`{"type":"function","name":…}` /
# `{"type":"function","function":{…}}`). Still decoded by _args_from_json_obj,
# which ignores objects that have no tool name.
_JSON_OPEN_RE = re.compile(
    r'\{\s*"(?:name|tool|tool_name|function|type)"\s*:',
    re.IGNORECASE,
)
_JSON_FENCE_LANGS = frozenset({"", "json", "jsonc", "json5"})


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """Character ranges covered by fenced code blocks (never tool calls)."""
    return [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _json_only_fence_span(
    text: str, json_start: int, json_end: int, fences: list[tuple[int, int]]
) -> tuple[int, int] | None:
    """Fence span if this JSON object is the entire fenced body.

    Models (Grok especially) wrap a real tool-call JSON object in `````json``.
    Skipping that fence left the sanitizer to strip the object and post an
    empty `````json`` block to Discord. XML/tool markup inside a fence is
    still ignored — only a fence whose body is exactly one tool JSON counts.
    """
    json_body = text[json_start:json_end].strip()
    if not json_body:
        return None
    for fence_start, fence_end in fences:
        if not (fence_start <= json_start and json_end <= fence_end):
            continue
        block = text[fence_start:fence_end]
        if block.startswith("```"):
            mark = "```"
        elif block.startswith("~~~"):
            mark = "~~~"
        else:
            continue
        rest = block[len(mark) :]
        if rest.endswith(mark):
            rest = rest[: -len(mark)]
        lang, sep, body = rest.partition("\n")
        if not sep:
            body = lang
            lang = ""
            stripped = body.lstrip()
            lowered = stripped.lower()
            for prefix in ("jsonc", "json5", "json"):
                if lowered.startswith(prefix):
                    after = stripped[len(prefix) :].lstrip()
                    if after.startswith("{"):
                        lang = prefix
                        body = after
                    break
        if lang.strip().lower() not in _JSON_FENCE_LANGS:
            return None
        if body.strip() != json_body:
            return None
        return fence_start, fence_end
    return None


def _clean_tool_name(name: str) -> str:
    """Strip the wrappers providers put around a function name."""
    cleaned = str(name or "").strip().strip("\"'")
    for prefix in ("functions.", "tool_", "tools.", "namespace."):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.strip()


def _balanced_json_object(text: str, start: int) -> tuple[Any, int] | None:
    """Parse the JSON object beginning at ``start``; return (value, end)."""
    import json

    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1]), i + 1
                except (ValueError, TypeError):
                    return None
    return None


def _args_from_json_obj(obj: Any) -> tuple[str, dict[str, Any]] | None:
    """Pull (name, arguments) out of a decoded tool-call JSON object."""
    if not isinstance(obj, dict):
        return None
    lowered = {str(k).lower(): v for k, v in obj.items()}
    if isinstance(lowered.get("function"), dict):
        inner = _args_from_json_obj(lowered["function"])
        if inner:
            return inner
    name = ""
    for key in ("name", "tool", "tool_name", "function"):
        value = lowered.get(key)
        if isinstance(value, str) and value.strip():
            name = value
            break
    if not name:
        return None
    args: Any = {}
    for key in ("arguments", "parameters", "args", "input"):
        if key in lowered:
            args = lowered[key]
            break
    if isinstance(args, str):
        args = _decode_tool_arguments(args)
    if not isinstance(args, dict):
        args = {}
    return _clean_tool_name(name), dict(args)


def _pairs_from_body(body: str, name: str) -> dict[str, Any]:
    """Decode one leaked call body into an arguments dict.

    Dialects are tried in order and the FIRST one that yields any pair wins,
    so a body carrying both ``<arg_key>`` pairs and stray angle brackets in a
    value does not get shredded by the looser patterns below it.
    """
    for pattern in _PAIR_PATTERNS:
        found = pattern.findall(body)
        if found:
            return {
                str(key).strip(): value.strip()
                for key, value in found
                if str(key).strip()
            }
    match = _JSON_OPEN_RE.search(body) or re.search(r"\{", body)
    if match:
        parsed = _balanced_json_object(body, match.start())
        if parsed is not None:
            decoded = _args_from_json_obj(parsed[0])
            if decoded:
                return decoded[1]
            if isinstance(parsed[0], dict):
                return dict(parsed[0])
    # Last dialect: the tool's own parameter names used as XML tags,
    # e.g. "<content>hola</content>". Only names the schema declares are
    # accepted, so prose in angle brackets cannot invent an argument.
    props = dict((TOOL_PARAMETERS.get(name) or {}).get("properties") or {})
    props.setdefault("reasoning", REASONING_PARAM)
    args: dict[str, Any] = {}
    for key in props:
        tag = re.search(
            rf"<{re.escape(key)}\s*>(.*?)(?:</{re.escape(key)}\s*>|$)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        if tag:
            args[key] = tag.group(1).strip()
    return args


# The Python-call dialect: ``send_message(reasoning=…, content=…)``. Models
# emit it constantly, nothing recovered it, so the whole parameter dump landed
# in the channel as the visible reply.
#
# Two things make it awkward, and both show up in every real example:
#   * values are unquoted and full of commas — "content=quedó santo pa, ya
#     tenés el aura" is ONE value, so splitting on commas truncates the reply
#     mid-sentence;
#   * keys repeat — the model likes to restate `reasoning` after `content`.
# So a comma only ends a value when a DECLARED parameter name and `=` follow
# it, and the first occurrence of a key wins.
_PAREN_ARG_KEY_RE = re.compile(r"([A-Za-z_]\w*)\s*=")
_paren_call_cache: dict[frozenset, re.Pattern] = {}


def _paren_call_re(names: frozenset) -> re.Pattern:
    cached = _paren_call_cache.get(names)
    if cached is None:
        alt = (
            "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
            or r"(?!x)x"
        )
        # The name must open the call and be followed immediately by
        # "key=", so ordinary prose containing "(" never matches.
        cached = re.compile(
            rf"(?<![A-Za-z0-9_])({alt})\s*\(\s*(?=[A-Za-z_]\w*\s*=)",
            re.IGNORECASE,
        )
        _paren_call_cache[names] = cached
    return cached


# ":)", ";-)", "=)" and friends. A smiley inside a value is not a closing
# paren, and Dame Curie's rooms are full of them — without this, "content=mira
# esto :) jaja" gets cut to "mira esto :".
_EMOTICON_CLOSE_RE = re.compile(r"[:;=xX8]-?\)$")


def _balanced_paren_end(text: str, start: int) -> int:
    """Index just past the ``)`` closing the ``(`` at ``start``.

    Falls back to the end of the text when the model never closed it, which
    is better than dropping the call and posting the dump.
    """
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if _EMOTICON_CLOSE_RE.search(text[max(0, i - 2) : i + 1]):
                continue
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _strip_wrapping_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _pairs_from_paren_body(interior: str, name: str) -> dict[str, Any]:
    """Split ``key=value, key=value`` where values may contain commas."""
    props = dict((TOOL_PARAMETERS.get(name) or {}).get("properties") or {})
    props.setdefault("reasoning", REASONING_PARAM)
    marks: list[tuple[int, int, str]] = []
    for match in _PAREN_ARG_KEY_RE.finditer(interior):
        key = match.group(1)
        if key not in props:
            continue
        before = interior[: match.start()].rstrip()
        # A key only starts a new argument at the very front or right after
        # the comma that ended the previous one. Anything else is a "x=y"
        # that happens to live inside a value.
        if before and not before.endswith(","):
            continue
        marks.append((match.start(), match.end(), key))
    args: dict[str, Any] = {}
    for index, (_start, value_at, key) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(interior)
        value = interior[value_at:end].strip().rstrip(",").strip()
        # First occurrence wins: the trailing repeat is the model echoing
        # itself, and the leading one is what it actually reasoned with.
        if key not in args:
            args[key] = _strip_wrapping_quotes(value)
    return args


def _coerce_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Cast string values to the JSON types the schema declares.

    A recovered call arrives as text, so ``reply`` is the string ``"true"``
    and ``max_results`` is ``"5"``. Tools take those through kwargs, where a
    non-empty string is truthy — ``reply="false"`` would Discord-reply.
    """
    props = dict((TOOL_PARAMETERS.get(name) or {}).get("properties") or {})
    out: dict[str, Any] = {}
    for key, value in args.items():
        declared = props.get(key)
        kind = str((declared or {}).get("type") or "")
        if not isinstance(value, str) or not kind:
            out[key] = value
            continue
        text = value.strip()
        if kind == "boolean":
            lowered = text.lower()
            if lowered in {"true", "yes", "1", "on"}:
                out[key] = True
                continue
            if lowered in {"false", "no", "0", "off"}:
                out[key] = False
                continue
        elif kind in {"integer", "number"}:
            try:
                out[key] = int(text) if kind == "integer" else float(text)
                continue
            except (TypeError, ValueError):
                pass
        out[key] = value
    return out


# Keys of a leaked send_message whose tags were eaten before we saw the text
# (a markdown renderer, a scrubber, a client that swallows angle brackets),
# leaving a bare "key\nvalue" ladder as the visible reply.
_TAGLESS_KEYS = ("reasoning", "content", "reply", "reply_to")


def _recover_tagless_kv(text: str) -> tuple[str, dict[str, Any]] | None:
    """Recover a send_message whose markup was stripped down to key lines.

    Deliberately narrow: the text must OPEN on a bare parameter-name line and
    carry at least two of them including ``content``. A real reply that opens
    with a line reading only "reasoning" and later a line reading only
    "content" is not a thing anyone types.
    """
    lines = str(text or "").split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first].strip().lower() not in _TAGLESS_KEYS:
        return None
    args: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[first:]:
        key = line.strip().lower()
        if key in _TAGLESS_KEYS and key not in args:
            current = key
            args[current] = []
            continue
        if current is None:
            return None
        args[current].append(line)
    if len(args) < 2 or "content" not in args:
        return None
    joined = {key: "\n".join(value).strip() for key, value in args.items()}
    if not joined.get("content"):
        return None
    return "send_message", joined


def _iter_gated(pattern: re.Pattern, text: str, lowered: str, marker: str):
    """Run ``pattern`` only when a cheap literal marker is present."""
    if marker not in lowered:
        return ()
    return pattern.finditer(text)


def recover_text_tool_calls(
    text: str, known_names: Any = None
) -> tuple[list[dict[str, Any]], str]:
    """Parse tool calls a model wrote as visible text.

    Returns ``(raw_calls, leftover_text)``. ``raw_calls`` are in the provider's
    own ``tool_calls`` shape, so callers can feed them straight into the same
    dispatch path a native call takes. ``leftover_text`` is the response with
    the recovered markup removed — the prose the model wrote around the call.

    Only names in ``known_names`` are recovered. XML/tool markup inside a
    fenced code block is skipped (quoting syntax is not a call). A fence
    whose body is exactly one tool-call JSON object is recovered — Grok
    wraps real calls in ``json`` fences, and skipping those left Discord
    an empty fence after the sanitizer ate the object.
    """
    import json

    raw = str(text or "")
    if len(raw) > _RECOVERY_MAX_INPUT_CHARS or not raw.strip():
        return [], raw
    allowed = {str(n).lower() for n in (known_names or ())} or None
    # Recovery runs on every reply the provider did not attach tool_calls to —
    # which is most of them. Cheap substring gates keep an ordinary chat
    # message from paying for six regex scans it can never match.
    lowered = raw.lower()
    fences = _fenced_spans(raw) if "```" in raw or "~~~" in raw else []

    found: list[tuple[int, int, str, dict[str, Any]]] = []

    def _add(start: int, end: int, name: str, args: dict[str, Any]) -> None:
        name = _clean_tool_name(name)
        if not name or _inside(start, fences):
            return
        if allowed is not None and name.lower() not in allowed:
            return
        found.append((start, end, name, args))

    for match in _iter_gated(_TOOL_CALL_BLOCK_RE, raw, lowered, "<tool_call"):
        body = match.group(1)
        name_attr = _NAME_ATTR_RE.search(match.group(0)[: match.group(0).find(">") + 1])
        name = name_attr.group(1) if name_attr else ""
        if not name:
            # "<tool_call>send_message\n<arg_key>…" — the name is whatever
            # leads the body, before the first tag or line break. Both the
            # newline-separated and the glued form show up in the wild.
            lead = re.split(r"[<\n]", body.lstrip(), maxsplit=1)[0]
            bare = _BARE_NAME_LINE_RE.match(lead)
            name = bare.group(1) if bare else ""
        if not name:
            json_match = _JSON_OPEN_RE.search(body)
            parsed = (
                _balanced_json_object(body, json_match.start()) if json_match else None
            )
            decoded = _args_from_json_obj(parsed[0]) if parsed else None
            if decoded:
                _add(match.start(), match.end(), decoded[0], decoded[1])
            continue
        _add(
            match.start(),
            match.end(),
            name,
            _pairs_from_body(body, _clean_tool_name(name)),
        )

    for pattern, marker in ((_FUNCTION_EQ_RE, "<function"), (_INVOKE_RE, "invoke")):
        for match in _iter_gated(pattern, raw, lowered, marker):
            name = _clean_tool_name(match.group(1))
            _add(
                match.start(), match.end(), name, _pairs_from_body(match.group(2), name)
            )

    if allowed and "<arg>" in lowered:
        for match in _bare_arg_call_re(frozenset(allowed)).finditer(raw):
            name = _clean_tool_name(match.group(1))
            _add(
                match.start(), match.end(), name, _pairs_from_body(match.group(2), name)
            )

    # send_message(reasoning=…, content=…) — a call written as a Python call.
    if allowed and "(" in raw and "=" in raw:
        for match in _paren_call_re(frozenset(allowed)).finditer(raw):
            name = _clean_tool_name(match.group(1))
            open_paren = raw.find("(", match.end(1))
            if open_paren == -1:
                continue
            end = _balanced_paren_end(raw, open_paren)
            interior = raw[
                open_paren + 1 : end - 1 if raw[end - 1 : end] == ")" else end
            ]
            args = _pairs_from_paren_body(interior, name)
            if args:
                _add(match.start(), end, name, args)

    for match in _iter_gated(_HARMONY_RE, raw, lowered, "functions."):
        name = _clean_tool_name(match.group(1))
        brace = raw.find("{", match.end())
        parsed = _balanced_json_object(raw, brace) if brace != -1 else None
        if parsed is None:
            continue
        args = parsed[0] if isinstance(parsed[0], dict) else {}
        decoded = _args_from_json_obj(args)
        _add(
            _harmony_call_start(raw, match.start()),
            parsed[1],
            name,
            decoded[1] if decoded else dict(args),
        )

    for match in _JSON_OPEN_RE.finditer(raw):
        parsed = _balanced_json_object(raw, match.start())
        if parsed is None:
            continue
        decoded = _args_from_json_obj(parsed[0])
        if not decoded:
            continue
        start, end = match.start(), parsed[1]
        wrapped = _json_only_fence_span(raw, start, end, fences)
        if wrapped:
            name = _clean_tool_name(decoded[0])
            if name and (allowed is None or name.lower() in allowed):
                found.append((wrapped[0], wrapped[1], name, decoded[1]))
            continue
        _add(start, end, decoded[0], decoded[1])

    # Drop overlaps (a <tool_call> wrapper and the JSON inside it both match),
    # keeping the outermost span so the wrapper is removed from the text too.
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int, str, dict[str, Any]]] = []
    for span in found:
        if any(not (span[1] <= k[0] or span[0] >= k[1]) for k in kept):
            continue
        kept.append(span)
    if len(kept) > _RECOVERY_MAX_CALLS:
        return [], raw
    kept.sort(key=lambda item: item[0])

    if not kept:
        tagless = _recover_tagless_kv(raw)
        if tagless is None:
            return [], raw
        name, args = tagless
        if allowed is not None and name.lower() not in allowed:
            return [], raw
        kept = [(0, len(raw), name, args)]

    leftover = raw
    for start, end, _name, _args in reversed(kept):
        leftover = leftover[:start] + leftover[end:]
    leftover = re.sub(r"\n{3,}", "\n\n", leftover).strip()

    calls: list[dict[str, Any]] = []
    for i, (_start, _end, name, args) in enumerate(kept):
        arguments = json.dumps(_coerce_args(name, args))
        if len(arguments) > _RECOVERY_MAX_ARGUMENT_CHARS:
            return [], raw
        calls.append(
            {
                "id": f"recovered_{i}_{name}",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    return calls, leftover


# ── tool-loop transcript bounds ──────────────────────────────────────────
# Every agent loop in this repo replays the
# whole assistant/tool transcript on every round, so an unbounded tail is how a
# turn walks off the end of the context window mid-loop. Per-result truncation
# is not enough on its own: 24 rounds of a 32k-capped result is still ~768k
# chars riding on top of an already-full prompt.
TOOL_TAIL_MAX_MESSAGES = 12
TOOL_TAIL_MAX_CHARS = 36_000
TOOL_TAIL_NEWEST_GROUP_CHARS = 24_000
TOOL_RESULT_COMPACT_CHARS = 4_000
_HISTORY_MARKER_RE = re.compile(
    r"\n… \[(\d+) chars truncated from (?:earlier tool result|tool result|tool history)\]$"
)


def message_chars(message: dict) -> int:
    """Prompt size of one chat message, tool_calls included.

    An assistant turn replayed in a tool loop carries its arguments (a
    file body, a shell script, a long send_message) and those are real
    prompt tokens — counting only ``content`` leaves a budget blind to the
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
    while len(groups) > 1 and sum(map(len, groups)) > max_messages:
        groups.pop(0)
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
        used -= sum(message_chars(msg) for msg in dropped)
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
            limit = 300 if key == "reasoning" else max_chars
            if isinstance(value, str) and len(value) > limit:
                if key == "reasoning":
                    marker = f"… [{len(value)} chars total; reasoning shortened]"
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
