# Child report A — ProviderIncompleteResponseError control flow (Fable, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../03-DISPOSITIONS.md`.
Coordinator spot-verified: class hierarchy, raise sites, `bot.py:13236-13268` handlers, the 4,096 short-turn
clamp at `bot.py:12246-12249` / `_is_short_live_turn`, `fallback_disable_reasoning=True` default at
`providers.py:1675/1729`, and the empty-response recovery branch at `providers.py:2893-2949`.

---

# Adversarial review: `ProviderIncompleteResponseError` control flow (commit 74d827d, HEAD c603cf2)

Method: read-only source reading of `providers.py`, `bot.py`, `provider_telemetry.py`, `error_reporting.py`, `operator_commands.py`, `tool_progress.py`, `message_pipeline.py`, `jobs.py`, `autonomy.py`, `rem.py`, `guild_onboarding.py`, the commit diff and the tests it changed. No code executed, no runtime, no private paths, `legacy/` untouched.

Class hierarchy (verified): `ProviderIncompleteResponseError(ProviderResponseError)` at `providers.py:1248`, `ProviderResponseError(RuntimeError)` at `:1244`. It is **not** related to `ProviderEmptyResponseError(RuntimeError)` at `:1301`.

Raise sites (verified):
- SSE: `providers.py:1079-1082`, inside `for choice in obj.get("choices")` (`:899`) inside the line loop (`:866`) inside `async for raw_chunk in resp.content.iter_any()` (`:858`).
- JSON `length`: `providers.py:2834-2835`.
- Reasoning-only: `providers.py:2848-2861`.

---

## 1. Is there any enclosing retry/failover after the re-raise at 3014?

**Finding 1.1 — No enclosing retry; the doc claim holds inside the provider.**
Severity: info. Status: CONFIRMED by complete control-flow reading.

- Both raise sites (SSE via `_read_sse_response` call at `:2788-2795`; JSON at `:2835`/`:2861`) sit inside the single per-attempt `try:` at `:2387`. They land in `except RuntimeError as e:` at `:3009` (the earlier `except ProviderUsageExhaustedError` `:3000` and `except ProviderRequestError` `:3004` do not match). `:3010` `incident.failure(...)`, `:3012-3014` `isinstance(..., ProviderIncompleteResponseError)` -> `incident.capture(...)` -> bare `raise`. `_retry_after_attempt` (`:3016`) is never reached for this type.
- The `finally` at `:3049-3052` only acts on `asyncio.CancelledError`.
- The `while attempt < max_attempts:` loop (`:2315`) has no `try` wrapping it: `:2293-2315` contains only local setup; `:3053-3057` (post-loop "failed after retries") is unreachable when the body raises.
- `generate_chat_completion` and `generate_response` are decorated by `track_provider_activity` (`:1646-1658`), which is `try/finally` only. `generate_response` (`:2103-2168`) has no exception handling. `bot._generate_response` (`bot.py:2889-2893`) has none.
- `empty_response_recoveries` / non-streaming recovery (`:2340-2347`, `:2893-2949`) is only entered via `continue` paths this exception never takes. `_media_endpoint_order`/`_attempt_endpoint` are only consulted at loop top (`:2317-2333`), i.e. never again.
- There is no symbol `_endpoint_order` in the file.

**Finding 1.2 — `incident.failure(...)` then `incident.capture(...)` does not double-record.**
Severity: info. Status: CONFIRMED.
`failure()` (`:691-705`) marks `failed`, appends summary/traceback to `current`. `capture()` (`:722-736`) calls `finish_attempt()` once (`:707-719`, serialises `current` into `attempts`, clears it) and calls `capture_incident` exactly once (`error_reporting.py:335-351`). Neither raise site calls `incident.failure` itself (only malformed-JSON frames do, `:887-888`). One provider-level store record per failure.

