# 03 — Dispositions of child-agent findings

Verdict key: **ACCEPTED** (coordinator re-read the cited control flow or metadata and agrees), **ACCEPTED
(estimate)** (reasoning sound, numbers are source-text estimates), **PLAUSIBLE** (kept, needs runtime or
private state), **DOWNGRADED**, **REJECTED**, **MERGED → id** (folded into a finding in `01-AUDIT-REPORT.md`).
Child reports are verbatim in `child-reports/`.

## Report A — provider incomplete-response path (Fable)

| Child item | Verdict | Report ID | Coordinator note |
| --- | --- | --- | --- |
| 1.1 no enclosing retry/failover after the re-raise | ACCEPTED (info) | — | Confirms the ledger's "no retry" claim inside the provider. |
| 1.2 `failure()`+`capture()` do not double-record | ACCEPTED (info) | — | `_merge_incident` body not read by either party. |
| 2.1 foreground: generic public error, ERROR-level traceback, cleanup complete | ACCEPTED (low) | MERGED → C-01 | Verified handlers at `bot.py:13236-13268`; preview deleted by `stop()`. |
| 2.2 follow-up round: side effects stand, then generic error | ACCEPTED (low) | MERGED → C-01 | |
| 2.3 other call sites (LTM, DM decision, VC, onboarding, watcher, autonomy, jobs, REM) | ACCEPTED (info) | — | jobs.py marks job `error` and posts the public text; no private content in the message. |
| 3.1 legitimate long text discarded; 4,096 clamp on short turns | ACCEPTED (high, combined) | MERGED → C-01 | Coordinator verified the clamp at `bot.py:12246-12249` and `_is_short_live_turn`. Frequency remains PLAUSIBLE. |
| 4.1 reasoning-only rule cannot misfire on custom markup / empty `reasoning_details` | ACCEPTED (info) | — | |
| 4.2 `reasoning_details` truthiness broader than `reasoning_content()` | ACCEPTED (low) | C-11 | |
| 5.1 no structured token telemetry survives an SSE `length` stop | ACCEPTED (medium) | C-12 | The metric that motivated the change is no longer recorded for the case it targets. |
| 5.2 raw streamed body kept uncapped in incident details | ACCEPTED (low) | C-13 | Pre-existing; made routine by the new raise. |
| 5.3 aiohttp connection release | PLAUSIBLE (info) | — | No action. |
| 6.1 reasoning-only `stop` now terminal for every model; fallback recovery bypassed | ACCEPTED (medium; high if the DeepSeek quirk is real) | C-14 | Coordinator verified `fallback_disable_reasoning=True` default (`providers.py:1675,1729`) and the recovery branch (`:2893-2949`). Documented as intended in `docs/STATUS.md:17`; flagged as a trade-off for root. |

## Report B — tool-loop economics (Fable)

| Child item | Verdict | Report ID | Coordinator note |
| --- | --- | --- | --- |
| 1 transformation table | ACCEPTED (reference) | — | Consistent with coordinator's own reading. |
| 2 drop-before-compact, incident-shaped example, 32k/36k ratio | ACCEPTED (high) | MERGED → C-02 | Child's example reproduces the observed 6-message request shape; ratio argument adopted. |
| 2 compaction marker not idempotent (wrong "N chars truncated" from 2nd pass) | ACCEPTED (low) | C-15 | Verified from `tool_schemas.py:1717-1725`. |
| 3 budget counts `tool_calls` args (refutes prior framing) but cannot trim them; `tools=` payload unbudgeted | ACCEPTED (medium) | C-16 | Verified alias at `bot.py:14504-14506`. |
| 4 catalog ≈75k chars/request; REASONING_PARAM ≈9-12% of it; `reasoning` replay un-elided | ACCEPTED (estimate) | C-17, MERGED → C-07 | Numbers are source-text sums, not measurements; direction and magnitude are credible (73 tools matches the incident). |
| 5 no aggregate per-turn budget; tracker is tracking-only; insertion point | ACCEPTED (medium) | MERGED → C-06 | Verified `bot.py:2262-2263` comment. |
| 6 398k-char recovery: synchronous regex on the loop; ~210-chunk delivery with no chunk cap; recovered args unbounded | ACCEPTED (medium) / chunk cap PLAUSIBLE | C-18 | Coordinator saw the `for i, chunk in enumerate(chunks)` loop with no visible cap at `bot.py:13152-13195`; `_split_response` internals not read. |
| 7 `all_tool_media` unbounded; 12 images re-attached every follow-up | ACCEPTED (medium) | C-19 | Verified `followup_images = all_tool_images` at `bot.py:12934`. |
| 7 `_remember_tool_call` stores raw `tool_result` uncapped in SQLite metadata | ACCEPTED (medium) / cap absence PLAUSIBLE | C-20 | Verified raw `line` at `bot.py:13736-13738` and `tool_result` in `meta_keys` (`rag_memory.py:1689`); did not read the insert path for a metadata size cap. |
| 7 dead `more_tools` expansion branch | ACCEPTED (info) | C-21 | |
| 7 others (llm_traces bounded, XML grouping, transcript budget) | ACCEPTED (info) | — | |

