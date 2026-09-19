# Discord source boundaries — implementation handoff

## Scope and ordered commits

Worktree: `/home/codexy/deepseek/dame-curie-worktrees/source-boundaries`.
Branch: `work/source-boundaries-20260919`.
Base: `2e340003633f5d252c0fe968a80530a56bdb1338`.

1. `b00b5b070d22ce67a1daf18efe8550e03b4733f2` — Normalize Discord prefixes and retire stale site-tool paths.
2. `49226a81383e01c9f9c631ff538b23236f356a0f` — Separate source-owned tool contracts from personality assembly.

Loaded `implement-tyranny` and `implement-sanity`; the parent approved the minimal module boundary before extraction. No nested agents, runtime operations, installs, builds, network requests, migrations, private configuration/state/log reads, or application/test execution occurred.

Inspection-scope deviation: one root-level grep using the basename filter `{README,SECURITY}.md` unintentionally returned matches from `legacy/v1/README.md`. That search was stopped; no archive path was followed or modified and those results were not used for implementation. Subsequent README/SECURITY checks used exact files. This is not a claim of zero archive reads.

## Prefix and stale-capability slice

- Canonical constructor/default/fallback prefix is `!`, including the operator-message isolation fallback. Existing environment/config overrides and command parsing remain intact. Main command help interpolates the configured prefix; source examples, tool descriptions, other literal command recipes and active comments use canonical `!`.
- `.env.example` and `docker/bot.env.example` expose `COMMAND_PREFIX=!`. Discord credentials remain blank; Docker example RAG remains false. No provider/model/credential defaults changed.
- Removed unused `ENABLE_CREATE_SITE` configuration, feature-report entry and example. The generic `guide` tool remains registered independently; its unavailable message no longer blames that deleted switch. No surviving dashboard-login command wrapper was found; removed the help advertisement for dashboard login, not Discord SDK login or administration.
- Removed `_auto_route_html_to_site`, its sole final-reply caller, `_looks_like_site_request`, `_SITE_REQUEST_RE`, `_looks_like_html_document` and `_HTML_DOC_HINTS` after caller inspection.
- Removed `site_loop_strikes`, `finish_site_turn`, the site-specific forced-final provider branch and failed-site final-reply fallback. Generic iteration/deadline budgets, acknowledgement follow-up allowance, native assistant/tool-result pairing and tail trimming remain.
- Removed the deleted `create_site` progress-field entry and `_SITE_RESULT_TOOLS` truncation exception, including its now-exclusive name map/argument. Generic truncation still strips extracted inline image/audio payloads only after gathering media; native results retain their tool-call IDs.
- Source-owned tool instructions no longer advertise create/edit/test/server tools or Python/PHP/Perl/CGI deployment. The narrow replacement states shell authoring of local files, external publication, no local hosting and no model-driven remote administration. Existing qualitative authoring/personality policy remains for root to tune.

Changed paths in commit 1:

- `.env.example`, `docker/bot.env.example`
- `autonomy.py`, `bot.py`, `bot_tools.py`, `config.py`, `control_defaults.py`
- `deep_test_harness.py`, `jobs.py`, `message_pipeline.py`, `operator_commands.py`
- `plugin_manager.py`, `prompt_storage.py`, `providers.py`, `rag_memory.py`, `rem.py`
- `tool_progress.py`, `tool_registry.py`
- `tests/test_bot_construction.py`, `tests/test_command_formatting.py`

`providers.py` changes are comments/docstrings only. `prompt_storage.py` changes only its module description. `bot_tools.py` changes only server-prompt command wording. No publisher, lifecycle, migration, installer, build implementation, dependency pin, `docker_runtime.py` or its fixtures changed.

## Minimal tool-prompt boundary

Commit 2 changes `bot.py` and adds `tool_prompts.py` (213 lines):

- `DISCORD_CAPABILITIES`: the existing explicit inbox/admin block, concatenated in its original position in `MAXWELL_BASE_KNOWLEDGE`. Identity substitution and surrounding persona text/order are unchanged.
- `TOOL_PROTOCOL` and `LEAN_TOOL_PROTOCOL`: moved from bot after the first slice's authorized capability cleanup; both remain importable from `bot` for existing fixtures.
- `tool_system_prompt(names, descriptions, *, native)`: renders already-selected names and plain descriptions using the existing `tool_schemas.contract_groups` and `result_contract`. No bot, personality store, provider or configuration object crosses this boundary.
- `custom_tool_prompt(names)`: extracts only the existing incremental JSON wire-format instruction.

`bot._tool_system_prompt(platform="discord", *, message=None, content=None)` remains the entrypoint adapter. It still performs the same tool-enabled/empty checks, preserves registration order, uses the same caller-scoped plugin selection and admin filter, and obtains descriptions only for non-native mode. Native descriptions remain in the existing `tools=` payload. XML catalog/form, custom JSON text and insertion order remain unchanged. The custom path retains its existing name order and disabled-tool filtering; no wire-format redesign was attempted.

