# dame-curie architecture and naming boundary

This describes the approved Discord-only source contract in `../phase-II_v2/REDESIGN_PLAN.md`, using the implementation lanes under review. It is not proof that the deployed V2 system matches it. Integration status belongs in `../phase-II_v2/REDESIGN_PROGRESS.md`; runtime has not been re-observed in this documentation round. V1 remains protected.

## Approved components

| Component | Source entry points | Responsibility |
| --- | --- | --- |
| Discord conversation and providers | `bot.py`, `providers.py`, `message_pipeline.py` | The single Dame Curie transport/identity, conversation/tool orchestration, queueing and outbound provider requests |
| Memory and prompts | `rag_memory.py`, `knowledge_graph.py`, `prompt_storage.py`, `control_defaults.py` | Functional RAG/REM/graph/context memory, persona/server prompts and controls |
| Tools and local authoring | `bot_tools.py`, `tool_registry.py`, `tool_schemas.py`, `docker_runtime.py` | Tool dispatch, direct-container shell, file/media storage and attachment paths; no site server/tools |
| Background jobs | `jobs.py`, `job_routing.py` | Detached jobs with trusted profile/model selection and canonical personality/server prompts |
| Deployment | `compose.yaml`, `docker/app.Dockerfile`, `scripts/instance.py` | Only `bot`, `ollama`, `ollama-pull`; no published ports; staged startup is a validated no-op |
| Independent publishing | `scripts/publisher/` | Protected external file mirroring, not a model-controlled deployment API |
| Retained capabilities | Discord administration, autonomy/REM, games/plugins, voice/media, inbox | Preserve independent permissions and redaction as well as functional behavior |

Dashboard/API/OAuth/Caddy/web image, local website/KV/FastAPI/uvicorn servers and six `site_*` tools, nested shell infrastructure, X/Telegram and companion/GF are removed from the target design. No replacement server, PHP/Perl/CGI installation or PM2 deployment. The human CAPTCHA HTTP fallback is removed; outbound CapSolver/TwoCaptcha remain. Historical `tg:%` privacy filtering remains to exclude old private records, not to enable Telegram.

## Intended identity isolation

One Linux service account and private rootless Docker engine per bot identity. The first V2 account **dame-curie** and its separate engine were provisioned earlier (UID/GID1005 in that observation); re-resolve the account/socket before every authorized runtime operation. Protected V1 uses **maxwell-curie**. Additional identities require explicitly assigned separate accounts/engines rather than a second bot writer in the first identity's state.

Each identity owns its configuration, credentials, prompts, databases, generated files, shell workspace, model storage and publisher state. Explicitly separate host mounts and remote publisher destinations; the redesigned stack publishes no ports. Future V2 identities may deliberately use the same immutable source/image artifact in their separate engines; this does not share mutable bot state or authorize reusing the deployed V1 image namespace. V2's `dame-curie-app` repository remains distinct from protected V1's `maxwell-*` repositories. Record image content IDs/digests separately from mutable tags. No image or runtime change was performed in this documentation round.

The source contains ownership/socket/private-root checks. That is evidence of design, not V2 runtime acceptance. The observed running-only V1 inventory does not cover stopped objects, all volumes/networks, other engines or remote resources.

## Selected source conventions

- Canonical project/files/URLs/resource namespace: `dame-curie`.
- Full instance/account/Compose slug: `dame-curie`, or `dame-curie-<identity>` for a replica, up to 30 characters. Accounts and resource prefixes derive directly from that slug, without duplicating the project name.
- Private host root: `/srv/<full-instance>`. Host operator access uses the approved account's freshly resolved UID-derived rootless socket; no engine socket is mounted into the bot.
- Shell/Python configuration identifiers: `DAME_CURIE_*`. Hyphenated shell/Python variable names are not the spelling to use.
- App image repository: `dame-curie-app`; no web image. Selectors remain separate from protected `maxwell-*` images.
- Custom ownership label namespace: `dame-curie.*`; Docker's reserved Compose/OCI labels are unchanged. Retired resource labels remain relevant only to ownership-checked cleanup.
- RAG basename: `dame-curie-rag.db`, used by bot memory/graph inside the identity-owned data root. No live database rename/copy is implied.
- Shell home: `/home/dame-curie` → `/state/shell`. Operator checkout convention: `/opt/dame-curie`; host wrappers require its `.venv/bin/python`.
- No startup checkout listener/socket bridge: the `DAME_CURIE_STARTUP_GIT_SOCKET` deployment mount/environment and listener unit templates are retired. The existing local-Git fallback in `capture_running_build` reports unknown checkout metadata in an archive image without `.git`; OCI labels/build arguments are not checkout-snapshot proof.
- Neutral filenames and storage paths (`bot.env`, `.env`, `.venv`, `/config`, `/state/data`, `/state/sites`, `/state/shell`) keep their names and explicit ownership. Retained public URL helpers are not local HTTP routes or hosting.
- Root's short URL component `dame` is intentional. It does not authorize sharing V1's live publishing destination. Public examples use reserved `.invalid` destinations; V2 publisher activation/destination remains unestablished.

