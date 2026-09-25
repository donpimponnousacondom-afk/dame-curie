# 08 — Round-two audit report and closure verdict

Target: `dev/phaseII_v2` @ `0e9519e` (remediation range `c603cf2..0e9519e`, 16 commits, six of them source).
Inputs: `05-IMPLEMENTER-RESPONSE.md`, `validation.md`, `07-PROCESS-DISPOSITIONS.md`, `06-TOOL-INVENTORY.md`,
`TODO.md`, `docs/STATUS.md`, `phase-II_v2/SESSION_LOG.md`, `AGENTS.md`, and the actual diffs. The implementer's
own `review-*.md` / `micro-*.md` were treated as context, not acceptance. Five read-only re-verification agents
(reports `child-reports/R1…R5`) worked from the diffs; every verdict below that is ranked medium or above was
re-read by the coordinator against the tree before inclusion. Method and boundary as in round one: source and
document review only, no execution, no runtime, no private reads, no evidence deleted or moved.

## 0. Verdict

**Conditional acceptance.** The remediation is real, coherent and honestly recorded: 42 of the 52 round-one
findings are closed in source, the two deferrals are honest and accepted, the QA trees match the commits, the
test-definition count is net-zero, root's grant is quoted verbatim, and the one live action was a bounded
candidate exercise that was restored. The round-one root cause (no whole-turn limits, one-large-result tail,
full catalog every round) is addressed structurally.

Acceptance is conditional because the remediation introduced **three medium defects and one plausible medium
regression** that would ship with the next release, and one push-back (C-28) is rejected because it sits on a
broader pre-existing defect. None requires redesign; all are small, local fixes. Closure therefore needs one
more **narrow slice** (section 5) followed by a **diff-only recheck of that slice**, not another full round.
Evidence retirement may begin for everything marked CLOSED or DEFERRED-ACCEPTED below.

