# Child report B — Whole-turn context/output economics of the native tool loop (Fable, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../03-DISPOSITIONS.md`.
Coordinator spot-verified: `_message_content_chars` alias (`bot.py:14504-14506`), `TokenBudgetTracker`
"tracking only" note (`bot.py:2262-2263`), `run_one` passing the raw `line` to `_remember_tool_call`
(`bot.py:13736-13738`), `tool_result` in RAG `meta_keys` (`rag_memory.py:1689`), compaction marker
non-idempotency (`tool_schemas.py:1717-1725`), and the constants/ordering in `trim_tool_tail`.
Catalog-size numbers are the child's source-text estimates, not measurements.

---

# Whole-turn context/output economics audit — native tool loop

Scope: read-only source review at HEAD c603cf2 (bot.py, tool_schemas.py, providers.py, tool_registry.py, rag_memory.py, response_observability.py, tool_progress.py, control_defaults.py, config.py). No code executed, no runtime/data/log access. All sizes below are derived from source text; where I extrapolate to tokens I say so.

Loop boundaries: the native tool loop is `for _iteration in range(max_iters):` at `bot.py:12853`, ending at the `finally: await self._release_ai_slot()` at bot.py:13027; post-loop terminal handling runs 13029-13235. Setup (max_iters, deadline, accumulators) is 12823-12852.

---

## 1. Transformations a tool round undergoes before the next request (in order)

