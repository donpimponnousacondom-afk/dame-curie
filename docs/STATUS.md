# dame-curie status

Updated 2026-09-19. This ledger concerns V2, not the archived V1 rollout history. **Root has now authorized V2 provisioning; it is in progress. Discord and Ollama/model-pull activation remain prohibited.** Current operational evidence and exact holds are in `../phase-II_v2/PROVISIONING.md`; earlier milestones below retain their historical limits.

## Completed boundaries and observations

- Root confirms V1 is functional and running under `maxwell-curie`. The authorized metadata-only observation recorded 19 running containers: four core services, fourteen site backends and one shell workspace. Immutable IDs, observed revision/version labels, timestamps and limitations are in `../phase-II_v2/DOCKER_INVENTORY.md`. No old commit was looked up.
- Root selected exactly `dame-curie` as the V2 service account, with its own private rootless Docker engine. Account/engine existence, provisioning and isolation have not been verified here.
- Documentation checkpoint `47cd6f1` quarantined 21 inherited documents/assets and rebuilt the active README, agent contract, security, operations, development and architecture guidance. The old contract is not named `AGENTS.md`; LICENSE and tokenizer provenance remain in place.
- Python 3.14.4 and standard-library venv help were checked without creating an environment, installing dependencies or importing application code. `uv` was not found on this session PATH; host-wide availability was not investigated.

## Source naming checkpoint

- Full instance/account/Compose identity is `dame-curie`, or `dame-curie-<identity>` for a future replica, up to 30 characters. Selectors derive the account directly and the private host root as `/srv/<full-instance>`; they do not double the prefix or accept a legacy instance alias.
- Coupled operational env/config keys, custom ownership labels, image/resource names, shell/socket paths, PM2 selectors and publisher markers/templates use the new namespace. Bot and API agree on `dame-curie-rag.db`. Neutral `/api`, `/bot`, configuration filenames and the intentional short URL `dame` remain.
- Baked V1 URL/mailbox selections were removed from runtime defaults. Examples use reserved synthetic destinations or explicit empty configuration, not invented real identities. Persona/internal identifiers, real Discord IDs, model choices and harmless historical prose were not globally rewritten.
- Host wrappers select checkout `.venv/bin/python`; installer/doctor version checks require Python 3.14. The shell image's distro-provided interpreter remains unverified; application/site image declarations remain 3.14.4.
- Root approved moving both V1-specific DNS provisioning scripts unchanged into `legacy/v1/email_integration/`. Bot email functionality remained at that historical checkpoint; it was subsequently removed in the separately reviewed slice below. Build-context and static-tool exclusions keep the quarantine out of ordinary source paths.
- Existing fixtures/import paths were aligned in 45 test files; no new tests, cases or assertions were added. None were collected or run. Root's unchanged `implement-sanity` skill is included as the review twin of `implement-tyranny`.
- Mapping and review evidence: `../phase-II_v2/CUTOFF_PLAN.md` and `../phase-II_v2/SOURCE_REVIEW.md`.

## Read-only subsystem map

- At source baseline `a9c0fba`, root requested three parallel same-model scouts and a coordinator-led tools/prompt audit before any further pruning. The resulting map is `../phase-II_v2/PRUNING_MAP.md`; application source, tests and runtime remain unchanged by this assignment.
- DNS archive cleanup, email and X are separate candidate cuts. Shared inbox/media infrastructure must remain. YouTube includes real search/catalogs, captions and visual context, with callers outside its exposed tool.
- Tools/site prompting is the priority: editable personality/server prompts do not centralize code-owned policy, schemas or tool-result guides. Local Python/KV execution, remote file publication and browser-test targets are distinct contracts. No prompt or runtime fix was made.
- TTS/image generation remain protected. Built-in background jobs lack independent per-job model/provider selection and use a different personality path; logging/console must be separated from functional memory events. These are scoped source findings, not production incident diagnoses.
- Root must select one next implementation slice; the map does not authorize a batch of removals or cross-subsystem compensation patches.

