---
name: council
description: Independent review of a dame-curie pull request by three models from three providers, through T3 Code. Use before any merge, when a PR head changes, or when root says 'council'.
---

# Council

Adapted from `skills/council` in t3dotgg/tstack (MIT; see [TSTACK-LICENSE](../TSTACK-LICENSE)). The protocol is [docs/REVIEW.md](../../../docs/REVIEW.md). Read it first.

This skill stays in the repository because it needs T3 Code to reach three providers, and every member and harness of this project can read it here.

If you were started as a council member, do the review yourself. Do not start a council or any other agent.

## Before a round

Address open PR comments, fix known issues and run `scripts/lint.sh` and `scripts/qa.sh`. Give the council the updated head. Do not defer a known fix until the reviews return.

## Members

Root names the members. Use these exact targets, at high effort:

| Member | `providerInstanceId` | `model` | `options` |
|---|---|---|---|
| Claude Opus | `claudeAgent` | `claude-opus-5-5` | `{"effort":"high"}` |
| GPT Sol | `codex` | `gpt-6.1-sol` | `{"reasoningEffort":"high"}` |
| Muse Wonder Full | `muse` | `muse-wonder-full-1.0` | `{"reasoningEffort":"high"}` |

- `muse-wonder-1.0` is a different model. So are the `-contributor` models and the `CLIProxyAPI/muse/...` models under the OpenCode provider. Do not use them.
- Call `orchestrator_capabilities` once and check that each target exists.
- Start one `delegate_task` per member in one response, with `role: "review"`, `mode: "async"` and no `isolation`. They read the shared checkout. Do not push or check out while they read it; the brief pins the SHA.
- If a member is unavailable or a newer Sol exists, report it to root. Do not substitute a model. Do not merge without root's go.
- Do not poll a running delegate. Each round is new delegates, never a message to an old one.

## Brief

Give each member the same text. Do not give it your verdict or another member's report.

> Independently review the pinned Dame Curie pull request. You are read-only: no edits, commits, checkouts, pushes, merges, runtime actions, provider calls, private-state reads or GitHub comments. Do the review yourself; start no agents.
>
> Repository: `/home/codexy/deepseek/dame-curie`. PR [URL], base [full SHA], head [full SHA]. Read `AGENTS.md`, `docs/REVIEW.md`, the full diff (`git diff <base> <head>`, `git show <head>:<path>`), the relevant contracts in `docs/` and the callers of changed code.
>
> Intent and acceptance: [requirements]. Non-goals: [scope]. Evidence: [commands, counts, CI links, limits]. New tests are allowed and wanted; do not flag them.
>
> Trace changed behaviour and its failure paths: permissions and state isolation, ordering, configuration parameters on the wire, data correctness. Check the hard rules in `AGENTS.md`: configuration is sacred, failures stay visible, no word triggers, container time zone. A green check and this summary do not prove correctness.
>
> Report each actionable regression with severity, file and line, a reachable trigger, the consequence and the evidence. Separate pre-existing issues, optional polish and uncertainty. A clean review is valid; there is no finding quota.
>
> Return: the reviewed SHA, findings or "no actionable findings", residual risks, a score out of 10, and READY or NOT READY.

For a later round, add the earlier findings, what changed, and your objections with their evidence. Keep the full brief: each round is a fresh review of the new head.

## After each round

- Verify every finding against the source yourself. A member can be wrong, and an agreeing majority is not proof.
- Fix confirmed findings that are in scope. Reject the others with evidence, and give that evidence to the next round.
- Summarize the useful findings, disagreements and next steps to root.
- Count each full pass as one round. A new commit makes the old verdicts stale.
- Continue until all three say READY on the current head. If a member still objects after it has seen your evidence, root decides.
- Fight scope creep. Repeated reviews grow a PR one cheap-looking fix at a time. Decline the rest with a written reason, and list them as follow-ups.

## Results

Put the results in the PR description, before the attribution line. Edit the description. Do not post a comment for this.

```markdown
## Council review

Rounds: 2

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| Claude Opus 5.5 | 7/10 | 9/10 |
| GPT Sol 6.1 | 8/10 | 10/10 |
| Muse Wonder Full 1.0 | 7/10 | 9/10 |
```

If a member gives no score, write `no score`. Do not invent one.
