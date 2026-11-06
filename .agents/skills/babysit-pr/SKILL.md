---
name: babysit-pr
description: Monitor a dame-curie pull request through CI and comments. Use when a PR is open, when its head changes, or when root asks to monitor, watch or babysit a PR.
---

# Babysit PR

Adapted from `skills/babysit-pr` in t3dotgg/tstack (MIT; see [TSTACK-LICENSE](../TSTACK-LICENSE)). `scripts/pr-wait` is an unchanged copy. The protocol is [docs/REVIEW.md](../../../docs/REVIEW.md).

Root's assignment: a Claude Haiku agent babysits each PR. The babysitter watches and reports. It is not a council member and gives no merge verdict. It does not edit, push, merge, or post comments.

## Start it

The director starts one babysitter per PR, after each push:

- In Claude Code: the `Agent` tool with `model: "haiku"` and `run_in_background: false`.
- In another harness: `delegate_task` with provider `claudeAgent` and model `claude-haiku-5-5`.

## Waiting

Never write your own watcher, polling loop or `sleep` loop. There is one watcher per PR, and in this project it is `pr-wait`. T3 Code does not let a delegated child call `watch_pull_request`, so the director does not call it for this PR either. All watchers on a GitHub account share one rate limit.

From the repository root:

```bash
.agents/skills/babysit-pr/scripts/pr-wait <pr> --until green
```

Use `--until green`. This repository has no Greptile or Macroscope, so the default `ready` never finishes.

- The command exits 0 when the checks are green on the head or the PR merged.
- It exits 1 when it needs action: a failed check, a conflict, a closed PR, or GitHub stayed unreachable. With `--until green` a BEHIND branch is only an event line, so report it.
- It exits 2 on bad input, or when another pr-wait watches this PR.
- Stdout has one line per real event. It remembers what it reported, in `~/.local/state/pr-wait/`, so a restart loses nothing.
- If your shell limits one command, run it again until it exits. Do not start a second copy. If it says another pid watches the PR, report that.

## Report

Return, for the head you watched:

- The full head SHA, and if the head changed while you watched.
- Each check with its run URL and its result. This repository has one workflow, `quality`, with one job, `lint`. CI does not run the tests.
- For a failed check, read its log and state the cause. Separate a repository failure from an infrastructure failure. Do not rerun it.
- Each new comment or review, with its author and link, and the merge state.

Only report checks and comments that are newer than the latest push.

## GitHub rate limits

`gh pr create`, `gh pr view` and `gh pr checks` use GraphQL. When GraphQL is used up, the REST limit is separate. Use `gh api repos/<owner>/<repo>/pulls/<n>` to read a PR, and `gh api repos/<owner>/<repo>/commits/<sha>/check-runs` for checks.

## The director's part

- A green report is news, not a merge decision. Check the gate in `docs/REVIEW.md` yourself.
- Verify each finding from a bot or a person against the source. Fix real findings. Reply with a written reason to the others.
- Right before a merge, run `git fetch` and read the PR again. Do not merge when it is BEHIND or DIRTY. Rebase, push, and start the babysitter again.
