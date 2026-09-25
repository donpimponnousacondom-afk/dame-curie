# Round-two child report R2 — native tool history, arguments, recovery, prompt budget, catalog (Fable, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../08-ROUND2-REPORT.md`.
Coordinator re-verified before accepting: `_apply_prompt_budget` counts `schema_chars` and deletes the
`<previous_conversation>` message whole (`del out[index]`) while `_context_budget_plan` adds only a fixed 4,000
overhead with no schema term; the native admission constants (8 calls, 16,000 bytes per argument string,
32,000 per batch); the pre-execution `trim_tool_tail` whose elided `tool_calls` become the assistant history
message for the next round; the new `trim_tool_tail` ordering and 24k/16k newest-group shrink. The C-19 anchor
was checked separately (see the report).

---

# Round-two re-verification — tool history / arguments / recovery / prompt budget / catalog cluster

Scope: `git diff c603cf2..HEAD` for `tool_schemas.py`, `tool_policy.py`, `tool_prompts.py`, `turn_budget.py`, `control_defaults.py`, `bot_tools.py`, `jobs.py`, and the `bot.py` hunks named in the assignment; current-tree anchors are HEAD `0e9519e`. Read-only; nothing executed, no tests, no runtime, no private paths. `rag_memory.py`, `tool_registry.py` are unchanged in the range (diff stat empty).

