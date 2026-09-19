# dame-curie

A working Discord bot undergoing a V2 foundation refactor: prune inherited complexity, separate operational identity, and prepare for new features. The existing V1 deployment remains protected and running.

**This checkout is not ready for V2 deployment.** The operational naming cut-off is implemented and source-reviewed; feature pruning and isolated acceptance remain. Inherited lifecycle helpers are not discovery commands. Do not run an installer, application or test suite from old instructions.

## Current documentation

- [Status](docs/STATUS.md): completed source cut-off, pending pruning and validation limits.
- [Operations](docs/OPERATIONS.md): V1/V2 accounts, rootless engines and safe read-only investigation.
- [Development](docs/DEVELOPMENT.md): Python 3.14 and isolated venv/uv use; configuration is not an interpreter environment.
- [Architecture](docs/ARCHITECTURE.md): component map and isolation intent, not unearned acceptance claims.
- [Agent contract](AGENTS.md): current permissions, naming and collaboration rules.
- [Security](SECURITY.md): private-state and disclosure boundaries.

Project name: **dame-curie**. Planned V2 service user: **dame-curie**, with its own rootless Docker engine. The intentional short URL component `dame` is retained. Project Python is **3.14**; the host's system Python is not the project environment.

Inherited documentation is quarantined under `legacy/`; it is not an installation guide or current authority. Temporary cut-off evidence lives in `phase-II_v2/`. No upstream/other-project lookup is needed to work here.
