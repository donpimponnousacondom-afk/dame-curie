# Independent lifecycle / admission review

**RETIRE AFTER ACCEPTED ROUND TWO.** Temporary source-review evidence only; not operating authority, QA acceptance, or a release receipt.

Reviewed the shared `dev/phaseII_v2` tree at `HEAD ab64853c93eb0268c976a5a3444d49fcd1f4f50a` with uncommitted remediation, then rechecked the author follow-ups in status, smoke receipts, and two narrowly assigned viewer changes. Static-only. No source/test edits, imports, collection/execution, lifecycle execution, Docker/runtime/private reads, dependency/network access, delegation, or commits.

## Findings

### C-36 — initial blocker resolved in current source recheck

The prior reviewed snapshot captured owned container state at `scripts/dirac.py:362-367` but allowed expected bridge/layout validation failures to escape before `main()` printed its report. The author follow-up now catches only the expected failures after state capture: bridge semantic validation `ValueError` (`374-379`) and private-layout `OSError`/`ValueError` (`381-386`). It returns the verified status/image/exit/OOM/finish fields, a safe config-unavailable reason, an explicit readiness skip, and exit code 1. The existing `test_status_reports_absent_container_without_mutating` case now exercises bridge and layout failures with a running and exited container and verifies metadata retention (`tests/test_dirac_operator.py:407-434`).

The catch boundaries are appropriately narrow. `owned_container()` and `container_state()` remain outside them (`364-367`), preserving ownership and inspect failures. I do **not** require catching `RuntimeError` from `outbound_bridge()`: `Instance.docker()` raises `RuntimeError` for Docker command failure/nonzero status or stderr (`scripts/instance.py:183-187`), not for the expected bridge-validation conditions (`ValueError`). A network-inspect command failure remains fail-closed rather than being presented as an ordinary config validation result. No false stopped/healthy status is produced on the handled validation paths.

### C-37 admission/settlement — no further confirmed blocker in the reviewed path

- `ReplyQueue.cancel_message_with_task()` returns the exact running task or the exact queued-removal result; the legacy bool method delegates without changing its contract (`message_pipeline.py:364-398`). The pump assigns `state.running` and `running_message_id` before its first await (`301-315`); the real bot binds `_track_task`, which returns the same task (`bot.py:2823-2837,4569`). The runtime calls the receipt API directly (`dirac_runtime.py:860-866`): no bool fallback and no `_channels` introspection.
- A registered pre-start task is available even while `_Turn.task` is still `None`; the runtime uses that exact task for cancellation/settlement (`dirac_runtime.py:704-735`). A queued removal is distinct. An already-done matching task returns `(False, task)` in the queue API and `_wait_for_settle()` treats its `.done()` state as settlement (`message_pipeline.py:387-398`; `dirac_runtime.py:810-828`). No runtime behavior conflates `(False, None)` with settlement.
- The new retained receipt is installed before the interruptible wait (`dirac_runtime.py:723-735`). A known task still live at the bound stays behind `_stuck`; the poll loop blocks admission until that exact task is done, reconciles `returned` and delivered IDs, removes only the provisional suffix, and leaves the original failed/timeout/interrupted status intact (`522-531`, `361-371`). Taskless, unconfirmed injection instead sets the fail-stop gate and does not discard the observer or unhook instrumentation (`739-746`; cleanup retains hooks for unsettled turns at `332-359`).
- The no-turn case is not inferred from `(False, None)` alone. The notice contains a literal bot mention (`smoke_protocol.py:229-255`); the real `_on_message_impl` checks the actual message content for that mention (`bot.py:3603-3625`) and, on the directed guild path, synchronously reaches `_dispatch_reply()`/`ReplyQueue.submit()` before returning (`bot.py:6135-6162`, `4498-4505`, `3504-3523`). Its gate returns do not schedule this directed notice through the soft debounce path. Thus normal handler return plus no exact queued/running/started work can support the no-turn/drop receipt. The fake-only case is not the proof; the source path is.
- External `CancelledError` is recorded and re-raised (`dirac_runtime.py:672-752`); an upstream `TimeoutError` is separated from the request deadline with `deadline.expired()` (`683-692`). Cleanup cancellation leaves the retained receipt available for `stop()` to settle; a write failure fails the poll/retains hooks rather than admitting another request. If the status mount itself cannot be written, an on-disk terminal receipt cannot be guaranteed; the existing fail-closed behavior and stale-record recovery are the limit, not proof of settlement.

