---
name: pr-review
description: Independent review and monitoring of a dame-curie pull request by two read-only reviewers of different models. Use when a PR is ready, when its head changes, or when reporting merge readiness. The director fixes findings and owns publication.
---

# Dame Curie PR review

The protocol is [docs/REVIEW.md](../../../docs/REVIEW.md). Read it first. This skill adds only the reviewer brief. It grants no push, merge, runtime or private-data permission.

## Launch

1. Record the PR number, base SHA and full head SHA. Prepare one brief with intent, acceptance criteria, non-goals, changed paths and measured evidence with its limits.
2. Start two independent reviewer agents of different models with the same brief. Do not share one reviewer's report with the other before both first digests arrive.
3. After both digests: verify, fix, push, then send both reviewers the new head and the delta. Repeat until both say READY on the current head and all checks are green.

## Reviewer brief

> Independently review the pinned Dame Curie PR and its current-head checks. You are a read-only reviewer: no edits, commits, checkouts, pushes, merges, runtime actions, provider calls, private-state reads or GitHub comments. Execute the review yourself; do not spawn another reviewer.
>
> Repository: `/home/codexy/deepseek/dame-curie`. PR [number/URL], base [full SHA], head [full SHA]. Read `AGENTS.md`, `docs/REVIEW.md`, the full diff, the relevant contracts in `docs/` and the callers of changed code.
>
> Intent and acceptance: [requirements]. Non-goals: [scope]. Evidence: [commands, counts, CI links, skips and limits]. New tests are allowed and wanted in this project; do not flag them.
>
> Trace changed behaviour and its failure paths: permissions and state isolation, ordering, configuration parameters on the wire, data correctness. Check the hard rules in `AGENTS.md`: configuration is sacred, failures stay visible, no word triggers, container time zone. Green CI and the implementation summary do not prove correctness. Hand-built fixtures can omit real variants; trace the real producer shapes.
>
> Report each actionable regression with severity, file and line, a reachable trigger, the concrete consequence and evidence. Separate pre-existing issues, optional polish and uncertainty. A clean review is valid; there is no finding quota.
>
> Watch all current-head checks with bounded waits, at most 60 seconds per interval. Before READY, read the complete `statusCheckRollup` of `gh pr view` and separate push from pull_request runs by run ID. If the head changes, mark the review stale and review the delta.
>
> Return: reviewed SHA, findings or "no actionable findings", check status with URLs, residual risks, and READY / NOT READY / INCOMPLETE.