`bot._get_personality()` and `PromptStore` behavior are unchanged: live configured storage, retain-valid semantics, fallback defaults and dynamic age injection stay where they were. Foreground prompt ordering remains base knowledge/chat protocol, originating-server instructions, core personality, existing static additions/tool contract, transcript and dynamic context. No tools were inserted into voice, onboarding, REM or autonomy consumers. Voice/onboarding still call `_get_personality`; autonomy still uses its existing personality adapter and separate planner/tool descriptions. RAG/REM, security/confirmation, access context, plugin/game hints and native dispatch remain intact.

The reviewed pending job-routing commits were inspected through public `job-routing/jobs.py` only. Their `background_messages` uses `_get_personality`, originating-server prompt and the unchanged `_tool_system_prompt` signature. This lane does not implement routing or rewrite that lifecycle. Parent should integrate routing **after** these source commits and retain the reviewed routing lane's replacement background messages when resolving the wording-only `jobs.py` overlap.

## Preserved consumers and meaningful remaining references

- `_load_sites` remains the reader for `sites.json`; startup, control refresh and `knowledge_graph.refresh_site` still call it. `_backfill_site_graph` and authored-source graph/history remain. `knowledge_graph.py` still reads historical `site_servers/<slug>` sources with the existing container/path checks; this is not a serving replacement or new registry writer.
- Shared HTML/JSON leak parsing and quote repair remain. Their historical `create_site` examples explain parser regressions rather than advertise tools. The deep harness's XML recovery payload likewise remains a generic synthetic parser sample, independent of the active schema registry.
- `create_site_quota_per_user` remains in `DEAD_CONTROL_KEYS` to suppress old stored controls, not activate a capability. Historical progress examples and the old `,auto` tombstone remain historical. Generic authoring/task words in `_ACTION_TOOL_HINT_RE` were not name-match-deleted.
- Explicit custom comma-prefix fixtures in `tests/test_rem_commands.py` and `tests/test_bot_mentions.py`, plus the multi-character prefix fixture, were preserved. Remaining commas in CSV/JSON/MIME/filter expressions were not changed.
- Generic file/URL delivery, attachments, progress finalization, suppression, taint/confirmation, permissions, reasoning traces, media extraction and image persistence/public URLs/sidecars remain. Namespace/privacy filters were not removed; the historical `tg:%` exclusion remains.
- Plugin source/manifest and `rem_defaults.json` needed no command-reference changes. No comma-command recipes were found in the inspected exact root README/SECURITY, active `docs/`, or non-publisher source script references (`instance`, `instance_backup_compat`, `checkout_snapshot`, `set_env`, `migrate_instance`, `build_for_human`, root setup/install). No script implementation was edited or executed. Historical evidence was not globally rewritten.

## Existing fixture alignment only

- `tests/test_command_formatting.py`: existing VC help expectation now uses `!vc`.
- `tests/test_bot_construction.py`: removed the deleted feature's synthetic environment entry.
- `deep_test_harness.py`: canonical prefix example/expectation now `!`; removed `create_site` from its existing registry-schema sample list; deleted three assertions for the retired nested-shell command denylist and relabeled that existing case. Empty-input, ordinary-command, heredoc and normalization assertions remain. The generic XML parser sample remains.
- No new tests, cases or assertions. No collection/execution. Existing prompt-fixture imports/method seams remain compatible by source inspection; no extra setup imports were needed for extraction.

## Packaging and acceptance gates

Parent owns adding `tool_prompts.py` alongside `job_routing.py` to `docker/app.Dockerfile` COPY and `docker/app.Dockerfile.dockerignore` allowlist. The constructor fixture copies the latter allowlist, so that packaging update also supplies the new module to its synthetic source tree. This worktree intentionally leaves packaging untouched.

Existing private V2 stored source-default prompts/configured prefixes may need the coordinator's separately authorized mechanical reconciliation; no private files were inspected or migrated here. Root's persona/authoring policy tuning remains deferred. No new custom-prompt format/UI, registry writer, API, local server, remote administration or package installation was introduced.

Validation performed:

- Full actual diffs reviewed for each source commit; `git diff --check` and staged equivalents passed.
- Explicit compile-only commands passed with the supplied Python 3.14.4 interpreter and isolated cache prefix:

```sh
/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/source-boundaries/.validation-cache -m py_compile autonomy.py bot.py bot_tools.py config.py control_defaults.py deep_test_harness.py jobs.py message_pipeline.py operator_commands.py plugin_manager.py prompt_storage.py providers.py rag_memory.py rem.py tool_progress.py tool_registry.py tests/test_bot_construction.py tests/test_command_formatting.py
/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/source-boundaries/.validation-cache -m py_compile bot.py tool_prompts.py
```

Sanity review: no new exception wrappers, type escapes, validation, logging machinery or oversized hidden helper. New renderers are typed, documented and used. Existing large legacy functions were not refactored beyond the requested removals/adapter.

These are **source/static checks, not behavior acceptance**. Tests, application imports, Discord/provider calls, image builds, real file publication, voice/media operation, tool-loop execution, private configuration reconciliation and V2 runtime isolation/activation remain untested here. Discord blank, RAG false, no bot/Ollama/model-pull starts, publisher untouched remain coordinator holds.
