# dame-curie

Discord-only V2, Python **3.14**. Protected V1 remains separate.

**Round-two source corrections are committed and passed isolated QA plus independent review.** That is not a deployment claim. [Status](docs/STATUS.md) records the exact source, artifact and running-instance evidence; [TODO](TODO.md) contains the remaining work. Canonical/V1 activation and publisher/remote changes remain held. Root delegated the temporary-Dirac release decision to the coordinator, not to every future agent.

## Current documentation

| Read | Purpose |
| --- | --- |
| [Status](docs/STATUS.md) | Source/QA milestones, actual runtime and release disposition |
| [Operations](docs/OPERATIONS.md) | Account/engine verification, temporary lifecycle, smoke and rollback |
| [Architecture](docs/ARCHITECTURE.md) | Components, tool/prompt/turn contracts and trust limits |
| [Development](docs/DEVELOPMENT.md) | Python, dependency and isolated-validation boundaries |
| [Images](docs/IMAGE_GENERATION.md) | Native generation/editing, configuration and delivery |
| [Server prompts](docs/LONGPROMPT.md) | Commands, byte limits, omission and exact export |
| [Provider reload](docs/PROVIDER_RELOAD.md) | Idle-boundary settings changes versus image identity |
| [Publishing](docs/PUBLISHING.md) | Existing independent publisher; no operating grant |
| [Dead-code review](docs/DEAD_CODE.md) | Report-only static analysis, not deletion authority |
| [Agent contract](AGENTS.md) / [Security](SECURITY.md) | Permissions, collaboration and private-state boundaries |

## Source contract

- Compose retains `bot`, `ollama`, `ollama-pull`, with no published ports. Dashboard/API/web hosting, nested shell, X/Telegram and companion/GF are removed. No replacement server or PM2 deployment.
- Shell runs as the bot UID inside its outer container. `/home/dame-curie` points to `/state/shell`; this is **not** isolation from bot-readable secrets or bot-writable controls. Admin/allowlist authority and this trust boundary are explicit in Architecture.
- Preserve Discord administration, autonomy, games/plugins, voice/media, inbox and functional RAG/REM/graph memory. Local authoring, image archives/sidecars and the independent publisher remain; the model does not administer remote publication.
- Generation uses explicitly configured OpenAI-compatible `OPENAI_*` settings, not an assumed vendor account. Local Ollama provides embeddings; ordinary shared embedding compute with separate profile storage is permitted.
- Default commands use **`!`**; an instance may configure `?`. Canonical staging defaults to validated **no-op** `up`/`start`/`restart`, not activation. Lifecycle/build scripts are actuators, not discovery commands.

The root-authorized `legacy/` archive removal and phase-note retirement do not authorize runtime changes. Surviving contracts live above; immutable recovery references and retained audit evidence live in Status and the closure ledger. Do not restore old instructions or inspect another checkout to fill gaps.