## Report C — longprompt / taint removal / image unification (Opus)

Boundary note: the child wrote and deleted a scratch copy of an old file under `/tmp`. No repository change; recorded.

| Child item | Verdict | Report ID | Coordinator note |
| --- | --- | --- | --- |
| A table (parsing cases) | ACCEPTED | — | Matches `content.split(maxsplit=1)` at `bot.py:6391-6394`. |
| A1 512 KiB prompt enters every system prompt unbounded | ACCEPTED, sharpened (medium, CONFIRMED path) | C-22 | Coordinator traced further: the server prompt joins the **first** system message (`bot.py:14815`, `:15287`); under budget pressure `_apply_prompt_budget` middle-trims that message to `max(12000, budget//3)` chars (`bot.py:14738-14741`), silently mangling identity, tool contract and server prompt together. |
| A2 `prompt` >2000 defect; helper exists; 512 KiB would be ~280 messages | ACCEPTED | MERGED → C-03 | Refinement adopted: view path should attach a file above ~1,800 chars; set path should acknowledge without echo. |
| A3 `docs/LONGPROMPT.md` uses `?` prefix | ACCEPTED (low) | D-03 | |
| B1 shell has no per-user authorization; `!shell` whitelist inert; full env inherited; docs claim otherwise | ACCEPTED (high) | C-23 | Coordinator verified: no reader of `_shell_whitelist` outside the command/load/save; `env={**os.environ,…}` at `bot_tools.py:5221`; `_turn_tool_names` filters only `join_server`. Predates `085c95b`; that commit removed the only same-turn web-read gate. |
| B2 personality/server-prompt rewrite tools lost the gate and have no admin check | ACCEPTED (medium) | C-24 | Verified no admin/owner/author check in either class body. |
| B3 stale "confirmation rules" wording in `jobs.py:499` and dated `phase-II_v2/` records | ACCEPTED (low) | D-04 | |
| B4 the removed gate was already partial | ACCEPTED (info) | — | Useful context for C-23. |
| C1 startup hard fail; canonical config likely affected; `restart: unless-stopped` loop; validate runs even when image gen disabled; malformed JSON breaks `doctor.py` | ACCEPTED (high) | MERGED → C-04 (upgraded) | Verified `compose.yaml:91`, `PROVISIONING.md:39`, `config.py:377,482-502`, `bot.py:2361`. Canonical config content itself is unknown (PLAUSIBLE). |
| C2 quality defaults disagree | ACCEPTED (low) | MERGED → C-05 | |
| C3 unconfigured image tool still advertised; auto = on; breaker churn; `docker/bot.env.example` lacks keys | ACCEPTED (low-medium) | C-25 | Verified `_feature_env("ENABLE_IMAGE_GEN")` has no detector. |
| C4 old private-URL refusal never existed; `abspath` symlink escape; downscale removed on edits | ACCEPTED (low/info) | C-26 | Symlink point is moot while shell is ungated (C-23). |
| C5 attachment fallback makes scratch generation impossible when the message has an image | ACCEPTED (low) | C-27 | Verified `bot_tools.py:1381-1382`. |
| C6 no `hd_image` alias; check private `disabled_tools` | ACCEPTED (low) / PLAUSIBLE | C-28 | Private control content unknown; implementer to check. |
| C7 schema injection safe | ACCEPTED (info) | — | |
| C8 empty-string optional args | PLAUSIBLE (low) | C-29 | |
| D dispatcher coherent | ACCEPTED (info) | — | |
| G1 new tests vs contract | ACCEPTED | MERGED → P-02 | |

## Report E — docs and process (Sonnet)

Independence note: this child read the coordinator's in-progress evidence file and cites it; its agreement on those points is corroboration, not a second source.

