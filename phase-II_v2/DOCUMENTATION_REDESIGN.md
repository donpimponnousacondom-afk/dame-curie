# Discord-only documentation reconciliation

Documentation-only lane: `work/discord-only-docs-20260919`, base `4b98f09`. Authority: root's approved `REDESIGN_PLAN.md` and coordinator's supplied current contract. No feature-selection question remains; source integration/runtime reconciliation belongs to the coordinator.

## Owned changes

- `README.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/DEVELOPMENT.md`: approved bot/Ollama/pull topology, validated staged no-op, direct same-UID container shell, preserved authoring/media/publisher paths, removed HTTP/social/companion surfaces, `!` commands, trusted job routes and opt-in Screen logging. Intended source behavior is separated from historical deployment evidence and unverified acceptance.
- `docs/DEAD_CODE.md`: the approved redesign is the selected pruning scope, not blanket authority to delete audit findings.
- `.agents/skills/curie-readonly-debug/SKILL.md`: retired V1 recipes and missing active-doc links replaced with target-specific authorization boundaries/current contracts. The skill was read as text for editing, **not activated**; none of its commands was executed.
- `phase-II_v2/README.md`, `PRUNING_MAP.md`: current scope summaries; original grounding/audit evidence explicitly historical. Historical comma-prefix/source anchors are retained, not mass-rewritten.
- `CUTOFF_PLAN.md`: concise supersession notice only; original namespace/bridge evidence left intact. This report is the only new document.

## Read-only source evidence

Targeted files were read only in the explicitly assigned sibling worktrees; no other checkout or legacy research:

| Lane / supplied checkpoint | Inspected contract |
| --- | --- |
| `discord-only-deploy`, `ac5f196` + `afa9eb5` | Compose/app image/examples; `scripts/instance.py` identity checks, staging early return, all-profile orphan cleanup and actual CLI; build-only helper and installer; `response_observability.capture_running_build` local-Git fallback |
| `direct-shell-tools`, `700cece` + `e53aece` | `bot_tools.py` direct Bash, explicit cwd/HOME, DEVNULL and timeout/cancellation process-group cleanup |
| `remove-web-api`, through `598bc66` | Scoped source diff paths and `config.py` dotenv `override=True`; no HTTP replacement inferred |
| `remove-social-transports`, `cbea8a5` | Preserved `rag_memory.py` historical `tg:%` privacy filter, not active transport |
| `job-routing`, `c1ec088` and in-progress follow-up | `job_routing.py` opt-in header/same-role selection and `jobs.py` primary/fallback wording, canonical personality/server prompt, user-role goal/context |
| `screen-logging`, through `bb5184a` | `scripts/instance.py` opt-in `screen`/`--no-keys` CLI; controls/acceptance remain in the unchanged `LOGGING_PLAN.md` |

The coordinator's removal contract also covers companion/GF and human CAPTCHA HTTP fallback; no independent runtime/provider verification is implied. Later coordinator handoff reports logging integrated as `cbe1e8d`, `25671a4`, `f023176`, web through `e984d0f`, shell through `d2d511c`, social through `192aac2`, and companion integration underway. These are coordinator-supplied source checkpoints, not additional checkout/runtime observations by this worker. Ongoing integration/review state belongs to `REDESIGN_PROGRESS.md`, not this bounded evidence list.

## Verification and holds

Completed scoped source/text review under `implement-sanity`, full owned diff inspection and clean `git diff --check`; commit scope is explicit owned Markdown paths only, with Git hooks/signing disabled. No application imports/execution, tests/collection/new tests, builds/install/network, Docker/sudo, private configuration/state/logs, Screen, migrations, lifecycle `--help` or nested agents. Publisher files, source/config/scripts/tests, `AGENTS.md`, `docs/STATUS.md`, redesign/logging plans and progress, other implementation reports and historical inventory/provisioning evidence are untouched.

Review correction: the debug skill's log command uses the explicit operator venv with `-B`, not `-I`; the script logs branch imports sibling `log_filter`, whose script-directory import would be excluded by isolated mode. This was source-reviewed, not executed. The coordinator was notified.

Runtime was **not re-observed**. The earlier handoff reported API/web running and bot/Ollama/pull/shell created but never started; it is not the redesign already deployed. Coordinator must reconcile only after reviewed source integration, re-resolving `dame-curie` (earlier UID/GID1005) and its private rootless engine, and auditing private structural dotenv overrides. No replacement listener/socket bridge; archive images without `.git` report unknown checkout metadata, not OCI-label proof.

Bot credentials stay blank, bot entrypoint never starts, RAG stays false, Ollama/pull never starts and model storage stays empty. No provider/Discord, terminal or refreshed-image acceptance is claimed. V2 publisher activation/destination remains unestablished; public examples are reserved `.invalid`, never borrowed V1 destinations. Protected `maxwell-curie` V1 remains untouched. Deployment effects of this lane: **none**.
