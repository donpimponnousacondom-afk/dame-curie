# 02 — Verified evidence ledger

Everything in this file was checked directly by the coordinating auditor against the working tree and Git
metadata at HEAD `c603cf2` (branch `dev/phaseII_v2`) on 2026-09-24 between 21:04 and 23:10 UTC.
Nothing here comes from a child agent's report; child claims are in `child-reports/` with dispositions in
`01-AUDIT-REPORT.md`.

Boundary honoured: read-only inspection only. No application import/execution, no test collection or
execution, no dependency installation, no Docker/service/Screen access, no reads of `.env`, `bot.env`,
data, logs, databases, credentials, `/srv`, `/opt`, `/var/backups`, or `legacy/`.

## E1. Repository state

| Item | Observation |
| --- | --- |
| HEAD | `c603cf2` "Record reasoning containment, audits and recovered Dirac viewer" |
| Branch | `dev/phaseII_v2`; `main` is 126 commits behind, 0 ahead |
| Working tree | 24 files under `legacy/` deleted on disk, **unstaged, uncommitted** (`git diff --stat -- legacy` → 24 files, 3,970 deletions). The directory itself no longer exists. |
| Untracked | `.agents/skills/root-review-reports/`, `reports/` (both pre-existing, unrelated to this audit) |
| Ignored but present | `/audit/` (gitignore line 138), `__pycache__/` (two `.pyc` files dated 2026-09-23 15:25–15:27 local for `provider_telemetry` and `response_observability`), `.validation-cache/` (compile-only `py_compile` cache from 2026-09-19; documented practice in `phase-II_v2/*_IMPLEMENTATION.md`) |
| Stash | empty |
| Worktrees | 26 total: main checkout, one stale T3 worktree at `e4e4582` (`t3code/adversarial-project-audit`, 15 behind, clean), two detached (`prefix-review` @ `b00b5b0`, `tool-prompt-review` @ `49226a8`, both contained in `work/source-boundaries-20260919`), 22 `work/*` worktrees under `/home/codexy/deepseek/dame-curie-worktrees/` |

### Unintegrated patches on `work/*` branches (`git cherry dev/phaseII_v2 <branch>`, `+` = patch-id not in dev)

| Count | Branch | Nature (subjects) |
| --- | --- | --- |
| 12 | `work/dirac-smoke-runtime` | "offline operator queue protocol", operator CLI, protocol docs — superseded by `work/dirac-smoke-lean` (0 unintegrated) |
| 5 | `work/dirac-hardening-smoke` | honest completion, notice provenance, actor refresh — overlaps R2/R3 later re-implemented as `dfc6141`/`acf5da9` |
| 3 | `work/dirac-hardening-jobs` | blocked-parent progress-thread placement — overlaps `65fe79e` |
| 2 | `work/dirac-hardening-ops` | writable smoke-mount refusal / read-only path canonicalisation |
| 2 | `work/dirac-attachment-limits` | docs only |
| 1 each | `dirac-hardening-relay`, `remove-social-transports`, `remove-companion`, `prune-email`, `openai-inference-names`, `job-routing`, `discord-only-deploy`, `direct-shell-tools` | mostly worktree-local report/doc commits whose content was cherry-picked or rewritten |
| 0 | remaining 8 branches | fully integrated |

No determination was made here about whether the differing patches were deliberately superseded; that is for the implementing agent/root to confirm before pruning.

## E2. Commit timeline (UTC) and live-replacement latency

Commit times from `git log --date=format-local` with `TZ=UTC`. Replacement times from `docs/STATUS.md` / `phase-II_v2/DIRAC_HANDOFF.md` / `audit/*.md` (ledger statements, not independently observed).

| Commit | Committed (UTC) | Kind | Ledger says live replacement began | Commit→live |
| --- | --- | --- | --- | --- |
| `723e7d8` longprompt | 2026-09-24 07:37 | source + new test file | included in later 4e4027a rollout | — |
| `085c95b` taint gate removal | 09:16 | source | included in later 4e4027a rollout | — |
| `4e4027a` image unification | 09:57 | source | recorded as rolled out in `33aae2d` committed 10:10 | ≤ 13 min |
| (private) `OPENAI_MAX_TOKENS` 115200 → 12345 | — | private profile edit | 15:18:25 restart | — |
| `74d827d` incomplete-output terminal | 15:41 | source | 15:43:18 | **~2 min** |
| (private) reasoning effort → low | — | private control edit | 18:34:29 hot reload | — |
| `6859025` bounded tool log + `--fresh` | 18:57 | source | 19:04:46 | **~7 min** |
| `c603cf2` ledger | 19:12 | docs | — | — |

