# Current model-facing tool inventory

Source: `aad36e6`, inspected 2026-09-25. Source-only: no application imports, tool execution, tests, private configuration or runtime access. This lists LLM tools, not Discord prefix commands or this coding harness's tools.

## Count and exposure

- **70 possible built-in registrations**, including the hidden compatibility no-op `more_tools`.
- **69 advertisable built-ins**, with all feature/dependency gates satisfied and an admin actor.
- **4 bundled checkers plugin tools**: **73 possible advertised tools** from the checked-in source.
- Actual per-turn exposure depends on feature flags, chess dependency availability, `tools_enabled`, native/custom protocol selection, `disabled_tools`, the actor and plugin state. No claim that every live turn currently receives every item below.
- The previously retained request's count of 73 is consistent with this complete catalog; the count alone is not a fresh live-name inventory.
- There is **no ordinary-chat versus task-specific catalog selection**. `_lean_chat_turn` always returns False; `lean_chat_tools` is documented as unused. Enabled/admin-appropriate tools are offered together, including games, moderation, voice, shell and persistent prompt rewrites.
- Advertised does not mean authorized to execute: individual tools can still reject a call due to actor, Discord permissions, context, configuration or dependency availability. This inventory is not a permission audit.

## 1. Messages and user lookup — 10

| Tool | Purpose |
|---|---|
| `send_message` | Send a Discord message. |
| `edit_message` | Edit a message. |
| `delete_message` | Delete a message. |
| `forward_message` | Forward a message. |
| `react` | Add a reaction. |
| `typing` | Show typing activity. |
| `create_poll` | Create a poll. |
| `pin_message` | Manage message pinning. |
| `search_messages` | Search message history. |
| `lookup_user` | Look up a Discord user. |

## 2. Web and execution — 3

| Tool | Purpose |
|---|---|
| `web_search` | Search the web. Registration: `ENABLE_WEB_SEARCH`. |
| `fetch_url` | Fetch URL content. Registration: `ENABLE_FETCH_URL`. |
| `shell` | Run Bash inside the outer bot container. Registration: `ENABLE_SHELL`. |

## 3. Images, media and files — 8

| Tool | Purpose |
|---|---|
| `image_generator` | Generate or edit images through the configured native Images API. Registration: `ENABLE_IMAGE_GEN`. |
| `see_image` | Inspect image input. |
| `see_video` | Inspect video input. |
| `youtube` | Process YouTube input. Registration: `ENABLE_YOUTUBE`. |
| `tts` | Generate speech. Registration: `ENABLE_TTS`. |
| `send_file` | Deliver a file. |
| `send_media` | Deliver media. |
| `send_meme` | Send a meme. |

## 4. Identity, persistent prompts and sleep — 8

| Tool | Purpose |
|---|---|
| `change_presence` | Change presence status. |
| `set_activity` | Change the displayed activity. |
| `set_nickname` | Change the bot's nickname. |
| `change_avatar` | Change the bot's avatar. Registration: `ENABLE_AVATAR`. |
| `update_base_personality` | Persistently rewrite the global editable personality. |
| `update_server_prompt` | Persistently rewrite or clear a server/DM prompt. |
| `sleep` | Enter a sleep window. |
| `clear_sleep` | Clear the sleep window. |

## 5. Server membership and onboarding — 6

| Tool | Purpose |
|---|---|
| `list_servers` | List joined servers. |
| `list_admin_servers` | List servers where the bot has administrative capability. |
| `join_server` | Join a server; explicitly hidden from non-admin actors during catalog selection. |
| `leave_server` | Leave a server. |
| `create_invite` | Create an invite. |
| `server_setup` | Read/answer server onboarding prompts and choose roles/channels; not a generic server-provisioning tool. |

## 6. Server/channel administration — 10

| Tool | Purpose |
|---|---|
| `create_category` | Create a channel category. |
| `create_channel` | Create a channel. |
| `edit_channel` | Edit a channel. |
| `delete_channel` | Delete a channel. |
| `lock_channel` | Manage channel locking. |
| `set_channel_permissions` | Change channel permission overrides. |
| `edit_server` | Edit server settings. |
| `manage_role` | Manage roles. |
| `manage_emoji` | Manage server emoji. |
| `audit_log` | Read the Discord audit log. |

## 7. Member moderation — 8

