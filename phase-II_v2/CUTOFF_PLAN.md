# dame-curie cut-off decisions and source map

> **Historical naming checkpoint, not current deployment guidance.** `REDESIGN_PLAN.md` supersedes the API/web/Caddy/OAuth/PM2, nested shell/site image and startup-snapshot bridge entries below. The approved topology is bot/Ollama/pull only; staged startup starts nothing, with no new listener/socket bridge. `capture_running_build` reports unknown checkout metadata for archive images without `.git`; image labels do not prove a checkout snapshot. Use `../docs/OPERATIONS.md` and `REDESIGN_PROGRESS.md` for the current contract/integration holds. Original source anchors and evidence are retained below, not re-verified or instructions to execute.

2026-09-19. Initial inventory baseline: `aa77fa0`. Source implementation baseline: `47cd6f1`, the intervening documentation-only checkpoint. These are successive local checkpoints, not conflicting sources of authority. Runtime evidence is separately scoped in `DOCKER_INVENTORY.md`.

## Root's decisions

- V1 is functional and working. This is pruning and foundation work, not an assumed incident or broken-deployment repair.
- Canonical project name: **dame-curie**. Intentional short URL component **dame** remains. Do not replace ordinary `max()`/`max_tokens` or every historical/comment/persona occurrence.
- Protected V1 account: **maxwell-curie**. Planned V2 account: exactly **dame-curie**, with a separate private rootless Docker engine. No account/engine creation or startup.
- Project Python: **3.14**, isolated from the host's system interpreter. Host-side project work uses a venv or uv-managed environment; active docs use generic host wording. `.venv` is not `.env`/`bot.env` configuration.
- Quarantine inherited operational documentation; rebuild active instructions from selected current evidence. Preserve local history, legal/license material and useful provenance. No recovery from another project, deleted history or the internet.
- No new tests, application/test execution, real login, builds, deployment or production state changes. Existing fixture alignment does not authorize test execution or new assertions.
- Root approved quarantining both V1-specific DNS provisioners unchanged. Email tools remain; broader feature removal/change decisions come later.
- Root explicitly requested committing the unchanged `implement-sanity` skill as the review twin of this project's `implement-tyranny` skill set. Concurrent `scratch-mermaid/` belongs to another session and is excluded.

## Selected and implemented source conventions

The coordinator selected the full instance slug before assigning non-overlapping application, infrastructure and publisher writes. Existing fixture alignment followed the settled contracts. Review corrections and limits are recorded in `SOURCE_REVIEW.md`. This is a source checkpoint, not provisioning or runtime acceptance.

| Boundary | Source convention | Limit / coupling |
| --- | --- | --- |
| Project name | `dame-curie` | Root decision |
| Initial service account / engine | `dame-curie`, its UID-derived local rootless socket | Existence/provisioning not verified; never reuse a recorded V1 UID as a V2 default |
| Full instance / Compose project | `dame-curie` or `dame-curie-<identity>`, up to 30 characters | Namespace-restricted safe slug; direct account lookup and resource prefix, not a doubled name |
| Future replica | Separate account/engine/private roots per full identity | Intended design, not tested replication |
| App/web images | `dame-curie-app:<revision>`, `dame-curie-web:<revision>` | Immutable artifacts may intentionally match across V2 engines; tags are not identity proof |
| Generated resources | `<full-instance>-shell`, `<full-instance>-site-<slug>`, matching site/runtime images and backend network | Builders, selectors, ownership and export checks aligned |
| Ownership labels | `dame-curie.instance`, `.kind`, `.site`, `.shell.*` | Reserved Compose/OCI keys unchanged; no legacy-label adoption alias |
| Environment/config attributes | `DAME_CURIE_*` replaces operational `MAXWELL_*` | Internal/persona `MAXWELL_BASE_KNOWLEDGE` is not an env key and remains |
| Shared RAG basename | `dame-curie-rag.db` | Bot/API agree; graph uses the same store. No live DB copied/renamed |
| Host private root | `/srv/<full-instance>` | Initial `/srv/dame-curie`; selected layout, not an inspected host path |
| Container-private roots | `/config`, `/state/data`, `/state/sites`, `/state/shell` | Neutral paths retained; private mounts/engines supply isolation |
| Configuration/interpreter filenames | `bot.env`, `.env`, `deploy.env`, `.venv` | Configuration/state cannot point at V1; `.venv` is project tooling, not identity configuration |
| Container engine socket | `/run/dame-curie/docker.sock` | Host endpoint stays `/run/user/<approved-service-uid>/docker.sock` |
| Shell home / export root | `/home/dame-curie` | Image workdir, mounts, path translation and export guards aligned |
| Shared read-only checkout | `/opt/dame-curie` | Host wrappers select `.venv/bin/python`; no system-Python fallback |
| Startup snapshot socket | `/srv/dame-curie-checkout/<full-instance>/snapshot.sock` → `/run/dame-curie-checkout/snapshot.sock` | Socket user/group are the full instance; reader runs as explicitly selected checkout owner |
| API/PM2 identifiers | `dame-curie-api`, `dame-curie-bot`, companion `dame-curie-gf` | Process definitions and API selectors aligned; logs use invoking account/PM2 home |
| Archive metadata | `dame-curie.instance`, `dame-curie.compat.link_sha256`, `dame-curie-interpreter-link-v1` | Writer, validation and generated reconstruction source aligned; no implicit V1 backup migration |
| Public URL/mail defaults | Reserved `.invalid` fallback or empty explicit configuration | No new real hostname/mailbox; existing OAuth flow retained |
| Persona / Discord identity / model | Existing content, IDs and choices retained | Naming does not choose new credentials or primary identity |
| Intentional short URL | `dame` | Does not authorize reuse of V1's live publisher destination |
| Neutral routes | `/api`, `/bot`, etc. | Retained; `/bot` is not attributed to root's `dame` exception |
| Publisher state / remote roots | `/srv/<full-instance>/publisher/{config,staging,state}`; synthetic distinct remote example | Real destinations still require assignment; no remote inspection/migration |
| Publisher markers | `.dame-curie-publisher-owner`, `.dame-curie-publisher-claim-` | Scanner, standalone remote guard and HTTP exclusions aligned; no module-layout refactor |

