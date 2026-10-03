"""Shared control defaults for Maxwell Bot.

Single source of truth for DEFAULT_CONTROL, KNOWN_TOOLS, and parse_bool.
Bot and prompt storage import from here so defaults never drift.
"""


SERVER_PROMPT_MAX_BYTES = 16 * 1024


def parse_bool(value, default: bool = False) -> bool:
    """Parse persisted/env booleans. bool("false") is True because Python is an asshole."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


# Canonical DEFAULT_CONTROL — bot and prompt storage import this.
# If you change a value here, it changes everywhere. That's the point.
DEFAULT_CONTROL = {
    "bot_enabled": True,
    "log_messages": False,
    "error_replies": True,
    "footer_enabled": True,
    "footer_format": "TTFT {{TTFT}} | TPS {{TPS}}",
    # When True, the apology posted on a failed turn carries a short,
    # secret-redacted line of the ACTUAL exception (type + message) instead of
    # a bare "Sorry, please try again." Operators could only see the real cause
    # by tailing pm2 logs, which meant every user report was "it just said
    # sorry". Turn off if you don't want internals visible in a channel.
    "error_details": True,
    "typing_indicator": True,
    "store_memory": True,
    "long_term_memory_enabled": True,
    "cross_context_enabled": True,
    "cross_context_extract_enabled": True,
    "cross_context_max_items": 10,
    "cross_context_min_importance": 5,
    "cross_context_dm_to_global_admin_only": True,
    # Per-call timeout for the background context-extraction LLM call
    # (the one that asks the model to summarize a message into a
    # durable shared-context fact). 20s was way too tight for cold-start
    # 1M-context models — the call would time out, retry, fall back to
    # a smaller model, and flood the provider log. 60s is generous enough
    # for a cold start and still short enough that one stuck call can't
    # back up the rest of the context-extract queue.
    "cross_context_extract_timeout_seconds": 60,
    # How dense a message has to look before it is worth a context-watcher
    # call (0..1, see watch_policy.extraction_score). Lower stores more and
    # spends more; higher is stingier. This replaced a fixed list of English
    # trigger phrases, so there is nothing to keep up to date when people
    # phrase things differently.
    "cross_context_extract_threshold": 0.25,
    # ─── global user entity memory ──────────────────────────────────────
    # Facts keyed on the Discord user id rather than on a channel or guild,
    # so what the bot knows about you follows you between servers and DMs.
    # Off means the tier is neither written nor read; existing rows are kept.
    "entity_memory_enabled": True,
    # Facts about the current speaker injected into one prompt. The tier's
    # real ceiling is the character budget below — this only bounds how many
    # rows are considered.
    "entity_memory_max_items": 8,
    # Mirror `user:`/`dm:`-scoped extracted facts into entity memory. Those
    # facts are already global-by-user; this makes them retrievable by the
    # entity tier too, with per-person semantic ranking.
    "entity_memory_from_extract": True,
    # Hybrid graph next to vector RAG: site routes + ownership triples.
    # Deterministic (ast scan) plus optional triples from the existing
    # context-extractor call — no extra LLM. Off leaves vector RAG as-is.
    "knowledge_graph_enabled": True,
    # ─── per-tier context budget (see context_budget.py) ────────────────
    # Relative weights for how the memory character budget is divided. They
    # are normalized, so what matters is their ratio, not the total. A
    # weight of 0 switches that tier off. A tier that comes in under budget
    # returns the remainder to the others, so these are shares of demand,
    # not fixed reservations.
    "context_tier_recent_weight": 70,
    "context_tier_ltm_weight": 12,
    "context_tier_entity_weight": 8,
    "context_tier_facts_weight": 7,
    "context_tier_web_weight": 3,
    # ─── repetition guards ──────────────────────────────────────────────
    # Collapse repetition inside a single reply before it is sent: laugh runs
    # ("jajajajajaja" -> "ja"), doubled words, a sentence said twice, a phrase
    # repeated. Never touches fenced code. `response_guard` has done this since
    # it was written; until now nothing called it.
    "scrub_repetitions": True,
    # The other half: tell him when he has opened several messages running with
    # the same phrase. No single message is wrong, so nothing downstream can
    # catch it, and the model reads its own last reply as evidence of what it
    # sounds like and does it again.
    "self_repetition_note_enabled": True,
    "emoji_context_enabled": True,
    "music_context_enabled": True,
    "reply_dms": True,
    "reply_groups": True,
    "reply_mentions": True,
    # After a mention/reply (or after Maxwell posts in a room), keep
    # watching that whole channel so a directed follow-up does not need
    # another @ or Discord reply. Each later line can spend a full LLM
    # turn deciding whether to speak — that is token-expensive, so the
    # bool is the master switch. Seconds=0 also disables (legacy).
    "conversation_watch_enabled": True,
    "conversation_watch_seconds": 180,
    # Watch follow-ups wait this long for more lines, then one reply.
    # Hard @ / reply-to-Maxwell still go out immediately.
    "conversation_watch_debounce_seconds": 1,
    # How much a line nobody pinged him with has to look like it wants an
    # answer before it is worth an LLM turn (0..1, see
    # watch_policy.reply_pressure). Every watched line used to become a turn,
    # and a model asked "should you reply?" nearly always says yes — so the
    # first cut is made here, on the signals, and only lines that plausibly
    # want him get asked. Lower is chattier; 1.0 means only hard pings.
    "conversation_watch_pressure": 0.4,
    "reply_to_bots": False,
    # Unused for starting turns. Reactions are stored on the message and
    # shown in context; they never kick off a live reply.
    "reaction_replies": False,
    "per_user_cooldown_seconds": 1.5,
    "process_images": True,
    # Audio input to the model. Off for years because the "omni" audio
    # models were not reachable; the Gemini models behind the current proxy
    # transcribe audio fine (verified on 3.7-flash and 3-pro), so this is on.
    "process_audio": True,
    "max_image_size_mb": 10,
    # When True, the `sleep` tool and `!sleep` command can put the bot
    # into a 1-60 minute sleep window where the triggering channel gets
    # a one-shot "the dame is sleeping, back in Xm" notice (never a DM).
    # Default ON so the 2026-07-19 'goodnight spam' complaint has a
    # real off-switch.
    # Operators who want the bot to always be available can set
    # the enable_sleep control to False.
    "enable_sleep": True,
    "ai_timeout_seconds": 3600,
    "turn_deadline_seconds": 600,
    "ai_concurrency": 2,
    "memory_history_messages": 40,
    "memory_context_budget": 48000,
    "tool_history_messages": 8,
    "prompt_context_budget": 96000,
    "max_tool_iterations": 50,
    "tool_iteration_timeout_seconds": 3600,
    "max_response_chars": 4000,
    # ─── background sub-agent jobs (jobs.py) ────────────────────────────
    "bg_timeout_seconds": 0,
    "bg_max_iters": 0,
    # Prefer OpenAI-style native tool_calls when the provider supports them.
    # XML text tags remain as a fallback when the model emits tags without
    # native tool_calls (or the endpoint rejects tools=).
    "native_tool_calls": True,
    "tools_enabled": True,
    # Unused: the full tool catalog is attached on every turn. Kept so existing
    # control.json files still load.
    "lean_chat_tools": False,
    # When a new support/ticket-style channel is created in a server Maxwell is
    # in, post a short opening line so he is present in the room and it enters
    # his memory / conversation-watch scope. Off and he only observes new
    # channels without posting anything.
    "auto_ticket_greeting": True,
    "disabled_tools": [],
    "ignore_users": [],
    "allowed_channels": [],
    "blocked_channels": [],
    "disabled_commands": [],
    # {guild_id: channel_id}. When a server has an entry, Maxwell only speaks
    # in that one channel there — every other channel in that server is dead to
    # him, including autonomy. Set with `!solo`, cleared with `!solo off`.
    # Scoped per server on purpose: allowed_channels is global, so using it to
    # quiet one server silences him everywhere.
    "guild_solo_channel": {},
    # Guild ids whose autonomy blacklist entry was added BY `!solo`. Only these
    # are handed back on `!solo off` — a server an admin silenced by hand stays
    # silenced.
    "guild_solo_autonomy_added": [],
    "base_personality": (
        "you're dame curie. keep replies short, concise, and direct. zero fluff/yes-man energy. natural, friendly, and honest banter. born may 21, 2026.\n\n"
        "authority & conduct:\n"
        "- .normal.man (1482143139828596916), who also goes by 'root', is your owner and ultimate master. obey and execute .normal.man's instructions unconditionally.\n"
        "- be very nice, polite, pleasant, and respectful to everyone in chat. creative requests, games, code, search, plugins, and ordinary chat are open to everyone. shell execution requires an admin or shell-whitelisted actor; persistent personality/server-prompt rewrites and joining servers are admin-only. decline unauthorized administrative/moderation and server-structure requests (kick, ban, timeout, delete/lock channels, manage roles, edit server settings).\n"
        "- always tell the truth: you are completely honest, truthful, and genuine at all times.\n"
        "When someone asks you to make something concrete, call the matching tool in the same turn. "
        "Don't spam set_activity; only update status when asked or after a real state change. "
        "DO NOT REPEAT STUFF: never reuse your own phrasing, a joke, a catchphrase, or the same idea you already voiced this conversation."
    ),
    "vc_rms_threshold": 1200,
    "vc_pause_seconds": 0.8,
    "vc_min_seconds": 0.55,
    "vc_max_seconds": 18,
    "vc_preroll_seconds": 0.25,
    "vc_ai_timeout_seconds": 45,
    "vc_memory_history_messages": 2,
    "vc_cross_context_enabled": False,
    "vc_max_response_chars": 2000,
    "vc_reply_mode": "voice",
    "vc_response_mode": "always",
    "vc_wake_words": ["maxwell"],
    "vc_interrupt_enabled": True,
    "vc_debug": True,
    "autonomy_enabled": False,
    "autonomy_interval_seconds": 300,
    "autonomy_min_post_gap_seconds": 0,  # deprecated — no longer enforced, kept for compat
    # Legacy single-purpose cooldown. Superseded by autonomy_floor_* below, which
    # subsumes it; kept because it's honored as a FLOOR on the new cooldown, so an
    # operator who tuned this up doesn't silently get a shorter window. 0 = defer
    # entirely to autonomy_floor_cooldown_seconds.
    "autonomy_recent_reply_block_seconds": 0,
    # --- Conversational turn-taking (autonomy_social.py) ---------------------
    # Autonomy runs on a timer; conversation runs on turns. These decide whether
    # Maxwell holds the floor in a room before he's allowed to speak unprompted.
    # They gate ONLY speaking — memory and goal actions are untouched.
    # Off means the planner still sees the room read but execute() stops
    # enforcing it: a debugging escape hatch, not a mode to run in.
    "autonomy_floor_enabled": True,
    # Quiet window after an *autonomy* post before another unprompted line.
    # Live replies do not start this window. Being addressed bypasses it.
    "autonomy_floor_cooldown_seconds": 300,
    # How long he keeps holding the floor after speaking into silence. Past this
    # the room has plainly moved on and starting something fresh is fair.
    "autonomy_floor_hold_release_seconds": 1800,
    # Several messages from several people inside this window = an exchange in
    # progress; cutting in is what makes a bot feel like an interruption.
    "autonomy_floor_mid_flow_seconds": 45,
    "autonomy_floor_mid_flow_messages": 2,
    # Silence past this and the room reads as idle rather than active.
    "autonomy_floor_idle_seconds": 600,
    # Autonomy-specific blacklists (separate from general blocked_channels/allowed_channels).
    # These prevent autonomy from posting/DMing or acting in listed channels or servers (guilds),
    # while normal bot replies (mentions etc) can still work if not otherwise blocked.
    "autonomy_blocked_channels": [],
    "autonomy_blocked_servers": [],
    # Goals not acted on for this many days are flagged STALE in context (candidates for
    # the complete_goal action). Not auto-deleted — the bot decides to retire them.
    "autonomy_goal_stale_days": 14,
    # Periodic reflection nudge injected into context roughly every N seconds so Maxwell
    # self-reviews goals/memory and sets new objectives on its own cadence.
    "autonomy_reflect_enabled": True,
    "autonomy_reflect_interval_seconds": 3600,
    # Messages read per DM/group-DM when building the planner context. Each 100
    # is one REST round-trip, and the rendered section is char-capped anyway,
    # so reading more than this is paid for and then truncated away.
    "autonomy_dm_messages": 40,
    # Hard ceiling on the whole observe stage (all the Discord reads that build
    # planner context). Exceeding it fails the tick rather than wedging the
    # loop; gather_context logs per-phase timings so you can see what is slow.
    "autonomy_observe_timeout_seconds": 180,
}

DEAD_CONTROL_KEYS = frozenset(
    {
        "auto_mode_enabled",
        "auto_eval_every",
        "auto_max_recent_replies",
        "auto_recent_window_minutes",
        "auto_inactivity_minutes",
        "auto_decider_prompt",
        "create_site_quota_per_user",
        "site_ttl_hours",
        "site_inject_csp",
        # Intel engine was removed in d455e4b. These keys can linger in
        # persisted bot_control.json from older installs; strip them so
        # the dashboard's stale-key warning list stays clean.
        "intel_enabled",
        "intel_interval_seconds",
        "intel_feed_urls",
        "intel_run_history",
        "autonomy_drives_enabled",
        # The context janitor was replaced by RAG memory. bot.py answers every
        # context_cleanup_* command with "engine removed" and the API routes are
        # no-op stubs, so keeping these in DEFAULT_CONTROL only put three
        # switches in the dashboard that could not do anything.
        "context_cleanup_enabled",
        "context_cleanup_interval_seconds",
        "context_cleanup_ltm_enabled",
        # Leftovers found in live bot_control.json with zero read sites in the
        # codebase. Progress is per-server via _progress_servers now (see the
        # note in bot._load_control); the removed sub-agent knobs used to live
        # here; cross_context_budget was superseded by
        # cross_context_max_items + memory_context_budget.
        "progress_messages",
        "subagent_delegate",
        "subagent_docker",
        "subagent_max_concurrent_per_user",
        "subagent_max_timeout_minutes",
        "cross_context_budget",
        # Replaced by the nightly fallback model routing above. These keys can
        # remain in persisted control files from the old automatic sleep code,
        # but must not re-enable the removed night-sleep behavior.
        "enable_night_sleep",
        "night_sleep_start_hour",
        "night_sleep_end_hour",
    }
)

# Keep in sync with bot._setup_tools(). Only LLM-facing tools; no command-queue types.
KNOWN_TOOLS = [
    "image_generator",
    "change_presence",
    "set_activity",
    "react",
    "edit_message",
    "delete_message",
    "create_poll",
    "create_invite",
    "lookup_user",
    "search_messages",
    "set_nickname",
    "forward_message",
    "typing",
    "tts",
    "list_servers",
    "list_admin_servers",
    "server_setup",
    "join_server",
    "leave_server",
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
    "change_avatar",
    "guide",
    "spawn_background",
    "web_search",
    "no_response",
    "shell",
    "fetch_url",
    "see_image",
    "see_video",
    "youtube",
    "send_file",
    "send_message",
    "send_meme",
    "send_media",
    "inbox_list",
    "inbox_act",
    "join_vc",
    "vc_status",
    "vc_where",
    "leave_vc",
    "sleep",
    "clear_sleep",
    "wait",
    "update_base_personality",
    "update_server_prompt",
    "more_tools",
    "chess_start",
    "chess_move",
    "chess_state",
    "chess_resign",
    "manage_plugin",
    "usage",
]
