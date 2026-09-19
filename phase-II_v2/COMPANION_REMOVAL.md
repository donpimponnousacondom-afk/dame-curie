# Companion / GF secondary-account removal

## Scope and commits

- Assigned worktree: `/home/codexy/deepseek/dame-curie-worktrees/remove-companion`.
- Branch: `work/remove-companion-20260919`; base: `43ce047`.
- Implementation: `2c3914f` — remove companion secondary-account runtime and routing (11 files, 12 insertions / 417 deletions).
- Root approved this removal in `REDESIGN_PLAN.md`. This is source-only evidence, not runtime acceptance or a deployment grant.
- Read the worktree's `AGENTS.md`, redesign plan and four orientation documents; loaded `implement-tyranny` and `implement-sanity`.

## Consumer map and implemented cut

| Boundary | Change |
| --- | --- |
| `config.py` | Removed `GF_DISCORD_TOKEN`, `GF_USER_ID`, `PARTNER_USER_ID`, `PARTNER_MAX_AUTO_TURNS`, `PARTNER_TURN_WINDOW_SECONDS`, `PARTNER_NAME` and `BOT_PERSONA_TYPE`. `DATA_DIR` retains its explicit override and primary `data` default, without persona-based `data_gf` selection. |
| `bot.py` construction / prompts | Removed GF identity text, persona alias selection, GF prefix/token/name overrides, partner ID allowlist and budget state, GF directory preparation and GF-only Telegram suppression. Primary configurable identity substitution remains. |
| `bot.py` message routing | Removed companion detection, exchange-budget helpers/callers, the partner exception to `reply_to_bots`, and DM companion-budget checks. Other message gates and storage order remain. |
| `bot.py` startup | One `MaxwellBot` still starts with `DISCORD_TOKEN`. Login-failure handling names that token directly and retains the 30-second backoff / exit code 2. |
| `ecosystem.config.js` | Removed the `.env` GF-token reader/parser and conditional `dame-curie-gf` PM2 process. Primary bot, local embedding server and API entries remain for their owning lanes. |
| `control_defaults.py` | Removed only the hard-coded two-line relationship with the secondary account Uni; retained the primary persona and ordinary social/autonomy controls. |
| `.env.example`, `docker/bot.env.example` | Removed secondary token/identity/persona/budget fields. Primary identity and owner values remain. |
| `bot_tools.py` | Removed Uni as an advertised alternative process name in a chess-helper docstring. No game implementation changed. |
| Existing fixtures | Removed GF data-directory parametrization and its now-unused imports; removed the companion-budget test and stale method bindings; removed obsolete persona selection from the constructor fixture. No new tests or assertions. |

The secondary account was a second PM2 invocation of the same bot, not a separate in-process Discord client. No distinct GF start/close/event implementation or companion-specific nudge control remained elsewhere in the inspected active source. Ordinary relationship events and periodic autonomy reflection are not companion machinery and were retained.

## Primary-path invariants reviewed

- Canonical defaults remain Dame Curie `1545541390392369165`, root / `.normal.man` `1482143139828596916`. No new identity or trust exception. `MaxwellBot` and existing primary internal identifiers were not renamed.
- `_is_admin` still gives the verified root ID its existing authority and otherwise checks the loaded admin set. Admin/owner loading, moderation/tool authorization, taint and one-shot confirmation code are unchanged.
- Normal Discord `author.bot` detection remains. `reply_to_bots` now has no secondary-account bypass; direct bot mentions still reach the existing direct-reply path when the control allows them. Soft bot chatter remains excluded from live-watch initiation.
- Self-message early return, blacklist/ignore/admin handling, command handling, channel/solo controls, cooldown behavior, direct mentions, DMs, group messages, watch/debounce/queue behavior and memory-before-reply gating are preserved for ordinary users.
- `on_relationship_add/update/remove`, inbox ingestion, group-join notices, recent-user/entity/context memory and REM paths remain. No stored user text, memories or configurable private personality was read or rewritten.
- Primary provider configuration, generation paths, voice calls/TTS/ASR, media handling and games are unchanged. Credential redaction logic and registration of every surviving credential remain; GF token registration was removed with its retired configuration field.
- Publisher/syncer, local authoring/image paths, shared image/archive behavior and remote mirroring were not modified. No edits to provider, voice, media, RAG, graph, autonomy or plugin modules.

## Checks and sanity review

- Reviewed the complete implementation diff, including the PM2 JavaScript removals, and traced surrounding Discord control flow.
- Scoped source searches covered active Python modules, plugins, launch/setup/install/example references, API/web companion references and existing fixtures. Removed identifiers have no remaining active consumers in those inspected paths.
- Retained `data_gf` in `.gitignore` and Ruff exclusions, and the generic Docker `data_*` exclusion: these keep historical private state out of source/build scans; they do not launch or configure a second account.
- Retained Uni strings in chess fixtures: they exercise generic live-name rendering and self-opponent protection. Separate-instance fixture names and the backup archive's ordinary “companion record” wording also remain unrelated to this subsystem.
- `git diff --check`: passed before implementation commit.
- Explicit interpreter version: Python **3.14.4**.
- Compile-only check passed for all eight changed Python files, using the existing isolated interpreter and an in-worktree cache:

```sh
/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B \
  -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/remove-companion/.validation-cache \
  -m py_compile \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/bot.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/bot_tools.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/config.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/control_defaults.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/tests/test_bot_construction.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/tests/test_bot_mentions.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/tests/test_conversation_watch.py \
  /home/codexy/deepseek/dame-curie-worktrees/remove-companion/tests/test_prompt_storage.py
```

Sanity verdict: no blocker found in the assigned diff. No new helpers, exception wrappers, type escapes, validation, logging or unrelated refactor. Existing large functions were narrowed, not broadly rewritten. No linter, JavaScript parser, application import/execution, test execution/collection or Discord client initialization was performed. No private configuration/state/log reads, installs, network, Docker, sudo, services, Screen or nested agents. Local commits use disabled hooks; nothing was pushed or deployed.

## Remaining integration edges

1. Reconcile overlapping hunks with the Twitter/Telegram, API/web and deployment lanes: `bot.py` credential registration and constructor area; `config.py`; public env examples; `control_defaults.py`; `ecosystem.config.js`; existing prompt-storage/constructor fixtures. This branch deliberately leaves their non-companion behavior intact.
2. The coordinator owns the final `!` prefix pass. The primary configured prefix and existing comma fallback were intentionally not changed here.
3. Private V2 settings and persisted source-default personality may still contain removed keys or the old Uni paragraph. Coordinator-only reconciliation must remove only account-specific defaults, not user-authored relationship text or ordinary memories. No private migration happened here.
4. Any persisted old PM2 `dame-curie-gf` definition must not be relaunched after integration: with the persona switch removed, an obsolete second invocation could consume the primary token/data path. Removing a source entry does not remove an already-saved process definition. No process inventory or lifecycle action was authorized or attempted.
5. Independent parent/integration review and separately authorized synthetic functional acceptance remain. Compilation does not establish Discord, provider, memory, voice or deployment correctness; Discord activation remains prohibited.