| Child item | Verdict | Report ID | Coordinator note |
| --- | --- | --- | --- |
| 1 cadence table; per-day counts (4 / 2 / 3+2); review artifacts post-date two of three 09-24 rollouts (mtimes) | ACCEPTED (high) | MERGED → P-01 | mtimes are a signal, not proof; recorded as such. |
| 1/4 root grants exist only as the coordinator's own sentences in the acting commits; `SESSION_LOG.md` has no 09-24 entry; `TODO.md` untouched since 09-23 | ACCEPTED (high) | P-09 (new) | Verified `git blame` claim for `REDESIGN_PLAN.md:32` → `085c95b`. This is about corroboration, not honesty. |
| 2 test-debt table; zero ownership hits | ACCEPTED (medium) | MERGED → P-03 | |
| 3 ~35 user-facing strings hard-code `!`; `job_routing.py:39` | ACCEPTED (medium) | C-30 | AGENTS.md's "`!command` in active references" is about docs/docstrings; runtime strings should interpolate `self.command_prefix`, as `help` already does. Root to confirm reading. |
| 3 model-naming drift (`AGENTS.md:57` vs `gpt-6-*`) | ACCEPTED (info) | MERGED → P-07 | |
| 4 removals genuinely absent; `shelldocker`/`data_gf` dead refs; PRUNING_MAP stale (self-flagged) | ACCEPTED (info) | — | Positive finding: the redesign removals are clean. |
| 4 `legacy/` deletion unassigned | ACCEPTED | MERGED → P-04 | |
| 5 `SECURITY.md` never updated for the taint removal | ACCEPTED (medium) | D-01 | |
| 5 `OPENAI_MAX_TOKENS` default 16384 vs `.env.example` 8192 | ACCEPTED (low) | D-02 | |
| 5 `docker/bot.env.example` lacks `IMAGE_GEN_*` | ACCEPTED | MERGED → C-25 | |
| 5 `docs/STATUS.md` top third functions as an incident log | ACCEPTED (low) | D-05 | |
| 6 `prompt` decision recorded only by the coordinator's own line | ACCEPTED | MERGED → C-03, P-09 | |

## Report D — Dirac runtime and log console (Opus)

Corrections the child made to the coordinator's brief were accepted: the `local` log driver is in use, and R3
(`dfc6141`) lives in `tool_progress.py`, not `bot.py`.

| Child item | Verdict | Report ID | Coordinator note |
| --- | --- | --- | --- |
| F1 any user can latch the viewer through the unescaped `MSG from …: content[:100]` INFO line; newline log injection; private-key marker blanks the stream | ACCEPTED (high) | C-31 | Coordinator verified `bot.py:5761-5771` (no newline neutralisation, logged before blacklist/allowlist), `bounded_structure` and the permanent `continuity_lost` at `append_events.py:52-71,88-90`, and the service-name latch at `:103-104`. The `6859025` fix bounded one producer; the cheapest trigger is user content. |
| F2 omitted records get scope `service`, which no key can show; the pane looks frozen | ACCEPTED (medium) | C-32 | Not re-read by coordinator; mechanism consistent with the notice text at `append.py:133-134`. |
| F3 permanent latch disproportionate for structure/service triggers; durable fix outline; "raise the limit" rejected | ACCEPTED (medium) | C-33 | Adopted as the recommended durable design. |
| F4 other >64 KiB producers (image prompt log, unknown-tool-name log, exception messages, untruncated model strings) | PLAUSIBLE (low) | MERGED → C-33 | Bounded in practice by the current 12,345 cap; list retained for the implementer. |
| F5 framing on reassembled CLI lines; stdout/stderr merge could mis-frame | PLAUSIBLE (low) | — | Docker behaviour; no action without runtime evidence. |
| F6 `restart` replays pre-restart lines; `--fresh` = `--tail 0`; `start --replace` clears logs | ACCEPTED (info) | D-06 | Document in `DIRAC_HANDOFF.md`. |
| `dirac.py` argument validation, ownership check, engine pinning sound | ACCEPTED (positive) | — | No path to the wrong engine found; matches AGENTS.md's no-fallback rule. |
| `dirac.py status` misleading on config failure; runs `docker exec` despite "without mutating" docstring | ACCEPTED (low) | C-36 | |
| `dirac.py restart` drops stop evidence on a stopped container | ACCEPTED (low) | C-36 | |
| smoke runtime: no health-file collision; R9 `.expired()` correct; stop/start serialisation sound | ACCEPTED (positive) | — | |
| smoke `_handle` generic `except Exception` leaves the opened turn running; traceback discarded | ACCEPTED (low) | C-37 | |
| smoke stop during timeout handling can leave a record `running` | PLAUSIBLE (low) | C-37 | |
| R3-1 `transition_to_final` returns True on double failure; chunk 0 lost while chunks 1..n send; memory/REM record the answer as delivered | ACCEPTED (medium) | C-34 | The handoff itself lists the double-failure boolean as a known limit; the chunk-0/memory consequence was not stated there. |
| R3-2 cancellation during settlement can delete a delivered answer | PLAUSIBLE (low) | C-35 | Newly reachable because the turn now stays active during the edit. |
| R3-3 no settlement timeout; pre-existing sticker/reference/slowmode drop | ACCEPTED (info) | — | Same class of wait as the normal send path. |
| R2 no defect | ACCEPTED (positive) | — | |
| H1 `legacy/` deletion; last touched `a9c0fba` | ACCEPTED | MERGED → P-04 | |
| H2 host-compiled bytecode; one file compiled from an uncommitted edit before `1445f03` | ACCEPTED (info) | MERGED → P-08 | |
| H3 `.validation-cache/` includes compiled test modules | ACCEPTED (info) | MERGED → P-08 | Documented compile-only practice in `phase-II_v2/*_IMPLEMENTATION.md`; the presence of test modules is the new detail. |