Effective numbers used below (all pre-existing, unchanged since c603cf2): `prompt_context_budget` 96 000 (`control_defaults.py:175`, same at `c603cf2:control_defaults.py:171`); `_prompt_budget_chars()` = 96 000 − max(16 000, 96 000//4) = **72 000** (`bot.py:15091-15110`, identical body at `c603cf2:bot.py:14523-14544`). The implementer's "96000 schema-inclusive budget" is the raw control, not the enforced figure.

---

## C-02 — tail eviction

**Verdict: CLOSED for the round-one failure; one undisclosed contract change (newest round no longer intact), no new crash path reachable.**

What the diff does (`tool_schemas.py:1927-1963`): message-count eviction first (`:1940-1941`); raise if newest group alone exceeds 12 messages (`:1944-1945`); `_compact_old_tool_results` on all older groups (`:1946`, `:1966-1977`, now also assistant `content`); newest group fitted to `min(24_000, max_chars)` (`:1947-1948`, `TOOL_TAIL_NEWEST_GROUP_CHARS` `:1807`); older groups fitted to the same limit; then evict oldest while `used > 36_000`, but if the room left for the newest is ≥ 16 000 the newest is shrunk instead and the loop breaks when it fits (`:1952-1962`).

Round-one worked example re-run (r1–r4 = 4 051 each with marker, r5 = 20 000, r6 = 29 890; ~300 chars/round of id/name/args overhead, matching round one's 67 894 total):
1. 12 messages → no count eviction.
2. Compaction: r1–r4 → body 3 950 + marker 50 = 4 000 (marker regex `:1809-1811` re-reads the old count, so no double-count); r5 → 4 000. Each older round ≈ 4 300 with overhead.
3. Newest fit: r6 → 23 700 content + overhead = 24 000.
4. used = 5×4 300 + 24 000 = 45 500 > 36 000. Iter 1: room = 14 500 < 16 000 → drop r1 (used 41 200). Iter 2: room = 18 800 ≥ 16 000 → shrink r6 to 18 800 → used = 36 000 → break.
5. **Surviving: r2, r3, r4, r5 (≈4 000 each) and r6 (≈18 500 of 29 890).** Round one: r6 only. Round one's proposed compact-first: r5 + r6 intact.

Ratio fault: a 32 000-char newest (post `_MAX_TOOL_RESULT_CHARS`, `bot.py:14504-14518`) is capped to 24 000, then to as low as 16 000, so ≥ 2 and up to 4 older compacted rounds always survive. Closed.

Pairing invariant: `tool_tail_groups` (`:1847-1878`) now raises on orphan/mismatched ids rather than silently regrouping; eviction is whole-group. In-place mutation of `conversation_tail` dicts persists (`:1922-1923`, `:1975-1977`) but is now idempotent via `_truncate_history_text` (`:1881-1896`) — omitted counts accumulate truthfully (verified: 29 890 → 18 450 body/11 440 omitted → 3 950 body/25 940 omitted).

Coordinator item 1 — admission before effects: `_NATIVE_MAX_CALLS = 8` (`tool_schemas.py:1002`), enforced at `:1119` inside `normalize_native_tool_calls`, called at `bot.py:14055`; tools execute only at `run_tools_once()` `bot.py:14444`. **Maximum admitted batch = 8 calls = 9 messages**, so `ValueError("Newest tool-call batch exceeds history message cap")` (`:1944`) is unreachable from native admission. The preflight `trim_tool_tail` at `bot.py:14092-14106` also runs before tools; its `_fit_tool_group` raise (`:1908-1909`) needs fixed overhead > 24 000, impossible with 8×(128-byte id + 128-byte name + ≤500-char args) + 8×128-byte tool ids ≈ 7 k. Post-execution `trim_tool_tail` at `bot.py:13288` operates on the same bounded groups and cannot raise in practice. If any of these did raise after tools ran, the only catcher is the generic `except Exception` at `bot.py:13666` → public error after side effects. Admission failures (`>8` calls, duplicate/non-string id, `type` ≠ function, args > 16 000 bytes per call / 32 000 per batch, envelope > 40 000, non-object arguments) also land in `:13666`: fail-closed (no tool ran) but the model receives no feedback and the generation is sunk.

Overclaim / undisclosure: block says "retain whole native groups within 36k characters/12 messages" and "replay keeps … original executed arguments as JSON strings". The newest group is capped at 24 000 (docstring `:1935`) and can be shrunk to 16 000 on the very first follow-up, so `_MAX_TOOL_RESULT_CHARS = 32_000` is dead weight beyond 24 000 and the round-one "newest round intact" invariant is dropped. Not stated in the block. Arguments claim: see C-07.

Minor: in custom (non-native) mode `_apply_prompt_budget` treats the last `=== TOOL RESULTS ===` user message as the live input (`bot.py:15305-15310`), so its tail-eviction step sees an empty tail; harmless because `trim_tool_tail` already bounds it.

## C-15 — compaction marker idempotency

**Verdict: CLOSED.** `_HISTORY_MARKER_RE` (`tool_schemas.py:1809-1811`) matches all three labels; `_truncate_history_text` strips the old marker, adds the old count, and re-fits (`:1885-1896`). Second-pass counts are truthful (see C-02 step 5). No new defect.

## C-07 — `reasoning` argument in replayed history; mandatory-param policy

**Verdict: PARTIALLY CLOSED — elision implemented; the block's "canonical immediate native replay" claim is false.**

Elision: `elide_tool_calls_for_history` (`tool_schemas.py:1980-2030`) caps `reasoning` at 300 with a marker (`:2009-2013`), any other string value at 2 000 (`:2014`), whole-call JSON at `max_args_chars` → `{"_elided": …}` (`:2021-2025`). Output is `json.dumps(...)` so both the shortened `reasoning` string and the `_elided` object are valid JSON (coordinator item 2, second half: confirmed; Python slicing cannot split a code point, and `json.dumps` escapes anything remaining).

Coordinator item 2, first half — what the provider sees next round: `canonical_tool_calls` (`bot.py:14078-14090`) is used **only** as input to elision (`:14091`; grep shows no other use). The preflight `trim_tool_tail` (`:14092-14106`) re-elides with `max_args_chars = max(160, 4000 // n)` (`:1902-1905`) and `assistant_msg["tool_calls"] = history_tool_calls` (`:14521-14525`) → `_last_native_followup_messages` → `conversation_tail` → `result_messages`. So **the model's very next round sees elided arguments for its just-executed batch**: 1 call → ≤ 4 000 chars, per value ≤ 2 000, reasoning ≤ 300; 8 calls → ≤ 500 chars per call or the whole call replaced by `_elided`. (12 calls cannot occur; the coordinator's "333 chars" premise should be "500 at n=8".) With the prompt still mandating ~280-char `reasoning` (`tool_prompts.py:242`), a typical 8-call batch will replay mostly `_elided` markers. Design tension, not a crash.

Overclaim: block C-07 "without changing … canonical immediate native replay"; block C-02 "replay keeps … original executed arguments as JSON strings". Both contradicted by `bot.py:14091-14106, 14521-14525`. Dispatch inputs (`calls[*]["arguments"]`) are indeed untouched.

Mandatory-param policy: **unchanged**. `build_openai_tools` still forces `reasoning` into `required` (`tool_schemas.py:901-915`). `micro-reasoning-policy.md` is about the `!reasoning`/`!effort` DeepSeek-transport commands (`bot.py:7265-7272`) and says nothing about the tool `reasoning` argument; it is not evidence for this finding.

## C-16 — prompt budget

**Verdict: PARTIALLY CLOSED; REGRESSION introduced (medium): planner ignores schema size, enforcer now deletes the whole transcript before trimming anything; `PromptBudgetExceeded` reachable mid-turn after several `more_tools` expansions.**

What the diff does (`bot.py:15290-15358`): `schema_chars = len(json.dumps(provider_tools))` counted in `total` (`:15294-15299`); protected: `out[0]`, system messages by prefix (`## Tool contract`, `## Tools`, `## Available tools\n`, `Custom tool protocol:`, `Server-specific instructions:`, omitted-prompt diagnostic; `:15304-15320`), live user input; then (a) evict older tool groups (`:15321-15329`), (b) **delete the `<previous_conversation>` user message whole** (`:15330-15341`), (c) middle-trim unprotected system messages to ≥ 512 (`:15343-15353`), (d) `raise PromptBudgetExceeded()` (`:15355-15357`, class `:2275-2282`). Caught at `:12868-12882` (build phase) and `:13640-13647` (generation/loop). `tool_calls` arguments are trimmed only via `trim_tool_tail`'s elision, not here — acceptable since the tail is bounded first. The old misleading "Trimmed prompt to budget" log is gone; nothing is logged when trimming succeeds.

Regression 1 — planner/enforcer mismatch: `_context_budget_plan` (`:15182-15230`) computes memory-tier allowance as `72 000 − (system_parts + len(tool_prompt) + JAILBREAK + 4 000)` (`:15201-15207`); `provider_tools` is not passed in. The enforcer then adds 14 413 chars (admin core schema per `06-TOOL-INVENTORY.md`) to the same 72 000 ceiling. Whenever the memory tiers fill their allocation (busy channel + RAG hits), the prompt is over by up to ~14 k with no tool groups to evict, and step (b) **deletes the entire channel transcript** (`bot.py:16182-16188` is the only `<previous_conversation>` message) rather than trimming RAG/system blocks. The round-one enforcer never deleted the transcript (it middle-trimmed system blocks). This contradicts "preserve … functional memory" and is unobservable (no log). Needs an isolated synthetic full-memory fixture to confirm frequency; the arithmetic is from the implementer's own numbers.

Regression 2 — mid-turn hard failure: with all groups expanded, schema 54 608 + native tool prompt 9 072 = 63 680 of 72 000, leaving 8 320 for the protected identity block, live input and the newest tool group (≤ 24 000, never evicted by `_apply_prompt_budget`). `PromptBudgetExceeded` then fires at `:13253-13255` or `:13289-13293` **after that round's tools executed**, ending the turn with a public error. Reachable after 3–4 `more_tools` calls (core+workflow+servers+moderation ≈ 40 k schema + 9 k prompt + identity + a 24 k newest group > 72 k).

Overclaim: "Prompt input budget is 96000 characters by default, including serialized native schemas" — enforced budget is 72 000 and unchanged; the schema was simply added to the count. Inventory: "The measured all-groups schema alone does not exceed the 96000 default" compares against the wrong number and ignores protected content.

## C-17 — catalog resent every round / progressive discovery

**Verdict: CLOSED for token economy; hidden ≠ blocked (disclosed); one stale helper.**

- Ordinary chat turn sees core only: `_handle_message` binds a `ForegroundTurn` (`bot.py:12401-12403`, reset `:12418`); `current_tool_groups()` returns its empty `expanded_tool_groups` (`turn_budget.py:132-138`); `_turn_tool_names` filters `compatible ∩ (CORE ∪ expanded)` (`bot.py:14730-14740`), plugins only with group `plugins` (`:14752-14753`), `spawn_background` dropped in jobs (`:14755-14756`), `tool_authorized` last (`:14758`). `CORE_TOOL_NAMES` (`tool_schemas.py:51-57`) = 15; `shell` is core but gated → ordinary 14. Group union + core = all 70 builtins (counted; no orphan tool). Matches inventory 15/74.
- Reaching moderation etc.: `more_tools(group=…)` (`bot_tools.py:4808-4826`, schema enum `tool_schemas.py:468-476`) mutates the shared set; it is in `RESULT_TOOL_NAMES` so a follow-up runs; the loop rebuilds tools, protocol, tool prompt, custom prompt and re-budgets when the visible set changes (`bot.py:13219-13255`). Follow-up `tools=provider_tools` (`:13353`) is the refreshed list.
- Leak across turns/channels: none found. Per-message `ForegroundTurn` with set/reset in `finally`; jobs bind their own `TOOL_GROUPS_CONTEXT` set (`jobs.py:680`, reset `:839`). Child tasks share the set object by reference, which is what makes `more_tools` inside a gathered tool task visible to the parent.
- `_lean_chat_turn` still returns `False` (`bot.py:14715-14722`) with a docstring now stating the opposite of current behaviour ("every turn sees every registered tool"). Dead and misleading; inventory's historical section quotes it.
- Hidden tools are not blocked at dispatch: checks at `bot.py:13843-13850` are disabled/compatible/registered/authorized/breaker — no `_turn_tool_names` membership. A model naming `ban_member` from a memory trace, or via text recovery (`KNOWN_TOOL_NAMES`, `:14637`), executes without `more_tools`. Implementer says so ("Discovery hiding is not execution authorization"); `tool_prompts.py:36` ("Instructions naming a hidden tool do not bypass discovery") is prompt text, not enforcement. Not a regression versus round one.
- `_process_native_tool_calls` computes `eligible_names`/`turn_tools` per dispatch (`:14058-14074`) only to decide `tool_` prefix restoration; wasted work, harmless.

## C-18 — giant text recovery

**Verdict: PARTIALLY CLOSED — regex cost and argument size bounded; no chunk-count cap on replies.**

`recover_text_tool_calls`: input > 16 000 chars → no recovery (`tool_schemas.py:1652`); > 8 kept calls → reject whole (`:1766-1767`); any call whose coerced args serialize > 4 000 → reject whole (`:1786-1788`). `_coerce_args` itself unchanged (`:1555-1591`); the cap is applied to its output, which is fine. Round one's "cap chunks per reply (control)" is **not implemented**: `_split_response` (`bot.py:10257-10296`) and `prepare_delivery` (`response_observability.py:152-194`, unchanged) have no count cap; only the `length`-stop path is bounded (`_MAX_PARTIAL_CONTENT_CHARS = 16*1024`, `providers.py:636,1413`). A complete 12 345-token reply (~50 k chars) still yields ~27 messages. New behaviour: a reply > 16 000 chars or with > 8 text calls is posted as text including its tool markup; whether bare-JSON lines are scrubbed by `strip_tool_payload_leaks` I did not verify (definition not located in the two files grepped). Block does not claim a chunk cap, so no overclaim; the finding is simply not fully addressed.

## C-19 — media re-attached every follow-up

**Verdict: CLOSED for the re-attachment; NEW low-medium defect (silent drop of legitimately repeated images).**

Follow-ups now attach only the current round: `followup_images = iter_images` (`bot.py:13296`), `media=iter_media` (`:13351`); `all_tool_images/all_tool_media` removed. Turn-wide admission `admit_media` (12 items / 20 MiB, `turn_budget.py:84-93`).

New defect: `_process_native_tool_calls` admits with `turn.admit_media(key, …)` alone (`bot.py:14466-14470`, `:14484-14488`), while every other site uses `admit_media(...) or key in turn.media_keys` (`:12588`, `:12652`, `:12777`, `:11683`, `:11729`, `:11868`, `:11888`). `admit_media` returns `False` for an already-seen key (`turn_budget.py:86`). Because attachments are now per-round, a tool returning an image already admitted earlier in the turn (e.g. `see_image` on the same file after an edit, or the 13th distinct image) is silently not attached to that follow-up while the tool text implies it is. Model is not told.

## C-20 — raw tool_result stored uncapped

**Verdict: CLOSED.** `_remember_tool_call` (`bot.py:13902-14027`): params deep-copied, media-like values labelled, `params_text` ≤ 8 000 with `tool_params` replaced by a `_truncated` dict; `tool_result` markers/data-URIs labelled, ≤ 8 000 head/tail; `content` ≤ 16 000. `rag_memory.py:1689` still lists `tool_result` in `meta_keys`, bounded at source. Other `is_tool` writers (`bot_tools.py:1510-1516` prompt[:200]; `:8135-8141` chess line) carry no `tool_result`. The base64 heuristic (`[A-Za-z0-9+/=_-]+`, > 64 chars under media-ish keys, `:13921-13925`) goes beyond the finding and can mislabel a long token-like value; minor.

## C-21 — dead `more_tools` branch

**Verdict: CLOSED.** `tools_expanded`/`message._tools_expanded` removed (no hits in `bot.py`; `bot_tools.py` `MoreToolsTool` rewritten). Replaced by the live visible-set comparison at `bot.py:13219-13222`.

## I-02 — shared native-replay slot

**Verdict: CLOSED for both paths, by ordering not by structure.** Foreground: slots set at `bot.py:14539-14540`, read at `:13214-13217` immediately after the awaited dispatch returns with no intervening `await`. Jobs: snapshot at `jobs.py:789` right after dispatch. The instance-level slots remain a latent hazard if any await is later inserted between set and read.

## I-03 — attachment bytes (skimmed only)

Post-read size check `bot.py:10547-10549`; archive/image-MIME contradiction refusal `:10626-10632`, `:11537-11538`. Consistent with the block's own residual disclosures. Not deeply reviewed; outside this cluster's core.

## I-04 — catalog state vs foreground spend

**Verdict: CLOSED for catalog scope.** `TOOL_GROUPS_CONTEXT.set(set())` (`jobs.py:680`), per-step catalog rebuild with terminal failure (`:688-697`), system prompt refreshed each step (`:723`), reset (`:839`). Observation for root/C-06 (outside cluster): a model-spawned job inherits the `ForegroundTurn` object via context copy, so its `reserve()` is bounded by the originating turn's 600 s / 12 attempts / 32 768 tokens (`jobs.py:5-12` docstring, `turn_budget.py:60-72`), which undercuts `spawn_background`'s stated purpose.

## Custom protected prefix / strict native JSON

Prefix protection: `bot.py:15311-15319`, origin-agnostic as disclosed. Strict admission (`tool_schemas.py:1066-1177`) — regressions versus the lenient `_decode_tool_arguments` (`:929-999`, now unused by bot.py): whole batch rejected for `type` ≠ `function` (`:1124`), non-string id (`:1149-1152`), duplicate non-empty ids (`:1153-1157`), arguments decoding to a non-object (`:1101-1102`; previously wrapped as `{"content": …}`), **any single call's arguments > 16 000 bytes or batch > 32 000** (`:1005-1006`, `:1083`, `:1144`). The last one caps `send_file`/`shell` heredoc authoring at 16 kB per call and ends the turn with a generic public error (`bot.py:13666`) instead of a tool-error line the model could react to. The block says "rejects … oversized … batches before effects" (true) but does not state the 16 k/32 k limits or their effect on file authoring. Recovery path is unaffected by these (its own 4 000-char cap, ids `recovered_{i}_{name}`).

## AGENTS.md discipline (tool_policy.py, new tool_schemas.py code)

- `tool_policy.py:1-25`: no try/except, no `Any`, no type-ignores. Declares `_is_admin` on the Protocol then treats it as optional via `getattr` — mild defensive redundancy. Privileged set hard-coded in the function body.
- New `tool_schemas.py` code: only `json.JSONDecodeError` is caught (`:1059`, `:1996`); `object` typing; `_native_argument_depth_is_bounded` (`:1011-1030`) is a pre-validator duplicating what the JSON decoder would reject — extra validation, justified by bounded cost. Lines `:2013`, `:2016` exceed 100 chars.
- `turn_budget.py:108-114` catches a specific tuple. Fine.
- `bot.py`: `_remember_tool_call` media heuristic is beyond the finding's ask; `except Exception` at `:13615`/`:14748` are pre-existing patterns retained.

## Not read / not done

`validation.md`, all `review-*.md`/`micro-*.md` except `micro-reasoning-policy.md`; `providers.py` diff (C-01/C-12/C-14 cluster) beyond the `partial_content` cap; `_handle_message` timeout/cleanup wrapper in depth (C-06); attachment ingress beyond the anchors above; `strip_tool_payload_leaks` definition; `plugin_manager.py`; tests. No execution of anything; character figures are the implementer's QA61 numbers, not re-measured.