Nothing in this verdict is a deployment grant. The running temporary instance is still the pre-remediation
image (implementer's own statement, `validation.md` QA69); none of the fixes are live.

## 1. Round-one findings — round-two verdicts

Legend: **CLOSED** (fix verified from the diff, closes the round-one scenario); **PARTIAL** (part of the scenario
or of the requested remedy remains); **DEFERRED-ACCEPTED** (honest deferral with owner and gate, auditor
accepts); **RETAINED** (policy decision under delegated authority, not a defect fix); **PUSH-BACK REJECTED**.

| ID | Verdict | Note (anchors in the child reports) |
| --- | --- | --- |
| C-01 | CLOSED | Content-bearing `length` now returns partial text with a cutoff notice; reasoning-only terminal with notice; dedicated handlers at both call sites; no recovery/dispatch. Residuals low: every length stop is also captured as an incident (noise); `partial_content_truncated` never surfaced; 4,096 short-turn clamp unchanged, so frequency is unchanged, only visibility. |
| C-02 | CLOSED | Compact-before-evict; newest group capped at 24k and shrinkable to 16k so ≥2 older compacted rounds always survive (round-one example now keeps r2–r6). Undisclosed contract change: "newest round intact" is dropped; `_MAX_TOOL_RESULT_CHARS=32k` is dead weight beyond 24k. Acceptable; must be stated. |
| C-03 | CLOSED | Inline readback ≤1,800 bytes, file export above, 16 KiB write cap, ack without echo, prefix interpolated. Residual low (R2-14): an oversized stored prompt exports with no hint it is omitted from model context. |
| C-04 | CLOSED | Image checks moved out of `validate()`; invalid profile disables only the capability; malformed JSON caught at import; forced-on overridden; hold recorded in `IMAGE_GENERATION.md` and `PROVISIONING.md`. |
| C-05 | CLOSED | `low` everywhere; explicit private `high` untouched. |
| C-06 | PARTIAL | Budget exists and is enforced before every POST (`ForegroundTurn`, 32,768 / 12 / 600 s). **New medium R2-01** (unrefunded failed-attempt reservations), **R2-06** (contextvar leak), low diagnostics loss, low request-time-only `extra_body` validation, and under-disclosed consequences (600 s hard-cancels tools; descendant jobs bounded by the parent turn; new controls undocumented). |
| C-07 | PARTIAL | `reasoning` elided to 300 chars and arguments bounded in history. Mandatory `reasoning` parameter policy unchanged (root item 7 not decided). Overclaim: the model's next round sees **elided** arguments for its own just-executed batch (`bot.py:14091-14106,14521-14525`), contradicting "canonical immediate native replay". |
| C-08 | CLOSED | Live-provider case replaced in place with synthetic SSE (coordinator-inspected per AGENTS.md); skip guard removed; net-zero definitions. Auditor did not re-read the test body. |
| C-09 | DEFERRED-ACCEPTED | Import-time `load_dotenv(override=True)` retained. Accepted as a permanent boundary given the isolated-QA discipline; record it in `docs/DEVELOPMENT.md` as a known limitation and close. |
| C-10 | CLOSED | `.dockerignore` excludes `audit/`, `reports/`; allow-list includes the two new modules (`be28b85`). |
| C-11 | CLOSED | `reasoning_content()` helper used on both paths. |
| C-12 | CLOSED | Bounded drain (64 KiB / 1 s) to the usage frame; usage on the exception; recorded by both call sites; `settle` before raise. |
| C-13 | CLOSED | 64 KiB head/tail body capture; 256 KiB incident text cap. |
| C-14 | RETAINED (mislabelled) | Reasoning-only `stop` remains terminal for every model; fallback recovery still bypassed. Authorised under the delegated "conservative policy" grant and recorded in TODO, but the block says "fixed". Relabel as retained policy; low open risk. |
| C-15 | CLOSED | Marker regex re-reads the prior count; truthful accumulation verified numerically. |
| C-16 | PARTIAL / REGRESSION | Schema counted, protected blocks fail visibly, honest logging. **New medium R2-02** (planner/enforcer mismatch deletes the channel transcript) and **plausible medium R2-03** (`PromptBudgetExceeded` mid-turn after group expansion). Overclaim: enforced budget is 72,000, not 96,000. |
| C-17 | CLOSED | Core 15 / full 74 by task-local discovery; no cross-turn leak; hidden ≠ blocked is disclosed. Low: `_lean_chat_turn` docstring now states the opposite of behaviour. |
| C-18 | PARTIAL | Recovery bounded (16k input, 8 calls, 4k args). No chunk-count cap on replies (round-one ask, not claimed by implementer); ~27 messages for a full 12,345-token reply. |
| C-19 | CLOSED | Per-round attachment; turn-wide 12 / 20 MiB admission. **New R2-08**: native result path drops legitimately repeated media silently (`admit_media` without the `or key in media_keys` used everywhere else). |
| C-20 | CLOSED | Params ≤8k, result ≤8k head/tail, media labelled, content ≤16k. |
| C-21 | CLOSED | Dead branch removed; live visible-set comparison. |
| C-22 | CLOSED | Server prompt is its own protected system message; identity/tool contract never middle-trimmed; overflow fails visibly. Residuals low: diagnostic reaches only the model; two paths give different advice; 16 KiB is a coordinator number; **pre-release check of stored prompt sizes required** (a >16 KiB prompt written since `723e7d8` will be omitted from context on the next release). |
| C-23 | CLOSED (scenario) | Whitelist consulted at dispatcher, catalog, plugin eligibility and inside `ShellTool.execute`; minimal subprocess env, `--noprofile --norc`. New: **R2-07** autonomy silently loses shell/rewrites while its planner advertises them; **R2-09** allowlist ≈ admin via writable `admins.json`; low `send_file` exports the workspace for any actor; low `TZ` dropped. The trust model is a coordinator choice and should be labelled as such (like C-28). |
| C-24 | CLOSED | Admin check inside both `execute` methods and in the catalog. |
| C-25 | CLOSED | `auto` registers only with a usable profile; template has the keys. |
| C-26 | CLOSED | `realpath` on roots and reference; TOCTOU and latency disclosed. |
| C-27 | CLOSED | Fallback only when `image is None`; tension with C-29 noted. |
| C-28 | PUSH-BACK REJECTED | The rationale is factually wrong (old `hd_image` also defaulted save-only and used attachments; existing `dalle`/`flux`/`image` aliases contradict the "no reinterpretation" principle). More importantly the rejected name is not recoverable for the model: see **R2-04**. The `disabled_tools` check for Dirac is accepted. |
| C-29 | CLOSED | Empty model/quality fall back to defaults. |
| C-30 | CLOSED | No hard-coded `!` remains in user-facing runtime strings; `job_routing.py` takes the prefix. |
| C-31 | CLOSED (source) | Preview line now integers only; structure/service failures are per-record omissions. **Not live.** Low: `autonomy.py:3150` logs 500 raw model chars with newlines at WARNING (forgery / span opening). |
| C-32 | CLOSED | `viewer` scope always visible; excluded from filters and health coalescing. |
| C-33 | PARTIAL | Record-local JSON redaction, pre-parse structure bound, rejected-line scanning done. The oversize-frame proportionate handling was neither done nor declined; **R2-10**: the console viewer used by canonical `instance.py logs` now latches permanently on >2 MiB records. Overclaim: "host viewer source only" hides that the change reaches the canonical viewer code. |
| C-34 | CLOSED | Real delivery flag; chunk 0 falls through; memory records only delivered chunks. |
| C-35 | CLOSED | Cancellation during the edit no longer deletes; deliberate orphan-progress trade-off. |
| C-36 | CLOSED | Status reads container state first, exec disclosed; restart refuses non-running with evidence. Low race window. |
| C-37 | CLOSED | Exact-task cancel/settle/discard; terminal record before the wait. **R2-11**: taskless unconfirmed path stops the poller silently with a stale "running" health file. |
| P-01 | CLOSED | Freeze recorded; the only runtime action since round one is the authorised bounded candidate exercise with byte-exact restoration (ledger; not independently observable by the auditor). |
| P-02 | CLOSED | 32 added / 32 removed definitions, no new or deleted test files; the two new modules implement requested fixes. |
| P-03 | CLOSED | QA60 full-safe green with failures retained; the four "unsupported reasoning" cases pass because production was restored, not tests weakened. Info: one viewer keyboard expectation was aligned to code (`["q"]`→`["[","q"]`), disclosed in `validation.md` bash-34 but not in the commit message. |
| P-04 | CLOSED | `legacy/` removal committed under the quoted grant; no active doc points at it. |
| P-05 | CLOSED (mapped, retained) | Branch dispositions verified on two rows; pruning gate remains root's. |
| P-06 | CLOSED | Bundle tracked deliberately (`3754a8a` message); content scan found no credentials or new snowflakes; retirement gate in TODO. |
| P-07 | CLOSED | Current route names in AGENTS.md. |
| P-08 | DEFERRED-ACCEPTED | Provenance unattributable; accept as "unknown, no further action"; keep the quarantined reviewer record. |
| P-09 | CLOSED | Root quoted verbatim; older "root chose" sentences removed; plan retitled historical. |
| D-01 | CLOSED (wording) | `SECURITY.md` honest on taint removal and no-secret-sandbox. Fix three overstatements: autonomy catalog exception, "read" → "read and write", allowlist ≈ admin (R2-09). |
| D-02 | CLOSED | 16384 aligned. |
| D-03 | CLOSED | `!` examples. |
| D-04 | PARTIAL | `jobs.py` and PRUNING_MAP/REDESIGN_PLAN fixed; seven dated lane docs still say taint/confirmation "remain" without a banner; `phase-II_v2/README.md:5` still calls the plan "the authority". |
| D-05 | CLOSED | STATUS 53 lines / 4 sections; history preserved in Git. |
| D-06 | CLOSED | Handoff documents replay and `--fresh`; line 23 ("redactor unchanged") is stale. |
| I-01 | CLOSED | `FileNotFoundError` only. |
| I-02 | CLOSED | By ordering, not structure; latent if an await is later inserted. |
| I-03 | CLOSED | Residuals disclosed. |
| I-04 | CLOSED | Separate catalog scope per job; descendant spend inheritance noted under C-06. |
| I-05 | DEFERRED-ACCEPTED | As P-08. |
| I-06 | CLOSED | `n` and cap aliases validated before reserve/POST. |

Totals: 42 CLOSED · 6 PARTIAL (C-06, C-07, C-16, C-18, C-33, D-04) · 2 DEFERRED-ACCEPTED (C-09, P-08/I-05) ·
1 RETAINED mislabelled (C-14) · 1 PUSH-BACK REJECTED (C-28). Implementer items: 5 CLOSED, 1 DEFERRED-ACCEPTED.

## 2. New findings introduced or exposed by the remediation

Status key as in round one. All anchors are HEAD `0e9519e`.

### R2-01 — Failed provider attempts never refund their output reservation (medium, CONFIRMED)
- **Anchors:** `providers.py:2589` (`turn.reserve` per attempt, outside the `try`), `:3074` (the **only** `settle`
  call, on the success path after JSON parse), `turn_budget.py:60-82`, `config.py:239-240` (5 retry attempts),
  `bot.py:13631-13639` (user notice).
- **Scenario:** default cap 16,384 and budget 32,768: attempt 1 gets a 5xx → `continue`; attempt 2 reserves the
  remaining 16,384, times out; attempt 3 → `reserve` yields 0 → `TurnBudgetExceeded("output_tokens")` → user sees
  "Foreground turn output allowance exhausted. No additional provider attempt will be made." after **zero**
  generated tokens. Dirac cap 12,345: attempt 3 runs with `max_tokens` silently reduced to 8,078, inviting the very
  `length` stop C-01 was about. Effective attempts ≈ budget ÷ cap, not the documented 12.
- **Fix:** settle with a full refund on every failure path where no response body was received (non-2xx before
  body, connection error, `incident.body_bytes_seen == 0`); keep retention for mid-stream timeouts where tokens may
  have been generated. Also capture the accumulated `incident.attempts` when `reserve` raises.

### R2-02 — Prompt-budget planner ignores schema size; the enforcer then deletes the whole channel transcript (medium, CONFIRMED mechanism; frequency PLAUSIBLE)
- **Anchors:** `_context_budget_plan` (`bot.py:~15182-15230`) subtracts only a fixed 4,000 overhead and never sees
  `provider_tools`; `_apply_prompt_budget` (`:~15290-15358`) adds `schema_chars` (≈14k core, ≈55k all groups) to
  the same 72,000 ceiling, evicts tool groups, then **`del out[index]` on the `<previous_conversation>` message**,
  then trims unprotected system blocks, then raises.
- **Scenario:** any turn whose memory tiers fill their planned allocation (busy channel plus RAG hits) is over by
  the schema size with nothing else to evict; the entire conversation transcript is dropped from the request with
  no log line. Round one's enforcer middle-trimmed; it never deleted memory. This contradicts "preserve functional
  memory".
- **Fix:** pass the serialized schema size (and the newest-group cap) into the planner's overhead; trim the
  transcript (oldest lines first) before deleting it; log when memory is dropped.

### R2-03 — `PromptBudgetExceeded` after tools have executed, once several groups are expanded (medium, PLAUSIBLE by arithmetic)
- **Anchors:** all-groups schema 54,608 + native tool prompt 9,072 = 63,680 of 72,000 (`06-TOOL-INVENTORY.md`,
  `bot.py:15091-15110`); newest group up to 24,000 is protected from eviction; raise sites `bot.py:13253-13255`,
  `:13289-13293` are inside the loop after dispatch.
- **Scenario:** three or four `more_tools` calls plus one large tool result → the protected content alone exceeds
  the budget → public error after side effects.
- **Fix:** same planner change as R2-02; when over budget after eviction, drop expanded groups' schemas (keep core)
  before failing.

### R2-04 — Dead error-prefix check: unknown or erroring non-result tools end the turn with no reply (medium, CONFIRMED)
- **Anchors:** `_tool_results_need_followup` checks `result.startswith(("Error:", "Error "))` or `"\nError:" in
  result` (`bot.py:~2153`); dispatcher lines always start with `Tool <name>: …` (`bot.py:13900`); unknown tool →
  `Tool hd_image: Error - unknown tool 'hd_image'` (`:13849`); non-result tools then `break` the loop.
- **Scenario:** a stale `hd_image` call from channel memory, any hallucinated name, or any error from a non-result
  tool, with no accompanying text → the user gets nothing. Pre-existing, but the C-28 push-back makes it routine.
- **Fix:** match `Tool <name>: Error` (one condition) so the model gets a follow-up turn. This also settles C-28
  either way; the auditor still recommends the `hd_image` alias as belt-and-braces since it is one dict entry.

### R2-05 — 16,000-byte per-call argument cap constrains file authoring and fails with a generic error (medium-low, CONFIRMED)
- **Anchors:** `tool_schemas.py:1002-1008,1083,1144` (`_NATIVE_MAX_ARGUMENT_BYTES = 16_000`, batch 32,000, envelope
  40,000, 8 calls); admission failures propagate to the generic `except Exception` at `bot.py:13666`.
- **Scenario:** `send_file` or a shell heredoc writing a 20 KB file in one call → whole batch rejected before any
  effect (fail-closed, good) but the model receives no tool-error line to react to and the user sees the generic
  error. Not disclosed in the C-02/C-18 blocks.
- **Fix:** return a `Tool <name>: Error - arguments exceed N bytes` result for oversized calls instead of raising;
  document the cap; root decides the number.

### R2-06 — Post-turn context extraction inherits the spent `ForegroundTurn` (low-medium, CONFIRMED)
- **Anchors:** `_flush_deferred_context_extraction` runs in the inner `finally` (`bot.py:~13711`) while the turn
  is still bound (reset in the outer `finally`, `:12418`); it schedules `asyncio.create_task(...)`, which copies
  the context; the watcher's `generate_response` then hits `reserve()` on a depleted turn.
- **Fix:** reset the contextvar before scheduling, or bind `None` around the `create_task`.

### R2-07 — Autonomy silently loses shell and prompt rewrites while its planner still advertises them (low-medium, CONFIRMED)
- **Anchors:** `autonomy.py:4166-4171` actor `id="autonomy"`, direct `tool.execute` at `:4199-4201`;
  `_autonomy_tool_allowed` and planner catalog (`:1291-1305`, `:2936-2947`) unchanged.
- **Fix:** filter the autonomy catalog through `tool_authorized`, or document the intentional loss.

### R2-08 — Repeated media silently dropped in the native result path (low-medium, CONFIRMED)
- **Anchors:** `_process_native_tool_calls` admits with `turn.admit_media(key, …)` alone (`bot.py:~14466,~14484`);
  every other site uses `… or key in turn.media_keys` (`:12589,12656,12778`) or the equivalent.
- **Fix:** align the two sites.

### R2-09 — Shell allowlist is effectively admin-level (low, CONFIRMED; docs)
- **Anchors:** `/state/data` writable from the shell (`compose.yaml:131-136`); `admins.json` reloaded every 5 s
  (`bot.py:~9550`); `SECURITY.md:18` says "read", TODO says "gated separately".
- **Fix:** wording now ("an allowlisted shell user can write the admin file"); making the admin file
  non-writable from the shell is an architecture decision for root.

### R2-10 — Console viewer (canonical `instance.py logs`) now latches permanently on oversize records (low, CONFIRMED)
- **Anchors:** `scripts/log_console/console.py:20,28-35` now uses `AppendParser`; `AppendLines.take` unchanged;
  `log_filter.py:80-81`, `instance.py:207-210`.
- **Fix:** decide the oversize-frame policy explicitly (C-33's remaining item) and state that the change reaches
  the canonical viewer code.

### R2-11 — Smoke poller can stop silently with a stale "running" health file (low, CONFIRMED)
- **Anchors:** `dirac_runtime.py:749-751` sets `_stop_requested` on taskless unconfirmed settlement; poll loop
  returns quietly (`:543-545`); health file not updated.
- **Fix:** write the health state and log before returning.

### R2-12 — Two policy decisions labelled "fixed" (low, CONFIRMED)
- C-14 (reasoning-only terminal) and the C-23 trust model (admin-or-allowlist) are coordinator choices under the
  delegated grant. Relabel as "retained by decision" in `05-IMPLEMENTER-RESPONSE.md` and list them for root in
  `TODO.md`, as C-28 already is.

### R2-13 — Raw model output logged with newlines (low, CONFIRMED)
- `autonomy.py:3150` logs 500 chars of raw planner output at WARNING; newlines survive, so log-record forgery and
  PEM/config span opening remain possible from model output. Neutralise newlines or log a length.

### R2-14 — Documentation residue (low, CONFIRMED)
- New controls `turn_output_token_budget` / `turn_generation_attempt_budget` / `turn_deadline_seconds` appear only
  in `control_defaults.py` and `TODO.md`; `_lean_chat_turn` docstring is inverted; `DIRAC_HANDOFF.md:23` says the
  redactor is unchanged; `phase-II_v2/README.md:5` calls the plan "the authority"; seven lane docs lack a
  historical banner; C-03 export gives no omission hint; `_MAX_TOOL_RESULT_CHARS` is dead beyond 24k;
  `partial_content_truncated` is never surfaced; the 600 s deadline dominating the 3,600 s controls and bounding
  descendant jobs is stated only in a `jobs.py` docstring.

### R2-15 — Nothing is live (info)
- The running temporary instance is the pre-remediation image; the round-one viewer latch and preview log are
  still active there (implementer states this). Audit closure is not deployment. Before the next release: check
  stored server-prompt byte sizes (C-22), confirm the private `disabled_tools`/image profile once more, and take
  new receipts.

## 3. Deferrals and push-back — auditor decisions

- **C-09 import-time dotenv:** deferral **accepted**. Close it by recording the boundary in `docs/DEVELOPMENT.md`;
  no lazy-loading change is requested by this audit.
- **P-08 / I-05 provenance:** deferral **accepted** as permanently unattributable. Keep the quarantined reviewer
  record; no cache deletion; one sentence in the final receipt.
- **C-28 alias push-back:** **rejected as argued**, superseded by R2-04. Either fix closes it; the generic
  follow-up fix is required, the alias is recommended.
- **C-14 reasoning-only policy:** the retention is within the delegated grant; the label must change (R2-12).
  Root's item 2 from round one remains theirs to revisit.

## 4. Process verdict

- Cadence: corrected. One authorised bounded candidate exercise with byte-exact restoration, recorded before and
  after, no other runtime action in the range (ledger statements; the auditor cannot observe runtime).
- Provenance: the three standalone commits match their tested trees exactly; the committed `d198c37` tree is
  identical to the QA61 snapshot in every Python and build input and differs from the QA60 full-suite snapshot by
  one comment-only `bot.py` hunk plus the two test files QA61 rechecked. This is honestly described.
- Contract: net-zero test definitions; two new modules within requested scope; no `xfail`/`skip` added; one
  baseline expectation aligned to code with disclosure in the ledger (should also be in the commit message next
  time).
- Ledgers: `SESSION_LOG.md` now carries root's words verbatim; older uncorroborated attributions were removed
  rather than merely relabelled; `STATUS.md` is a milestone ledger again.
- Reviewer discipline: one implementer-side reviewer violated its no-execution assignment and was quarantined
  with its conclusions excluded; that is the correct handling and the record should stay.
- The audit bundle is now tracked despite `/audit/` in `.gitignore` (deliberate, stated in `3754a8a`); the
  content scan found nothing private. Acceptable.

## 5. Closure conditions (the final slice)

One reviewed slice, existing-test adaptation only, isolated QA, no deployment:

1. **R2-01** refund-on-no-body settlement, plus incident capture on `reserve` failure.
2. **R2-02 / R2-03** planner includes schema and newest-group sizes; transcript trimmed before deleted; log on
   memory drop; drop expanded-group schemas before raising.
3. **R2-04** `Tool <name>: Error` follow-up match (closes C-28); add the `hd_image` alias.
4. **R2-05** oversized-argument admission returns a tool-error line instead of raising; document the cap.
5. **R2-06** reset the turn before scheduling post-turn context extraction.
6. **R2-07, R2-08, R2-11** one-line alignments.
7. **R2-12, R2-13, R2-14, D-01 wording, D-04 banners** documentation and labels; state the C-02 newest-group
   contract change and the 72,000 enforced budget where "96000" is claimed.

Then: the auditor rechecks **only that slice's diff** and the updated `05` blocks, and issues the closure
receipt. After that, retirement per `TODO.md` may proceed; the auditor's originals (00–04, child reports, this
report and any closure receipt) stay verbatim until root retires the bundle.

## 6. Decisions still root's

1. C-14 reasoning-only: keep terminal, or allow one fallback attempt.
2. Shell trust model: admin-or-allowlist as implemented, and whether the shell may write the admin/control files
   (R2-09).
3. Numbers chosen by the coordinator: 32,768 / 12 / 600 s turn budget; 16 KiB server prompt; 16,000-byte
   argument cap; 24k newest-group cap. All are defensible; all are yours.
4. Mandatory `reasoning` tool argument (C-07 policy) — unchanged, still costs input every round.
5. Lifting the release freeze: only after the closure receipt and the pre-release checks in R2-15.

## 7. Method and limits

Coordinator read the full `providers.py` diff, the new `turn_budget.py`, `tool_policy.py`, the new
`trim_tool_tail`/`elide_tool_calls_for_history`, the `_handle_message` wrapper, the incomplete-response
handlers, the shell subprocess environment, the `MSG` producer line, the budget-exception handlers, and the
anchors of every medium-or-higher child claim. Tree hashes, test-definition counts and template diffs were
re-run directly. Not done, by contract: no execution, no runtime observation, no private reads; QA counts,
image digests, container IDs and the restoration are ledger statements. Catalog and budget arithmetic reuse
the implementer's QA61 measurements. Reviewer routes named in AGENTS.md were again unavailable to this harness;
Fable, Opus and Sonnet were used and this remains a recorded deviation.