The later `logger.error` in `bot.py:13258` also reaches `IncidentLoggingHandler.emit` (`error_reporting.py:365-398`): the record has no `incident_id`, `exc_info` is None, but `sys.exception()` inside the `except` block is the same exception, which carries `incident_id` set at `providers.py:735-736`; `IncidentStore.record` (`error_reporting.py:288-298`) finds the existing id and merges rather than inserting. Not a duplicate. (`_merge_incident` body not read.)

---

## 2. bot.py call sites: what the user sees, what is released

**Finding 2.1 — Foreground turn: user gets the generic public error; cleanup is complete.**
Severity: info (behaviour), low (log noise). Status: CONFIRMED.

`_handle_message` (`bot.py:12208`). Generation `try:` at `:12714`. Primary call `:12772-12780` with `_acquire_ai_slot` `:12768` / `finally: _release_ai_slot()` `:12781-12782`. Handlers: `CancelledError` `:13236`, `ProviderUsageExhaustedError` `:13239`, `ProviderEmptyResponseError` `:13248`, then `except Exception` `:13257-13266`. `ProviderIncompleteResponseError` falls into the generic handler: `logger.error("Error handling message: ...", traceback)` and, if control `error_replies` is on, `send_public_error` (`operator_commands.py:44-46`) posts `PUBLIC_ERROR_TEXT` (`error_reporting.py:24`, the "tears in the rain" line) and sets `normal_reply_sent = True`.

`finally` `:13267-13312`: `_end_inflight_context`, `_exit_live_typing`, `stop()` on every entry of `active_progresses` (`:13272-13277`), `forget_shell_progress`, `_current_progress_by_channel.pop`, `_active_requests`/`_active_request_user` pop if this task (`:13291-13293`), `_tick_media_context`, `_replying_channels.discard`, `_flush_deferred_context_extraction`, `_last_bot_reply`/`_arm_conversation_watch` (because the error reply counts as `normal_reply_sent`). The reply-queue pump (`message_pipeline.py:301-346`) never retries a failed turn; `_handle_message` swallows anyway.

Streamed preview: `_on_token` (`bot.py:12706-12712`) feeds `gen_progress.tick` (`tool_progress.py:358-399`) which edits the posted progress message. `stop()` (`tool_progress.py:550-582`) cancels the deferred post and fire-and-forget deletes the message. So the partial preview is removed, not orphaned. In DMs `gen_progress` is None (`bot.py:12633-12637`) so nothing was ever shown.

Note: the exception is not `ProviderEmptyResponseError`, so a now-expected operator-induced condition (cap hit) is logged at ERROR with a full traceback (`:13258`) instead of the WARNING used for the empty-response path (`:13249`). Smallest fix: add `except ProviderResponseError as e:` beside `:13248` with the same body at WARNING level (import at `bot.py:359-360`).

**Finding 2.2 — Native tool follow-up loop: already-executed tool side effects stand, then the generic error.**
Severity: low. Status: CONFIRMED.
`:12983-12992` wrapped by `except Exception:` `:12993-12998` which stops `followup_progress` and re-raises; escapes the `for _iteration` loop (`:12912`), `finally: _release_ai_slot()` `:13031`, into the handler at `:13257`. Any `send_message`/shell already dispatched in earlier iterations remains visible; the user then sees `PUBLIC_ERROR_TEXT`. No re-generation. `_recover_text_tool_calls` (`:14046-14075`) never runs because it consumes a returned `response`, which does not exist.

