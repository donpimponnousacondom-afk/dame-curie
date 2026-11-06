# dame-curie - agent contract

Skills live in `.agents/skills/<name>/SKILL.md`. Any harness reads them there. Root's current instruction overrides this file.

## Read first

- [README.md](README.md) is the documentation index.
- Read [docs/OPERATIONS.md](docs/OPERATIONS.md) before any runtime action.
- Read [docs/REVIEW.md](docs/REVIEW.md) before any pull request.
- Dated decisions and recovery references are in [docs/HISTORY.md](docs/HISTORY.md).
- Do not inspect another checkout or an upstream project to fill gaps.

## Identities and protected resources

- V2 is account `dame-curie` with its private rootless Docker engine. Root calls the live V2 seat "throne-v2".
- V1 is account `maxwell-curie`. Never start V1, its shell or its stack, also not for rollback. V1 is out of scope.
- Discord IDs: Dame Curie `1545541390392369165`; root `1482143139828596916`; test channel `1566164090039304285` in server `1545673830960340992`. Do not infer trust from other IDs.
- The independent publisher (`scripts/publisher/`) mirrors local sites outward. The model never administers remote publication.
- Removed V1 features stay removed: dashboard, API, web hosting, nested shell, X, Telegram, companion, SMTP/IMAP tools and the web-read confirmation gate. Do not restore one to answer a review finding.
- REM (`rem.py`) is off. Root replaces it later. Do not test, flag or optimize REM paths.

## Hard rules from root

- **Configuration is sacred.** Operator configuration and explicit operator commands are the only authority for AI request parameters. Never add, strip, normalize or override generation, reasoning or routing parameters in any request path: foreground, background, retries, fallbacks, jobs, images or embeddings. A parameter absent from configuration stays absent on the wire. Never relax `provider.only` or `allow_fallbacks`. Test the outgoing JSON at the HTTP boundary.
- **Failures stay visible.** Do not strip, filter or rewrite model output to hide a symptom. Never add a regex that removes `<think>` or similar blocks. An error stops the operation and names what failed and why. Do not continue in a degraded mode. Do not replace an error with a warning. Code that hides a failure is removed, with a regression test.
- **Errors are visible to the model.** When the harness fails while her prompt is built, add one line with the exact cause to her prompt or the tool result. Log it too. For an optional setting whose default is the safe state, use the default and state the cause in her prompt.
- **No word triggers.** Never add keyword or regex detection on model output or user input that changes behaviour. The model declares intent with an argument or a tool. Flag existing word triggers when you find them.
- **Container time zone.** Use the process local zone, for example `datetime.now().astimezone()`. Never write a fixed offset, a zone name or a `ZoneInfo` literal in code.
- **Security policy belongs to root.** Ask before you add, widen, remove or replace a content filter, credential detection, redaction, publication refusal, path exclusion or access restriction. The publisher content-based credential filter stays removed.
- **Profiles.** A blank `AUX_*` or `AUTONOMY_*` key falls back to the main profile.

## Naming and configuration

- Use `dame-curie` externally and `DAME_CURIE_*` for environment names. Root's short URL segment `dame` is intentional.
- Generation uses the configured OpenAI-compatible `OPENAI_*` settings, not an assumed OpenAI account. No `OLLAMA_*` aliases exist.
- Preserve the difference between an unset and an explicitly blank setting. Preserve coupled selectors, credentials and storage consumers.
- No compatibility fallback may reconnect V2 to V1.
- Do not change the persona or model, invent real endpoints, or rename `max()` or `max_tokens` as a naming shortcut.
- Default commands use `!`. Help text uses the prefix that the instance configures.

## Writing

- Write comments, documentation, commit messages and reports in ASD-STE100 Simplified Technical English. One statement per sentence. At most 20 words per instruction, 25 per description.
- A check passed or it failed. Report what you measured. Otherwise write "not measured".
- No em dashes or en dashes. `scripts/lint.sh` refuses them in the commit hook and in CI. `audit/` is excluded.
- Dates in prose are day-first: "3 October 2026". ISO dates are allowed in commit messages and logs.
- Enable the hook once per clone: `git config core.hooksPath .githooks`.

## Code and tests

- Python 3.14 only. Never replace system Python or install into its package tree. Keep strict pins.
- New tests are allowed and wanted. Each fix gets a regression test that fails on the old code.
- Quality gate: `scripts/lint.sh` runs the dash check, `ruff check` on the whole tree and `ruff format --check` on added files. Do not reformat untouched code. Details: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
- Tests run only in the isolated container through `scripts/qa.sh`. No host application import. No live suite. `tests/test_streaming.py` and `tests/test_streaming_primary.py` stay excluded.
- Load `implement-tyranny` for new Python and `implement-sanity` for the diff review. No unrequested helpers, broad `except`, type escapes, guards or logging.

## Change flow

- Every change is a pull request to `main` from a `pr/*`, `hotfix/*` or `dev/*` branch. One active branch at a time.
- Never push to `main`. Never force-push. Merge only after all three council members say READY on the current head and CI is green. Protocol: [docs/REVIEW.md](docs/REVIEW.md).
- Deploy after merge with `scripts/deploy.sh`, inside GNU Screen session `dame_curie`, window `throne-ops`. Runbook: [docs/OPERATIONS.md](docs/OPERATIONS.md).
- Delete your test artefacts after a live test. Leave no large backups on the host; see the backup section of the runbook.

## Boundaries for delegated agents

- A source or documentation task permits inspection only: no application import, test run, build, lifecycle command, migration, login or deletion. Do not run lifecycle scripts for discovery or `--help`.
- Do not read production or backup files, real environment files, databases, raw logs, credentials or process environments without an explicit grant. Never dump inspect, environment or label collections.
- Reviewers are read-only. They do not edit the shared checkout.
- Delegated agents work locally: no fetch, push, PR or remote research unless the task says so. Do not amend others' history or prune refs, worktrees or caches.
- Do not stage, edit or mention untracked material that is not yours, such as root's `reports/`.
