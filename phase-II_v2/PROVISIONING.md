# dame-curie V2 provisioning — in progress

## Current authorization and hard stops

Root explicitly included provisioning in this round: create the `dame-curie` account, separate private rootless Docker engine, images and containers. This supersedes the earlier source-only assignment for the coordinator's scoped V2 operations; it does not authorize modifying V1.

- **Fresh V2 databases, memory, sites and mutable state.** No V1 database/history copy or migration.
- Reuse necessary V1 provider configuration/credentials through read-only, secret-safe transfer. Bounded non-Discord provider smoke tests and their billing are authorized. Never print secret values or bake configuration into images.
- **No Discord token transfer, login, request/probe or bot entrypoint startup.** Main/companion/API-OAuth Discord credentials stay blank. Root must personally authorize and debug future Discord activation.
- Telegram is disabled and selected for later removal; this is not a feature-pruning batch.
- **Ollama and its model-pull job must remain stopped.** Do not download/warm models through these containers. Stage V2 with `ENABLE_RAG=false`; preserve the embedding endpoint/model/dimension settings for later activation. RAG runtime acceptance is deferred.
- No V1 lifecycle changes, publishing, remote destination reuse, broad test execution, or unrelated pruning/extraction. Use the reviewed staging sequence, not `scripts/build_for_human.sh`.
- Root subsequently authorized email removal in its own worktree and background Hortator source research for a reviewed logging proposal. Neither child assignment grants runtime access; shared inbox/media and existing logging remain protected.
- Canonical principals: **Dame Curie `1545541390392369165`**; **root / .normal.man `1482143139828596916`**. No other ID identifies either. Unconfigured third-party owner/partner trust must not be inherited.

## Observed and completed so far

- Source checkpoint before this slice: `3a71cbb` on `dev/phaseII_v2`. Existing `scratch-mermaid/` remains unrelated and unread.
- Host: Debian 13.6; Docker 26.1.5+dfsg1; Compose v2.39.4. Required rootless binaries and subordinate-ID helpers already exist; no host package upgrade/replacement was needed.
- Created locked-password account **`dame-curie`, UID/GID `1005`**, home `/home/dame-curie` (0750), private root `/srv/dame-curie` (0700), and empty config/prompts/data/sites/shell/publisher directories.
- Its subordinate UID/GID range is `427680:65536`; user-manager lingering enabled.
- Installed the repository's rootless unit as `/home/dame-curie/.config/systemd/user/docker.service` and started only that new engine.
- Verified rootless engine ID `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`, explicit socket `unix:///run/user/1005/docker.sock`, private Docker root `/home/dame-curie/.local/share/docker`, systemd cgroup driver. No containers existed at that verification.
- New-account slice limits: CPU quota 400%, memory high 6 GiB, memory max 8 GiB. These constrain the new UID, not V1.
- Added only pinned `python-dotenv==1.2.3` (matching the image lock) to the existing isolated Python 3.14 tool venv for secret-safe configuration handling. This still is not an application-ready host environment.

## Current V1 artifact evidence — read-only

V1 UID re-resolved as `1003`; all Docker calls used its explicit private socket. Current observation still showed 19 running containers. No Docker exec or lifecycle command was used on V1.

- Bot container `14376eedce38a6b01a2137cb7bf77d6a8999be112c0d8c859a712689cf85ce5c`, image `maxwell-app:0468dde`, immutable ID `sha256:d7606aec88ae0823fedfe27390b7ba030e42e9374bb986cfaab4234cd8f12491`, read-only rootfs. Its selected configuration mount is `/srv/maxwell/curie/config` → `/config` (read-only); the data mount was identified but databases/messages were not read.
- Web container `9d5a3edc8ef651837ab21a03539ea9026906d394475ba12d1a037d251b96bd9d`, image `maxwell-web:1b96027`, immutable ID `sha256:641a53ae1e295f7747818d0d4c9e26dc74fe9087fb663ec75fc5748b3dabad75`, read-only rootfs, no `/srv/web` mount.
- Current checkout lacked both HTML files required by `docker/app.Dockerfile`; no files existed under `web/`, and no tracked `legacy/v1/web` or `legacy/web` artifact was found. Recovered only `/srv/web/index.html` and `/srv/web/admin/index.html` from the existing immutable web container into the corresponding source paths using read-only Docker archive copy. This is deployed static source, not copied personal state or proof that all V2 source matches V1 byte-for-byte.
- Pre-edit recovered SHA-256: landing `0a99c3d9ee6bcd97f88476a1a5a4108c55c43fc1929a88870f5ed5c98c43a0de`; admin `23a01c77fc9243aaec133794c160b2ccc2ad5cfd1ec6266cddfe452f6fc8b698`. Flash completed the bounded namespace changes; Luna verified their auth/API/PM2/Caddy seams. Upstream attribution is preserved. Browser storage now uses `dame-curie.*`, requiring one fresh sign-in rather than reusing V1 keys.
- Existing UI warning deferred: “Clear saved login” clears form fields but does not remove persisted credentials; use the existing Logout action. This was inherited from the recovered artifact, not introduced by the namespace change.

## Private configuration and staging gate

- Created `/srv/dame-curie/config/bot.env` and a fresh `/srv/dame-curie/data/bot_control.json`, service-owned mode0600. Transferred 79 allowlisted provider environment fields and nine provider-control fields from V1 configuration only; no personality/history/admin state was copied. Only the provider settings in V1 `data/bot_control.json` were selected. Discord credentials and inherited ownership/path settings were excluded.
- Preserved four embedding settings under `DAME_CURIE_EMBED_*`; `ENABLE_RAG=false`. Main/companion/OAuth/Telegram credentials are blank. Autonomy and REM are disabled; fresh control has `bot_enabled=false` and the explicit wake phrase `dame curie`. A fresh dashboard password is stored only in private `bot.env` (username `root`).
- Selected loopback web port18081 was unbound at preflight; actual binding acceptance remains pending. No remote publisher is configured or activated.
- Compose2.39.4 parsed the staging overlay and selected only `api`/`web` by default. Validation as the new service account initially failed because `/home/codexy` is private0700; reran static validation as the checkout owner. No home permission was weakened. The deployment source must live separately under `/opt/dame-curie`.
- Luna identified that the existing lifecycle wrapper ignored overlays and would bypass the hold. The targeted fix adds optional literal `DAME_CURIE_STAGING=true|false`, defaulting to **true**, includes the overlay, and limits staged restart to API/web. Ownership checks permit only the exact base file or base+known-staging file list in the same checkout. Down selects all profiles only for cleanup. Both public Docker examples now default to staging/RAG-disabled operation.
- Luna re-reviewed the wrapper/template/ownership fix without a remaining source blocker. Existing test fixtures were aligned, not expanded or executed. Moving an already-active instance back into staging would require an authorized all-profile down first; changing the flag and running up does not stop inactive-profile containers. This new V2 instance has never run those services.
- `discord-activation` alone is not an activation recipe: bot intentionally still depends on Ollama. Root must approve full activation, start/verify embedding readiness, enable RAG, configure Discord manually and explicitly leave staging mode first. No such activation is authorized now.
- Pulled the pinned Ollama OCI image into V2's private engine. This downloaded the container image, **not an embedding model**, and did not start a container.

## Pending acceptance

Finish the reviewed source checkpoint and image builds, create containers and start only permitted support services. Initialize fresh database schema without messages/embeddings; verify local API/web and bounded provider calls, then record exact images/container states/ports. Integrate the separately reviewed email cut and collect the logging proposal. **No Discord, RAG or terminal-interaction readiness is claimed.**
