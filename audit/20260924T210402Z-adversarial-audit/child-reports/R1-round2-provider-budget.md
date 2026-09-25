# Round-two child report R1 — provider outcomes, usage, whole-turn budget (Fable, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../08-ROUND2-REPORT.md`.
Coordinator re-verified before accepting: `turn.settle` is called at exactly one site (success path after JSON
parse); `turn.reserve` sits outside the per-attempt `try`; `_flush_deferred_context_extraction` runs inside the
inner `finally` while the turn contextvar is still bound; the exhaustion arithmetic with the default retry count.

---

# Round-two re-verification — provider outcomes, usage, whole-turn budget

Scope: `git diff c603cf2..HEAD` for `providers.py`, `turn_budget.py`, `provider_telemetry.py`, `error_reporting.py`, `control_defaults.py`, `jobs.py`, and the `bot.py` hunks around `_handle_message`, the provider call sites, the tool loop, `TurnBudgetExceeded`, the 4,096 clamp, and the post-turn `finally`. All anchors are current-tree (HEAD `0e9519e`). Read-only; nothing executed, no tests, no runtime, no private paths.

---

## C-01 — terminal `length` rule

**Verdict: CLOSED** (one Low residual, one Low overclaim).

What the diff does:
- SSE: `finish_reason == "length"` no longer raises inside the reader; it sets `length_limited` (`providers.py:1230-1238`), keeps draining (see C-12), drops all native tool calls (`:1297`), skips `custom_buffer.drain()` and rebuilds visible content from `text_parts` only (`:1285-1292`), and returns the message with `finish_reason` preserved (`:1311-1316`).
- JSON and SSE then share one path in `generate_response`: `partial_content` is taken only if content exists and is not a policy-block text, then cut at the first `_CUSTOM_TOOL_OPEN_RE` opener (`:3096-3104`); a typed `ProviderIncompleteResponseError(classification="output_token_limit")` is built with bounded partial (16 KiB, `:1413-1414`), usage and metrics (`:3113-3148`) and re-raised without retry (`:3308-3310`, `isinstance(e, ProviderIncompleteResponseError)` → `raise` before `_retry_after_attempt`).
- `bot.py`: dedicated `except ProviderIncompleteResponseError` on the initial call (`bot.py:13119-13121`) and the follow-up call (`:13359-13367`, `break`). `native_calls = []` when incomplete (`:13125-13127`), text-tool recovery skipped (`:13140-13141`), `max_iters = 0` (`:13172-13173`), `_should_skip_plaintext_after_send` bypassed (`:13446`). `_format_incomplete_response` (`:1845-1866`) prefixes `INCOMPLETE RESPONSE: … No tool calls from this response were executed.` and passes partial through `_sanitize_visible_reply`, which contains nothing that strips that prefix (`:1800-1842`).

Round-one scenario (Dirac 12,345 cap, long content, `length`): now delivers the sanitized partial with a cutoff notice instead of the generic error; no dispatch; no paid retry. Closed.

Coordinator item 3 (SSE half-emitted custom JSON): `_CustomToolCallBuffer.feed` releases text to `text_parts` only up to the opener start (`providers.py:231-234`) and, with no opener, holds back from the last `{` (`:210-228`); the held region reaches `text_parts` only via `drain()` (`:298-309`), which is skipped when `length_limited` (`:1286-1287`). The generate-path opener cut (`:3101-3104`) applies on top. SSE is therefore equivalent-or-stricter than JSON; no fragment leak path found.

Residuals / overclaim:
- Low: every legitimate `length` stop is recorded as an incident (`incident.failure` at `:3306` sets `failed`, `capture` at `:3309` calls `capture_incident`). Diagnostic noise, not a correctness defect.
- Low: `partial_content_truncated` (`:1414`) is never surfaced; a paid answer longer than 16 KiB is silently cut a second time with no mention in the notice.
- The 4,096 short-turn clamp (`bot.py:12486-12489`, `_is_short_live_turn` `:14816-14826`) is unchanged, so the round-one "reasoning banter hits length" frequency is unchanged; only its visibility improved. The block does not claim otherwise.
- Overclaim (minor): "Confirmed delivery only is persisted" — I did not verify the persistence path (`bot.py:~13480-13600`); not checked, not disputed.

