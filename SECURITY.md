# dame-curie security boundary

Report security concerns privately to the maintainer before public disclosure. Do not include credentials, private messages, raw runtime logs or production configuration in a public report.

- Keep real tokens, `.env`/`bot.env`, databases and private configuration outside images, source commits, public dashboards and generated-site origins.
- A new Docker user/engine does not isolate a deliberately shared host mount, credential, database, port or remote publisher destination. Review those boundaries separately.
- Do not expose administrative API/data routes or weaken authentication to make an environment appear healthy. Generated public sites must not inherit access to administrative storage.
- Read-only Docker investigation uses only specifically authorized scalar metadata. No environment, command, mount or label dumps; no container exec or runtime logs under an inventory grant.
- Rotate exposed credentials through the authorized operator workflow; do not rotate, copy or inspect them as part of this source cut-off.
- Existing production is hands-off except for an explicit, bounded operator assignment. A commit or backup is not deployment authorization.

See [operations](docs/OPERATIONS.md) and the [agent contract](AGENTS.md) before any investigation.
