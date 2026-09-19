# Web/API removal — source-only slice

Date: 2026-09-19. Base: `43ce047`. Branch: `work/remove-web-api-20260919`.
Worktree: `/home/codexy/deepseek/dame-curie-worktrees/remove-web-api`.

## Implemented

- Deleted `api/`: inbound dashboard/admin HTTP routes, Basic/OAuth authentication, API configuration/storage adapters, API-only control sanitizers, site KV/item endpoints and site HTTP/WebSocket proxying. No replacement API.
- Deleted `site_backend.py`, `site_server.py`, `site_test.py`: local KV/item storage machinery, generated Python server/container lifecycle and browser/server testing machinery.
- Deleted `web/index.html` and `web/admin/index.html`. These are the application landing/dashboard pages, not generated authoring directories or publisher assets. No `api.env.example` was present among tracked source files.
- Removed only API bind/CORS and dashboard username/password attributes from `Config`, plus its obsolete missing-dashboard-password warning. Removed API/OAuth/trust-proxy fields from `.env.example`; retained application/env paths, local authoring root, publication URL fields and the Discord owner allowlist. Outbound provider keys and HTTP client dependencies are unchanged.
- Preserved the sole non-serving production consumer of `site_server`: `knowledge_graph.refresh_site` now resolves the existing `DATA_DIR/site_servers/<slug>` authored-source directory inline. It retains the original 2–30-character slug acceptance, container-mode `/state/data` requirement, `confined_path` symlink/traversal restrictions, optional-directory behavior and existing error containment. There is no server import or new serving abstraction.

## Reverse-consumer evidence and preserved seams

References below describe base `43ce047` unless noted.

| Source seam | Evidence / disposition |
| --- | --- |
| `api.state`, `api.storage`, `api.config`, `api.auth` | No production Discord/core consumer imported them. API routes and API-specific fixtures consumed them; `deep_test_harness.py` imported the API sanitizer. Those adapters do not own the surviving bot implementations. |
| Control/prompt/state/notification infrastructure | The initial commit leaves `control_defaults.py`, `prompt_storage.py`, `utils.py` atomic writes/FileLock, `inbox.py`, `error_reporting.py`, `rem.py`, `rag_memory.py` and Discord implementations untouched. The follow-up below removes only three obsolete site controls and the bot's site lifecycle hooks. API endpoint removal is not memory/state deletion. |
| `knowledge_graph.py:640–677` | `refresh_site` imported `site_server` only to call `code_dir`; the path-only logic is relocated into that existing caller. `index_site`, site title/owner metadata, static directory and public URL construction are unchanged. |
| `bot_tools.py:1230–1284` | `_public_image_target` and `_persist_public_image` retain `<DAME_CURIE_SITE_DIR>/_images`, `<DAME_CURIE_PUBLIC_BASE_URL>/bot/_images`, image filenames and redacted matching `.txt` prompt sidecars. No media writer is changed here. |
| `scripts/publisher/scan.py:123–169` | Existing scanner treats ordinary top-level site directories separately from `_images`; archived images and matching prompt sidecars remain its inputs. Source inspected only. |
| `scripts/publisher/mirror.py:36–48` | Existing site synchronization and append-preserving image archive synchronization (`delete=False`) remain untouched. No remote destination/configuration was read or changed. |
| Plugins and static assets | `plugin_manager.py` and active `plugins/` have no API/site-module import dependency. `plugins/checkers/`, `assets/tokenizers/` and their consumers remain unchanged. |
| Filesystem layout | No generated content, private state, site root, archive, database, publisher template/configuration or remote object was read, moved or deleted. Existing authored `site_servers/` content remains addressable for graph indexing; removing the server module does not remove its disk directory. |
| Shared confinement | `docker_runtime.container_mode`, `docker_runtime.confined_path`, `docker_runtime.STATE_ROOT` remain the import contract for graph path confinement. Other lanes must preserve these non-serving helpers or coordinate an equivalent relocation. |

## Existing fixture alignment

Deleted fixtures devoted entirely to removed HTTP/server behavior:

- `test_api_corrupt_writes.py`, `test_api_rem.py`, `test_container_api.py`
- `test_backend_error_reporting.py` (site lifecycle and API incident adapters; shared incident implementation/tests remain)
- `test_control_sanitize_ranges.py`, `test_extract_timeout.py` (API sanitizer consumers, not bot-side implementations)
- `test_site_backend_api.py`, `test_site_server.py`, `test_site_test.py`, `test_site_test_render.py`

Removed only API-specific cases/request fixtures from `tests/test_inbox.py` and `tests/test_prompt_storage.py`. Preserved direct inbox, voice, prompt-store, file-lock and Discord prompt-tool coverage. Removed the local backend suite and API sanitizer case/imports from `deep_test_harness.py`; retained its existing default-control case under a control-only name. No new tests or assertions were added.