**Finding 2.3 — Other call sites** (all CONFIRMED):
- `bot.py:3157` LTM summarizer: `except Exception` `:3193-3195` -> warning, returns `[]`. Silent.
- `bot.py:6249` DM-call decision: `except Exception` `:6268-6270` -> deny. Silent.
- `bot.py:7814` `_vc_generate_ai_response`: try/finally only; caller `_handle_vc_utterance` `try:` `:7881` / `except Exception` `:7991`. The substring check at `:7995` ("empty response"/"provider call failed") does not match the new messages, so it takes the non-info branch. No voice output.
- `bot.py:8586` `_onboard_ask_llm`: try/finally; `guild_onboarding.py:388-405` catches and falls back to first option.
- `bot.py:9845` context watcher: `except Exception` `:9871-9872` -> warning.
- `autonomy.py:3068`: `except Exception` `:3082-3089` logs and re-raises to `tick()` backoff. Nothing posted.
- `jobs.py:714/723`: `except Exception` `:737-742` -> `failure_text = "generation failed at step N: <exc>"`, `break`; `:812-816` `_fail` (`:558-567`) records the incident, marks the job `error` with that text, and posts `PUBLIC_ERROR_TEXT` in the origin channel and thread. The exception text ("Provider response reached the output token limit") contains no private content.
- `rem.py:314/323` via `run_rem_once` try/finally (`:388`, `:426-440`), propagates to `bot.py:8889` (handler not traced; STATUS.md says REM is off on the live instance).
- `message_pipeline.py`, `channel_watch.py`, `voice_live.py`: no provider calls (grep).

---

## 3. SSE partial content discarded on `finish_reason=length`

**Finding 3.1 — Behavioural regression for legitimate long plain-text answers under the 12,345 cap; no path delivers partial content.**
Severity: medium (text), info (tool calls, where the new behaviour is safer). Status: CONFIRMED for the code path; PLAUSIBLE for frequency (depends on whether the endpoint counts reasoning tokens inside `max_tokens`, which the 115,200-token incident implies).

Before the commit `_read_sse_response` only recorded `finish_reason` (`:1080`) and continued to `[DONE]`; the message was assembled from every delta (`:1150-1165`) and returned; nothing downstream reads `finish_reason` (`generate_response :2103-2168`). Truncated text was posted or fed to `_recover_text_tool_calls` (STATUS.md:23 records `wait`->`wait`->`no_response` recovered from such text). Now the raise at `:1082` discards content, tool calls and reasoning regardless of how much was streamed.

Delivery paths checked: the only exposure is the live preview, deleted by `stop()` (2.1). `transition_to_final` (`tool_progress.py:590`) runs only on success. No continuation ("continue where you left off") logic exists (`finish_reason`/truncation greps in `bot.py` hit only tool-result truncation `:13939-13970`).

Budget: `max_out_tokens = OPENAI_MAX_TOKENS` (`bot.py:12246`), forced to `min(..., 4096)` for `_is_short_live_turn` (`:12247-12249`, def `:14250`), passed as `max_tokens` (`:12776`, `:12988`) and placed in the payload as `max_tokens` (`providers.py:1987-1994`). Nothing adapts after a `length` finish: `_endpoint_output_caps` is learned only from HTTP 400 "maximum output tokens" (`:2695-2740`). The primary request is fully consumed and then thrown away, so the "no paid retry" claim is true but the paid call yields nothing.

User experience: preview streams for the duration of the generation, vanishes, `PUBLIC_ERROR_TEXT` appears. With a short-turn cap of 4096 and reasoning enabled ("low" per STATUS.md), banter turns may hit this too (PLAUSIBLE).

Smallest fix: in the SSE reader, when `finish_reason == "length"` and `content_parts` is non-empty and `tool_calls_by_index` is empty (pure text), do not raise; keep streaming to `[DONE]` and return the message with an explicit marker (e.g. leave `finish_reason: "length"` in `merged["choices"][0]` and have `generate_response` append a short visible "[output truncated at the token limit]" suffix). Keep the raise for tool-call and reasoning-only cases. Same split at `:2834-2835` for JSON.

---

## 4. The "reasoning without answer" rule (`:2848-2861`) and `OutputObservation`

**Finding 4.1 — Rule cannot misfire for whitespace content with custom/XML tool markup or for empty `reasoning_details: []`.**
Severity: info. Status: CONFIRMED.