Runtime-producing defaults, consumers, labels, path guards and templates were aligned together; no legacy-name compatibility alias was added to reconnect V2 to V1. Harmless historical prose, ordinary `max()`/`max_tokens`, persona content and unrelated internal identifiers are not a global replacement target. No new real domain, mailbox or Discord identity was inferred.

These are source contracts, not a fresh deployment observation. Private dotenv loads with `override=True`; the coordinator must audit effective structural settings during separately authorized reconciliation rather than assuming Compose wins. Consult `STATUS.md` and the redesign progress ledger for integration/acceptance limits. No V2 execution follows from this document.

## Direct shell and publication boundaries

Shell executes `bash --noprofile --norc -c` inside the outer bot container, with explicit `cwd=/home/dame-curie`, a fixed minimal HOME/PATH/LANG/PYTHONUNBUFFERED environment, DEVNULL stdin and a new process group for timeout/cancellation cleanup. `/home/dame-curie` resolves to persistent `/state/shell`; files persist between calls, shell process state does not. Shell requires the permission actor to be a bot admin or on the shell-user allowlist; persistent prompt rewrites require a bot admin. Catalog selection, dispatcher aliases and direct execution share that policy. Existing Discord delivery/export limits remain. There is no per-turn web-read confirmation lock; authorization does not eliminate injected-instruction risk inside an authorized turn.

This shell runs as the bot's UID and can read bot-readable configuration/secrets. It is **not a separate inner security boundary**. Isolation comes from the outer service account/private rootless engine/container and explicitly V2-owned mounts. No nested Docker, Docker socket, host-root mount, host networking, host execution or V1 roots are granted. Process-group cleanup is not a general security sandbox.

Author files locally under `/state/sites`; preserve `_images` files and matching prompt sidecars and their shared attachment/image-edit consumers. The independent publisher mirrors local authored directories and archives images externally. Its implementation/configuration and `scripts/publisher/**` are immutable in this redesign. Removing HTTP serving does not remove file/URL helpers or transfer remote administration to the model. Do not start local servers, install PHP/Perl/CGI, test an invented public destination or claim a public link proves publishing succeeded.

## Background jobs and prompts

Active command prefix: **`!`**. The source contract preserves free-prose goals and adds an opt-in routing header:

```text
!bg Summarize the design tradeoffs
!bg --provider autonomy -- Summarize the design tradeoffs
!bg --provider aux --model MODEL -- Summarize the design tradeoffs
```

`!bg GOAL` keeps ordinary prose intact; it does not shell-parse the goal. The optional `--provider main|autonomy|aux` / `--model MODEL` header requires the `-- GOAL` separator. Model-facing `spawn_background` accepts `goal`, optional `context`, `provider` and `model`, never endpoint URLs, keys or headers.

Default main routing without overrides remains unchanged. Explicit routing resolves trusted **same-role** settings and requires that role's configured base URL and model; an AUX job does not silently borrow autonomy/main configuration. A model override changes only the primary request model: existing configured fallback may answer on another endpoint/model. A requested route is not proof of which provider returned the answer. Jobs share tools, permissions and delivery machinery, not a separate credential/security sandbox.

Jobs use the canonical live personality and originating server prompt, with capability instructions kept separate from identity. Goal/context are user-role content, not system policy. Authoring/personality policy tuning remains deferred. This documents the approved routing/source behavior under review, not real provider or Discord acceptance.