| # | Step | Where | Bound |
|---|------|-------|-------|
| 1 | Tool runs; result string `"Tool {name}: {result_text}"` | bot.py:13483 | none |
| 2 | `record_reasoning` -> `_record_llm_trace` | tool_registry.py:78-127; bot.py:14082-14107 | reasoning 280 chars, param previews 200/value, file keeps last 300 entries |
| 3 | `_remember_tool_call` with the **raw, pre-truncation** `line` | bot.py:13737 (run_one), 13485-13517 | `reasoning` stripped, heavy param keys >2000 elided; result **unbounded** at this point |
| 4 | Base64 image/audio extraction into `tool_images`/`tool_media` | bot.py:13910-13937 | each blob <5,000,000 chars |
| 5 | `_truncate_tool_result`: strip b64 markers; head 16,000 + tail 16,000 if >32,000 | bot.py:13913, 13939-13946 | 32,000 chars/result (newest round only ever sees this cap) |
| 6 | `elide_tool_calls_for_history`: heavy keys `body/content/code/html/data` >2000 -> placeholder; unparseable arg JSON >2000 -> placeholder | bot.py:13560; tool_schemas.py:1728-1767 | **`reasoning` is not elided** |
| 7 | Assistant history message `{role: assistant, content: cleaned or None, tool_calls}`; `reasoning_content` never replayed (`ProviderResult.assistant_message` is unused in bot.py) | bot.py:13950-13964 | — |
| 8 | Accumulators: `all_tool_results.extend`, `all_tool_media.extend`, `all_tool_images` keep newest 12 | bot.py:12888-12895 | media unbounded; images 12 |
| 9 | `conversation_tail.extend(native_followup)` | bot.py:12912 | — |
| 10 | `trim_tool_tail`: **evict** whole oldest rounds while `count > 12 or used > 36,000` (using `message_chars`, which includes tool_calls args), **then** compact role=tool content of all-but-newest rounds to 4,000 + marker | tool_schemas.py:1679-1700, 1704-1725, constants 1626-1628 | 12 msgs / 36,000 chars |
| 11 | `_apply_prompt_budget(messages + tail)`: budget = 96,000 - 24,000 reserve = 72,000 chars default; trims non-first system blocks (to >=1000, <=8000), then `out[0]` (to max(12000, budget//3)), then `out[-1]` content (to >=8000). Never removes a message; never touches `tool_calls.arguments`; `tools=` payload not counted | bot.py:14717-14748, 14523-14544 | 72,000 chars (messages only) |
| 12 | `_generate_response(result_messages, images=all_tool_images, media=all_tool_media, max_tokens=max_out_tokens, tools=provider_tools)` — full catalog resent every round | bot.py:12983-12993 | OPENAI_MAX_TOKENS per round |

Budget pass and pairing (item 3 asked): step 11 can trim a role=tool message's content (last message in a native round is always role=tool) — safe. An assistant message with `content=None` fails `isinstance(..., str)` at bot.py:14742 and is skipped; an assistant with string content + tool_calls has only its content trimmed. No message is ever dropped, so the budget pass cannot orphan a `tool_call_id` or produce a 400. CONFIRMED.

---

## 2. Drop-before-compact — CONFIRMED (medium)

Status: CONFIRMED by complete control-flow reading of tool_schemas.py:1690-1700. The while-loop at 1693 pops `groups[0]` using `used` computed from uncompacted contents (1691); `_compact_old_tool_results(groups)` runs only at 1700 after eviction. Compaction is persisted in the shared `conversation_tail` dicts (in-place mutation, 1720), so the bug bites exactly once per round: at the round-N trim, round N-1 is still uncompacted (it was newest at round N-1).

Worked example (assistant msg ~300 chars incl. one-sentence `reasoning`; rounds 1-4 already compacted to 4,051 = 4,000 + 51-char marker; round 5 result 20,000 uncompacted; round 6 result 29,890 — the incident's failing-request size; 12 messages so no count pressure):

- `used` = 4 x (300+4,051) + (300+20,000) + (300+29,890) = 17,404 + 20,300 + 30,190 = **67,894**
- Current order: pop r1 -> 63,543; r2 -> 59,192; r3 -> 54,841; r4 -> 50,490; r5 -> 30,190 <= 36,000 stop. **Survivor: r6 only** (2 messages). Request = 4 base + 2 tail = 6 messages — this exactly matches the observed failing request shape (four base + one assistant + one 29,890-char tool result), and is consistent with the input drop 43,235 -> 38,600 tokens.
- Compact-first: r5 -> 4,351; `used` = 17,404 + 4,351 + 30,190 = 51,945; pop r1 -> 47,594; r2 -> 43,243; r3 -> 38,892; r4 -> 34,541 stop. **Survivors: r5 + r6** (4 messages).
- Minimal 2-round case: r1 = r2 = 20,000. Current: `used` 40,600 -> evict r1, keep r2 only. Compact-first: r1 -> 4,351, `used` 24,541 -> nothing evicted, both kept.

Minimal fix: move `_compact_old_tool_results(groups)` to before the while-loop and recompute `used = sum(message_chars(m) for g in groups for m in g)`; delete the trailing call at 1700. Invariant check: newest round intact (compaction skips `groups[-1]` at 1712; eviction keeps >=1 group at 1693) — held; `tool_call_id` pairing — held (compaction edits content only, eviction is whole-group via `tool_tail_groups` 1660-1676); message count — held (loop still enforces `count > max_messages`). No invariant violated.

Deeper problem the reorder does not fix (medium): the ratios are wrong. Per-result cap 32,000 vs tail cap 36,000 means any newest result >= ~31,650 leaves 36,000 - 32,300 = 3,700 chars, below one compacted round (4,351), so **at most the newest round survives regardless of ordering** whenever one result is near the cap. "12 messages" is nominal; realistically 1-2 rounds. Smallest fix: raise `TOOL_TAIL_MAX_CHARS` to at least `_MAX_TOOL_RESULT_CHARS + 2 x (TOOL_RESULT_COMPACT_CHARS + marker)` (~41k), or lower the newest-round cap.

Also (low, CONFIRMED): the compaction is not idempotent. Compacted content is 4,000 + ~46-51 chars > `TOOL_RESULT_COMPACT_CHARS`, so the `len(content) <= 4000` guard at 1717 fails on the next round and the marker is rewritten with `omitted` ~48-51 — the "N chars truncated" count is wrong from the second pass on. `marker_prefix` (1711) is defined but never used for detection. Fix: skip when `content[TOOL_RESULT_COMPACT_CHARS:].startswith(marker_prefix)`.

---

## 3. Budget blind spot — prior audit partly REFUTED (medium)

`_message_content_chars` (bot.py:14504-14506) is a direct alias of `message_chars` (tool_schemas.py:1631-1657), which **does** count `function.name` + `function.arguments`. The question "does it count tool_calls arguments at all" is answered yes; the prior framing was wrong.

The real blind spot, CONFIRMED: arguments are counted but never trimmable (only `content` fields are edited at 14733-14747), so a tail whose weight is in arguments (a long `reasoning`, un-elided keys) makes `total > budget` unrecoverable — the pass logs "Trimmed prompt to budget" (14747) and returns an over-budget prompt. Second blind spot: the `tools=` catalog is outside `_apply_prompt_budget` entirely (it only sees `messages`; the docstring at 14526-14527 admits "plus the tools= payload"). Quantified below: ~75k chars of tools vs a 72k-char message budget — the unbudgeted part is roughly equal to the whole budget.

---

## 4. REASONING_PARAM and catalog overhead (high, estimate)

Catalog composition for the incident's 73 tools: 70 built-in registrations (`self.tools[...] =` count in bot.py = 70) + 4 checkers plugin tools (plugins/checkers/tools.py:56,118,184,218) - `more_tools` discarded at bot.py:14194 = **73**. Matches the incident.

Serialized-size estimate (awk over source text, no execution):
- Descriptions: string-literal content of the 70 `get_description` bodies = 47,468 chars raw; after the 1,024 cap (tool_schemas.py:812-838) = 41,063 chars; 12 descriptions are cut with "…". Plus ~73 x 17 chars of contract suffix (tool_schemas.py:740-742) and 4 plugin descriptions: ~42.7k.
- `TOOL_PARAMETERS` (tool_schemas.py:49-772) whitespace-stripped = 16,844 chars; + plugin params ~1k: ~17.8k.
- `REASONING_PARAM` (tool_schemas.py:773-778) injected at 872 and forced into `required` at 880-886: ~108 chars + 12 for `"reasoning"` in required, x 73 = **~8.8k chars**.
- Per-tool wrapper JSON ~77 chars x 73: ~5.6k.
- Total **~75k chars/request**. At 3.3-4 chars/token for JSON: **~19k-23k tokens**, i.e. roughly 60-75% of the 30,007-token base input, resent unchanged on all 6 rounds (~115k-135k of the turn's 216,479 input tokens). `REASONING_PARAM` alone is ~2.2k-2.7k tokens/request (~13k-16k tokens across the 6 rounds).

Output side: the required `reasoning` string is one sentence per call (~20-60 tokens). It does **not** materially explain the 3,728 -> 12,345 output growth; that is `reasoning_content` from the thinking model. So "double reasoning" is real but asymmetric: the schema costs input every round; the model's private reasoning costs output. Two things that plausibly feed the per-round output growth (PLAUSIBLE, provider-dependent, not verifiable from source): (a) `reasoning_content` is never replayed into history (bot.py:13950-13954 builds the assistant message from `cleaned` + `tool_calls` only; `assistant_message` is unused in bot.py), so a thinking model may re-derive its chain each round; (b) the growing `tool_results` in the tail.

`extract_reasoning` (tool_registry.py:129-139) pops it before `execute`; `record_reasoning` (78-104) caps the trace at 280 via `_sanitize_reasoning`. Both fine. **Replay risk (high, CONFIRMED path):** `elide_tool_calls_for_history` heavy_keys = `("body","content","code","html","data")` (tool_schemas.py:1731) — `reasoning` is replayed verbatim into `assistant_msg.tool_calls` every round until eviction. Newest round is never compacted, `message_chars` counts it, `_apply_prompt_budget` cannot trim it. A 30k-char `reasoning` in the newest round evicts every older round while itself surviving; a ~400k one (see item 6) would go out unbounded. Smallest fix: add `"reasoning"` to `heavy_keys` with a small cap (e.g. 300, matching `REASONING_MAX_CHARS`) — or cap it in `normalize_native_tool_calls`.

---

## 5. Whole-turn budget — no aggregate output/cost cap (high, CONFIRMED)

Controls found:
- Iterations: `max_tool_iterations` (control_defaults.py:172 = 50; code fallback 30; clamp 0..100) — bot.py:12823-12828.
- Loop wall-clock: `tool_iteration_timeout_seconds` (control_defaults.py:173 = 3600) -> `tool_deadline`, checked only at iteration start (bot.py:12829-12831, 12854); an in-flight request is not interrupted.
- Per-request timeout: `ai_timeout_seconds` (control_defaults.py:165 = 3600; clamp 10..7200; bot.py:12239-12245) -> `aiohttp.ClientTimeout(total=timeout, connect=10)` (providers.py:2393). Worst case per turn ~2 h.
- Per-round output: `OPENAI_MAX_TOKENS` (config.py:194-196 default 16,384, 1..131,072; provider_settings.py:227-228) -> `max_out_tokens` bot.py:12246; 4,096 for short live turns (12247-12249).
- Usage is recorded (bot.py:12789-12792, 12995-12998) into `TokenBudgetTracker` (bot.py:2233-2280), whose enforcement was removed by design ("Tracking only — daily-budget enforcement was removed", 2264-2265).

No per-turn token or cost budget exists. Worst case with defaults: 50 x 16,384 = 819k output tokens plus ~50 x 30k+ input in one turn. The incident turn was 216,479 in + 42,660 out.

Cheapest place: in the loop, accumulate `usage.get("completion_tokens")` (and optionally `prompt_tokens`) at 12789-12792 and 12995-12998 into a turn counter; before `_acquire_ai_slot` at 12923 check against a new control (e.g. `turn_output_token_budget`), log, set a flag, `break`; after the loop, if the flag is set and nothing visible was sent, post one short notice through the existing `notice_send()`/`send_public_error` path. ~10 lines, no new module. Not implemented.

Note: the operator containment (12,345 + effort low) bounds one round; it does not bound the turn, and with the new terminal rule a length-cut round is fully paid and then discarded.

---

## 6. Text-tool-call recovery on a 398k-char reply (medium)

Path (CONFIRMED): first generation returns content with no `tool_calls` -> `_recover_text_tool_calls` (bot.py:12794-12795, 14046-14075) -> `recover_text_tool_calls(text, KNOWN_TOOL_NAMES)` (tool_schemas.py:1454-1616). On 398k chars it runs, synchronously on the event loop: gated XML dialects (cheap), the paren-call regex over 73 alternated names gated only on `(` and `=` (1546-1560; almost always present), the harmony regex, and an **ungated** `_JSON_OPEN_RE.finditer` + `_balanced_json_object` per hit (1573-1585). Up to `_RECOVERY_MAX_CALLS = 8` (1022) kept by position.

`wait -> wait -> no_response`: `KNOWN_TOOL_NAMES` explicitly includes `wait` (bot.py:1160-1167); `wait`/`no_response` are recovered from either bare JSON `{"name": "wait", ...}` or paren pseudo-calls `wait(seconds=…)` / `no_response(reasoning=…)` rehearsed in the dump. Dispatch: all three are terminal and run sequentially (bot.py:13587-13590, 13789-13876); `wait` caps at 10 s (bot_tools.py:1935-1941); `no_response` returns `__NO_RESPONSE__` (bot_tools.py:4799-4800). `_tool_results_need_followup` (bot.py:2103-2145): no RESULT tool, second pass hits `no_response` -> False -> `break` at 12898-12899. Post-loop 13030-13040: `_note_watch_silence`, `_ensure_reasoning_trace` returns early (tool_results non-empty), `return`. **User saw nothing**; the 398k leftover was discarded. Had no call been recovered, the reply would have gone through `_sanitize_visible_reply` (scrub_repetitions/break_echo_loop on 398k, synchronous) and `_split_response` into ~210 chunks of 1,900 with no chunk cap in the delivery loop (bot.py:13152-13195).

Huge recovered args (PLAUSIBLE magnitude, CONFIRMED path): `_balanced_paren_end` falls back to `len(text)` when unclosed (tool_schemas.py:1327-1340); `_pairs_from_paren_body` takes a value up to the next declared key or end of interior (1349-1373); `_coerce_args` (1376) does not cap. A recovered `reasoning` can therefore approach the whole 398k. Downstream: `record_reasoning` caps (safe); `_remember_tool_call` strips it (safe); `progress.update` whitespace-normalizes the full string (tool_progress.py:333); `elide_tool_calls_for_history` keeps it (item 4) — not exercised in this incident only because `no_response` ended the turn.

Does the finish_reason=length rule (74d827d) prevent this? **Yes for length-cut replies.** Stream: providers.py:1079-1082 raises `ProviderIncompleteResponseError` on the first frame carrying `finish_reason=length`; non-stream: 2834-2835; reasoning-only + stop: 2848-2861. At 3009-3014 it is re-raised without retry/failover. bot.py has no handler for it (no "Incomplete" match), so it lands in the generic `except Exception` at bot.py:13257 -> `send_public_error` (operator_commands.py:44-46) -> the user sees the fixed public error line ("I waited, waited and I am losing things like tears in the rain" plus a dove emoji). Caveats: the 543 s / 115k output tokens are still spent (detection is at stream end, not an abort); a runaway that stops under the cap still enters recovery; tool side effects already performed earlier in the turn stand, so a `send_message` followed by the public error is possible.

---

## 7. Other per-round growers

| Finding | Severity | Status | Anchor | Note / smallest fix |
|---|---|---|---|---|
| `all_tool_media` unbounded across rounds, resent as `media=` every followup | medium | CONFIRMED | bot.py:12889-12891, 12986 | mirror the images cap (keep newest N) |
| `all_tool_images` capped 12 but all 12 re-attached on **every** followup | medium | CONFIRMED | bot.py:12893-12895, 12934, 12985 | attach only the current round's images, or once |
| `_remember_tool_call` metadata `tool_result` stored **uncapped** in SQLite (content is capped 8,000, metadata is `json.dumps` of the raw result incl. any `__IMAGE_B64__` <5MB) | medium/high (disk) | CONFIRMED by reading | bot.py:13737 (raw `line`), 13514; rag_memory.py:1690-1700 (meta_keys), 1781 | cap `tool_result` in `_remember_tool_call`, or pass the truncated result |
| `all_tool_results` unbounded, in-memory only (marker scans) | low | CONFIRMED | bot.py:12888 | none needed |
| `_last_native_followup_messages` reset per dispatch, not accumulating | info | CONFIRMED | bot.py:13533, 14001 | — |
| `llm_traces.json` bounded to 300 entries; per-entry bounded via `record_reasoning`; `ReasoningLogTool` extra kwargs pass through unbounded; whole file read+rewritten on every tool call | low | CONFIRMED | bot.py:14082-14107; tool_registry.py:104-127; bot_tools.py:4757-4783 | append-only or cap extra kwargs |
| Dead `more_tools` expansion branch resets `max_out_tokens` to full `OPENAI_MAX_TOKENS` (would lift the 4,096 short-turn cap); `MoreToolsTool.execute` never sets `_tools_expanded` | info | CONFIRMED | bot.py:12867-12884; bot_tools.py:4818-4823 | delete branch |
| XML/custom path: `tool_tail_groups` puts each `role=user` result in its own group, so eviction can split an assistant/user pair (no 400 risk; coherence only; path unused when native is on) | info | CONFIRMED | tool_schemas.py:1660-1676; bot.py:12914-12922 | — |
| Channel transcript in base prompt bounded by `memory_context_budget` 48,000 chars clamped to remaining budget | info | CONFIRMED | bot.py:15295-15321 | — |

---

## Summary of verdicts on prior-audit claims

- "drop-before-compact" in `trim_tool_tail`: **CONFIRMED**, with the incident-shaped worked example; the reorder is safe against all three invariants, but the 32k-per-result vs 36k-tail ratio is the larger cause of the observed one-round tail.
- Implied concern that the budget does not count tool_calls arguments: **REFUTED** — it counts them (alias of `message_chars`); the actual gap is that it cannot trim them and excludes the ~75k-char `tools=` payload.
- REASONING_PARAM: material on **input** (~2.2-2.7k tokens/request, ~9-12% of the catalog), immaterial on **output**; the un-elided `reasoning` replay is the concrete risk.
- No aggregate per-turn output/cost budget: **CONFIRMED**; proposed insertion point given.
- finish_reason=length terminal rule: **CONFIRMED** it closes the 398k recovery/silence/210-chunk paths for length-cut replies; it does not reduce spend.

Files inspected: bot.py, tool_schemas.py, providers.py, tool_registry.py, rag_memory.py, response_observability.py, tool_progress.py, operator_commands.py, error_reporting.py, control_defaults.py, config.py, bot_tools.py (WaitTool, NoResponseTool, MoreToolsTool, ReasoningLogTool, description bodies), plugins/checkers/tools.py. Not checked: actual provider behavior regarding `reasoning_content` replay, real `llm_traces.json`/DB sizes, any runtime state.
