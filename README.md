# dame-curie

A Discord bot undergoing the approved Discord-only V2 redesign. The existing V1 deployment remains protected and running.

**Audit remediation is in progress, not deployment acceptance.** The Discord-only source cuts are implemented; current fixes still require integrated review, full isolated QA and bounded temporary acceptance. [Status](docs/STATUS.md) separates verified source commits from the last recorded runtime. Lifecycle helpers are not discovery commands; old instructions do not authorize an installer, application or test run.

**Release freeze, 2026-09-25:** root approved complete audit remediation, isolated validation and bounded temporary-Dirac acceptance. Normal releases remain frozen pending the final independent audit. [TODO](TODO.md) owns the work and mandatory temporary-document retirement; [Status](docs/STATUS.md) records milestones. The archive-removal commit is cleanup, not application acceptance.

## Approved source contract

- Compose retains only `bot`, `ollama` and `ollama-pull`, with no published ports. Dashboard/API/OAuth/Caddy, the web image, local website/KV servers, six `site_*` tools, nested shell infrastructure, X/Telegram and companion/GF are removed from the target design. No replacement server or PM2 deployment.
- Shell runs Bash inside the outer bot container, with `/home/dame-curie` pointing to `/state/shell`. It is the bot's own UID, not a secret-isolated inner sandbox. No host root, host-network mode or Docker socket access; permitted outbound network requests remain possible.
- Local authored directories under `/state/sites` and `_images` files plus sidecars remain. The independent publisher/syncer is untouched; the model authors local files, never administers the remote host or starts local hosting. No PHP/Perl/CGI installation. Publication and destination changes are outside this remediation; historical activation receipts are not new authority.
- Preserve Discord administration, autonomy, games/plugins, media, shared inbox, functional RAG/REM/graph memory, independent tool authorization and redaction. Historical `tg:%` privacy filtering is not an active Telegram transport.
- The project-default Discord prefix is **`!`**; runtime help must use the configured prefix. `!bg GOAL` remains free prose; optional trusted profile/model routing is documented in [Architecture](docs/ARCHITECTURE.md#background-jobs-and-prompts).

**Canonical staging contract:** with `DAME_CURIE_STAGING` omitted or `true`, wrapper `up`/`start`/`restart` validates the target but starts **nothing**. Canonical identity/configuration and Ollama/model-pull remain held; this is not a statement that the separately authorized temporary Dirac has no credentials or has never run. See [Operations](docs/OPERATIONS.md) and the canonical image-profile activation hold in [Image generation](docs/IMAGE_GENERATION.md). No fresh runtime inventory is implied.

## Current documentation

- [Status](docs/STATUS.md): source milestones, historical deployment evidence and validation limits.
- [Historical redesign scope](phase-II_v2/REDESIGN_PLAN.md) and [integration evidence](phase-II_v2/REDESIGN_PROGRESS.md): retained source scope and dated reviews, not current worker/runtime grants.
- [Operations](docs/OPERATIONS.md): V1/V2 accounts, rootless engines and safe read-only investigation.
- [Development](docs/DEVELOPMENT.md): Python 3.14 and isolated venv/uv use; configuration is not an interpreter environment.
- [Architecture](docs/ARCHITECTURE.md): component map and isolation intent, not unearned acceptance claims.
- [Image generation](docs/IMAGE_GENERATION.md): one native generation/edit tool with operator-configured model choices.
- [Agent contract](AGENTS.md): current permissions, naming and collaboration rules.
- [Security](SECURITY.md): private-state and disclosure boundaries.

Project name and provisioned V2 service user: **dame-curie**, with its own private rootless Docker engine. Re-resolve that account and socket before every newly authorized runtime operation. The intentional short URL component `dame` is retained; it does not select a publisher destination. Project Python is **3.14**; the host's system Python is not the project environment.

The obsolete `legacy/` source/documentation archive was removed under root's explicit 2026-09-25 instruction. Historical citations describe earlier trees; do not restore or follow those instructions. Temporary V2 evidence remains in `phase-II_v2/` until its useful content is reconciled into current documentation. No upstream/other-project lookup is needed to work here.