## Coordinated integration requirements

This branch is one parallel removal slice, not a runnable integrated release. Early messages to the coordinator identified these separately owned consumers:

- The bot's site module imports and reconciliation/profile-sweep/expiry destruction loop are removed in the follow-up below. Tool class imports/registrations/catalogs remain shell-lane ownership; active prompt/result handling remains coordinated integration work. Preserve shared Discord state, memory, media and notification behavior.
- Shell lane: remove site tool classes and `site_*` imports in `bot_tools.py`, schema/registry entries, their site-only fixtures and site-specific tool-error cases. Preserve image persistence, asset saving, URL constructors and local authoring paths. Mixed `test_site_public_urls.py` also has obsolete API/CORS/OAuth expectations.
- Deployment lane: remove Compose/Dockerfiles/Caddy/lifecycle serving references and deployment fixtures. `doctor.py:95–98` directly reads the removed `Config.DAME_CURIE_ADMIN_PASSWORD` and must lose that check. The `aiohttp` client must remain; its old requirements comment can be updated without changing the dependency/pin.
- Coordinator: align the synthetic constructor fixture (the bot's obsolete dashboard-password registration is removed in the follow-up); reconcile shared `.env.example`/`config.py` edits, deep-harness social removals, active docs/comments and command-prefix changes after integration. No private configuration was inspected here.

## Validation and limits

- Loaded `implement-tyranny` and `implement-sanity`; reviewed surviving-source diffs, deletion scope and reverse imports. No new helper module, exception handler, validation layer, logger, dependency or server was introduced. The relocated graph restrictions are existing behavior, not additional policy.
- Explicit interpreter reports **Python 3.14.4**.
- Compile-only succeeded for exactly `config.py`, `deep_test_harness.py`, `knowledge_graph.py`, `tests/test_inbox.py`, `tests/test_prompt_storage.py` using `/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/remove-web-api/.validation-cache -m py_compile` and absolute source paths.
- `git diff --check` passed. No application/test import, execution, collection, linter, type checker, new test, dependency installation or build was performed. Compile success is syntax evidence only.
- No Docker, sudo, service, Screen, network, private configuration/state/log access or nested agent was used. Publisher code/config/templates and image mirror are unchanged. Deployment effects: **none**.
- Existing generated pages that depended on removed local `/api/site/...` or per-site `/bot/<slug>/api/...` endpoints will no longer have those endpoints after deployment. Their files are preserved, not rewritten or secretly routed elsewhere. Functional publication/Discord/media acceptance remains a separately authorized integration task.

## Follow-up: remove bot-local lifecycle hooks

Separately assigned after initial commit `d63f23c`; no earlier commit rewritten.

- `bot.py`: removed the three `site_backend`/`site_server`/`site_test` module imports, the single `_site_cleanup_loop` task registration, `_site_cleanup_loop`, `_site_expired`, `_cleanup_sites` and its nested registry writer. This removes startup backend reconciliation, periodic browser-profile sweeping, TTL expiry deletion of authored files/backend state/containers, and the associated site-metadata rewrite. No historical/private metadata or content was inspected or changed.
- Removed only `DAME_CURIE_ADMIN_PASSWORD` from the explicit incident-secret registration tuple. Other provider/transport credentials and shared error reporting remain intact.
- Exact retired `DEFAULT_CONTROL` keys: **`create_site_quota_per_user`**, **`site_ttl_hours`**, **`site_inject_csp`**. They are now in the existing `DEAD_CONTROL_KEYS` set, so `_load_control` drops persisted values rather than reviving obsolete active settings. No new migration or state write was added.
- Caller evidence: quota and CSP settings were read only by the removed `CreateSiteTool`; TTL was read by the removed bot expiry predicate and site-tool lifetime labels. Scoped searches found no surviving shared/core/plugin/publisher consumers or additional server-quota control defaults. Shell lane owns removing its obsolete TTL/CSP helpers and fixtures.
- Preserved `_load_sites`, the `_backfill_site_graph` task, all authored-file graph indexing, `DAME_CURIE_SITE_DIR`/publication URL construction, `_images` and other asset writers. `shutil` remains imported because TTS still uses `shutil.which` for espeak detection. Shared memory cleanup/control reload/command/Discord-state/REM tasks are unchanged. Six site-tool class imports/registrations/catalog entries and generic Guide placement were not edited.
- Reviewed the complete two-file Python diff and report changes. Compile-only passed exactly `bot.py` and `control_defaults.py` with the same isolated Python3.14 command and worktree-local cache documented above; `git diff --check` passed. No new tests, application imports, execution, collection, private reads, service actions or publication occurred. Deployment effects remain **none**.
