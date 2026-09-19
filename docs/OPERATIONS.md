# dame-curie operations: identity first, hands off by default

This page defines a safe investigation procedure. It does not grant deployment access, install anything, or prove that V2 is provisioned. A source/documentation task is not a runtime assignment.

## Account → engine → identity map

| Workload | Service account | Engine | State of this knowledge |
| --- | --- | --- | --- |
| Protected running V1 | `maxwell-curie` | That account's private local rootless Docker engine | Root identified the account; bounded running-resource metadata was observed on 2026-09-19 |
| Planned V2 | **`dame-curie`** | A separate private rootless engine owned by that account | Root's target decision; account/engine creation and existence not verified here |
| Future replicas | Explicitly assigned distinct accounts | One private engine per identity | Design intent, not tested V2 replication |

The account, Compose project, application instance key, image reference and database root are different fields. Do not guess one from a pretty container name. The observed V1 Compose project is `maxwell-curie`; V2 source now uses the full instance/project slug `dame-curie`, with replicas `dame-curie-<identity>` and private roots `/srv/<full-instance>`. This source convention does not prove a V2 engine exists. Do not silently make its user `dame-curie-v2` or `dame-curie-dame-curie`.

The intended local rootless endpoint is `unix:///run/user/<service-uid>/docker.sock`, with UID resolved from the **approved service account**, not copied from a historical document. Socket/engine availability and ownership must be established for the actual target. No default-rootful fallback is acceptable. Separate engines do not protect against shared host mounts, credentials, database roots, exposed ports or remote publisher destinations; those need their own boundaries.

## Choose the assignment before touching Docker

1. **Source-only:** read this checkout; no Docker requests.
2. **Explicit metadata inventory:** root names/approves the target identity and grants read-only observation. Use only the allowlisted fields below. Run-as/sudo must be specifically authorized for that account.
3. **Runtime mutation or deeper diagnosis:** provisioning, builds, pulls, lifecycle operations, container exec, logs, private configuration/state and real logins require a separate explicit scope. Neither this page, the historical debug skill nor a previous inventory grants it.

Once a metadata/run-as assignment is granted, use that known account directly. Do not repeat the discovery mistake of starting with bare `docker` against the caller's default daemon. Do not execute a lifecycle wrapper, deployment helper or installer to discover the identity—even `--help` can cross boundaries through initialization.

## Read-only discovery

Run steps separately. If any step fails or yields an unexpected target, stop before the next one. The quoted angle-bracket tokens below are placeholders to replace with **already approved/observed values**, not defaults to guess.

Resolve the local CLI and the approved account UID:

```sh
command -v docker
id -u '<approved-service-account>'
```

Use the verified CLI path and construct the local socket from that observed UID. The examples below use `/usr/bin/docker`, the path verified in this session; another host must resolve its own installed client. No remote SSH/TCP endpoint, context switch, profile sourcing or process-environment dump is needed.

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

The scalar scope used for the current root-authorized inventory is: container ID/name, configured image reference, immutable image ID, state/health summary, creation/start timestamps, Docker client/server version, and specifically named Compose project/service/image or OCI revision/version labels. Identity/kind/site labels may be read only as exact known keys relevant to the assigned namespace. Never dump all labels.

This is a maximum procedure allowlist, not permission for a future task. If root grants a narrower set, reduce both the command format and recorded output to that subset; do not execute a broader example unchanged. Names/versions/commits and the explicit metadata-only run-as grant were not narrowed during the inventory recorded in this phase.

Do not return raw inspect JSON, `Config.Env`, command/argument arrays, mount details/contents, logs, process environments, secrets or private configuration. Do not use broad `docker info`, container exec or deployment scripts for inventory.

Tags can move. OCI revision/version labels are self-declared image metadata and may describe a base image rather than the application. Missing labels mean unknown. Record the immutable image ID separately, and do not look up an old commit in another checkout or online to manufacture provenance.

Classify resources by exact account/engine/project/ownership metadata, not substring searches. One protected V1 site is named `maxwell-curie-site-dame-curie-the-queen`; the embedded project name does not make it V2.

## Permission/error boundary

Unknown account, missing/unexpected socket, remote endpoint, permission denial or malformed metadata: **stop and report the exact sanitized failure**. Ask root for the specific target/run-as grant or a sanitized inventory. Do not retry as root against the default socket, scan other users' engines, change socket permissions, add groups, start a daemon or alter a Docker context.

In this session the default local socket rejected access. After root explicitly supplied `maxwell-curie` and the run-as instruction, the targeted metadata-only query succeeded. This is why the account map is written down rather than rediscovered through privileged trial and error.

## Mutation and acceptance remain separate

No create/build/pull/run/start/stop/restart/kill/remove/prune/retag, user/service provisioning, migration/restore, configuration edit, provider probe or real login follows from an inventory grant. Do not touch GNU Screen or invoke a logging/debugging skill under this procedure.

Running-only metadata does not inventory stopped containers, unused image tags, networks, volumes, other engines, host services or remote publisher roots. It cannot establish host-wide name availability or multi-instance isolation. Any future startup needs its own explicit authorization, private-root/identity checks and agreed synthetic acceptance first; a backup or documentation commit is not that authorization.

Record bounded evidence under `phase-II_v2/` while this phase is active and summarize milestones in `STATUS.md`. Before retiring that temporary folder, retain any still-needed live identity mapping and unresolved safety boundary in the active docs; do not copy the entire historical ledger back in.