| Tool | Purpose |
|---|---|
| `kick_member` | Kick a member. |
| `ban_member` | Ban a member. |
| `unban_member` | Remove a ban. |
| `list_bans` | List bans. |
| `timeout_member` | Manage member timeout. |
| `purge_messages` | Bulk-delete messages. |
| `set_member_nickname` | Change a member's nickname. |
| `voice_mod` | Moderate members in voice channels. |

## 8. Voice participation — 4

| Tool | Purpose |
|---|---|
| `join_vc` | Join a voice channel, optionally following a user. |
| `leave_vc` | Leave the active voice channel. |
| `vc_status` | Inspect voice-connection status. |
| `vc_where` | Find a user's visible voice-channel location. |

## 9. Workflow, plugins, usage and inbox — 8

| Tool | Purpose |
|---|---|
| `wait` | Wait before proceeding. |
| `no_response` | Choose not to send a reply. |
| `guide` | Create a guided-build thread and ask a fixed clarification questionnaire. |
| `spawn_background` | Launch a detached model job. |
| `manage_plugin` | List/status/enable/disable plugins; global changes have a separate admin requirement. |
| `usage` | Query OpenRouter primary-key spending/cap information; not generic token counts or account balance. |
| `inbox_list` | List actionable friend requests/notices. |
| `inbox_act` | Accept/decline friend requests or mark/read/dismiss notices. |

## 10. Games — 8

| Tool | Purpose / gate |
|---|---|
| `chess_start` | Start chess; `_CHESS_IMPORTED` dependency gate. |
| `chess_move` | Make a chess move; same gate. |
| `chess_state` | Read chess state; same gate. |
| `chess_resign` | Resign chess; same gate. |
| `checkers_start` | Start checkers; plugin visibility gate. |
| `checkers_move` | Make a checkers move; plugin visibility gate. |
| `checkers_state` | Read checkers state; plugin visibility gate. |
| `checkers_resign` | Resign checkers; plugin visibility gate. |

The checked-in checkers manifest defaults to globally enabled. It only initializes missing persisted state; existing per-user/global enabled/denied state takes precedence. Plugin load success is also required. Checkers is the only plugin present in the checked-in `plugins/` tree inspected here.

## Not additional advertised tools

- `more_tools`: registered compatibility no-op, explicitly removed from the advertised name set. It does not provide working lazy discovery.
- `reasoning_log`: an internal backfill instance, not in the model-facing registry.
- `hd_image`: removed; no alias in the current dispatcher map.
- Mandatory public `reasoning` is an argument injected into each native tool schema, not a separate tool and not the provider's private reasoning channel.
- Prefix commands such as `!help`, `!prompt` and `!longprompt` are not extra LLM tool definitions in this inventory.

## Dispatcher aliases — accepted names, no extra schemas

| Canonical tool | Aliases |
|---|---|
| `shell` | `local_shell_call`, `bash`, `terminal`, `exec`, `execute`, `run_command`, `command` |
| `web_search` | `web`, `duckduckgo`, `google`, `search`, `ddg` |
| `fetch_url` | `browse`, `scrape`, `curl`, `http_get`, `fetch` |
| `image_generator` | `generate_image`, `gen_image`, `dalle`, `flux`, `image` |
| `send_message` | `msg`, `message`, `dm` |

These 25 aliases do not add 25 definitions to the `tools` payload. They resolve to the canonical name before its normal dispatch checks. In particular, the tool alias `curl` maps to `fetch_url`, not to a shell command.

## Source anchors

- Built-in registration: `bot.py:3206–3301`; matching control-name inventory: `control_defaults.py:348–420`.
- Full catalog/no lean selection: `bot.py:14114–14149`; unused control: `control_defaults.py:188–190`.
- Per-turn disable/admin/plugin selection: `bot.py:14151–14222`.
- Native enable/protocol selection and schema construction: `bot.py:14224–14290`, `tool_schemas.py:812–897`.
- Checkers registration/default: `plugins/checkers/__init__.py:12–19`, `plugins/checkers/plugin.json:1–8`.
- Plugin persisted-state initialization and actor visibility: `plugin_manager.py:585–594`, `706–745`.
- Dispatcher aliases: `bot.py:13359–13385`.

This inventory makes no removal, enable/disable, permission, prompt, runtime or deployment change. Catalog size in tokens was not measured or recalculated in this pass.