## First soft dead-code audit

- Root subsequently authorized static-audit tooling and an initial report-only pass, not removals. Vulture `2.16` is pinned and installed in a fresh isolated Python `3.14.4` `.venv`; Ruff settings and existing pins remain unchanged. Both review skills now carry the audit/triage discipline. No hooks or automatic clean-tree gate were added.
- **87 tracked source files / 70,746 physical lines / 163 findings**: 150 at 60%, 2 at 90%, 11 at 100%; no unreachable blocks reported. The high-confidence set is mostly required callback parameters. Retired helper/catalog candidates are recorded separately from framework consumers; the report is not removable-LOC or production-usage evidence.
- Workflow: `DEAD_CODE.md`. Exact inputs, raw report and bounded triage: `../phase-II_v2/DEAD_CODE_PASS.md`. No application source, test, private configuration or running service was changed; the scan parsed source without importing it. Application validation remains unperformed.

## Historical review limits through `3a71cbb`

- Flash implementation/static review and Luna max adversarial review do not establish runtime correctness. An infrastructure child ran generic-Python AST and shell/JavaScript parser checks on an earlier edit; those are not isolated Python 3.14 validation or final-snapshot acceptance. No linter/type-checker/test pass is claimed.
- Broader feature pruning remains root's next assignment. An inherited provider-resilience test still references retired/missing documentation; its purpose was not rewritten to preserve obsolete documentation checks.
- Future validation needs a separately authorized, reproducible, synthetic/private-read-isolated environment. No image build, current suite baseline or V2 multi-instance acceptance is established.
- Real V2 configuration, private mounts/state, ports and publisher destinations need explicit assignment and verification. Names alone do not isolate mutable state. No permission to reuse a V1 remote destination is implied.
- Backup/rollback readiness remains unconfirmed; no backup content was read.

## Earlier source-only boundary (through `3a71cbb`)

Through that checkpoint: no application imports/execution or test collection/execution; no new tests, real login/provider probes, application-dependency installation, user/engine provisioning, builds/pulls/retags/pruning, deployment, service/container lifecycle changes, migrations, production configuration/state reads or remote publication. No other-project, upstream or deleted-history research was performed in those earlier assignments.

## Current authorized implementation

- Root subsequently authorized account/engine/image/container provisioning, fresh V2 state, read-only V1 provider configuration transfer, and bounded non-Discord provider checks. The account and engine now exist; detailed progress and remaining acceptance are in `../phase-II_v2/PROVISIONING.md`.
- Discord credentials and activity are forbidden; Telegram is disabled for later removal. Ollama and its pull job must remain stopped, with RAG disabled during staging. V1 must not be changed.
- Root fixed Dame Curie's identity as `1545541390392369165` and root/.normal.man as `1482143139828596916`; incorrect inherited companion/identity defaults are being removed without pruning the companion feature.
- Email source removal was independently reviewed by Luna and integrated as `9b01074`/`70b8ceb`, with the restored admin polling control removed in main. Shared web fetching/inbox/notifications/media remain. Refreshed-image acceptance is tracked separately; see `../phase-II_v2/EMAIL_REMOVAL.md`. Twitter/X is the next queued pruning cut, not started.
- Root additionally selected remote inference naming: `OPENAI_*` means the OpenAI-compatible protocol, not OpenAI's service/account. Its separate worktree removes the misleading localhost inference default while preserving configured endpoints and local Ollama embedding settings; independent actual-diff reviews are underway.
- Logging is the next priority: `f94c291` records the Hortator-based Screen plan with Flash/Luna reviews. Existing logging is retained; neither the logging implementation nor terminal acceptance has occurred.

Work remains local on `dev/phaseII_v2` and explicitly owned worktrees. A source/documentation commit alone never synchronizes V1 or authorizes Discord/RAG activation.