---

## C-06 — whole-turn budget

**Verdict: PARTIALLY CLOSED** — the budget exists and is enforced before every POST; three new defects, one Medium.

What the diff does:
- `turn_budget.py:31-105`: `ForegroundTurn` with defaults 32768 / 12 / 600 s (`:51-53`, mirrored in `control_defaults.py:167-169`). `reserve()` (`:60-72`) checks attempts, deadline, remaining output, then debits; `settle()` (`:74-82`) refunds `reserved - explicit` once, only when an explicit count is given.
- `providers.py:2584-2591`: per attempt, validate → clamp aliases → `reserve(data["max_tokens"], timeout)` → overwrite wire `max_tokens` and timeout → clamp again. This is before `incident.begin` and before `session.post` (`:2628-2634`). `settle` at `:3073-3074` after JSON parse. `_explicit_output_tokens` (`:640-668`) requires consistent explicit counters; `merge_usage` overwrites rather than sums (`provider_telemetry.py:185-205`), so cumulative per-chunk usage streams do not over-refund.
- `bot.py:12401-12424`: `_handle_message` creates the turn, binds the contextvar with a token, wraps the whole inner handler in `asyncio.timeout_at(turn.deadline)`, resets in `finally`. `except TurnBudgetExceeded` at `:13631-13639` posts `"<reason>. No additional provider attempt will be made."`.
- Descendants: `SpawnBackgroundTool.execute` → `_spawn_background` → `loop.create_task` (`jobs.py:443`, `utils.py:882`) copies the context, so model-spawned jobs share the object. `!bg` runs from `_handle_command` (`bot.py:5842`, `:6521-6552`) which is called from `on_message`, not from `_handle_message`, so it has no turn. Claim "descendants share, jobs don't" is accurate.

Coordinator item 1 (reserve/retry interaction): `turn.reserve` at `:2589` is **outside** the per-attempt `try:` (`:2628`), so `TurnBudgetExceeded` is *not* caught by `except RuntimeError` (`:3305`); it escapes `generate_response` (no `track_provider_activity` interference, `:1840-1852`; `bot._generate_response` `:2943-2947` has no handler) and lands at `bot.py:13631`. Exhaustion arithmetic with `OPENAI_RETRY_ATTEMPTS` default 5 (`config.py:239-240`): every failed attempt (5xx `:2637-2657` `continue`, timeout `:3274-3286`, ClientError `:3328-3338`, ProviderResponseError `:3305-3327`) leaves its reservation unsettled. Default 16,384 cap: attempt 1 → remaining 16,384; attempt 2 fails → remaining 0; attempt 3 → `reserve` gives 0 → `TurnBudgetExceeded("output_tokens")`. Dirac 12,345 cap: attempts 1–2 fail → remaining 8,078; attempt 3 runs with wire `max_tokens` silently reduced to 8,078; attempt 4 → exhausted. User text: "Foreground turn output allowance exhausted. No additional provider attempt will be made." (`turn_budget.py:15`, `bot.py:13635`) — **after zero generated tokens**.

New defects:
1. **Medium — misleading exhaustion after transient failures.** Two transient 5xx/timeouts with the default cap end the turn with "output allowance exhausted" though nothing was generated, and the third Dirac attempt runs with a reduced cap that itself invites a `length` stop. The policy "unknown usage retains reservation" is disclosed (TODO.md:64), but its interaction with the provider's own retry loop is not, and the response's "12 actual generation POSTs" is not what a turn gets in practice: effective attempts ≈ `budget / max_tokens` unless every attempt returns usage.
2. **Low-Medium — contextvar leak into the post-turn context watcher.** `_flush_deferred_context_extraction` runs in the inner `finally` (`bot.py:13711`) while the turn is still bound (reset is in the outer `finally`, `:12418`). It calls `asyncio.create_task(self._extract_shared_context_fact(...))` (`:9698`), which inherits the spent turn, then `context_provider.generate_response(...)` (`:9950`) → `reserve()` against a depleted `output_remaining`/`attempts`, clamped `max_tokens`, `min(timeout, remaining_seconds)`. The watcher is bot housekeeping deliberately deferred to *after* the turn, not a "model-spawned descendant"; it now degrades or fails silently after heavy turns.
3. **Low — lost diagnostics on budget exit.** `incident.capture` only runs inside the except branches (`:3275-3339`); when `reserve` raises at `:2589` after N failed attempts, the accumulated `incident.attempts` for those failures are never captured.

