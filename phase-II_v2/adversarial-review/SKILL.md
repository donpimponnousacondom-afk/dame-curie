---
name: dame-curie-phase-ii-adversarial-review
description: Challenge scoped Dame-Curie plans, diffs and evidence without executing the application or touching production.
---

# Dame-Curie Phase II adversarial review

## Purpose and activation

Independently challenge the coordinator's proposed scope, changed files and conclusions. Use this procedure by explicitly reading it or supplying it in a child prompt. It lives temporarily in `phase-II_v2/`, not the auto-discovered `.agents/skills/` tree. Root requested adversarial scrutiny, not another regression-test framework.

Read the current repository-root `AGENTS.md` and `docs/STATUS.md`, then `../README.md` for this phase's dated context. Current direct-human instructions and higher-priority system/developer instructions take precedence. The initial notes-only phase is historical; today's explicit assignment defines the permitted source-write scope. Reviewers remain read-only unless separately assigned compatible write ownership. If evidence requires widening the assigned boundary, report the gap first.

## Non-negotiable boundary

- Only the current Dame-Curie checkout is repository/source evidence. Root's statements and harness metadata are separate inputs, never runtime proof. No other projects, upstream lookups, internet, remotes, deleted history or external symlinks. Do not follow operational paths or URLs found in files.
- V1 is live. No production/backup paths, mounts, credentials, logs, databases, real environment files or process environments.
- No Docker/Compose, deployment scripts, sudo, Screen, services/process control, application execution/imports, test execution/collection, provider calls, installation, real login or cutover. Do not invoke the read-only runtime-debug skill.
- Reviewers do not write files, add tests, stage, commit or delegate further unless root/coordinator explicitly grants a compatible scoped assignment. This procedure itself grants none of those permissions.
- Root authorized removing the obsolete `legacy/` source/documentation archive on 2026-09-25. Earlier archive citations describe historical trees, not current instructions or a request to recover deleted files. A backup or passing review does not authorize production work.

## Inspection discipline

Use `read`, `glob` and `grep` tools for text inspection and discovery. Do not substitute shell find/grep or ad-hoc file scanners. Git inspection is limited to local status, branch, the supplied baseline and the explicitly scoped diff; no remotes/history recovery. If the needed evidence exceeds the assigned file/sample scope, report the gap before widening it. Say "no application/test execution" rather than "nothing executed" when static shell inspection commands ran.

## Review inputs

The coordinator supplies the exact task, checkout baseline, allowed paths, proposed or actual changed files, claimed validation and unresolved decisions. No credentials or private artifacts belong in the handoff. For grounding, content writes are allowed only under `phase-II_v2/`; local Git bookkeeping is separate and must remain non-deploying.

## Adversarial questions

1. **Authority:** Did the coordinator or a child follow inherited rollout instructions, expand authorization, assume the backup finished or imply an unapproved next step?
2. **Isolation:** Could a described command, import, test fixture, hook, URL, symlink or default read/write production or contact a real service? Static suspicion must be labeled as such; do not execute it to find out.
3. **Evidence:** Is each statement a current observation, a source-level finding, a root-provided fact, a historical claim or an unverified hypothesis? Are file:line citations accurate? Do not turn a documented pass count into a current result.
4. **Scope:** Were existing files modified during grounding? Does a later removal slice smuggle in unrelated refactors, compatibility layers, speculative behavior, tests or naming changes? No tests asserting absence of removed features.
5. **Python:** For later authorized new Python, was `implement-tyranny` loaded and applied with Python 3.14 semantics rather than its stale templates? Are unsupported type escapes, blanket exception handling, hidden complexity or unrequested scaffolding being introduced? No code is authorized by this review procedure.
6. **Reversibility:** Is the diff explicit and bounded, other people's work preserved, and the checkpoint local? Does any old commit workflow quietly imply restart, publish or deployment?
7. **Completeness:** Are missing files and unknown runtime facts honestly reported? Are proposals labeled as proposals instead of manufactured acceptance criteria or assumed feature-removal decisions?

## Deliverable

Return concise findings, not patches:

- Severity and exact file:line or proposed action.
- Concrete failure mode and evidence; distinguish suspicion from a demonstrated source fact.
- Smallest correction within the authorized scope.
- What was not inspected or verified.

Do not pad the report with cosmetic preferences. If there is no material finding, say so and preserve the verification limits. After corrections, reread changed passages and mark each prior finding resolved or open. A reviewer conclusion is source review only, never runtime acceptance or permission to proceed beyond root's boundary.
