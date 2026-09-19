# dame-curie cut-off decisions and source map

2026-09-19. Source baseline `aa77fa0`; runtime evidence is separately scoped in `DOCKER_INVENTORY.md`. This is an implementation map, not a deployment recipe or a claim that every reference has already been changed.

## Root's decisions

- V1 is functional and working. This is pruning and foundation work, not an assumed incident or broken-deployment repair.
- The project codename is exactly **dame-curie**. Intentional short URL component **dame** remains. Do not replace ordinary `max()`/`max_tokens` or every historical/comment/persona occurrence.
- Protected V1 service account: **maxwell-curie**. Planned V2 service account: **dame-curie**, with a separate private rootless Docker engine. This supersedes the earlier provisional `dame-curie-v2` account suggestion. Account/engine creation and startup are not part of this observation/documentation slice.
- Project Python is **3.14**, isolated from the host's system interpreter. Host-side project work uses a venv or uv-managed environment; active docs use generic host wording. `.venv` is an interpreter environment; `.env` and `bot.env` are configuration files, not interpreter environments.
- Archive inherited operational documentation and rebuild active instructions from selected current evidence. Better explicit omissions than stale rollout commands masquerading as current authority. Preserve local history, legal/license material and useful component provenance; do not recover anything from another project, deleted history or the internet.
- No new tests, especially assertions that deleted features/files no longer exist. No application/test execution, real identity login, builds, deployment or production state changes are currently authorized.

## Namespace conventions to implement source-only

| Boundary | V2 direction | Status / caveat |
| --- | --- | --- |
| Project name | `dame-curie` | Root decision |
| Initial service account / engine | `dame-curie`, its UID-derived local rootless socket | Root decision; existence/provisioning not verified |
| Initial instance / Compose project | `dame-curie` | Proposed full identity slug, avoiding `dame-curie-dame-curie` prefix duplication |
| Future replica identity | `dame-curie-<identity>` | Design convention only; each identity needs its own account/engine/private roots |
| Application images | `dame-curie-app:<revision>`, `dame-curie-web:<revision>` | Versioned shared source artifacts are allowed; images are not mutable shared bot state. Record immutable ID/digest separately from mutable tags |
| Generated resources | `<full-instance>-shell`, `<full-instance>-site-<slug>`, corresponding site/runtime images and backend network | Must update builders, selectors and exported-path checks together |
| Custom ownership labels | `dame-curie.instance`, `.kind`, `.site`, and corresponding shell metadata keys | Keep Docker's reserved Compose/OCI keys unchanged; do not adopt `maxwell.*` resources via compatibility aliases |
| Environment names | `DAME_CURIE_*` instead of operational `MAXWELL_*` | Necessary underscore spelling for shell/Python identifiers; canonical project/file/URL spelling stays hyphenated |
| Python-only identifiers | Syntax-compatible underscores/CamelCase where necessary | Not a mandate to rename every internal class/helper; change only required coupling |
| RAG database basename | `dame-curie-rag.db` | Bot and API must agree; always under the identity-owned data root. Do not move/copy V1 databases |
| Host private instance root | `/srv/<full-instance>` (initial `/srv/dame-curie`) | Proposed source convention, not an inspected/provisioned host path; ownership/socket/mount validation must stay aligned |
| Container-private roots | `/config`, `/state/data`, `/state/sites`, `/state/shell` | Neutral paths may remain; isolation comes from separate mounts/engines, not cosmetic changes |
| Config/interpreter filenames | `bot.env`, `.env`, `.venv`, `deploy.env` | Neutral names may remain; config/data roots must not point at V1. Development `.venv` is checkout-owned, not shared across bot identities |
| Container engine socket path | `/run/dame-curie/docker.sock` | Source counterpart to the existing image-internal `/run/maxwell/docker.sock`; host socket remains account-UID-derived |
| Shell home / export root | `/home/dame-curie` | Proposed functional rename; must match image user/workdir, mounts, guards and export checks |
| Public URLs / mailbox / Discord IDs | Explicit intended configuration or clearly synthetic examples | Never invent a renamed real domain/mailbox or import V1 credentials/identity defaults. Real values remain root's decision |
| Intentional short URL | `dame` | Root explicitly preserves it. Reusing the same live publisher destination is a separate decision, not implied by this spelling |
| Neutral route segments | `/api`, `/bot`, etc. | Do not attribute `/bot` to root's `dame` exception. Retain unless a concrete project-name collision requires change |
| Publisher roots and markers | Separate V2 local state and remote destination; coordinated `dame-curie` marker naming | No remote inspection or migration. A new local daemon does not isolate a shared remote destination |

