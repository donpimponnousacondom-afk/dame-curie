# dame-curie status

Updated 2026-09-19. This ledger concerns the fresh V2 checkout, not the archived V1 rollout history.

## Completed observations

- Root confirms V1 is functional and running. Its service account is `maxwell-curie`.
- Root authorized metadata-only Docker observation as that account. The coordinator observed 19 running containers in its private local engine: four core services, fourteen site backends and one shell workspace. Bot/API reference `maxwell-app:0468dde`; web references `maxwell-web:1b96027`. Immutable IDs, observed labels, timestamps and limitations are recorded in `../phase-II_v2/DOCKER_INVENTORY.md`; no old commit was looked up.
- Root fixed the intended V2 service account as exactly `dame-curie`, using a separate private rootless engine. Its provisioning/existence has not been verified here.
- Local Python 3.14.4 and standard-library venv help were checked without creating an environment, installing dependencies or importing application code. `uv` was not found on this session PATH; host-wide availability was not investigated.
- The tyranny skill's templates now target Python 3.14, its application is explicitly scoped to authorized new/rewritten code, and obsolete hook-version examples were removed without inventing replacements. No project dependency/configuration pins or installed hooks were changed.
- Source inventories identified coupled environment names, DB basenames, resource labels, shell paths, operator wrappers and publisher boundaries. Their proposed mapping is in `../phase-II_v2/CUTOFF_PLAN.md`. Reviewer overclaims were challenged; no source repair was made.

## Documentation cut-off

Inherited project/operation guides and their assets were moved intact to `legacy/v1/`; the old agent contract uses a non-active filename. Active README, agent contract, security, operations, development and architecture guidance are rebuilt around the current boundaries. Legal/license material and tokenizer provenance remain in place. The archive is not a default search source or a live runbook.

## Still pending

- Application/deployment/template namespace changes. **Code still contains inherited Maxwell selectors; target names in these new docs are not implemented-runtime evidence.**
- Final agreement/implementation of full instance identifier, private-root layout, all producer/consumer pairs, explicit configuration and any publisher destination changes. Do not infer permission to reuse a V1 remote root.
- Reproducible isolated V2 validation and multi-instance acceptance. No current test count/pass baseline, image build or V2 runtime acceptance is established.
- Backup/rollback readiness confirmation from root's separate backup work. No backup path or content was read here.

## Actions not performed

No application/test execution or collection; no new tests; no source behavior changes in this documentation slice; no real login/provider probes, user/engine provisioning, image build/pull/retag/prune, deployment, service/container restart/stop/removal, production configuration/state reads, or remote publication. No other-project, Git-history or internet archaeology.

Current work remains local on `dev/phaseII_v2`. Documentation/source commits do not synchronize production.
