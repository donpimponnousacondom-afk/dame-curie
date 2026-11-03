# dame-curie

Dame Curie is a Discord bot in Python 3.14. She runs as account `dame-curie` in a private rootless Docker engine. Generation uses a configured OpenAI-compatible endpoint. Memory embeddings use a configured external embedding endpoint. An independent publisher mirrors locally authored sites to a remote host.

## Documentation

| Read | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Rules for every agent and human: identities, hard rules, writing, code, change flow |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Runbook: identity, deploy, rollback, smoke tests, embeddings, backups, diagnostics |
| [docs/REVIEW.md](docs/REVIEW.md) | Pull request and review protocol |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Environments, quality gate, isolated QA, dead-code audit |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Source contract: components, budgets, commands |
| [docs/STATUS.md](docs/STATUS.md) | Behaviour change log per merged PR, and known open items |
| [docs/PUBLISHING.md](docs/PUBLISHING.md) | Site authoring and the publisher |
| [docs/IMAGE_GENERATION.md](docs/IMAGE_GENERATION.md) | Image generation and editing |
| [docs/LONGPROMPT.md](docs/LONGPROMPT.md) | Server prompt commands and limits |
| [docs/PROVIDER_RELOAD.md](docs/PROVIDER_RELOAD.md) | Provider settings reload at idle |
| [docs/HISTORY.md](docs/HISTORY.md) | Dated milestones and recovery references |
| [TODO.md](TODO.md) | Open items |
| [SECURITY.md](SECURITY.md) | Security boundary |

Agent skills are in `.agents/skills/<name>/SKILL.md`.
