# X / Telegram source removal

## Scope and baseline

- Worktree: `/home/codexy/deepseek/dame-curie-worktrees/remove-social-transports`.
- Branch: `work/remove-social-transports-20260919`; clean starting HEAD `43ce047d9d5985a78a9cf3899e0302acc36383d6`.
- Root explicitly approved both removals. Read `AGENTS.md`, the approved redesign plan and the four orientation documents; loaded `implement-tyranny` and `implement-sanity`.
- This is source-only implementation, not runtime or deployment acceptance.

## Removed surface and consumer trace

| Surface | Removal |
| --- | --- |
| X implementation | Deleted `x_client.py`: cookie/API/RSS/syndication backends, tweet normalization/rendering, GraphQL overrides, post budget, mention poller and X state-file consumers. |
| Bot X wiring | Removed imports, construction, tool registration, mention task scheduling, shutdown, admin command authorization/dispatch/help/handler, control reloading and X-specific tool-intent hints. |
| Model interface | Removed `XReadTool` / `XPostTool`, schemas, result-tool entries and known-tool catalog entries. No replacement names, aliases or shims. |
| Autonomy | Removed only the `x_post` / `x_autonomy_post` hook. Retained autonomy lifecycle, tool enable/disable policy, permission boundaries and Discord behavior. |
| Telegram | Removed message/channel/user/typing adapters, HTML chunking, webhook server and registration, polling, per-chat locks, audio ingestion, Telegram prompt/history/retrieval/tool-loop wrappers, startup and companion-only token suppression. |
| Shared delivery seams | Removed Telegram compatibility allowlist, progress fallback and the TTS `send_voice_file` adapter branch. Discord voice flags/waveform, conversion, provider selection and temporary-file lifecycle remain. |
| Configuration / diagnostics | Removed X and Telegram environment settings, feature reports and warnings, incident credential enumeration for removed settings, X doctor checks and dedicated deep-harness suite. Generic credential handling and JSON parsing remain. |
| Inbox | Removed X mention priority/render override and per-kind cap entry. Retained the store, generic per-kind rendering machinery, notifications, decisions and read/announce lifecycle. |
| Build / examples | Removed only the `x_client.py` COPY/allowlist entries and X/Telegram example settings. No dependency pins changed. |
| Existing fixtures | Deleted `tests/test_x_client.py` and X/Telegram-specific cases. Renamed the retained generic cases from `test_x_integration.py` to `test_tool_gates.py`; these are existing taint/confirmation/chat-gate checks, not new tests. Aligned existing TTS fixtures to the already-established Discord HTTP `send_message(..., params=...)` seam, preserving their prior no-channel cooldown behavior where applicable. Removed obsolete control stubs; retained generic non-Discord boundary fixtures with synthetic platform values. |

## Preserved edges

- Generic Twitter Card/OpenGraph extraction in `bot.py` and `tests/test_see_image.py`, including the shared `html` import. Generic URL fetching, HTTP clients, saved media/images, audio, video, YouTube and image tools remain.
- All publisher/syncer/archive/image replication implementation, local authoring roots and public URL selections are unchanged. No files under `scripts/publisher/` were touched.
- Discord administration, autonomy, games, plugins, provider routing and main conversation/context behavior remain. Removed Telegram-only wrappers did not remove their shared graph, RAG, cross-context, inbox, sanitization or tool-dispatch implementations/callers.
- RAG/REM/graph modules are unchanged. In particular, `rag_memory.py:2737` retains `channel_id NOT LIKE 'tg:%'`: this excludes legacy private-chat rows from cross-channel LTM summarization. Removing that privacy filter would widen historical-data exposure; it does not activate or emulate a transport.
- Shared taint/confirmation, incident handling, JSON utilities, notifications and redaction remain. No email integration was restored; stdlib HTTP-date parsing was not changed.
- Companion and shell/site features were not independently removed or refactored here; only their X/Telegram-specific intersections changed.

## Checks and sanity review

- Scoped source searches covered root Python modules, plugins, examples, Docker sources and non-publisher lifecycle/log-console sources. Remaining root social-name matches are generic metadata, the legacy privacy filter and the separately owned deleted site-server credential consumer.
- Reviewed source and fixture diffs, retained call paths and import consumers. No new production helper, exception handler, validation, dependency, type escape or compatibility layer was introduced.
- `git diff --check HEAD`: passed.
- Interpreter: `/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B --version` reported Python **3.14.4**.
- Explicit `py_compile` on all **27** changed surviving Python files passed using that interpreter with `-I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/remove-social-transports/.validation-cache -m py_compile`. Generated validation files were not staged.
- No application/test imports, tests, collection, new test cases, installs, builds, network requests, Docker, sudo, services, Screen, private configuration/state/log reads or nested agents. No runtime changes.
- Sanity verdict: ready for cross-lane source integration; functional behavior is not validated by compilation.

## Integration risks / coordinator handoff

1. Merge shared-file hunks narrowly, especially `bot.py` constructor/help/lifecycle, `bot_tools.py`, `config.py`, `control_defaults.py`, schemas, Docker COPY lists and retained fixtures. Do not resurrect X/Telegram while resolving companion, shell/site, logging or deployment conflicts. Parent owns the final command-prefix and shared-documentation pass.
2. Separate web/API lane owns legacy consumers still present in this isolated baseline: `api/state.py:235–242` X control clamps, `web/admin/index.html:1386–1393` X controls, `api/api_server.py:2506` and `site_server.py:922` special `X_CT0` redaction, and their backend-only fixtures. These modules are slated for deletion; this lane deliberately did not refactor them.
3. Existing private X budget/cursor/GraphQL data, old settings/prompts/inbox notices and Telegram conversation history were not read, migrated or deleted. Obsolete keys have no active feature consumer after integration; old generic stored content is not silently rewritten. Any coordinator-authorized V2 settings cleanup must remain separate from V1.
4. A previously registered Telegram webhook is not remotely unregistered by this source change: there is no runtime/network grant. Any account-side cleanup needs explicit separate authority.
5. Build, constructor, tool/media behavior and private-state isolation need separately authorized acceptance after all lanes integrate. No bot start, Discord login, provider request or publishing action was attempted.
