# dame-curie V2 foundation — provisioned, activation held

This is a historical provisioning receipt, not current operating instructions. Component names and grants below describe that earlier slice; several components were subsequently retired. Current authority is in `AGENTS.md` and `TODO.md`. Temporary-Dirac acceptance does not activate the canonical instance. Retire this working receipt only after accepted round two, preserving unique isolation/readiness evidence in current operations documentation.

## Canonical image activation hold — 2026-09-25

Before any separately authorized canonical activation, reconcile its effective private `IMAGE_GEN_*` and `ENABLE_IMAGE_GEN` settings with the native-only contract in [IMAGE_GENERATION.md](../docs/IMAGE_GENERATION.md#migration): explicit endpoint, valid exact-ID model/description map, listed default model, intentional credential/quality settings, and no retired split profiles. The temporary Dirac migration is not evidence that the canonical profile was migrated. Invalid image settings now disable that capability without blocking unrelated startup; neither disabled capability nor successful startup proves image readiness. No canonical private configuration was inspected or changed during this remediation.

## Historical provisioning authorization and hard stops

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
- Selected loopback web port18081 was unbound at preflight; final inspection confirmed `127.0.0.1:18081` and successful HTTP checks. No remote publisher is configured or activated.
- Compose2.39.4 parsed the staging overlay and selected only `api`/`web` by default. Validation as the new service account initially failed because `/home/codexy` is private0700; reran static validation as the checkout owner. No home permission was weakened. The deployment source must live separately under `/opt/dame-curie`.
- Luna identified that the existing lifecycle wrapper ignored overlays and would bypass the hold. The targeted fix adds optional literal `DAME_CURIE_STAGING=true|false`, defaulting to **true**, includes the overlay, and limits staged restart to API/web. Ownership checks permit only the exact base file or base+known-staging file list in the same checkout. Down selects all profiles only for cleanup. Both public Docker examples now default to staging/RAG-disabled operation.
- Luna re-reviewed the wrapper/template/ownership fix without a remaining source blocker. Existing test fixtures were aligned, not expanded or executed. Moving an already-active instance back into staging would require an authorized all-profile down first; changing the flag and running up does not stop inactive-profile containers. This new V2 instance has never run those services.
- `discord-activation` alone is not an activation recipe: bot intentionally still depends on Ollama. Root must approve full activation, start/verify embedding readiness, enable RAG, configure Discord manually and explicitly leave staging mode first. No such activation is authorized now.
- Pulled the pinned Ollama OCI image into V2's private engine. This downloaded the container image, **not an embedding model**, and did not start a container.

## Image and fresh-state checkpoint

- Logging proposal committed as `f94c291`; namespace/staging closeout as `8876dc4`. Email source removal subsequently integrated as `9b01074`/`70b8ceb`; refreshed images must include it and the separately reviewed remote-inference rename before final handoff.
- Built `dame-curie-shell-image` (`sha256:f46befbafc842c6ea8f91c9678db694ca0bf308d75c357954f079129d07ac0c3`) and `dame-curie-site-runtime` (`sha256:697f5b2966d82378bef464995e77805d18a63d6e81cf7583ab2d9b3ab57ddf7c`) from unchanged Dockerfiles at `3a71cbb`, with canonical ownership labels and shell source hash. Network-disabled, read-only ephemeral checks reported Python3.14.4 in both; site Flask/FastAPI imports succeeded. No site/application server was started by those checks.
- Initial app/web builds from an immutable `8876dc4` archive succeeded: app `sha256:a10a650008b4352c1c88c8dd6f50c715bd15f14a309b94105cc94b473d9869ea`; web `sha256:0f185ef727db249a17c2c6e5a4c559a4ad105cde1565b92619f2af226ff78950`. These are pre-email/pre-inference integration checkpoints, not the final requested release. No private configuration entered the build context.
- Installed a root-owned, service-readable source archive at `/opt/dame-curie` with its own Python3.14 operator venv. Created private service-owned0600 `/srv/dame-curie/deploy.env` with staging enabled. The canonical installed wrapper independently selected API/web. The empty `/srv/dame-curie-checkout/dame-curie` bind source exists; no checkout-snapshot socket service has been started.
- A network-disabled, read-only-rootfs one-off app container initialized fresh source-default personality, empty server prompt mapping and `dame-curie-rag.db`. Integrity check returned `ok`; `vectors`, `user_entities`, `embed_cache`, `embed_backfill`, `graph_nodes` and `graph_edges` each had zero rows. No embedding request/model generation or V1 memory transfer occurred.
- All five Compose services were created through the verified staging wrapper using both profiles for **create only**. Bot, Ollama and model-pull were inspected as `created`, `StartedAt=0001-01-01T00:00:00Z`, restart policy `no`. No entrypoint from any of those three ran.

## Final source/configuration checkpoint

- Remote inference cut `85eafb1` passed independent Flash/Luna reviews and was integrated cleanly as `b2f5380`. Combined Python3.14 compilation, Node syntax, Bash parser and whitespace checks passed. Existing email and staging fixes were retained; no tests were executed.
- Atomically renamed 18 configured private V2 keys from the 22-entry `OLLAMA_*` → `OPENAI_*` map. Missing keys stayed missing; explicit blanks and all values were preserved. The shared compat bearer and four embedding settings were unchanged; removed the obsolete disabled email flag. Source-default inference now requires an explicit remote URL/model and assumes no vendor. See `INFERENCE_NAMING.md`.
- Built final app `dame-curie-app:b2f5380` (`sha256:e78fd663b29f4c8fbd5a7d98cd11c1a1af4563f3d444cb9165b2aad73cced8c9`) and web `dame-curie-web:b2f5380` (`sha256:7521271f14e8c9e6d587caa6344cb489419de71319a024631a7fa85965fd9935`) from the exact committed archive. Updated private deploy references and recreated app/web containers using create only.
- Replaced `/opt/dame-curie` with a clean integrated archive and fresh operator venv, so removed mail source was not left behind by an overlay extraction. Bootstrap source is retained separately at `/opt/dame-curie-bootstrap-8876dc4`, without private configuration; this is not a validated state backup/rollback procedure.
- Created the isolated `dame-curie-shell` container with its exact ownership, image/source hash, mounts, security and resource contract. It remains unstarted; site-runtime has no container because fresh V2 has no sites.
- The new local model volume contained zero entries. The first coordinator startup command used reversed CLI arguments and was rejected by argparse before any runtime action; no source defect or service crash occurred. Correct operator order is `instance.py dame-curie up`.

## Verified staged handoff

Final code/image revision: **`b2f538017edb3a8aa0b1d800e994a11f5944da07`**. Subsequent handoff changes are documentation-only, not an automatic rebuild/restart or a claim that deployed archives follow Git HEAD.

| Resource | Final observed state |
| --- | --- |
| `dame-curie-api-1` | Running, healthy; final app image; restart `unless-stopped` |
| `dame-curie-web-1` | Running, healthy; final web image; `8080/tcp` → **`127.0.0.1:18081`**; restart `unless-stopped` |
| `dame-curie-bot-1` | Created, never started, restart `no`; final app image |
| `dame-curie-ollama-1` | Created, never started, restart `no` |
| `dame-curie-ollama-pull-1` | Created, never started, restart `no` |
| `dame-curie-shell` | Created, never started, restart `no`; isolated shell image |
| Site runtimes | Image ready; no site containers or published site directories |

The four unstarted containers retain `StartedAt=0001-01-01T00:00:00Z`. The pinned Ollama manifest remains `ollama/ollama:0.33.3@sha256:32931b46719f673c05fdbaa81ccb26da18ea4a1c57590a754874ab28ba269eb2`; its container image ID is `sha256:2a5d0462221131b2313d838e99c30cf4190a5207236f065b246acd11ae718e85`.

- Canonical staged `up` completed, with API and web healthchecks passing. `/`, `/admin/` and `/api/health` returned200; health identified `dame-curie-api`. Anonymous `/api/control` returned401; private Basic authentication returned200 with `bot_enabled=false`. These are HTTP checks, not interactive browser acceptance.
- The final app's actual `Config` and renamed provider supplied the configured primary endpoint/model, headers and request builder for a bounded synthetic completion. The corrected check returned HTTP200 and five visible response characters. There were **two** requests, each capped at512 output tokens: the first received HTTP200 but the coordinator's reader mistook a partial/keepalive chunk for complete JSON; the replacement consumed the bounded complete body. No production-code change was needed. No redirects, tools, retries inside either request, bot entrypoint, Discord request or embedding call occurred; only one configured primary endpoint was exercised.
- Final private-file checks: `bot.env`, `deploy.env` and the SQLite database are UID/GID1005 mode0600; main/companion/API-OAuth/Telegram credentials are blank and RAG false. SQLite integrity remains `ok`; all six memory/graph tables have zero rows, the local model volume has zero entries, and no sites are published.
- Site-runtime offline `pip check` passed. App `pip check` **failed** on the voice extension's declared `discord-py` distribution dependency; the lock intentionally installs `discord.py-self==2.1.0` into that shared namespace, and the existing installer reinstalls the fork after extras. No competing package, metadata shim or relaxed pin was added. This is not a clean dependency/voice acceptance result.
- Final V2 engine ID matched the original private engine. Protected V1 still reported19 running containers during the final bounded inventory. No V1 exec, lifecycle/configuration mutation or DB/history migration occurred.

## Still deliberately unaccepted

**Discord remains held; RAG remains disabled and cold.** Root must explicitly authorize activation, resolve/accept the voice packaging/transport issue, establish embedding readiness, enable RAG and configure Discord credentials personally. No full bot, voice, media, auxiliary-provider, real-site, multi-instance or backup/rollback acceptance is claimed. The checkout snapshot socket is not deployed; its bind directory is empty.

**Historical roadmap at the original provisioning handoff, superseded:** logging implementation/Screen acceptance and the X/Telegram cuts were then future work; the existing logger and functional memory were preserved, and that provisioning assignment collected/ran no suites or remote publication. Logging and transport pruning were subsequently integrated. Use `../docs/STATUS.md` and `../TODO.md` for current source progress and temporary-versus-canonical holds; this old roadmap is not a new implementation assignment.
