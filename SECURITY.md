# dame-curie security boundary

Report security concerns privately to the maintainer before public disclosure. Do not include credentials, private messages, raw runtime logs or production configuration in a public report.

- Keep real tokens, `.env`, `bot.env`, databases and private configuration outside images, source commits and generated-site origins.
- A separate Docker user or engine does not isolate a shared host mount, credential, database, port or remote publisher destination. Review those boundaries separately.
- Do not expose administrative routes or weaken authentication to make an environment appear healthy. Generated public sites must not inherit access to administrative storage.
- Rotate exposed credentials through the operator workflow. Do not rotate, copy or inspect them as part of a source task.
- Production is hands-off except for an explicit, bounded operator assignment. A commit or a backup is not deployment authorization.

## Model-directed actions

Shell is restricted to bot admins and the shell-user allowlist. Persistent personality and server-prompt rewrites are admin-only. The same actor policy applies to catalog visibility, dispatcher aliases and direct tool execution. A background or synthetic turn keeps the requesting permission actor; it never substitutes the bot poster.

Shell starts without Bash startup files and with a fixed minimal environment. This is defense in depth, **not secret isolation**: the process has the bot's UID, so it can read bot-readable configuration and state and make network requests. Where control files are writable by that UID, the shell allowlist is admin-equivalent. Reading external content does not activate a confirmation lock; root confirmed on 3 October 2026 that the removed taint gate stays removed. Strong secret isolation needs a separately authorized execution architecture.

See [docs/OPERATIONS.md](docs/OPERATIONS.md) and [AGENTS.md](AGENTS.md) before any investigation.
