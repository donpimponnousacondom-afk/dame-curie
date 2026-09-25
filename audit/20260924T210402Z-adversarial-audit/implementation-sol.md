# Sol source lane — bounded tool history and delivery settlement

**Temporary audit evidence; retire after accepted independent round two.** Baseline `aad36e6`; shared worktree has parallel parent/agent changes outside this lane. No commit, application import, test/collection, Docker/runtime/private read, provider/network request or install in this lane.

## Owned source changes

- `tool_schemas.py`: retain a maximum of 12 messages and 36,000 counted replay characters. Compact older assistant/tool/synthetic-result text to 4,000 *before char eviction*, then cap the newest complete batch at 24,000; under pressure it can shrink to 16,000 to retain an immediately preceding batch. Multi-result content shares the group allowance. Drop whole oldest batches, never half a native assistant/call-result set. Validate exact native IDs/results and reject orphan/mismatched or oversized immutable batches; text fallback assistant plus `=== TOOL RESULTS ===` user message is a single group. Tool-result truncation markers keep cumulative omitted counts when re-compacted. History-only argument copies cap `reasoning` to 300 characters, other long string fields to 2,000 and serialized JSON per call to 4,000, including previously unlisted/nested-large keys. Argument data used for actual dispatch is not modified. Executable text recovery scans at most 16,000 input characters; any recovered argument JSON over 4,000 rejects the entire candidate batch without executing a subset and returns the original text to the caller's separate delivery cap.
- `tool_progress.py`: `transition_to_final` reports `True` only after a settled edit or a fallback send returning a message. When both fail, it returns `False` so the caller may send chunk zero. A cancelled edit can have committed remotely without its receipt: propagate cancellation without deleting the possibly final original; `stop()` cannot later delete it. Once an edit has failed and fallback is attempted, remove the stale progress post cosmetically after fallback settles or is cancelled.

## Existing test adaptations (no new functions/files)

- `tests/test_tool_calls.py`: rationale/argument limits, text fallback pairing and strict malformed-native rejection.
- `tests/test_custom_tool_calls.py`: three-result, four-round replay; total/newest caps, useful preceding batch, repeat-trim and accurate omission count.
- `tests/test_text_tool_call_recovery.py`: whole-recovery rejection on oversized input or one oversized argument among several calls.
- `tests/test_tool_progress.py`: former live-provider `.env`/HTTP test replaced **in the same function** with fake SSE chunks/client and actual parser-to-progress callbacks; edit/send double failure and cancelled-after-remote-edit behavior included in existing tests.
- `tests/test_token_trim.py`: unchanged.

## Caller integration and invariant limits

The coordinator owns `bot.py` admission before side effects: a native batch exceeding eight calls, duplicate/missing IDs, oversized IDs/names or unbounded raw argument envelopes must be rejected. Construct replayed assistant calls from **normalized IDs and JSON-string arguments**, not raw provider objects (which may lack IDs or carry argument dictionaries). If a single group's immutable overhead or message count cannot fit, `trim_tool_tail` raises `ValueError`; neither silently split a batch nor exclude it from the budget. Base prompt, `tools=` schema payload, media and total turn spending are outside this 36k text-replay budget and belong to caller accounting. On no-receipt cancellation, the edit may be visible despite no local success report; keeping it is safer than deleting a user's answer. Coordinator owns partial-chunk/memory honesty and final fallback.

## Static checks and proposed isolated QA

`git diff --check` for the six owned source/test files succeeded. No tests or application imports were run here, so there are **no passed-test claims**. Coordinator should run credential-free isolated QA on `tests/test_tool_calls.py`, `tests/test_custom_tool_calls.py`, `tests/test_text_tool_call_recovery.py`, `tests/test_tool_progress.py`, and unchanged pairing cases in `tests/test_prompt_cache.py`, plus its delivery-call-site cases. The former streaming case is now synthetic; never execute the original live-provider body from the baseline. No runtime/deployment effect from source edits alone.
