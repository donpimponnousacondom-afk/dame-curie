# dame-curie

A Discord bot undergoing the approved Discord-only V2 redesign. The existing V1 deployment remains protected and running.

**Redesign source integration/review is in progress, not deployment acceptance.** The isolated V2 foundation was provisioned earlier; its deployed runtime has not been re-observed for this documentation round. The coordinator owns reconciliation after reviewed source integration. Lifecycle helpers are not discovery commands; do not run an installer, application or test suite from old instructions.

**Release freeze, 2026-09-25:** root approved complete audit remediation, isolated validation and bounded temporary-Dirac acceptance. Normal releases remain frozen pending the final independent audit. [TODO](TODO.md) owns the work and mandatory temporary-document retirement; [Status](docs/STATUS.md) records milestones. The archive-removal commit is cleanup, not application acceptance.

## Approved source contract

- Compose retains only `bot`, `ollama` and `ollama-pull`, with no published ports. Dashboard/API/OAuth/Caddy, the web image, local website/KV servers, six `site_*` tools, nested shell infrastructure, X/Telegram and companion/GF are removed from the target design. No replacement server or PM2 deployment.
- Shell runs Bash inside the outer bot container, with `/home/dame-curie` pointing to `/state/shell`. It is the bot's own UID, not a secret-isolated inner sandbox. No host root/network or Docker socket access.
- Local authored directories under `/state/sites` and `_images` files plus sidecars remain. The independent publisher/syncer is untouched; the model authors local files, never administers the remote host or starts local hosting. No PHP/Perl/CGI installation. V2 publication/destination is not established.
- Preserve Discord administration, autonomy, games/plugins, media, shared inbox, functional RAG/REM/graph memory, independent tool authorization and redaction. Historical `tg:%` privacy filtering is not an active Telegram transport.
- Active Discord commands use **`!`**. `!bg GOAL` remains free prose; optional trusted profile/model routing is documented in [Architecture](docs/ARCHITECTURE.md#background-jobs-and-prompts).

With `DAME_CURIE_STAGING` omitted or `true`, wrapper `up`/`start`/`restart` validates the target but starts **nothing**. Bot credentials remain blank, the bot entrypoint is never started, RAG stays false, and Ollama/model-pull and empty model storage remain held. See [Operations](docs/OPERATIONS.md); these are constraints, not a fresh runtime observation.

## Current documentation

- [Status](docs/STATUS.md): source milestones, historical deployment evidence and validation limits.
- [Approved redesign](phase-II_v2/REDESIGN_PLAN.md) and [integration progress](phase-II_v2/REDESIGN_PROGRESS.md): current scope, lane reviews and activation holds.
- [Operations](docs/OPERATIONS.md): V1/V2 accounts, rootless engines and safe read-only investigation.
- [Development](docs/DEVELOPMENT.md): Python 3.14 and isolated venv/uv use; configuration is not an interpreter environment.
- [Architecture](docs/ARCHITECTURE.md): component map and isolation intent, not unearned acceptance claims.
- [Image generation](docs/IMAGE_GENERATION.md): one native generation/edit tool with operator-configured model choices.
- [Agent contract](AGENTS.md): current permissions, naming and collaboration rules.
- [Security](SECURITY.md): private-state and disclosure boundaries.

Project name and provisioned V2 service user: **dame-curie**, with its own private rootless Docker engine. Re-resolve that account and socket before every newly authorized runtime operation. The intentional short URL component `dame` is retained; it does not select a publisher destination. Project Python is **3.14**; the host's system Python is not the project environment.

The obsolete `legacy/` source/documentation archive was removed under root's explicit 2026-09-25 instruction. Historical citations describe earlier trees; do not restore or follow those instructions. Temporary V2 evidence remains in `phase-II_v2/` until its useful content is reconciled into current documentation. No upstream/other-project lookup is needed to work here.
