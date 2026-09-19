# Protected V1 Docker inventory

Observed 2026-09-19, between 01:03:42 and 01:05:20 UTC. This is a non-atomic, read-only metadata snapshot, not a deployment action or V2 acceptance result.

## Authorization and scope

Root explicitly requested current Docker names/versions/commits, then identified the service account `maxwell-curie` and authorized running the observation as that user. `id -u maxwell-curie` returned `1003`; the coordinator used noninteractive sudo as that account with the explicitly constructed local endpoint `unix:///run/user/1003/docker.sock`. No context switch occurred. Docker client/server both reported `26.1.5+dfsg1`. The private rootless topology is root's/source-design description; this inventory did not separately audit the engine's security configuration.

The initial attempt against the default local socket returned permission denied and no container metadata. The coordinator stopped, asked about privileged metadata access, and proceeded only after root supplied the service account/run-as instruction. The default daemon and other accounts' engines were not subsequently inspected.

Allowed observations were formatted running-container names/IDs/image references/state/timestamps, immutable image IDs, and exact Compose/instance/OCI revision/version labels. No raw inspect output, environment arrays, credentials, logs, mount paths/contents, databases, container commands, exec, deployment scripts, builds, pulls, stops, restarts, removals, pruning or service changes were used.

**All resources below belong to the protected running V1 deployment. Do not rename, retag, replace, adopt, stop or remove them as part of V2 source work.** A V1 resource containing `dame-curie` in its site name is still V1, not a V2 resource.

## Running containers

19 running containers were observed: four core services, fourteen site backends and one shell workspace. API, web and Ollama were reported healthy by `docker ps`; this does not establish application correctness or a new acceptance result.

The image key resolves to the immutable IDs in the next section. Container IDs below are observed 12-character display prefixes; the observation also returned full IDs. They are inventory references, not destructive-command selectors.

| Container name | ID prefix | Image key | Observed grouping |
| --- | --- | --- | --- |
| `maxwell-curie-bot-1` | `14376eedce38` | app | Compose project `maxwell-curie`, service `bot` |
| `maxwell-curie-api-1` | `d7260e64c84d` | app | Compose project `maxwell-curie`, service `api` |
| `maxwell-curie-web-1` | `9d5a3edc8ef6` | web | Compose project `maxwell-curie`, service `web` |
| `maxwell-curie-ollama-1` | `b35dd97b8198` | ollama | Compose project `maxwell-curie`, service `ollama` |
| `maxwell-curie-shell` | `dbb891f41761` | shell | Custom instance `curie`, kind `shell` |
| `maxwell-curie-site-reasoning30` | `ff91385a5250` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-unicorn-php` | `74e4c55b44cd` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-unicorn-svg` | `1394aa36ecb9` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-remote-probe` | `e1efba460693` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-llm-box-128` | `a8e5a579f53f` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-seals` | `9cf99c19cf39` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-unicorn-bicycle-v2` | `4d76d9509f4e` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-boss-unicorn` | `9eceb1156d2b` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-unicorn-bicycle` | `c1bd68f4e193` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-slab-swap` | `792422cfd8b3` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-dame-curie-the-queen` | `9e08147cab0c` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-curie-emotes-remote` | `ade258318069` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-dead-signal` | `6df4633c92a5` | site | Custom instance `curie`, kind `site` |
| `maxwell-curie-site-curie-node` | `8d19632900ee` | site | Custom instance `curie`, kind `site` |

Core containers carry the observed Compose labels; their custom `maxwell.instance`/`maxwell.kind` labels were absent. Shell/site containers carry custom instance/kind labels; their Compose project/service labels were absent. Neither absence authorizes adoption or deletion.

## Protected images and commit/version evidence

### app

- Running reference: `maxwell-app:0468dde` (bot and API).
- Immutable local image ID: `sha256:d7606aec88ae0823fedfe27390b7ba030e42e9374bb986cfaab4234cd8f12491`.
- OCI revision label: `0468ddedbab21e0a9b2ecba6b642e405c07ece95`.
- OCI version label: absent.
- Image creation timestamp: `2026-09-19T00:34:55.382709762+02:00`.
- Bot started: `2026-09-19T00:03:16.086006331Z`; API started: `2026-09-19T00:03:15.670967716Z`.

### web

- Running reference: `maxwell-web:1b96027`.
- Immutable local image ID: `sha256:641a53ae1e295f7747818d0d4c9e26dc74fe9087fb663ec75fc5748b3dabad75`.
- OCI revision label: absent. `1b96027` is the observed tag suffix, not independently verified Git provenance.
- OCI version label: `v2.10.2`; do not interpret this inherited component label as the dame-curie application release.
- Image creation timestamp: `2026-09-13T16:28:39.262626129+02:00`.
- Container started: `2026-09-19T00:03:11.705671579Z`.

### site

- Running reference: `maxwell-curie-site-runtime` (all fourteen site backends).
- Immutable local image ID: `sha256:db4c2097c6898f89d6336c542bd30cb17ce895633d1a522262c2ad379b468158`.
- OCI revision/version labels: absent; source commit unknown.
- Image creation timestamp: `2026-09-09T20:12:31.170987119+02:00`.
- The observed backend starts span `2026-09-19T00:03:11.976840554Z` through `2026-09-19T00:03:15.029553254Z`.

### shell

- Running reference: `maxwell-curie-shell-image`.
- Immutable local image ID: `sha256:98916ffdc0c68b708354fcaa851f777b5ebd77314ee8417810df7ca795bc008b`.
- OCI revision label: absent; source commit unknown.
- OCI version label: `26.04`, an inherited base-image label, not a project release or proof of its Python version.
- Image creation timestamp: `2026-09-09T18:15:29.560398816Z`.
- Container started: `2026-09-19T00:03:15.250451915Z`.

### ollama

- Running reference: `ollama/ollama:0.33.3@sha256:32931b46719f673c05fdbaa81ccb26da18ea4a1c57590a754874ab28ba269eb2`.
- Immutable local image ID: `sha256:2a5d0462221131b2313d838e99c30cf4190a5207236f065b246acd11ae718e85`.
- OCI revision label: absent.
- OCI version label: `24.04`, an inherited base-image label; the observed image reference names Ollama `0.33.3`. No Ollama executable/service probe was run.
- Image creation timestamp: `2026-09-03T17:04:13.963556691Z`.
- Container started: `2026-09-19T00:03:11.430293318Z`.

Tags are mutable. OCI revision labels are image-supplied metadata, not independently verified source provenance. Image IDs identify the local content; the Ollama repository digest and its local image ID are distinct identifiers. No commit was resolved against old history, another checkout or a remote repository.

## Limits and V2 implications

- This snapshot covers running resources in the one root-specified engine only. Stopped containers, unused image tags, networks, volumes, other engines/accounts, host services, remote publisher roots and backup contents were not inventoried.
- No host-wide namespace-availability or multi-instance isolation claim follows from this list.
- Root subsequently fixed the planned V2 service account as exactly `dame-curie`, with a separate rootless engine. The prospective V2 resource namespace differs from observed V1, but account/engine provisioning, private roots, explicit configuration, storage ownership and remote publication boundaries still need separate validation before any startup.
- A V2 account, engine, image, volume, network or bot was not created. Existing V1 defaults and live configuration were not changed.
