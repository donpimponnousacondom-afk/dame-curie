# dame-curie development environment

## Interpreter boundary

**Python 3.14 is mandatory.** The host's system interpreter is unrelated to the project's required version and must not be replaced. Do not install project packages into the system Python tree or use a system-package bypass flag.

Application/site images declare Python3.14.4; the provisioned shell/site images each reported Python3.14.4 during network-disabled checks. The service-readable `/opt/dame-curie/.venv` is an operator-only Python3.14.4 environment; app dependencies live in the image. These checks do not establish full bot, voice, RAG or site behavior. A host-side project interpreter must also be 3.14 and isolated through a venv or an explicitly configured uv-managed environment. A venv created from the host's default Python does not automatically become 3.14.

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

## Provisioned image evidence and dependency caveat

The final app/web release is built from code revision `b2f5380`; later handoff commits are documentation-only. Site-runtime's offline `pip check` passed. The app check did **not** pass: `discord-ext-voice-recv==0.5.2a179` declares `discord-py`, while the lock intentionally installs `discord.py-self==2.1.0` into the shared `discord` namespace. The installer also explicitly reinstalls the self-fork after optional extras. Do not install the competing distribution or relax pins to silence metadata checking. Voice compatibility and a clean/explicitly resolved packaging contract remain prerequisites for future Discord activation; this round performed no Discord or voice probe. Successful API/primary-inference checks do not resolve that caveat.

## Source and review

Apply `implement-tyranny` to authorized new Python, not as a whole-repository formatting campaign. Its current template targets are 3.14; obsolete hook-version examples were removed rather than replaced with invented pins. Use `implement-sanity` on the actual diff: real defects, unnecessary scaffolding, hidden complexity and typing—not a mandate to split every legacy file over a line-count threshold. Type hints alone do not validate external input.

## Static dead-code audit

Root authorized a first report-only Vulture pass after the source mapping. Use [the static-audit workflow](DEAD_CODE.md) for exact source selection, tool installation and confidence/exit-code interpretation. Initial results are in `../phase-II_v2/DEAD_CODE_PASS.md`. This AST-only exception does not permit application/test imports, full dependency installation or runtime checks, and does not authorize deleting reported code.

## Execution is a separate boundary

Do not import the application, run tests or even collect tests during the current cut-off. `config.py` loads dotenv at import time; the named live-provider test in `AGENTS.md` directly parses `.env` independently. A dummy environment-variable setting is not sufficient proof of isolation.

Future validation requires a separately agreed source-only environment, synthetic configuration/state, disposable databases, no private mounts or real Discord token, and no live provider/message/publisher side effects. No new tests are authorized, especially tests memorializing absence of removed features. Static source review is not runtime or image-build acceptance.