**Delivery uncertainty — addressed in the current source recheck.** The send wrapper still records an ID only after the HTTP send returns a payload (`dirac_runtime.py:431-441`), but the receipt now says `delivered_ids` are confirmed IDs and unacknowledged sends may still have reached Discord both for turn exceptions (`728-731`, retained through `_reconcile_settled_input`) and normal failed/no-ID outcomes (`631-643`). It does not invent an ID or claim `no_response`. Existing parametrization of `test_a_silent_turn_is_a_failure_not_a_pass` covers a fake send accepted with its response lost, both caught and raised (`tests/test_dirac_smoke.py:59-78,817-843`); the stuck partial-delivery case verifies the qualifier survives settlement (`1690-1745`). This is an explicit uncertainty receipt, not proof of the external delivery outcome.

## Narrow viewer-redaction spot-check

Reviewed only `scripts/log_console/safety.py:71-90` and the relevant `EvidenceRedactor` value/span state (`92-114`), plus the existing generic-diagnostic parameterization in `tests/test_log_console_events.py:185-203`. `fields()` now calls `self.value(item)` before replacing a sensitive-key value with `[REDACTED]`. That lets a hidden value such as `api_key: "-----BEGIN PRIVATE KEY-----"` set private-key span state before the following `body` field is traversed; the body is then redacted rather than leaking `opaque-secret`. The two pertinent existing inputs cover an image-prefixed diagnostic and standalone JSON; both EventParser and AppendParser paths assert the payload secret is absent, while AppendParser additionally asserts its span state is clear and the following ordinary record is unaffected. The fix is scoped to the omitted state transition, with no counter/schema change. No broader viewer review or test execution was done here; coordinator reports QA41's frozen snapshot includes this hunk, not a result independently verified by this review.

**Verdict:** no issue found in this narrowly reviewed hunk/state flow.

## Narrow post-gap health-display spot-check

Reviewed only `scripts/log_console/console.py:39-42`, `scripts/log_console/render.py:105-115` (and the viewer-summary scope exception at `60-62`), and the existing health-coalescing case `tests/test_log_console_render.py:259-283`. `Console.ingest()` feeds raw source lines to `HealthDisplay` only when the retained entry is not viewer-owned. After a redaction continuity gap, AppendParser emits `viewer.omitted` records; these no longer join the health coalescer. In live rendering, viewer-owned entries bypass health `hidden` state and use no health repeat note, while `state.visible()` still governs display. The extended existing case covers two post-gap GIN lines, verifies they do not re-enter pending health state, then passes an explicit hidden sequence and synthetic repeat note and confirms the omission marker remains visible and unmodified. No issue found in this bounded change. No broader viewer rerun or source review was done.

## Operator and isolation checks

The stopped/dead restart path checks owned state before private preparation and refuses without removing the container, retaining state/exit/OOM/finish/image-reference evidence in its error (`scripts/dirac.py:324-340`). Running restart remains the explicit Docker restart path. The edits reviewed in `scripts/dirac.py` do not alter `service_account()` or `Instance`; the existing account re-exec, private deployment/socket identity, rootless-engine, and ownership checks remain in `scripts/instance.py:111-187` and `owned_container()` (`scripts/dirac.py:212-228`).

## Scope, QA handoff, and limits