Other consequences the block understates: `asyncio.timeout_at(turn.deadline)` (`bot.py:12404`) is a hard cancel of the whole turn including in-flight tool execution; `ai_timeout_seconds`/`tool_iteration_timeout_seconds` (3,600) are now dominated by 600. Model-spawned background jobs — whose docstring purpose was "EXTENDED budgets" — are bounded to the remaining foreground seconds/attempts/output; a job's own 7,200 s deadline is moot after 600 s from the *user's message* (`reserve` deadline check → `jobs.py:745 except Exception` → job fails "generation failed at step N"). The updated docstring (`jobs.py:8-12`) says so, but the C-06 block only states "600 monotonic seconds". The three new controls appear only in `control_defaults.py` and `TODO.md:64`; no current `docs/*.md` documents them.

Coordinator item 2 (config validation): `config.py:225` only JSON-parses `OPENAI_EXTRA_BODY`; neither `Config.validate` (`:499-`) nor any provider-settings code checks `n`/aliases (grep empty). A bad value passes startup and every foreground turn raises `ValueError` at `providers.py:2422` → `bot.py:13655` generic `except Exception` → ERROR log with the message + generic public error. Not silent in logs, but no startup detection, and non-foreground calls (`!bg`, autonomy) succeed with the same extra body. Low.

Root authority: SESSION_LOG 2026-09-25 grants "full authority to do the fixes" with "conservative policy decisions"; the numbers are covered by that delegation and recorded in TODO.md:64. Round-one's "default off, ~10 lines" advice was not followed; that is a legitimate choice, not a defect.

---

## C-11 — `reasoning_details` truthiness

**Verdict: CLOSED.**

`providers.py:3106-3112` now uses `reasoning_content(message)` (`provider_telemetry.py:95-108`), which extracts text from `reasoning_content`, `reasoning`, or `reasoning_details` items of type `reasoning.text`/`reasoning.summary` only; encrypted/empty containers yield `""`. SSE deltas use the same helper (`:1094-1096`, `:1115`) and the merged message carries `reasoning_content` (`:1308-1309`), so JSON and SSE agree. Encrypted-only `reasoning_details` now fall through to the existing empty-content recovery (`:3190-3245`) instead of being misclassified. Claim matches diff.

---

## C-12 — telemetry lost on SSE `length`

**Verdict: CLOSED.**

Drain loop `providers.py:969-1007`: after `length_limited`, reads continue up to 64 KiB / 1.0 s (`:634-635`), error events and non-dict frames are ignored, choices skipped (`:1055-1056`), and the usage merge (`:1243-1250`) still runs on every frame until `[DONE]`. `usage_drain_complete` is recorded in the incident (`:1261-1263`, `:3146-3147`) and the exception carries `usage`/`metrics` (`:3113-3145`). `bot.py` records usage from the exception on both call sites (`:13130-13136`, `:13362-13365`) and `TokenBudgetTracker.record` accepts canonical aliases (`:2300-2314`). `settle` runs before the raise (`:3074` precedes `:3148`), so the reservation is refunded correctly for length stops. Bounded-drain loss (usage frame after 1 s / 64 KiB) is disclosed. I did not verify whether the "Provider timing complete" log line runs on this path.

---

## C-13 — incident raw-body cap

**Verdict: CLOSED.**

`_PROVIDER_DIAGNOSTIC_BODY_LIMIT = 64 KiB` (`providers.py:633`); `append_body` head/tail retention with omitted-byte marker (`:684-724`), `capture_text` (`:726-741`), `ProviderUpstreamError.incident_details` (`:1444-1453`); SSE uses `append_body` (`:1002-1003`); `error_reporting.py:46` `_INCIDENT_TEXT_LIMIT = 256 KiB` applied to traceback/details on create and merge (`:120-126`, `:179-183`, `:192-197`). Scope limits ("ingress not capped", "nested lengths describe intermediate input") are stated honestly in the block. `append_body`'s three-branch logic is hard to read but I traced no incorrect retention.