These proposed layout conventions must be kept internally consistent before source implementation is called complete. Names alone do not prove isolation or authorize startup. No old-name alias/fallback may silently reconnect new configuration to protected V1 roots or resources.

## Coupled source surfaces found

| Surface | Evidence / coupling |
| --- | --- |
| Import-time environment selection | `config.py:31-39`; `MAXWELL_ENV_FILE` feeds dotenv. API storage has its own app-root selection. Rename all consumers and templates together; no config values read here |
| Data/prompt/site defaults | `config.py:502-517`, `prompt_storage.py:20-28`, API defaults | Relative `data/` and prompt fallbacks become unsafe only if roots/mounts/environment are shared; they are not inherently reads of V1 |
| Shared RAG basename | `rag_memory.py:756`, `api/api_server.py:89` | Bot/API must use one new basename; knowledge graph shares that store. A scoped name search is not an exhaustive database inventory |
| Resource labels/names/host roots | `docker_runtime.py:12-74`, `compose.yaml:1,21,32-37,73-74` | Environment, full instance slug, host root, image-internal socket and backend network are one contract |
| Operator identity/socket validation | `scripts/instance.py:103-130,143-145` | Current code derives `/srv/maxwell/<name>`, `maxwell-<name>` and account-owned socket. V2's exact account decision requires aligned source changes, not a display rename |
| Container ownership selector | `scripts/instance.py:173-193` | Name-prefix matches are validated; lines190-191 reject missing/foreign labels before append. No name-only deletion bypass was established |
| Shell image/home/export guards | `docker/Dockerfile`, shell/export sections in `bot_tools.py` | `/home/maxwell` is functional, not cosmetic; the separate app container's UID does not remove this coupling |
| Systemd/snapshot/build wrappers | `docker/systemd/`, `scripts/build_for_human.sh`, `scripts/instance.sh` | Existing source contains V1 account/UID/path/image assumptions. Never execute these to discover deployment identity |
| Publisher ownership/destination | `scripts/publisher/` configuration, service template, transport/guard/common | Remote destination and marker ownership must be distinct or explicitly migrated; no actual remote state was read |
| Additional operational names | API PM2 selectors, installer examples, persona/default display names, checkers persisted names, email defaults | Inventory is not permission to redesign unused integrations/persona or invent identity. Resolve load-bearing references, defer unrelated prose/behavior |

## Documentation replacement slice

- Replace root `AGENTS.md` with a short current contract. Archive the old text under a non-`AGENTS.md` filename so it cannot become an active nested instruction file.
- Archive the old root project README, historical analyses, deployment/status guides, guide assets and feature-operation READMEs under `legacy/v1/`, preserving their relative directory cluster and dated evidence. Missing linked files remain missing; no recovery expedition.
- Keep `LICENSE` and tokenizer asset/license provenance in place. Preserve root's untracked `implement-sanity` skill. Do not activate the runtime-debug skill during this work.
- New active set: a small root README, current agent contract, `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/DEVELOPMENT.md`. A short archive boundary notice is sufficient; no rebuilt archaeology portal.
- Active operations docs must map account → UID → explicit local socket → run-as identity, distinguish inventory permission from mutation permission, and explain exactly where to stop. Do not begin with bare `docker`, use old hardcoded UIDs, or execute a lifecycle wrapper for discovery.
- Pick explicit Python3.14 venv as the currently verified minimal local workflow. The installed interpreter reported3.14.4 and its standard-library venv help worked without creating an environment. `uv` was not found on this session PATH; this is not proof it is absent from the entire host. Do not install/probe alternate locations or pretend a uv workflow was exercised.
- Document current source migration status honestly. New documentation names are target conventions until the corresponding source cut-off is implemented and separately validated.

## Review corrections, not new defects to fix

The source scouts' first reports contained overclaims. The coordinator rejected an invented real hostname, blanket claims about import-time reads/database coverage, attribution of `/bot` to root, treating relative defaults as inherent V1 reads, treating mutable tags as identity, and treating shell-home paths as cosmetic. The claimed name-only stop/remove bypass was disproved by reading the complete existing selector: missing/foreign ownership raises before inclusion. No repair of that working selector is authorized or needed on that evidence.

The Docker inventory is running-only and limited to the one root-specified engine. Other daemons, stopped resources, networks, volumes, user provisioning, actual V2 state roots and publisher destinations remain unverified. Multi-instance isolation is intended architecture, not a demonstrated acceptance result.
