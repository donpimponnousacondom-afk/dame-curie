# dame-curie operations: identity first, hands off by default

This page defines a safe investigation procedure. It does not grant deployment access, install anything, or prove that V2 is provisioned. A source/documentation task is not a runtime assignment.

## Account → engine → identity map

| Workload | Service account | Engine | State of this knowledge |
| --- | --- | --- | --- |
| Protected running V1 | `maxwell-curie` | That account's private local rootless Docker engine | Root identified the account; bounded running-resource metadata was observed on 2026-09-19 |
| V2 foundation | **`dame-curie`** | Its separate private rootless Docker engine | Account UID/GID 1005 and engine verified during authorized provisioning; see `../phase-II_v2/PROVISIONING.md` for readiness and activation holds |
| Future replicas | Explicitly assigned distinct accounts | One private engine per identity | Design intent, not tested V2 replication |

The account, Compose project, application instance key, image reference and database root are different fields. Do not guess one from a pretty container name. The observed V1 Compose project is `maxwell-curie`; V2 uses the full instance/project slug `dame-curie`, with replicas `dame-curie-<identity>` and private roots `/srv/<full-instance>`. Engine provisioning evidence is separate from this source convention and does not establish application readiness. Do not silently make its user `dame-curie-v2` or `dame-curie-dame-curie`.

The intended local rootless endpoint is `unix:///run/user/<service-uid>/docker.sock`, with UID resolved from the **approved service account**, not copied from a historical document. Socket/engine availability and ownership must be established for the actual target. No default-rootful fallback is acceptable. Separate engines do not protect against shared host mounts, credentials, database roots, exposed ports or remote publisher destinations; those need their own boundaries.

## Choose the assignment before touching Docker

1. **Source-only:** read this checkout; no Docker requests.
2. **Explicit metadata inventory:** root names/approves the target identity and grants read-only observation. Use only the allowlisted fields below. Run-as/sudo must be specifically authorized for that account.
3. **Runtime mutation or deeper diagnosis:** provisioning, builds, pulls, lifecycle operations, container exec, logs, private configuration/state and real logins require a separate explicit scope. Neither this page, the historical debug skill nor a previous inventory grants it.

Once a metadata/run-as assignment is granted, use that known account directly. Do not repeat the discovery mistake of starting with bare `docker` against the caller's default daemon. Do not execute a lifecycle wrapper, deployment helper or installer to discover the identity—even `--help` can cross boundaries through initialization.

## V2 staging gate

The approved source topology is **`bot`, `ollama`, `ollama-pull` only**, with no published ports, dashboard/API/OAuth/Caddy, web image, local site server or nested shell container. No replacement server or PM2 deployment. Source integration is in progress; this is not a claim that deployed resources already match it.

The canonical instance wrapper reads optional `DAME_CURIE_STAGING=true|false` from private `deploy.env`; missing means **true**. With staging enabled, `up`, `start` and `restart` are **validated NO-OPs: nothing starts**. Account, private-root, engine and resource ownership checks still run before the early return, so even a staged no-op is runtime access, not a source-review command. Both exact base-only and base+staging Compose labels remain recognized for the same checkout.

Keep Discord credentials blank and `ENABLE_RAG=false`. Never start the bot entrypoint, contact Discord, start Ollama/model-pull or populate/warm model storage under the current holds. Do not substitute raw base-only Compose or an activation profile: bot retains its Ollama dependency. Leaving staging requires a separate explicit activation grant and readiness checks; changing a flag alone is not permission.

Staging does not stop existing resources. After reviewed source integration, only the coordinator may reconcile obsolete V2 resources with renewed account/socket and ownership checks. An authorized wrapper `down` performs `--profile '*' down --remove-orphans` internally after ownership validation, including legacy shell/site cleanup; do not run that raw Compose command separately. V1 is never a cleanup target.

The **earlier** provisioning handoff reported API/web running and bot/Ollama/pull/shell created but never started. Runtime has not been re-observed in this documentation round. That historical state is not the approved source topology or a fresh health claim; see `../phase-II_v2/PROVISIONING.md`.

## V2 operator entrypoint and configuration holds