---

## C-14 — reasoning-only `stop` terminal for all models

**Verdict: NOT CLOSED as a defect; RETAINED BY DECISION — and mislabeled "fixed".**

Behavior is unchanged from round one in substance: `providers.py:3106-3112` classifies reasoning-only `stop` as `incomplete_classification = "reasoning_only"` and raises at `:3148` before the empty-content recovery at `:3190-3245` can rotate to the reasoning-disabled fallback. There is no `len(self._endpoints) == 1` gate. The user sees "The provider returned reasoning without a usable answer." (`bot.py:1863-1866`). Reasoning text is not leaked, correct. Root delegated "conservative policy decisions" (SESSION_LOG 2026-09-25), and TODO.md:63 records "Reasoning-only stays terminal and private", so the retention is authorized.

Overclaim: the block's disposition line says **"fixed — in source"** for a finding whose remedy (if any) was a root decision; the honest disposition is "retained policy under delegated authority". The body text ("without … paying for automatic retry/recovery") does disclose that no recovery runs, so the substance is not hidden — the label is wrong. Round-one was correct to frame this as a decision, not wrong. Severity of what remains open: Low (policy risk that a Flash model answering in `reasoning_content` always fails; only C-11 narrowed the false-positive set).

---

## I-06 — request multiplicity / cap ambiguity (with the 4,096 clamp)

**Verdict: CLOSED.**

`_validate_foreground_request_options` (`providers.py:1855-1867`): rejects present `n` unless `type(...) is int` and `== 1` (bools excluded), rejects non-positive-int aliases. Called on raw `self.extra_body` at generation entry (`:2420-2422`) before `_attempt_endpoint`/session — this closes the alternate-first hole the implementer's own review found. Per-attempt validate/clamp before and after `reserve` (`:2587-2591`); `_clamp_foreground_output_aliases` uses `min(value, cap)` (`:1869-1880`), preserving lower positive values. With the 4,096 clamp: `reserve(4096, …)` → `min(4096, remaining)` → aliases ≤ that. Non-foreground payloads (fallback `extra_body` = `{}` at `:2194`) untouched. `reasoning.max_tokens` (`:2234`) is not a "recognized" alias; the block's scoping to two fields is honest. Claim matches diff. Config-load gap noted under C-06 item 2.

---

## turn_budget.py — AGENTS.md discipline

- No `except Exception`; the only `try` catches `(TypeError, ValueError, OverflowError)` in `_positive_control` (`:108-114`). Pass.
- No `# type: ignore`, no `Any`; `Mapping[str, object]` is appropriate. Pass.
- Cohesion: `ForegroundTurn` also carries `expanded_tool_groups`, `media_*`, `admit_media` and a cleanup callback (`:43-47`, `:84-105`) serving C-17/C-19/I-04 — not unrequested for the audit as a whole, but the class is now a turn grab-bag rather than a budget; `remaining_seconds`, `set_cleanup`, `clear_cleanup`, `cleanup` lack docstrings.
- `from_controls` annotates `-> ForegroundTurn` inside the class body with no `from __future__ import annotations` (`:50`); valid only under PEP 649 (3.14 is mandatory, so acceptable, but 3.14-only).
- `_positive_control` silently truncates floats (`int(3.9)`) and maps any invalid value to the default without logging; minimal, acceptable for control parsing.
- `_handle_message` mixes `time.monotonic()` deadlines with `asyncio.timeout_at` (loop time); equal on the default loop, an implicit assumption.

---

## What I did not read

`validation.md`, the QA logs, any test file, the implementer's `review-*.md` other than `review-provider-budget.md` and the `micro-provider-admission.md`/`micro-reasoning-policy.md` notes, the `config.py` diff beyond grep, the delivery/persistence path in `bot.py` after `:13440`, the C-17/C-19 tool-group and media hunks that share `turn_budget.py`, `_is_policy_block_text`, and the learned output-cap adjustment blocks at `providers.py:2860-2960`. No code was imported or executed.
