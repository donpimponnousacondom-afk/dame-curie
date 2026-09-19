# dame-curie architecture and naming boundary

This is a source map and target isolation contract, not proof of a deployed V2 system. V1 already works; V2 is intended to remove accumulated workarounds before adding features.

## Components in this checkout

| Component | Source entry points | Responsibility |
| --- | --- | --- |
| Discord conversation and providers | `bot.py`, `providers.py`, `message_pipeline.py` | Transport, conversation/tool orchestration, queueing and provider requests |
| Memory and prompts | `rag_memory.py`, `knowledge_graph.py`, `prompt_storage.py`, `control_defaults.py` | Persistent memory, graph data, persona/server prompts and controls |
| Tools and generated sites | `bot_tools.py`, `tool_registry.py`, `tool_schemas.py`, `site_server.py`, `docker_runtime.py` | Tool dispatch, generated-site runtime and ownership/resource paths |
| API and web routing | `api/`, `docker/Caddyfile`, `compose.yaml` | Administration and routing; a complete V2 dashboard/image build has not been established |
| Operations and publishing | `scripts/instance.py`, `docker/`, `scripts/publisher/` | Existing lifecycle/backup/provisioning source and independent site publishing; not safe discovery commands |
| Additional inherited capabilities | autonomy/REM, email, voice and plugins | Feature-pruning decisions remain root's; presence is not a request to extend them |

## Intended identity isolation

One Linux service account and private rootless Docker engine per bot identity. The planned first V2 account is **dame-curie**; protected V1 uses **maxwell-curie**. Additional identities must have explicitly assigned separate accounts/engines rather than a second bot writer in the first identity's state.

Each identity owns its configuration, credentials, prompts, databases, generated sites, shell workspace, model storage and publisher state. Explicitly separate host mounts, exposed ports and remote publisher destinations. Future V2 identities may deliberately use the same immutable source/image artifact in their separate engines; this does not share their mutable bot state or authorize reusing the deployed V1 image namespace. V2's `dame-curie-*` repositories remain distinct from protected V1's `maxwell-*` repositories. Record image content IDs/digests separately from mutable tags. No image was built, copied, retagged or provisioned by this documentation decision.

The existing source contains ownership/socket/private-root checks. That is evidence of design, not V2 runtime acceptance. The observed running-only V1 inventory does not cover stopped objects, all volumes/networks, other engines or remote resources.

## Target naming rules

- Canonical project/files/URLs/resource namespace: `dame-curie`.
- Planned initial service account: `dame-curie`; proposed initial full instance/Compose slug: `dame-curie`, not a duplicated prefix.
- Shell/Python configuration identifiers: `DAME_CURIE_*`. Hyphenated shell/Python variable names are not the spelling to use.
- Target app/web image repositories: `dame-curie-app`, `dame-curie-web`; selectors must remain separate from protected `maxwell-*` images.
- Target custom ownership label namespace: `dame-curie.*`; keep Docker's reserved Compose/OCI labels unchanged.
- Target RAG basename: `dame-curie-rag.db`, shared consistently by bot/API inside the identity-owned data root. No live database rename/copy is implied.
- Neutral filenames and paths (`bot.env`, `.env`, `.venv`, `/config`, `/state/data`, `/api`, `/bot`) need no cosmetic replacement. Their purpose, ownership and configuration must remain explicit.
- Root's short URL component `dame` is intentional. It does not authorize sharing V1's live publishing destination.

Runtime-producing defaults, consumers, labels, path guards and templates must change coherently; no legacy-name compatibility alias may silently reconnect V2 to V1. Harmless historical prose, ordinary `max()`/`max_tokens`, persona content and unrelated identifiers are not a global replacement target. No new real domain, mailbox or Discord identity is inferred from the project rename.

These are target conventions. Consult `STATUS.md` for implementation state; until the source cut-off and isolated acceptance are complete, do not run V2.