Three source releases and two private setting changes to the live temporary instance in one calendar day (2026-09-24), each following an incident observed the same day (image profile break, 115,200-token runaway, console freeze).

## E3. Ledger provenance claims that were verified

| Claim (ledger) | Check | Result |
| --- | --- | --- |
| `74d827d` exact tested tree `516c90e0…` | `git rev-parse 74d827d^{tree}` | **MATCH** |
| `6859025` exact tested tree `1c85c6d1…` | same | **MATCH** |
| `162b39c` exact tested tree `6e9d2d7f…` | same | **MATCH** |
| `74d827d` "No new test functions or files" | `git show 74d827d -- tests` | 4 `def test_` removed, 4 added (renamed/re-parameterised): net 0, claim defensible |
| `6859025` "No new test functions or files" | same | 2 removed, 2 added with new parameters: net 0, claim defensible |
| `4e4027a` | same | 31 removed, 31 added; whole image test surface rewritten |
| `085c95b` | same | 6 removed, **1 added**: `test_dispatch_allows_shell_after_fetch` (asserts the removed gate is absent) |
| `723e7d8` | `--diff-filter=A` | **new file** `tests/test_longprompt_command.py` (15 test functions, 417 lines) |
| `162b39c` | same | **new file** `tests/test_smoke_protocol.py` (13 test functions) |
| `dfc6141` | same | **new file** `tests/test_final_delivery_round.py` |

Image digests, container IDs, Discord login receipts and test pass counts in the ledger were **not** verifiable under this boundary and are reported as ledger statements only.

## E4. Source constants and control flow anchors verified by reading

