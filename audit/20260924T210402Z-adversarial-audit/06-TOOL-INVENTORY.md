# Current model-facing tool inventory

Historical flat baseline: source `aad36e6`, inspected 2026-09-25. That earlier pass was source-only: no application imports, tool execution, tests, private configuration or runtime access. The current measured section below supersedes its exposure claims. This lists LLM tools, not Discord prefix commands or this coding harness's tools.

## Scope note — current section versus historical baseline

- **"CURRENT catalog — QA61 measurement"** below is the current evidence for the catalog produced by the committed source and is anchored to `validation.md` QA61.
- The sections from **"Count and exposure"** onward are the **historical `aad36e6` baseline**: their flat counts, per-tool rows and their "no lean selection / every enabled tool on every turn" exposure statement are the state of that earlier committed source and are **not current claims**. They are preserved unedited as baseline, not rewritten or removed.
- No new tests, test runs or privacy claims are introduced here. This pass measured nothing; it records the coordinator's QA61 measurement.

## CURRENT catalog — QA61 measurement

Measured in the credential-free, network-none isolated QA image, on frozen tree `25763dfee4483e4887479b2997ff64b0009d562c`, whose catalog source is committed `d198c37` and remains unchanged by packaging commit `be28b85`. Real `MaxwellBot._setup_tools`, `_turn_tool_names`, `_build_openai_tools` and `_tool_system_prompt` were executed against synthetic bot/actors, all `ENABLE_*` feature gates true, empty synthetic plugin state, and the actual checkers plugin. **No tools, provider or Discord calls were made.**

Registered: **70 built-in tools + 4 checkers plugin tools**. Selected-row measurements (count / compact schema chars / schema UTF-8 bytes / native system-prompt chars / custom combined system-prompt chars):

| Actor / group | Count | Schema chars | Schema bytes | Native system chars | Custom combined chars |
|---|---|---|---|---|---|
| admin, core | 15 | 14413 | 14436 | 8272 | 14845 |
| admin, workflow | 24 | 21431 | 21460 | 8381 | 17930 |
| admin, all_groups and debug_full | 74 | 54608 | 54649 | 9072 | 30085 |
| ordinary, core | 14 | 12892 | 12915 | 8265 | 13955 |
| ordinary, workflow | 21 | 18744 | 18773 | 8327 | 16560 |
| ordinary, all_groups and debug_full | 70 | 51085 | 51122 | 9005 | 28328 |

Conditions and limits of those numbers:

- `custom combined` = the actual tool-system prompt plus `custom_tool_prompt(names)`; native and custom are alternative serializations, not additive.
- These are **fixture-specific character/byte measurements** from compact serialized schemas. They are **not token counts, not billing, not the full prompt and not live exposure**.
- Counts and char sizes are the result of `_turn_tool_names`/`_build_openai_tools` under exactly those gates; a different actor, gate set, plugin state or `disabled_tools` value yields different rows.

**`more_tools` discovery is working and bounded** (`tool_schemas.py:51`, `58–99`, `468–475`; `bot.py:14730–14740`; `turn_budget.py:33–50`, `132`):

- `CORE_TOOL_NAMES` is the always-offered core set; `TOOL_DISCOVERY_GROUPS` defines the named groups `messaging`, `media`, `identity`, `servers`, `moderation`, `voice`, `workflow`, `games`, `plugins`.
- `more_tools` carries the group enum. Discovery adds a group to the task-local catalog scope, unioned with core names for the **following model round within the same foreground/job turn**. `current_tool_groups()` prefers the explicit groups context and otherwise uses `ForegroundTurn.expanded_tool_groups`; jobs get separate catalog sets even when a descendant shares foreground spend. This is not persistent cross-user discovery.
- This supersedes the historical "hidden compatibility no-op `more_tools`" and "every enabled tool on every turn" framing **as current claims only**; that framing stays as written under the historical baseline above.

**Actor and config gates are separate**, and both apply on top of the above:

- Actor/context: admin-only visibility and per-tool authorization.
- Config/feature: `tools_enabled`, `disabled_tools`, native versus custom protocol selection, and the individual `ENABLE_*` tool gates (`ENABLE_WEB_SEARCH`, `ENABLE_FETCH_URL`, `ENABLE_SHELL`, `ENABLE_IMAGE_GEN`, `ENABLE_YOUTUBE`, `ENABLE_TTS`, `ENABLE_AVATAR`), plus chess import availability and checkers plugin visibility (global/per-user state and successful plugin load).

**Budget boundary:** `control_defaults.py` sets `prompt_context_budget` to **96000** characters (`control_defaults.py:175`), the schema-inclusive prompt budget bound to `_prompt_budget_chars` (`bot.py:15091–15110`). The **36 000-character figure is the bounded tool-history tail limit** (`tool_schemas.py:1806`, `TOOL_TAIL_MAX_CHARS`) enforced by `tool_schemas.py:1931`, **not** the prompt budget. The measured all-groups schema alone does not exceed the 96000 default. No token or billing inference follows from these character counts.

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

## Measurement receipt (CURRENT section)

- `validation.md`, section **"Full-safe green run and checkpoint — QA57–61"**, QA61 entry: frozen tree `25763dfee4483e4887479b2997ff64b0009d562c`, `201 passed` on the four selected existing test files, then the tool-registration and serialized-catalog measurement executed there; `validation.md` also records the 36k-bounded-history versus 96000-prompt-budget correction.
- QA65 repeated the same-tree, same-envelope measurement without the long name inventories; the complete scalar output reconfirmed every table value. See `validation.md`, "Candidate artifact and compact measurement recheck — QA63–65".
- Commits: catalog source `d198c37`; packaging commit `be28b85` does not change the catalog source.
- These receipts validate only that named frozen tree/subset. They are not full-suite, artifact, live-Dirac or model-facing acceptance.