Names alone do not prove isolation. Private credentials, configuration, prompts, DBs, sites, shell/model storage, mounts, ports and publisher destinations must be separated. Sharing an intentionally immutable source/image artifact does not imply sharing any mutable identity state. No old-name fallback may silently reconnect V2 to protected V1.

## Coupled source surfaces reviewed

| Surface | Current source |
| --- | --- |
| Import-time configuration and optional-feature gates | `config.py`, `bot.py`, `bot_tools.py`, `api/config.py`, `api/auth.py`, `api/storage.py` |
| Data, prompt, site and memory consumers | `rag_memory.py`, `knowledge_graph.py`, `prompt_storage.py`, `api/api_server.py`, tool configuration attributes |
| Docker names, labels, host translation and shell exports | `docker_runtime.py`, `site_server.py`, shell/export sections in `bot_tools.py`, `compose.yaml`, Dockerfiles |
| Operator account/socket/private-root validation | `scripts/instance.py`; full control flow retained, labels checked before ownership selection |
| Backup/migration metadata and embedded reconstruction | `scripts/instance.py`, `scripts/instance_backup_compat.py`, `scripts/migrate_instance.py` |
| Snapshot/build/host wrappers and examples | `docker/systemd/`, `scripts/build_for_human.sh`, `scripts/instance.sh`, `install.sh`, PM2/Caddy examples |
| Publisher local/remote ownership | `scripts/publisher/` config/service/common/guard/HTTP exclusion source |
| Existing fixtures | 45 modified files under `tests/`; existing assertions retained, no added cases/functions |

Relative `data/`, `.env` and prompt defaults are not inherently V1 reads: their safety depends on roots, mounts and environment. The namespace search is not an exhaustive inventory of every database or an application acceptance test. `scripts/build_for_human.sh` remains a deployment actuator, not a harmless build-check command; never execute it for discovery.

## Documentation and quarantine

- `47cd6f1` rebuilt active README/AGENTS/SECURITY and `docs/{STATUS,ARCHITECTURE,OPERATIONS,DEVELOPMENT}.md`; 21 inherited documents/assets were preserved under `legacy/v1/`. The old contract is `AGENT_CONTRACT.md`, not active `AGENTS.md`.
- The two DNS provisioners are additionally preserved unchanged under `legacy/v1/email_integration/`. LICENSE and tokenizer provenance remain active. No archived command/path/URL becomes current authority.
- `.dockerignore` excludes `legacy/` and `phase-II_v2/` from normal build contexts. Ruff/mypy exclude the quarantined source; pytest already restricts discovery to `tests/`. No dependency pins or installed tools changed.
- Active operations guidance permanently maps account → UID → explicit socket → run-as identity, with allowlisted metadata and stop boundaries. It grants no new inventory, runtime debugging or mutation.
- Python 3.14.4 and standard-library venv help were observed without creating an environment. `uv` was absent from this session PATH only. Shell-image Python, isolated validation and actual V2 resources remain unverified.

## Review corrections, not speculative repair

The coordinator rejected invented real identities, blanket claims that relative defaults read V1, using tags as immutable identity, treating `/home/maxwell` as cosmetic, and attribution of `/bot` to root. The claimed name-only deletion bypass was disproved: matching-name objects with missing/foreign labels raise before selection. The same existing fail-closed behavior can reject a foreign overlapping-prefix object; the contract requires separate engines, not shared-engine replica acceptance. No selector rewrite or new test was justified.

Review fixed doubled Compose/socket-account prefixes, aligned env/resource/archive/publisher consumers, removed V1 runtime URL/mailbox fallbacks and reverted unnecessary internal persona renames. Historical mail/URL comments remain non-authoritative prose, not configured endpoints. Final source review is not a deployment, provider or test pass.