`OutputObservation` (`provider_telemetry.py:113-150`): `.reasoning: dict[int, list[str]]`, one string per observed delta/message for that choice, computed by `reasoning_content()` (`:95-110`) from `reasoning_content`, then `reasoning`, then `reasoning_details` items of type `reasoning.text`/`reasoning.summary`. `any(observation.reasoning.get(0, ()))` is True iff some observation for choice 0 had non-empty reasoning text.

- `reasoning_details: []`: `message.get("reasoning_details")` is falsy and `reasoning_content()` returns `""` -> `any([""])` is False -> falls to the empty-content retry at `:2893-2949`. `tests/test_provider_error_reporting.py:453-456` covers `reasoning_content: ""`.
- XML/DSML/bare-JSON tool markup in `content` makes `content.strip()` non-empty -> rule skipped -> bot-side `_recover_text_tool_calls` (`bot.py:14046`).
- `custom_tool_calls=True`, SSE: `_CustomToolCallBuffer` (`providers.py:126-310`) strips the JSON and rebuilds `content_parts` from `text_parts` (`:1125-1139`, possibly empty) while `tool_calls` is populated -> `not message.get("tool_calls")` is False -> skipped. JSON (non-stream) path applies no custom extraction (`generate_response` does none), so the JSON stays in `content` -> non-empty -> skipped.
- Note: the rule can never see a `length` response (both paths raise earlier at `:1082`/`:2835`); it exclusively converts `finish_reason=stop` reasoning-only replies into terminal failures. See 6.1.

**Finding 4.2 — Truthiness of `message.get("reasoning_details")` is broader than `reasoning_content()`.**
Severity: low. Status: CONFIRMED (code), PLAUSIBLE (provider shapes).
A non-empty list of non-text items (e.g. encrypted/redacted reasoning blocks) or a non-string truthy `reasoning` (dict echo) with empty content and no tool calls now raises terminal instead of taking the empty-content retry that could reach the fallback. Nothing deliverable either way; the difference is retry versus terminal. Smallest fix: replace the three `message.get(...)` checks with `provider_telemetry.reasoning_content(message)`, which already normalises all three fields.

---

## 5. Telemetry lost by raising inside the SSE loop; connection release

**Finding 5.1 — No structured token telemetry survives an SSE `length` stop.**
Severity: medium. Status: CONFIRMED.

The raise at `:1082` precedes the same-frame usage merge (`:1086-1093`) and every later frame, including the trailing `choices: []` usage frame requested by `stream_options.include_usage` (`:1984-1985`). `observation.finished_s` (`:1099`) is never set. `build_call_metrics` (`:2952-2958`) is never reached: no `CallMetrics`, `_last_usage` (`:2965`) unchanged, no "Provider timing done" log (`:2968-2977`), and `bot.py:12785-12788` `_token_tracker.record` never runs. The test at `tests/test_provider_error_reporting.py:343-344` asserts `read_chunks == 1`, i.e. the reader stops at the first chunk containing the `length` frame.

The incident record (`_ProviderDiagnostics.begin` `:636-666`, `finish_attempt` `:707-719`) contains request parameters (`max_tokens`, model), message field shapes, status, header timing, selected headers, routing flags, elapsed ms, failure summaries, tracebacks and the raw body bytes read so far (`:861-862`). Token counts are present only if the provider embedded `usage` in an already-read frame, and then only as raw text. The 115,200-token figure that motivated the change would not be recorded as a metric under this code. Smallest fix: on `length`, set a flag and keep draining to `[DONE]` so the usage frame merges, then raise after the loop (before `:1107`) with the merged usage attached to the exception (`e.usage = ...`) and recorded into `incident.current`.

