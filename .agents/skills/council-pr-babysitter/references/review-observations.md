# Observed review gaps

## 2026-09-26 · Conversation context audit

The local Luna/max review of implementation `2b7afcc` reported no actionable code
findings after source tracing and did not run focused reproductions. A separate
external audit subsequently demonstrated gaps: runtime unresolved replies carry
a nonempty `reply_target` dict unlike the passing hand-built fixture; the separate
compaction prompt lacked the generation prompt's temporary-label rule; and the
renderer omitted image capture errors and external author/routing types.
The parent confirmed these against actual adapter/builder output and added
runtime-shaped regressions.

Correction: the brief now explicitly traces producer shapes, omitted field
semantics, and independent generation/compaction/persisted-state prompt variants.
Use focused reproduction for a concrete uncertainty, not another full-suite run
or arbitrary test/finding quotas. This is one observed review miss; recurring
limitations and a justified model change have not been established.

Detailed evidence remains in the project's ignored audit folder:
`audit/2026-09-26/02-context-compaction-review/REPORT.md` (F1–F4, F12–F13).

## 2026-10-01 · PR #75 check coverage

Luna/max returned READY around 18:24:14 UTC after consulting a workflow tool
that listed only pull_request runs. The PR check had passed at 18:24:03, but
the separately triggered push check did not finish until 18:24:26. The parent
caught the incomplete check coverage before merge; Luna confirmed the omission
and rechecked all runs at 18:26:26. Sol/high independently waited for both runs
and returned READY at 18:24:53. Both final verdicts were clean. Luna also found
an accurate documentation concern, which was fixed; that finding is separate
from her monitoring miss.

Correction: the reviewer brief now calls out workflow-list filtering and asks
for complete current-head checks/statuses, distinguishing identical names by
run ID/event. This is an observed monitoring mistake, not an application defect
or evidence to retire either model. Detailed evidence is in the ignored
`audit/2026-10-01/05-search-default-guidance/` folder and PR review digest.

## 2026-10-02 · PR #76 cancellation evidence

Sol/high found that a total request deadline discarded already-received HTTP
headers/body; Luna/max's initial review missed it. The parent's first correction
stored partial responses, but both reviewers then found that owner cancellation
left the response handle unreachable from console T evidence. Luna additionally
reproduced a diagnostic-write exception replacing the pending cancellation.
The parent confirmed these issues and added registry/console and injected-write-
failure regressions. These were application defects and incomplete fixes, not
false positives. Subsequent delta verification is not independent discovery.

Correction: when reviewing cancellation-time capture, follow evidence through
the supported inspection path and check diagnostic-write failure semantics.
Do not infer accessibility from direct SQL assertions or infer cancellation
propagation solely from a successful persistence callback. The owner’s dual
review settings remain unchanged; this PR does not establish a general ranking.
Detailed timings, findings and delivery status are in ignored
`audit/2026-10-02/02-dumb-search/REPORT.md` and the PR digest.
