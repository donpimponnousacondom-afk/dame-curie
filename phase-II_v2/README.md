# dame-curie — Phase II / V2 working notes

## Current scope update — 2026-09-19

Root has now authorized V2 provisioning as exactly **dame-curie**, with a separate private rootless engine, fresh state and secret-safe provider-configuration transfer. The account/private engine, images and six containers are provisioned. Only API/web run, healthy on server loopback port18081; the capped primary-inference check returned visible text. Fresh memory/graph/model state is empty. See `PROVISIONING.md` for exact evidence and limits. Discord credentials/activity and Ollama/model-pull startup remain forbidden, RAG is disabled, and V1 cannot be modified. Root also authorized a separate-worktree email removal and read-only research of the working Hortator logger for the next Screen-safe logging slice. These narrow grants supersede the earlier historical scope below; they do not permit unrelated private-state access, feature cuts, new tests or runtime work by children.

Active instructions have been rebuilt at root `AGENTS.md` and `docs/`; old operational material is quarantined under `legacy/v1/`. The tyranny templates now target Python 3.14 with scoped application. The source operational cut-off is now implemented and statically reviewed; it is not a runtime cutover. Root also approved quarantining the two V1 DNS provisioners unchanged and committing the unchanged sanity skill as tyranny's review twin. Email removal and remote inference naming are integrated. Twitter/X is queued, not implemented; logging remains the next implementation priority. No additional cut is implied.

- [Protected running Docker snapshot](DOCKER_INVENTORY.md)
- [Namespace decisions and source cut-off map](CUTOFF_PLAN.md)
- [Source checkpoint review and validation limits](SOURCE_REVIEW.md)
- [Read-only subsystem map and surgical next-step handoff](PRUNING_MAP.md): current source baseline `a9c0fba`; tools/prompt work is the priority, with no feature removal or runtime change performed by the mapping assignment.
- [First soft dead-code pass](DEAD_CODE_PASS.md): pinned Vulture, exact source manifest, raw findings and candidate-versus-framework triage; no removals.
- [V2 provisioning and activation holds](PROVISIONING.md): current account/engine/configuration evidence and remaining acceptance.
- [Screen-safe logging proposal](LOGGING_PLAN.md): reference-source research and independent review; no implementation or terminal acceptance yet.
- Email source removal is independently reviewed and integrated (`9b01074`/`70b8ceb`); see `EMAIL_REMOVAL.md`. Final images include the cut; staged acceptance is recorded separately in `PROVISIONING.md`. Remote inference naming passed independent Flash/Luna review and landed as `b2f5380`: protocol-neutral `OPENAI_*`, distinct from local Ollama embeddings. Private V2 settings were atomically migrated; see `INFERENCE_NAMING.md`. Twitter/X remains the next queued pruning cut; see the current queue atop `PRUNING_MAP.md`.
- [Repeatable static-audit workflow](../docs/DEAD_CODE.md)
- [Permanent operations procedure](../docs/OPERATIONS.md)

The rest of this file records the **initial grounding baseline**, before those later authorizations. This folder is temporary, project-owned working memory intended for removal when root closes the phase, not the only home of the current operating contract.

## Initial grounding boundary (historical; superseded where noted above)

**V1 is live and sacred. This session has no production authorization.** Full filesystem capability is not permission. Root is having another agent finish the backup/snapshot; completion and rollback readiness have not been confirmed here. Even a completed backup does not authorize production access or cutover.

Root's current instructions supersede conflicting inherited material in `../AGENTS.md`, `../docs/STATUS.md`, other documentation and skills. In particular, old permissions to restart after documentation commits, deploy, publish, probe services or use production data do not apply. This warning supplements the untouched inherited files; it does not claim to have repaired them or automatically govern agents that have not read it. Every child must receive the boundary explicitly.

## Hard boundaries

