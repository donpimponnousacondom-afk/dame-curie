# Core implementation handoff

**Temporary review evidence.** Shared source tree remained mutable while this lane worked; source and test writes are now frozen at the coordinator's request. No commit was created. This lane did not import the application, collect/run tests, lint, build, install, access private/runtime state, use network, stage files, or commit. The report is documentation only and does not certify integration or acceptance.

## Scope and changed files

- `bot.py` — foreground incomplete-response delivery now uses the sanitizer-safe `INCOMPLETE RESPONSE:` cutoff label; initial and follow-up incomplete outcomes remain terminal, and delivery/memory/metrics follow the producing call and confirmed chunks. `TokenBudgetTracker.record` retains canonical `input_tokens`/`output_tokens` and explicit `total_tokens` without synthesizing totals. The same file also owns the current-turn catalog view and exact eligible plugin-name dispatch/replay integration.
- `providers.py` — foreground calls reject configured or payload `n` unless it is exactly integer `1`, before reservation/POST. Present `max_completion_tokens` and `max_output_tokens` must be positive integers and are clamped to the admitted `max_tokens` value before reservation and again after reservation; lower values remain lower. This is applied on each rebuilt attempt. Unrelated extra-body keys and the nonforeground path are left unchanged.
- `tool_schemas.py` — native arguments require a bounded UTF-8 envelope/depth and a fully consumed JSON object; direct Python objects reject nested non-string keys. No scalar, array, trailing-markup, or `key=value` fallback is admitted. Normalized calls retain their exact provider `raw_name` for eligible plugin resolution and canonical replay.
- `turn_budget.py`, `bot_tools.py`, `tool_prompts.py` — foreground turn state exposes progressive group expansion; `MoreToolsTool` expands through the shared accessor; prompt guidance directs hidden inbox/chess/workflow capabilities through discovery rather than calling unavailable schemas immediately.

No files were staged or committed. Parent-owned `jobs.py` and `tests/test_background_jobs.py` are outside this lane's ownership.

## Existing test-case adaptations

No new test function or test file was added. The existing cases changed or used for this lane are:

- `tests/test_foreground_observability.py::test_real_foreground_handler_preserves_producing_call` — existing parameterized modes now include `followup_incomplete`; checks sanitizer-safe cutoff on full/partial delivery, second-call metrics, no third generation/recovery, canonical usage counters, and confirmed-only persistence. Deadline fixture now returns an awaited coroutine from a synchronous `Mock`; partial assertion matches its constructed payload.
- `tests/test_provider_error_reporting.py::test_healthy_json_and_sse_never_capture_incidents` — existing budgeted fake-request case covers `n=2` rejection without reservation/POST, `n=1`, competing alternate caps, preserved unrelated extra body, and unchanged nonforeground payload behavior.
- `tests/test_tool_calls.py::test_normalize_native_tool_calls_decodes_provider_argument_shapes` — strict malformed/trailing/scalar/array/native-envelope cases and raw provider name preservation.
- `tests/test_tts_silent.py::test_dispatch_native_runs_nonterminal_tool` — paired failures and malformed-batch atomicity; `::test_dispatch_native_records_tool_history_in_memory` — exact prefixed-plugin/builtin collision routing, original replay names, and nested image/audio parameter redaction; `::test_prompt_budget_trims_large_background_blocks` — protected prompt/schema budget behavior.
- `tests/test_token_trim.py::test_every_turn_offers_every_registered_tool` and `::test_tool_prompt_lists_full_catalog_on_chat_turn` — real actor and bound foreground turn; invoke `MoreToolsTool.execute` before checking expanded schemas/prompt. `tests/test_prompt_behaviour.py::test_protocols_do_not_ask_for_a_placeholder_send` and `::test_protocol_tells_him_to_pick_his_own_chess_moves` — progressive-discovery wording.
- `tests/test_operator_commands.py::test_help_is_bounded_and_lists_operator_commands` — configured `?` prefix and malformed `?job` usage. `tests/test_rem_commands.py::test_rem_command_admin_gating_and_on_off_fix` — configured comma-prefix fallback usage.

These are selector recommendations for the coordinator's isolated integrated QA, not evidence that this lane ran them.

## Exact parent-attributed QA available at freeze

Parent-reported **QA51**:

- Frozen tree `869157081116c6968c177e7f1954e0e56e418f37`, based on `be7a9d146695c0e17a4eae256d508e1f90e1f40d` plus only `jobs.py` and `tests/test_background_jobs.py`.
- Ruff command: `ruff check --target-version py314 --select F821,F822,F823 jobs.py tests/test_background_jobs.py` — passed.
- Test command: `python -B -m pytest -o addopts=-ra -q tests/test_background_jobs.py` — **39 passed**, 1.21 s, exit 0.
- Parent reported frozen image `sha256:a81175b66e37c3aabcb2d6f92e087af49974126e87e60064bbfd890695383792`, network disabled, read-only root, all capabilities dropped, no-new-privileges, disposable tmpfs for suite/tmp/state, synthetic environment, and no private mounts.

QA51 covers only the named background-job slice. It does not include this lane's changed source/test files and is not integrated-core QA. The coordinator is taking the first frozen integrated snapshot and will run the next isolated selection. No result for that snapshot is claimed here. Earlier provider-only QA49 is recorded in `implementation-luna.md` and is also not integrated-core QA.

## Remaining integration concerns and limits

1. **No integrated run yet.** Provider reservation, turn-budget accounting, native admission, bot dispatch/replay, progressive catalog rebuilding, final sanitization and delivery must be tested together on the coordinator's frozen snapshot. This report cannot say they pass.
2. **Provider semantics remain unverified.** The source clamps both recognized alternate caps because provider precedence is ambiguous; it does not claim every endpoint implements those fields identically. No live/provider request or network check occurred. Retry, learned endpoint-cap and fallback behavior require synthetic request assertions in the integrated selection.
3. **Persisted tool-result media needs separate scrutiny.** The adapted C20 case verifies recursive omission of embedded media from persisted tool parameters while raw arguments still reach the tool. It does not establish that arbitrary tool-result strings containing embedded media are redacted before persistence; `_remember_tool_call` applies its result-length cap separately. Do not treat the parameter test as proof of result-value sanitization.
4. **Catalog scope is not authorization.** Discovery tests use a real actor and bound foreground state, but integrated background catalog filtering/refresh and the `JOB_TURN` `spawn_background` exclusion remain coordinator-owned. Parent QA51 was against a background-only frozen slice, not this full bot/catalog composition.
5. **No runtime, artifact, or release claim.** No application image/build, provider call, Discord interaction, private configuration read, deployment, or temporary-channel acceptance was performed by this lane. The broader audit's attachment/archive/MIME, process/document reconciliation, full safe-suite, and bounded temporary acceptance work remains open in the audit ledger.
