# dame-curie architecture and naming boundary

This is a source map and intended isolation contract, not proof of a deployed V2 system. V1 already works; V2 is intended to remove accumulated workarounds before adding features.

## Components in this checkout

| Component | Source entry points | Responsibility |
| --- | --- | --- |
| Discord conversation and providers | `bot.py`, `providers.py`, `message_pipeline.py` | Transport, conversation/tool orchestration, queueing and provider requests |
| Memory and prompts | `rag_memory.py`, `knowledge_graph.py`, `prompt_storage.py`, `control_defaults.py` | Persistent memory, graph data, persona/server prompts and controls |
| Tools and generated sites | `bot_tools.py`, `tool_registry.py`, `tool_schemas.py`, `site_server.py`, `docker_runtime.py` | Tool dispatch, generated-site runtime and ownership/resource paths |
| API and web routing | `api/`, `docker/Caddyfile`, `compose.yaml` | Administration and routing; a complete V2 dashboard/image build has not been established |
| Operations and publishing | `scripts/instance.py`, `docker/`, `scripts/publisher/` | Existing lifecycle/backup/provisioning source and independent site publishing; not safe discovery commands |
| Additional inherited capabilities | autonomy/REM, voice and plugins | Feature-pruning decisions remain root's; presence is not a request to extend them |

## Intended identity isolation

One Linux service account and private rootless Docker engine per bot identity. The planned first V2 account is **dame-curie**; protected V1 uses **maxwell-curie**. Additional identities must have explicitly assigned separate accounts/engines rather than a second bot writer in the first identity's state.

Each identity owns its configuration, credentials, prompts, databases, generated sites, shell workspace, model storage and publisher state. Explicitly separate host mounts, exposed ports and remote publisher destinations. Future V2 identities may deliberately use the same immutable source/image artifact in their separate engines; this does not share their mutable bot state or authorize reusing the deployed V1 image namespace. V2's `dame-curie-*` repositories remain distinct from protected V1's `maxwell-*` repositories. Record image content IDs/digests separately from mutable tags. No image was built, copied, retagged or provisioned by this cut-off.

The source contains ownership/socket/private-root checks. That is evidence of design, not V2 runtime acceptance. The observed running-only V1 inventory does not cover stopped objects, all volumes/networks, other engines or remote resources.

## Selected source conventions

- Canonical project/files/URLs/resource namespace: `dame-curie`.
- Full instance/account/Compose slug: `dame-curie`, or `dame-curie-<identity>` for a replica, up to 30 characters. Accounts and resource prefixes derive directly from that slug, without duplicating the project name.
- Private host root: `/srv/<full-instance>`. Each account requires its own UID-derived rootless socket; the image-internal engine path is `/run/dame-curie/docker.sock`.
- Shell/Python configuration identifiers: `DAME_CURIE_*`. Hyphenated shell/Python variable names are not the spelling to use.
- App/web image repositories: `dame-curie-app`, `dame-curie-web`; selectors remain separate from protected `maxwell-*` images.
- Custom ownership label namespace: `dame-curie.*`; Docker's reserved Compose/OCI labels are unchanged.
- RAG basename: `dame-curie-rag.db`, shared consistently by bot/API inside the identity-owned data root. No live database rename/copy is implied.
- Shell home: `/home/dame-curie`. Shared read-only checkout convention: `/opt/dame-curie`; host wrappers require its `.venv/bin/python`.
- Startup snapshot socket: host `/srv/dame-curie-checkout/<full-instance>/snapshot.sock`, exposed inside the bot at `/run/dame-curie-checkout/snapshot.sock`. The service-user socket boundary and checkout-owner reader remain distinct roles.
- Neutral filenames and paths (`bot.env`, `.env`, `.venv`, `/config`, `/state/data`, `/api`, `/bot`) need no cosmetic replacement. Their purpose, ownership and configuration remain explicit.
- Root's short URL component `dame` is intentional. It does not authorize sharing V1's live publishing destination. Publisher state belongs under the identity's private root; the remote example is deliberately synthetic and distinct.

Runtime-producing defaults, consumers, labels, path guards and templates were aligned together; no legacy-name compatibility alias was added to reconnect V2 to V1. Harmless historical prose, ordinary `max()`/`max_tokens`, persona content and unrelated internal identifiers are not a global replacement target. No new real domain, mailbox or Discord identity was inferred.

These conventions are implemented in source, not provisioned on the host. Consult `STATUS.md` for review limits and outstanding pruning/acceptance work. Do not run V2 without a separate compatible assignment.