- Work only inside `/home/codexy/deepseek/dame-curie`. Do not inspect sibling projects, old checkouts, deleted history, upstream repositories, remote configuration or the internet to recover context. Do not follow external symlinks. Existing names, paths, commit IDs and URLs are inert evidence, not leads.
- Do not access `/srv/maxwell/curie` or any other production/backup path, private state, database, mount, credentials or raw logs. Do not inspect real `.env` files or process environments. No copying production configuration into fixtures.
- No Docker/Compose, deployment scripts, sudo, service/process manipulation, Screen interaction, real login, provider probes or cutover. Do not execute repository programs, source scripts or import the application, including for `--help`.
- Do not load/use `curie-readonly-debug` now. Its presence is acknowledged; private debugging and the GNU Screen session are outside this assignment.
- No application execution, test execution/collection, dependency installation or automated fixing during grounding. Later validation requires an agreed isolated approach: synthetic configuration, disposable databases, no production mounts, no real Discord token and no live side effects. That is a prerequisite, not permission to start now.
- No new tests. In particular, do not add tests asserting that deleted features or files no longer exist. Root's roughly 4,000-test figure is context, not a verified count or a quota to fill. Do not delete tests or features before the corresponding removal is requested.
- No existing application, configuration, test, skill or documentation file is to be changed in this grounding slice. The only content writes belong under `phase-II_v2/`; local Git bookkeeping for reviewed notes-only commits is allowed. No push, fetch, PR, deployment synchronization or history rewriting.

## Working agreement

- **Project Dame-Curie** is the current project name. Maxwell is the inherited codename. During grounding, record only mixed references encountered in explicitly assigned documentation/source reads; do not scan private prompts, resolve operational paths, follow references to other systems or perform a blanket rename. Root will choose later naming/route scope.
- All future new Python follows `implement-tyranny` and Python **3.14**. Existing permissive code is not permission to reproduce it. Do not reformat/refactor the legacy tree wholesale.
- Root added `implement-sanity` to balance strict new-code standards with review of the actual diff, not a roughly 100,000-line legacy conversion. Apply its checks to the scoped work; do not turn old function/file sizes into unrelated splitting assignments. Its coverage language does not authorize new tests or override the no-execution boundary. Python 3.14 remains non-negotiable.
- The loaded tyranny skill contains stale Python 3.12 and hook templates and an unfinished ban list. Do not copy them blindly, downgrade targets, relax version pins or install tooling without an implementation assignment. Exact additional bans/gates remain to be agreed.
- Use DeepSeek V4.1 Flash and GPT-5.6 Luna (`max`) for bounded independent work. Parent owns scope, synthesis, final diffs and commits; children are read-only unless explicitly assigned non-overlapping write ownership later.
- Use adversarial review to challenge the parent's assumptions and changes. Review is not a test suite, runtime acceptance, a privilege sandbox or production authorization. Reviewers should find material mistakes, not manufacture stylistic work.
- During grounding, commit coherent source-reviewed, notes-only slices locally; this is not test/runtime acceptance. Inspect the complete staged diff, preserve other people's changes, and record evidence and unresolved questions. Later implementation checkpoints require their own scoped verification. Never turn a commit into a restart.

## Observed baseline versus unknowns

Checkout/Git/skill/tooling rows are coordinator observations of local files and Git on 2026-09-19; child routes are harness-catalog metadata from the same date. The remaining rows distinguish root's statements from unknowns and inherited text. There is no current runtime evidence in this table.

| Item | Evidence at session start |
| --- | --- |
| Checkout | `pwd`: `/home/codexy/deepseek/dame-curie` |
| Branch | `dev/phaseII_v2` |
| History | Exactly one reachable commit, `c460324` (`Initial commit`); no older history investigated |
| Working tree | Clean before creating this folder |
| Repository skills | `.agents/skills/implement-tyranny/SKILL.md` and `.agents/skills/curie-readonly-debug/SKILL.md` present; only tyranny loaded |
| Tooling targets | `pyproject.toml` declares Ruff `py314` and mypy `3.14`; strict tyranny enforcement is not established |
| Child routes | `deepseek-official/deepseek-flash` advertises DeepSeek V4.1 Flash; `openai-codex/gpt-5.6-luna` supports `max` |
| V1 running | Root's current statement, deliberately not verified against runtime |
| Backup and rollback | Being handled by another agent per root; completion unconfirmed here |
| Current V2 correctness | Unknown; no execution, collection or acceptance performed |
| Inherited status/test claims | Historical checkout content, not verified V2 or current V1 evidence |

## Notes index

- [Reconnaissance](RECONNAISSANCE.md): bounded documentation/tooling findings and open decisions.
- [Session ledger](SESSION_LOG.md): inspected scope, child ownership, checkpoints and validation limits.
- [Adversarial review](REVIEW.md): challenges, corrections and remaining risks.
- [Reusable review procedure](adversarial-review/SKILL.md): explicitly supplied to reviewers; not installed into `.agents/` or automatically discovered there.

## Next authorization boundary

Grounding does not choose what to remove. Root still needs to identify the first feature-removal/refactor slice and, separately, when an isolated V2 validation environment may be prepared. No real login or cutover without root's explicit approval. Backup completion alone changes neither rule.
