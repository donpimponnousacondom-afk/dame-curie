# dame-curie security boundary

Report security concerns privately to the maintainer before public disclosure. Do not include credentials, private messages, raw runtime logs or production configuration in a public report.

- Keep real tokens, `.env`/`bot.env`, databases and private configuration outside images, source commits, public dashboards and generated-site origins.
- A new Docker user/engine does not isolate a deliberately shared host mount, credential, database, port or remote publisher destination. Review those boundaries separately.
- Do not expose administrative API/data routes or weaken authentication to make an environment appear healthy. Generated public sites must not inherit access to administrative storage.
- Read-only Docker investigation uses only specifically authorized scalar metadata. No environment, command, mount or label dumps; no container exec or runtime logs under an inventory grant.
- Rotate exposed credentials through the authorized operator workflow; do not rotate, copy or inspect them as part of this source cut-off.
- Existing production is hands-off except for an explicit, bounded operator assignment. A commit or backup is not deployment authorization.

## Model-directed actions

**Source contract under audit remediation, not a claim about installed protection.** The actor/environment changes below are not yet committed, built or deployed as a candidate; consult [current status](docs/STATUS.md) for exact accepted source and runtime evidence. The last recorded temporary image predates these mitigations.

Shell is restricted to bot admins and the existing shell-user allowlist. Persistent personality/server-prompt rewrites are admin-only. The same actor policy applies to catalog visibility, dispatcher aliases and direct tool execution. A background or synthetic turn must retain the requesting permission actor, never substitute the bot poster.

Shell starts without Bash startup files and with a fixed minimal environment, not the bot's inherited credentials. This is defense in depth, **not secret isolation**: the process has the bot's UID and can still read bot-readable configuration/state and make network requests. Authorizing shell means accepting that access and the remaining risk of prompt injection in an authorized user's turn. Reading external content does not activate a confirmation lock; do not claim the removed taint gate exists. Strong secret isolation would require a separately authorized execution architecture.

See [operations](docs/OPERATIONS.md) and the [agent contract](AGENTS.md) before any investigation.