The earlier provisioned operator checkout is `/opt/dame-curie`, not the private coordinator home. Its operator venv is Python3.14 and is not the application environment; app dependencies live in the image. Do not assume it contains the redesign until the coordinator records release integration. With a separately granted V2 lifecycle assignment and freshly resolved target, the canonical argument order is:

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/instance.py dame-curie up
```

The redesigned `deploy.env` contract selects `INSTANCE_ID`, `INSTANCE_DIR`, `ENGINE_SOCKET`, versioned `APP_IMAGE` and optional `DAME_CURIE_STAGING`. It no longer selects a web image or port. The wrapper can validate and discard a paired legacy `WEB_IMAGE`/`WEB_PORT` during transition; that does not restore either service. No private configuration was inspected here. The recipe above is not permission to run it or to bypass staging.

`config.py` loads the selected dotenv file with **`override=True`**. During separately authorized private configuration reconciliation, the coordinator must audit structural keys as well as credentials: container mode, instance identity, data/site/shell/prompt roots, command prefix and retired socket settings can override injected environment values. Do not treat Compose environment entries as proof of the effective bot configuration or print private values.

The `DAME_CURIE_STARTUP_GIT_SOCKET` mount/environment and checkout listener unit templates are removed from deployment. Do not provision a replacement listener/socket bridge. Existing `capture_running_build` falls back to local Git; an archive-built image without `.git` reports unknown checkout metadata. Build arguments/OCI labels are separate self-declared image metadata, not checkout-snapshot proof.

Public URL examples use reserved `.invalid` destinations. V2 publisher activation and destination have not been established; do not invent a host or reuse V1's destination. Publisher/syncer files and configuration are outside this redesign's mutation scope.

## Log viewer source contract

The integrated logging source adds opt-in `logs --format screen [--no-keys]`; `auto`, `console`, `plain` and `jsonl` retain their existing/default behavior. Screen mode appends to the ordinary screen without repaint or alternate-screen switching. `--no-keys` is valid only with `logs --format screen`. Launching the instance log wrapper still reads private deployment selection and contacts its engine, so it needs a separate runtime/log-access grant.

Controls, redaction limits and synthetic terminal acceptance requirements are in `../phase-II_v2/LOGGING_PLAN.md`; source review/integration status is in `../phase-II_v2/REDESIGN_PROGRESS.md`. No terminal acceptance is claimed. Do not use an existing production Screen session, start a producer to exercise the viewer, or confuse filtered diagnostic output with functional RAG/REM/graph storage.

## Read-only discovery

Run steps separately. If any step fails or yields an unexpected target, stop before the next one. The quoted angle-bracket tokens below are placeholders to replace with **already approved/observed values**, not defaults to guess.

Resolve the local CLI and the approved account UID:

```sh
command -v docker
id -u '<approved-service-account>'
```

Use the verified CLI path and construct the local socket from that observed UID. The examples below use `/usr/bin/docker`, the path recorded in the earlier inventory; every new runtime assignment must resolve its actual target/client again. No remote SSH/TCP endpoint, context switch, profile sourcing or process-environment dump is needed.

If running as the approved account already, use the explicit `--host` with its CLI. If root has explicitly granted run-as inventory, the noninteractive form is:

```sh
sudo -n -H -u '<approved-service-account>' -- /usr/bin/docker \
  --host 'unix:///run/user/<observed-uid>/docker.sock' \
  ps --no-trunc --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}'
```

This lists **running containers in one engine**, not all host resources. Record the observation timestamp and target account. Do not inspect an unrelated engine if the expected containers are missing.

For an exact container ID returned by that query, use formatted fields rather than a raw inspect:

```sh
sudo -n -H -u '<approved-service-account>' -- /usr/bin/docker \
  --host 'unix:///run/user/<observed-uid>/docker.sock' inspect --type container \
  --format 'id={{.Id}} name={{.Name}} image_id={{.Image}} image_ref={{.Config.Image}} state={{.State.Status}} started={{.State.StartedAt}} project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}' \
  '<observed-container-id>'
```

Then, if image identity/version metadata is part of the assignment, inspect the observed immutable image ID without pulling or resolving an external registry:

```sh
sudo -n -H -u '<approved-service-account>' -- /usr/bin/docker \
  --host 'unix:///run/user/<observed-uid>/docker.sock' image inspect \
  --format 'id={{.Id}} created={{.Created}} revision={{index .Config.Labels "org.opencontainers.image.revision"}} version={{index .Config.Labels "org.opencontainers.image.version"}}' \
  '<observed-image-id>'
```

A read can race with another authorized operator. If an ID disappears or results are partial, record the limit; do not restart/recreate anything to finish an inventory.

## Metadata allowlist and interpretation

The scalar scope used for the earlier root-authorized inventory was: container ID/name, configured image reference, immutable image ID, state/health summary, creation/start timestamps, Docker client/server version, and specifically named Compose project/service/image or OCI revision/version labels. Identity/kind/site labels may be read only as exact known keys relevant to the assigned namespace. Never dump all labels.

This is a maximum procedure allowlist, not permission for a future task. If root grants a narrower set, reduce both the command format and recorded output to that subset; do not execute a broader example unchanged. Names/versions/commits and the explicit metadata-only run-as grant were not narrowed during the inventory recorded in this phase.

Do not return raw inspect JSON, `Config.Env`, command/argument arrays, mount details/contents, logs, process environments, secrets or private configuration. Do not use broad `docker info`, container exec or deployment scripts for inventory.

Tags can move. OCI revision/version labels are self-declared image metadata and may describe a base image rather than the application. Missing labels mean unknown. Record the immutable image ID separately, and do not look up an old commit in another checkout or online to manufacture provenance.

Classify resources by exact account/engine/project/ownership metadata, not substring searches. One protected V1 site is named `maxwell-curie-site-dame-curie-the-queen`; the embedded project name does not make it V2.

## Permission/error boundary

Unknown account, missing/unexpected socket, remote endpoint, permission denial or malformed metadata: **stop and report the exact sanitized failure**. Ask root for the specific target/run-as grant or a sanitized inventory. Do not retry as root against the default socket, scan other users' engines, change socket permissions, add groups, start a daemon or alter a Docker context.

During the historical inventory the default local socket rejected access. After root explicitly supplied `maxwell-curie` and the run-as instruction, the targeted metadata-only query succeeded. This is why the account map is written down rather than rediscovered through privileged trial and error.

## Mutation and acceptance remain separate

No create/build/pull/run/start/stop/restart/kill/remove/prune/retag, user/service provisioning, migration/restore, configuration edit, provider probe or real login follows from an inventory grant. Do not touch GNU Screen or invoke a logging/debugging skill under this procedure.

Running-only metadata does not inventory stopped containers, unused image tags, networks, volumes, other engines, host services or remote publisher roots. It cannot establish host-wide name availability or multi-instance isolation. Any future startup needs its own explicit authorization, private-root/identity checks and agreed synthetic acceptance first; a backup or documentation commit is not that authorization.

Record bounded evidence under `phase-II_v2/` while this phase is active and summarize milestones in `STATUS.md`. Before retiring that temporary folder, retain any still-needed live identity mapping and unresolved safety boundary in the active docs; do not copy the entire historical ledger back in.
