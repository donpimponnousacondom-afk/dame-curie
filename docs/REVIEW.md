# Pull request and review protocol

This is the only review protocol. The `pr-review` skill points here and holds the reviewer brief.

## Branches and merges

1. Every change is a pull request to `main` from a `pr/*`, `hotfix/*` or `dev/*` branch. Root's branch ruleset forbids deleting branches outside these prefixes.
2. One active branch at a time. After a PR merges or closes, remove its worktree and local branch. GitHub deletes merged heads.
3. Never push to `main`. Never force-push.
4. Run `scripts/lint.sh` before you push. CI runs the same script.
5. Merge only when both reviewers say READY on the current head and all current-head checks are green:

```sh
gh pr merge <number> --squash --match-head-commit <full 40-character sha>
```

6. Deploy after merge with `scripts/deploy.sh`. See [OPERATIONS.md](OPERATIONS.md).

## Two independent reviewers

- Two reviewers of different models review every PR head. In Claude Code: one Sonnet agent and one Haiku agent. In Codex: `gpt-6-luna` at `max` and `gpt-6.1-sol` at `high`.
- Give both the same brief: intent, acceptance criteria, non-goals, changed paths, base and head SHA, measured test evidence and its limits. Do not prime them with a verdict.
- Tell reviewers up front that new tests are allowed and wanted.
- Keep initial findings independent: no cross-reviewer messages until both return their first digest.
- Reviewers are read-only. They do not edit the checkout, run the application, read private state or post to GitHub.
- A new commit invalidates the old verdict. Send both reviewers the new head and the delta.

## The director's part

- Verify each finding. Fix confirmed in-scope defects. No speculative refactors, weakened assertions or security-policy changes.
- Read a red CI job's log before any rerun. Distinguish code from infrastructure. After two attempts at the same failure, reassess the cause.
- Before readiness, query the complete current-head `statusCheckRollup` with `gh pr view`. Separate push and pull_request runs of the same name by run ID. A pending, missing or cancelled check is not a pass.
- Publish one digest per reviewed SHA as a PR comment, or update the existing one. Mark older digests stale.
- Escalate to root only for unavailable credentials, access, external intervention or a decision reserved for root.