Read `AGENTS.md`, `TODO.md`, audit originals C-36/C-37 in `01-AUDIT-REPORT.md` and their disposition in `03-DISPOSITIONS.md`, `implementation-lifecycle.md`, the requested Dirac/operator/smoke/message-pipeline tests, and the relevant bot admission/observer, response-observability, smoke-protocol, instance-ownership, and embedding-checker source. Rechecked author follow-ups in `scripts/dirac.py`, `dirac_runtime.py`, `tests/test_dirac_operator.py`, and `tests/test_dirac_smoke.py`. For the bounded viewer appendices only, read `scripts/log_console/safety.py`, `console.py`, `render.py`, the directly relevant history/health state flow, and the existing diagnostic/health test cases. No general viewer rerun/review or generation/tool/command pipeline review in `bot.py`.

Coordinator reported isolated QA41 on frozen tree `9b53c52dec958112315f747d59807fa31c2ac613`: 302 tests passed in 57.24s, including the lifecycle follow-ups and sensitive-field redactor change. This is coordinator-reported and was not run or independently validated here. The subsequent `console.py`/`render.py` health-display follow-up is not in that QA41 snapshot; coordinator plans QA42 across six viewer suites. Earlier coordinator-reported QA on `2cd14b1248d7abbe85e0c5c887df073f78f42ca` passed 298 selected cases; the two failures on older tree `907bb269ab22b8f011d5e5542b434dbfba67fcc8` were the stuck-task deadline/partial-delivery variants, addressed by separating known tasks from taskless unknown injection.

Coordinator QA selection; existing cases only:

- `tests/test_dirac_operator.py::test_start_replace_reports_the_previous_state_before_removing`
- `tests/test_dirac_operator.py::test_status_reports_absent_container_without_mutating` — now includes expected bridge/layout failures and verifies ownership/inspect failures still raise.
- `tests/test_dirac_smoke.py::test_a_silent_turn_is_a_failure_not_a_pass[silent]`, `[lost_response_caught]`, `[lost_response_raised]`
- `tests/test_dirac_smoke.py::test_an_input_that_expires_while_queued_never_runs`
- `tests/test_dirac_smoke.py::test_an_input_the_bot_never_dispatches_is_recorded_as_no_turn`
- `tests/test_dirac_smoke.py::test_unconfirmed_stop_cannot_resume_into_notice_or_injection[injection]`
- `tests/test_dirac_smoke.py::test_stop_interrupts_the_request_in_flight`
- `tests/test_dirac_smoke.py::test_the_deadline_covers_the_notice_not_only_the_turn`
- `tests/test_dirac_smoke.py::test_an_upstream_timeout_is_not_the_request_deadline`
- `tests/test_dirac_smoke.py::test_a_stuck_owned_task_holds_back_the_next_request[deadline]`, `[after_partial]`, `[stop_during_cleanup]`
- `tests/test_dirac_smoke.py::test_fatal_poll_io_cleans_only_owned_inputs_and_restores_hooks[record_write]`
- `tests/test_dirac_smoke.py::test_fatal_poll_with_missing_status_storage_reports_unavailable`
- `tests/test_dirac_smoke.py::test_a_stalled_readback_cannot_downgrade_a_completed_turn`
- `tests/test_dirac_smoke.py::test_stop_during_a_readback_keeps_the_completed_record`
- `tests/test_log_console_events.py::test_generic_diagnostics_do_not_emit_auth_or_configuration_arrays`
- `tests/test_log_console_render.py::test_live_health_requests_stay_coalesced_but_history_keeps_every_record`
- `tests/test_message_pipeline.py::test_cancel_message_cancels_one_input_and_leaves_other_rooms_alone`
- `tests/test_message_pipeline.py::test_cancel_message_removes_a_queued_input_before_it_runs`
- `tests/test_message_pipeline.py::test_running_message_id_names_the_input_being_answered` — extend within the existing case to assert the already-completed `(False, task)` receipt.

No test was run or collected by this reviewer. No real Discord delivery outcome, worker liveness, or post-write-failure persistence is proven by this static review. QA41 is coordinator-reported; the post-QA41 console/render change still awaits coordinator-reported QA42 on six viewer suites and final integrated acceptance.
