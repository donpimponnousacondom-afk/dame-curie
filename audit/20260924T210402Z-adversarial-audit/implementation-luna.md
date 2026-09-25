# Provider Incomplete-Response Implementation

**Temporary review evidence. Retire after accepted round two.**

Baseline: `aad36e6`. Scope: C-01, C-11, C-12, C-13, C-14 provider/error-reporting lane only. No budget/deadline hooks, bot dispatch changes, runtime changes, or deployment work are included.

## Outcome

- JSON and SSE `finish_reason="length"` now raise `ProviderIncompleteResponseError`, carrying a fixed safe `classification`, bounded `partial_content` (16,384 characters maximum, with `partial_content_truncated`), finish reason, usage, and `CallMetrics`. Partial text is not included in `str(error)` or exception `repr`.
- Only response content is eligible for partial display. Readable reasoning stays separate; tool-only/native-tool-only cutoffs yield no partial prose. Custom-tool JSON in text is cut off before its opener, preserving only preceding prose. No tool calls or assistant message are returned on this terminal exception, so this path cannot dispatch recovered/native tools or trigger retry, empty-response recovery, or endpoint fallback.
- After an SSE length frame, the reader drains for usage only, bounded to 64 KiB and 1 second. It merges usage trailers, records whether `[DONE]` arrived and whether the drain timed out, and still propagates caller cancellation. A drain timeout/interruption remains terminal and is not retried.
- Reasoning-only stop uses `reasoning_content(message)`, including readable reasoning aliases/details; opaque metadata without readable reasoning does not trigger that classification or promote text to content.
- Provider diagnostic body capture keeps at most 64 KiB of raw bytes (head/tail plus omission count); decoded response text and direct upstream-error detail are similarly bounded. Persisted incident traceback/details are capped at 256 KiB characters, again retaining head/tail with a truncation marker.

## Settlement interface

For `ProviderIncompleteResponseError`:

- `.usage` contains only available provider-reported numeric counters: `input_tokens`, explicit `output_tokens`, `reasoning_tokens`, and/or explicit `total_tokens`; missing fields are omitted, and reported zero is retained. `output_tokens` is omitted if it could only be inferred from total usage. Gemini output is included only when both candidate and thought counts are reported.
- `.metrics` always carries the `CallMetrics` record. When provider usage is absent, metric estimates remain available but are not settlement evidence. Settle output only from `.usage["output_tokens"]`; an absent output count is unknown, not zero.
- Normal successful `ProviderResult.usage` is synthesized from metrics. Its `output_source == "provider"` follows the existing telemetry helper, which can derive output from reported total minus input; parent should decide whether that is sufficient for successful-response refunds. The success result does not expose raw provider counters separately.

Unknown-spend paths include transport/network failures, cancellation, timeouts before a terminal response, malformed/rejected responses without usage, and incomplete responses whose output counter never arrived. Do not refund those reservations as zero. Parent owns reservations before each actual `session.post`; this slice makes no admission, retry-budget, or deadline hook changes.

## Changed files

- `providers.py` — typed terminal outcome, bounded post-length SSE drain, reported usage/metrics, bounded provider diagnostics.
- `error_reporting.py` — bounded traceback/details at incident creation and merge.
- `tests/test_provider_error_reporting.py`, `tests/test_providers.py`, `tests/test_error_reporting.py` — adapted existing cases only; no new test functions or files.

`provider_telemetry.py` was not changed. `tests/test_streaming.py` and `tests/test_streaming_primary.py` were not changed; they are provider-facing smoke scripts and were not run.

## Existing QA selection for the coordinator

Run only in the separately authorized synthetic, isolated Python 3.14.4 environment; this agent did not execute or collect tests.

- `tests/test_provider_error_reporting.py::test_bounded_http400_body_is_private_with_exact_request_metadata`
- `tests/test_provider_error_reporting.py::test_upstream_exception_keeps_private_details_without_public_body` (both current parameters)
- `tests/test_provider_error_reporting.py::test_http200_incomplete_response_is_typed_bounded_and_terminal` (all current parameters: JSON/SSE, upstream error, prose/large/custom/native/reasoning length cutoffs, length drain timeout, total-only usage, readable and opaque reasoning cases)
- `tests/test_provider_error_reporting.py::test_empty_response_recovery_keeps_original_shape_and_nonstream_switch`
- `tests/test_provider_error_reporting.py::test_midstream_network_error_retains_received_body_and_trace`
- `tests/test_provider_error_reporting.py::test_cancellation_in_next_attempt_preserves_prior_http_failure`
- `tests/test_provider_resilience.py::test_supported_sse_framing`
- `tests/test_provider_resilience.py::test_explicit_sse_errors_never_return_partial_success`
- `tests/test_provider_resilience.py::test_empty_stream_failure_reports_framing_counts`
- `tests/test_provider_resilience.py::test_unterminated_tail_is_not_silently_discarded`
- `tests/test_providers.py::test_reasoning_only_response_is_terminal`
- `tests/test_provider_telemetry.py::test_reasoning_only_is_terminal_and_custom_json_is_counted_once`
- `tests/test_provider_telemetry.py::test_stream_usage_keeps_last_valid_count_across_partial_trailers`
- `tests/test_provider_telemetry.py::test_stream_usage_merges_nested_partial_details_without_summing`
- `tests/test_error_reporting.py::test_bounded_body_exception_chain_and_provider_diagnostics`

No application imports, test collection/execution, dependency install, build, provider call, Docker operation, private-file access, or Git commit was performed in this lane. Static review included `git diff --check` on the owned files; no output/errors. Parent owns isolated QA, cross-review, budget integration, and acceptance.