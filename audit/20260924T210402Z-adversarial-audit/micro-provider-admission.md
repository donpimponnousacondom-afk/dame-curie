# Micro-audit — foreground provider admission

## Result

The interrupt snapshot already satisfies the assigned contract. No provider implementation or test edits were needed. The checked `providers.py` and `tests/test_provider_error_reporting.py` are byte-for-byte unchanged from tree `e47270b89faa6c0c93d76d1bb74b760baa6b9700` (`git diff` of those paths was empty).

## Source evidence

- `providers.py:1855-1867`: foreground admission rejects present `n` unless exact integer `1`; rejects present `max_completion_tokens` and `max_output_tokens` unless positive exact integers (`bool` excluded).
- `providers.py:2420-2427`: when a foreground turn exists, validates raw `self.extra_body` at generation entry, before availability initialization, session acquisition or endpoint selection. This also rejects malformed primary extras when fallback/vision would otherwise be selected first.
- `providers.py:2045-2084`: `prefer_fallback=True` selects the configured fallback on the first non-media attempt; media routing can select vision first (`:2050-2065`).
- `providers.py:2189-2217`: only the primary payload receives configured `extra_body`; fallback/vision payload extras remain untouched.
- `providers.py:2584-2592`: each selected payload is validated/clamped before reservation, then `max_tokens` is set to reserved output and both aliases are clamped again. The minimum preserves already-lower positive alias values; absent aliases and unrelated keys are not added or removed by the clamp.

## Existing-case coverage

`tests/test_provider_error_reporting.py::test_healthy_json_and_sse_never_capture_incidents` (`:724-759`) already exercises the requested admission edge:

- malformed boolean `max_completion_tokens` and zero `max_output_tokens`, with `prefer_fallback=True` and a configured fallback;
- rejection leaves requests empty, `turn.output_remaining` at 512 and `turn.attempts` unchanged at 8;
- the following primary request starts with configured `max_tokens` above remaining budget; the final request asserts `max_tokens == 512`, the too-large alias re-clamped to 512, lower alias preserved at 128, and unrelated extra preserved.

The selector makes the tested fallback-first route explicit (`providers.py:2077-2084`). No new test function or test file was added. Tests were not run, as instructed.

## Changed lines and limits

Only this report was created: `audit/20260924T210402Z-adversarial-audit/micro-provider-admission.md` (lines 1-27). No source/test lines changed. Source review only; no runtime or behavioral claim beyond the inspected control flow and existing assertions. No unresolved issue found within this bounded contract.