| Anchor | Fact |
| --- | --- |
| `control_defaults.py:172-173` | `max_tool_iterations: 50`, `tool_iteration_timeout_seconds: 3600` |
| `bot.py:12823-12831` | `max_iters = clamp(control, 0..100)`; `tool_deadline = monotonic + timeout` |
| `bot.py:12853-12856` | deadline checked **only at the top of each iteration**; an in-flight provider call is not bounded by it |
| `tool_schemas.py:1673-1675` | `TOOL_TAIL_MAX_MESSAGES = 12`, `TOOL_TAIL_MAX_CHARS = 36_000`, `TOOL_RESULT_COMPACT_CHARS = 4_000` |
| `tool_schemas.py:1709-1725` | `trim_tool_tail`: eviction `while` loop runs first; `_compact_old_tool_results(groups)` runs after (drop-before-compact confirmed) |
| `tool_schemas.py:1749-1767` | `elide_tool_calls_for_history` heavy keys = `body, content, code, html, data`; `reasoning` is **not** elided |
| `tool_schemas.py:874-886` | `reasoning` forced into `required` for **every** tool schema |
| `tool_schemas.py` `TOOL_PARAMETERS` | 70 static entries (`grep -c '^    "[a-z_]*": _obj('`) |
| `bot.py:13906-13931` | `_MAX_TOOL_RESULT_CHARS = 32_000`, head/tail split per result |
| `bot.py:14717-14747` | `_apply_prompt_budget` trims system blocks, then first, then last message content |
| `providers.py:1080-1082` | SSE: `finish_reason == "length"` → raise `ProviderIncompleteResponseError` immediately |
| `providers.py:2834-2835` | JSON: same check **before** the message is inspected |
| `providers.py:2848-2861` | empty content + no `tool_calls` + any reasoning field → raise incomplete |
| `providers.py:3009-3014` | `except RuntimeError`: incomplete → `incident.capture` then `raise` (no `_retry_after_attempt`) |
| `providers.py:1248-1249` | `ProviderIncompleteResponseError(ProviderResponseError)`; `ProviderResponseError(RuntimeError)` |
| `bot.py:13236-13268` | `_handle_message` catches `CancelledError`, `ProviderUsageExhaustedError`, `ProviderEmptyResponseError`, then generic `Exception` → `send_public_error` |
| `error_reporting.py:24` | `PUBLIC_ERROR_TEXT = "I waited, waited and I am losing things like tears in the rain 🕊️"` — the only user-visible signal for an incomplete response |
| `operator_commands.py:44-46` | `send_public_error` honours `error_replies` control (default `True`, `control_defaults.py:47`) |
| `bot.py:6391-6394` | `_handle_command`: `content.split(maxsplit=1)`; `args = None` when no argument text |
| `bot.py:6533-6545` | `prompt`: entire prompt sent in one `channel.send` inside a code fence; usage hint hard-codes `` `!prompt <text>` `` instead of `self.command_prefix` |
| `bot.py:631` | `TEXT_ATTACHMENT_MAX_BYTES = 512 * 1024` |
| `config.py:34-37` | `ENV_FILE` from `DAME_CURIE_ENV_FILE` else `APP_ROOT/.env`; `load_dotenv(ENV_FILE, override=True)` **at import time** |
| `config.py:194-195` | `OPENAI_MAX_TOKENS` default 16384, max 131072; `.env.example:46` documents 8192 |
| `config.py:482-502` | `Config.validate()` raises unless `IMAGE_GEN_PROTOCOL == "images"`; `IMAGE_GEN_MODELS` strict JSON object; `IMAGE_GEN_MODEL` must be a key |
| `config.py:379` vs `.env.example` | `IMAGE_GEN_QUALITY` default `"low"` in code, `high` in the example file |
| `tests/test_tool_progress.py:735-760` | live-provider test still parses `../.env` into `os.environ` and calls the configured endpoint; skip depends only on `OPENAI_BASE_URL` being unset |
| `pytest.ini` | no marker/deselect for that test; every QA run must remember to exclude it manually |
| `docker/app.Dockerfile.dockerignore` | `**` allow-list; `audit/`, `reports/`, `tests/`, `phase-II_v2/` cannot enter the app image |
| `.dockerignore` (root) | excludes `legacy/`, `phase-II_v2/`, `tests/` but **not** `audit/` or `reports/`; only relevant if a build ever bypasses the per-Dockerfile ignore file |
| `docs/STATUS.md` | 179 lines, 19 `##` sections; newest first; three "Previous same-day runtime" sections for 2026-09-24 alone |
| `bot.py:12246-12249` | `max_out_tokens` clamped to `min(OPENAI_MAX_TOKENS, 4096)` when `_is_short_live_turn` (unaddressed text < 80 chars, watch follow-ups, active conversation watch) |
| `providers.py:1675,1729` | `fallback_disable_reasoning=True` by default; the fallback endpoint is created with reasoning disabled |
| `providers.py:2893-2949` | empty-content recovery rotates to a non-cooling alternative endpoint within `empty_response_retries`; the new raise at `:2861` runs before it |
| `bot.py:2528,4543,6987-7013,8471-8487` | every reference to `_shell_whitelist`; none is on a tool-execution path; the `!shell` whitelist is inert |
| `bot_tools.py:5221` | `ShellTool` spawns with `env={**os.environ, "HOME": …}`; the process environment includes everything `load_dotenv(override=True)` loaded |
| `bot.py:14176-14191` | `_turn_tool_names` removes only `join_server` for non-admins; `shell` is offered to every author |
| `bot_tools.py:7667-7790` | `UpdateBasePersonalityTool` / `UpdateServerPromptTool`: no admin, owner or author check in either class |
| `compose.yaml:91` | bot service `restart: unless-stopped` (canonical); a construction-time `ValueError` becomes a restart loop |
| `config.py:248` | `ENABLE_IMAGE_GEN = _feature_env("ENABLE_IMAGE_GEN")` with no detector: `auto` means on |
| `bot_tools.py:1381-1382` | `if not refs: refs = self._attached_images(message)` |
| `bot.py:14815, 15287` | server prompt is appended to `system_parts`, which are joined into the **first** system message |
| `bot.py:14738-14741` | `_apply_prompt_budget` middle-trims that first message to `max(12000, budget // 3)` chars when the total exceeds the budget |
| `bot.py:14504-14506` | `_message_content_chars` is an alias of `tool_schemas.message_chars` (counts `tool_calls` arguments) |
| `bot.py:2262-2263` | `TokenBudgetTracker`: "Tracking only — daily-budget enforcement was removed" |
| `bot.py:13736-13738`, `rag_memory.py:1689,1760` | raw pre-truncation tool result stored as `tool_result` metadata via `json.dumps(metadata)` with no size cap |
| `bot.py:10152-10166` | `_split_response(text, limit=1900)` has no cap on the number of chunks |
| `tool_schemas.py:1717-1725` | compaction re-runs on already-compacted content; second pass rewrites the marker with `omitted ≈ len(marker)` |
| `phase-II_v2/SESSION_LOG.md` | no entry dated 2026-09-24; newest heading is "2026-09-23 — narrow review-fix implementation" |

## E5. Ledger statements that could not be checked (recorded as claims)

- All Docker image digests, container IDs, Screen session IDs, Discord login timestamps.
- All "N passed / M failed / K excluded" receipts.
- The 115,200- and 12,345-token incident token counts and timings (from the private provider dashboard and bounded Docker logs, per `audit/provider-incomplete-validation.md` and `audit/dirac-reasoning-audit.md`).
- Whether `legacy/` was deleted by root, by an agent, or by tooling: no commit, stash or ledger line records the deletion.
