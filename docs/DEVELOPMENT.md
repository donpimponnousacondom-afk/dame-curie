# Development and isolated validation

## Python and environments

**Python3.14 is mandatory.** Never replace system Python, install project packages into its package tree or use a system-package bypass. Select the interpreter explicitly before creating an environment. `.venv/` is an interpreter/dependency environment; `.env`, `bot.env` and `deploy.env` are configuration files and may contain secrets.

The app recipe selects Python3.14.4. Shell uses that app environment inside the outer container, not host Python or a nested image. `/opt/dame-curie/.venv` is a separate trusted **operator-only** environment, not the application's installation. A host project venv must also use an explicitly selected3.14 interpreter. No project uv workflow has been verified; do not assume one exists or search unrelated environments.

Under an explicit environment-creation assignment, for a new intended checkout environment:

```sh
python3.14 -m venv .venv
.venv/bin/python --version
```

Do not use `--clear`, `--system-site-packages`, an unrelated existing environment or generic `python3`. Invoke the selected interpreter/pip explicitly. Installation needs a compatible grant and reviewed pinned requirements; do not relax pins, upgrade packages automatically or install full application/dev requirements for a report-only tool task.

## Source review versus execution

A source-only assignment permits **no application import, test collection/execution, build or runtime probe**. Loading a skill does not expand that authority. Apply `implement-tyranny` to authorized new Python and `implement-sanity` to the actual diff, not as a whole-repository formatting/refactoring campaign. Preserve valid3.14 syntax, strict pins and real typing; avoid unrequested helpers, blanket catches, guards and logging. Type annotations do not validate external input.

**C09 is an accepted deferral:** `config.py` retains import-time dotenv loading with `override=True`. No lazy-loading/import-isolation redesign is pending. A synthetic `DAME_CURIE_ENV_FILE` redirect alone is **not** private-read isolation. Effective structural configuration may override injected deployment values and must be reconciled only under an explicit private/runtime grant.

Root's closure assignment permits the coordinator to run the established frozen credential-free QA image with **synthetic configuration/state, no private mounts, no real Discord credentials and network-none**. Other source workers have no execution grant. Loopback sockets and subprocesses used by relay tests remain inside that container. No host/live-environment suite. Exact image, commands, source trees, failures and counts belong in the [validation ledger](../audit/20260924T210402Z-audit/validation.md), not this durable policy.

**No new test files/functions:** adapt existing cases/parameterization. Never run the historical dotenv/live-provider version of `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas`; only its inspected synthetic SSE/fake-channel replacement is admitted to isolated QA. `tests/test_streaming.py` and `tests/test_streaming_primary.py` remain excluded. Do not sum overlapping passing counts or call the safe selection unrestricted coverage.

Guarded constructor probes may import the **actual candidate image** only inside the same no-network/no-private-state envelope. Source QA, copied-input/provenance checks, image construction, Discord identity, model delivery and broader feature acceptance are distinct gates. A baked source label alone does not prove image contents; a successful constructor is not a login or live-feature test.

## Independent PR review and monitoring

Every implementation PR uses the project-local [PR babysitter skill](../.agents/skills/council-pr-babysitter/SKILL.md): independent `gpt-6-luna` at `max` and `gpt-6.1-sol` at `high`, through verified DSH routes. Give both the same pinned base/head, scope and measured evidence; keep initial findings independent. The coordinator validates findings, fixes routine defects, owns commits/publication and requests both final-head reviews. Reviewers do not edit the shared checkout or gain private/runtime authority.

Read complete current-head CI status, including distinct push and pull-request runs, and unresolved review threads before readiness. Publish the authorized SHA-bound digest; do not present a comment as independent GitHub approval or claim a completed agent still watches. Without a published PR, record that only local review occurred. Preserve push/merge and security-policy boundaries; bring root only an actual need for human intervention or a reserved decision.

## Builds and dependency limits

`scripts/build_for_human.sh` is an app-image build actuator using a committed Git archive and selected V2 private engine. It does not deploy, but still requires build/runtime authority. `install.sh` installs checkout dependencies/configuration; it neither provisions nor activates the bot and supplies no host-Python/PM2 deployment permission. Do not execute either for discovery or `--help` during source-only work.

The historical app `pip check` reported `discord-ext-voice-recv==0.5.2a179` declaring `discord-py` while the lock intentionally supplies `discord.py-self==2.1.0` in the shared `discord` namespace. Do not install the competing distribution or weaken pins to silence that metadata conflict. Constructor/chat smoke acceptance does not resolve the voice compatibility or packaging caveat; voice remains unverified. Retired site/web-image checks do not validate the current topology.

The Vulture report-only workflow, source selection, exit codes and immutable baseline recovery are in [DEAD_CODE.md](DEAD_CODE.md). Findings are not deletion authority. Runtime/account/private boundaries remain in [OPERATIONS.md](OPERATIONS.md) and [AGENTS.md](../AGENTS.md).
