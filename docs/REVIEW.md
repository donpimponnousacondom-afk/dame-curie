# Pull request and review protocol

This is the only review protocol. The `council` and `babysit-pr` skills in `.agents/skills/` hold the steps and the reviewer brief. Root set this protocol on 6 November 2026, for now.

## Branches and merges

1. Every change is a pull request to `main` from a `pr/*`, `hotfix/*` or `dev/*` branch. Root's branch ruleset forbids deleting branches outside these prefixes.
2. One active branch at a time. After a PR merges or closes, remove its worktree and local branch. GitHub deletes merged heads.
3. Never push to `main`. Never force-push.
4. Run `scripts/lint.sh` before you push. CI runs the same script.
5. Merge only when all three council members say READY on the current head, all current-head checks are green, and the branch is not BEHIND or DIRTY:

```sh
gh pr merge <number> --squash --match-head-commit <full 40-character sha>
```

6. Deploy after merge with `scripts/deploy.sh`. See [OPERATIONS.md](OPERATIONS.md).

## Council

- Three models from three providers review every PR head through T3 Code: Claude Opus 5.5, GPT Sol 6.1 and Muse Wonder Full 1.0, at high effort. The exact targets are in the `council` skill. The exact Muse model is `muse-wonder-full-1.0`, not `muse-wonder-1.0`.
- Do not substitute a member. If one is unavailable, report it to root, and do not merge without root's go.
- Give all three the same brief: intent, acceptance criteria, non-goals, changed paths, base and head SHA, measured test evidence and its limits. Do not prime them with a verdict.
- Tell reviewers up front that new tests are allowed and wanted.
- Keep their reviews independent. Do not share one member's report with another inside a round.
- Members are read-only. They do not edit the checkout, run the application, read private state or post to GitHub.
- Each round is new delegates on the current head. A new commit invalidates the old verdicts.
- Each member returns a score out of 10 and READY or NOT READY. The scores go in the PR description, not in a comment.

## Babysitter

A Claude Haiku agent watches each PR head with `pr-wait`, and reports checks and comments. It gives no merge verdict and changes nothing. See the `babysit-pr` skill. CI runs lint only, so the test evidence comes from `scripts/qa.sh`.

## The director's part

- Verify each finding. Fix confirmed in-scope defects. Reject the others with evidence and give that evidence to the next round. No speculative refactors, weakened assertions or security-policy changes.
- Keep the scope of the PR. List declined items as follow-ups.
- Read a red CI job's log before any rerun. Distinguish code from infrastructure. After two attempts at the same failure, reassess the cause.
- Before readiness, query the complete current-head `statusCheckRollup` with `gh pr view`. Separate push and pull_request runs of the same name by run ID. A pending, missing or cancelled check is not a pass.
- Escalate to root for unavailable credentials, access, external intervention, a council member that still objects after it has seen your evidence, or a decision reserved for root.
