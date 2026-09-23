# dame-curie development environment

## Interpreter boundary

**Python 3.14 is mandatory.** The host's system interpreter is unrelated to the project's required version and must not be replaced. Do not install project packages into the system Python tree or use a system-package bypass flag.

The redesigned app image declares Python3.14.4; separate shell/site/web images are no longer part of the approved topology. Shell uses the app environment inside the outer bot container, not a host interpreter or nested container. The earlier provisioned `/opt/dame-curie/.venv` is an operator-only Python3.14.4 environment; app dependencies live in the image. Historical shell/site checks do not establish redesign acceptance. A host-side project interpreter must also be 3.14 and isolated through a venv or an explicitly configured uv-managed environment. A venv created from the host's default Python does not automatically become 3.14.

| Name | Meaning |
| --- | --- |
| `.venv/` | Isolated interpreter and project dependencies; not runtime configuration |
| `uv` | Optional interpreter/environment/package manager; its interpreter selection must be explicit |
| `.env` | Configuration file name used by some source paths; potentially secret, not a Python environment |
| `bot.env` | Neutral per-identity runtime configuration filename; potentially secret |
| `deploy.env` | Deployment-selection configuration; not a virtual environment or blanket startup permission |

## Chosen minimal local workflow

Use an explicitly selected Python 3.14 venv. The source cut-off verified Python 3.14.4 and standard-library `venv --help` without creating an environment. Root's later static-audit assignment created a fresh `.venv` with Vulture 2.16 (besides bootstrap pip). The subsequently authorized provisioning assignment added `python-dotenv==1.2.3`, matching the image lock, for secret-safe configuration transfer. This is a tool environment, not application readiness. `uv` was not found on PATH or exercised; do not search unrelated environments to recover it.

When environment creation is explicitly in scope, from this checkout and only if `.venv` is a new intended environment:

```sh
python3.14 -m venv .venv
.venv/bin/python --version
```

Do not use `--clear`, `--system-site-packages`, an unrelated existing environment or generic `python3 -m venv`. Verify the selected interpreter is 3.14 before project work. Invoke `.venv/bin/python` and `.venv/bin/python -m pip` explicitly rather than relying on an activated shell or global pip. Dependency installation needs a separate compatible assignment and reviewed requirements/pins; the Vulture-only grant does not authorize installing the application's or entire development requirements. Do not weaken pins or automatically upgrade dependencies.

If root later chooses uv, verify its local availability and document the exact 3.14 selection/environment path before use. This page does not pretend a second unverified workflow is configured.

## Historical image evidence and dependency caveat

The earlier staged app/web release used code revision `b2f5380`; it is **not** the Discord-only redesign release. Historical site-runtime's offline `pip check` passed, but that image is now retired from the source design. The earlier app check did **not** pass: `discord-ext-voice-recv==0.5.2a179` declares `discord-py`, while the lock intentionally installs `discord.py-self==2.1.0` into the shared `discord` namespace. The installer also explicitly reinstalls the self-fork after optional extras. Do not install the competing distribution or relax pins to silence metadata checking. Voice compatibility and a clean/explicitly resolved packaging contract remain prerequisites for future Discord activation. Earlier API/primary-inference checks do not resolve that caveat or validate the redesign; no builds, application imports, provider/Discord probes or runtime re-observation occurred in this documentation round.

The redesigned `scripts/build_for_human.sh` builds only the app image from a Git archive in the explicitly selected V2 private engine; it does not deploy or start it. It remains a build/runtime actuator requiring separate authorization, not a source check. `install.sh` installs checkout dependencies/configuration only; it does not provision/activate the bot and supplies no host-Python or PM2 deployment recipe. Do not execute either script, even for discovery, during a source-only assignment.

## Source and review

Apply `implement-tyranny` to authorized new Python, not as a whole-repository formatting campaign. Its current template targets are 3.14; obsolete hook-version examples were removed rather than replaced with invented pins. Use `implement-sanity` on the actual diff: real defects, unnecessary scaffolding, hidden complexity and typing—not a mandate to split every legacy file over a line-count threshold. Type hints alone do not validate external input.

## Static dead-code audit

Root authorized a first report-only Vulture pass after the source mapping. Use [the static-audit workflow](DEAD_CODE.md) for exact source selection, tool installation and confidence/exit-code interpretation. Initial results are in `../phase-II_v2/DEAD_CODE_PASS.md`. This AST-only exception does not permit application/test imports, full dependency installation or runtime checks, and does not authorize deleting reported code.

## Execution is a separate boundary

Do not import the application, run tests or even collect tests during source-only work. `config.py` loads dotenv at import time with `override=True`; the named live-provider test in `AGENTS.md` directly parses `.env` independently. A dummy environment-variable setting is not sufficient proof of isolation. During separately authorized private reconciliation, the coordinator must audit structural settings that could override Compose (identity, container mode, storage roots and retired socket settings); this documentation task grants no private-file access.

Future validation requires a separately agreed source-only environment, synthetic configuration/state, disposable databases, no private mounts or real Discord token, and no live provider/message/publisher side effects. This document itself authorizes no new tests, especially tests memorializing absence of removed features. Static source review is not runtime or image-build acceptance.

When focused tests are separately authorized, redirect `DAME_CURIE_ENV_FILE` before collection and exclude `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas`: it independently reads `.env` and may call a real provider. Redirection alone is not isolation; use the approved credential-free container with no private mounts or external networking. Relay hardening tests require loopback sockets and subprocess spawning inside that container, not host/service access.