**Finding 5.2 — Incident details carry the full raw streamed body with no size cap.**
Severity: low. Status: CONFIRMED (no cap found in `error_reporting.py:146-174`, `:282-302`).
Pre-existing pattern, but this raise makes it routine. At 12,345 tokens that is tens of KB of model output (reasoning included) per incident in the store; restoring a larger cap scales it linearly.

**Finding 5.3 — Connection release.**
Severity: info. Status: PLAUSIBLE (needs runtime or installed source).
The exception exits `async for ... iter_any()` (`:858`) and `async with session.post(...) as resp:` (`:2388-2393`); aiohttp's context manager releases the response and, with an unread body, closes rather than pools the connection. `aiohttp>=3.14.0` (`requirements.txt:4`) is not installed in `.venv` (`.venv/lib/python3.14/site-packages` has no `aiohttp`), so this is inferred from aiohttp's documented semantics, not read. Expect no leak; expect no keep-alive reuse of that socket.

---

## 6. Other reliance on the removed promotion; DeepSeek-family impact

**Finding 6.1 — The commit removed retry/fallback for reasoning-only `stop` replies on every model, not only DeepSeek promotion.**
Severity: high if the configured DeepSeek model actually emits answers in `reasoning_content` (unverifiable statically); medium otherwise. Status: CONFIRMED for the code path and tests; PLAUSIBLE for the model quirk.

- Repo grep (excluding `legacy/`, tests): `reasoning_content` appears only in `providers.py:934-937, 960, 1156, 2855` and `provider_telemetry.py:95-96, 122, 287`. No `_reasoning_content_is_answer`, `reasoning_to_content` or promotion consumer anywhere else; `bot.py` never reads `reasoning_content`.
- Tests encoding the new behaviour: `tests/test_providers.py:881-889` (`test_reasoning_only_response_is_terminal`, parametrised with `deepseek-v4-flash`, `deepseek/deepseek-v4.1-flash:nitro`, `grok-4.6`, asserting a single request and no fallback), `:892-913`, `tests/test_provider_telemetry.py:448-456`, `tests/test_provider_error_reporting.py:295-347`.
- Removed tests (diff): `test_reasoning_only_response_is_not_treated_as_empty` (DeepSeek promoted to "pong") and `test_reasoning_only_not_promoted_for_non_deepseek_models` (grok fell through to the empty-response path). `test_empty_response_recovery_keeps_original_shape_and_nonstream_switch` previously used `reasoning_content: "private scratchpad"` and asserted recovery to `"ok"` through the fallback; the commit changed the fixture to `""` to keep it passing.
- Consequence: a `finish_reason=stop`, empty-content, non-empty-reasoning reply from any model is now terminal (`:2861`), whereas before it entered `empty_response_retries` non-streaming recovery (`:2907-2949`), which rotates to the fallback endpoint (created with `fallback_disable_reasoning=True` by default, `:1675`, `:1722-1731`) — the natural recovery for exactly this failure. DeepSeek-family replies that legitimately carry the answer in `reasoning_content` will always fail with "reasoning without an answer or tool call" and the user sees `PUBLIC_ERROR_TEXT`. `docs/STATUS.md:17` documents the terminal choice as intended, so this is a trade-off flag, not an undocumented change.

Smallest fix if the trade-off is reconsidered: delete the `raise` at `:2861` and let the existing `if not content and not message.get("tool_calls")` branch (`:2893`) handle reasoning-only `stop` replies (bounded by `empty_response_retries`), keeping both `length` raises terminal. If cost containment must hold, at least gate the terminal raise on `endpoint.name == "fallback"` or on `len(self._endpoints) == 1` so a single fallback attempt is still allowed.

---

## Not checked
- Runtime behaviour of aiohttp release, actual provider `max_tokens` accounting for reasoning tokens, and whether any DeepSeek model in use emits answers in `reasoning_content`.
- `_merge_incident` internals, `_is_short_live_turn` heuristics, and `run_rem_once`'s caller handler at `bot.py:8889`.
