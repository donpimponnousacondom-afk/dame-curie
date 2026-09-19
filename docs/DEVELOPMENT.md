# dame-curie development environment

## Interpreter boundary

**Python 3.14 is mandatory.** The host's system interpreter is unrelated to the project's required version and must not be replaced. Do not install project packages into the system Python tree or use a system-package bypass flag.

Application/site images currently declare Python 3.14.4. The inherited shell image installs distro `python3`; its actual interpreter version has not been verified and is a future acceptance check, not proof of compliance. A host-side project interpreter must also be 3.14 and isolated through a venv or an explicitly configured uv-managed environment. A venv created from the host's default Python does not automatically become 3.14.

| Name | Meaning |
| --- | --- |
| `.venv/` | Isolated interpreter and project dependencies; not runtime configuration |
| `uv` | Optional interpreter/environment/package manager; its interpreter selection must be explicit |
| `.env` | Configuration file name used by some source paths; potentially secret, not a Python environment |
| `bot.env` | Neutral per-identity runtime configuration filename; potentially secret |
| `deploy.env` | Deployment-selection configuration; not a virtual environment or blanket startup permission |

## Chosen minimal local workflow

Use an explicitly selected Python 3.14 venv. This session verified Python 3.14.4 and standard-library `venv --help`, without creating an environment. `uv` was not found on this session PATH; do not claim it was installed or exercised, and do not search unrelated environments to recover it.

When environment creation is explicitly in scope, from this checkout and only if `.venv` is a new intended environment:

```sh
python3.14 -m venv .venv
.venv/bin/python --version
```

Do not use `--clear`, `--system-site-packages`, an unrelated existing environment or generic `python3 -m venv`. Verify the selected interpreter is 3.14 before project work. Invoke `.venv/bin/python` and `.venv/bin/python -m pip` explicitly rather than relying on an activated shell or global pip. Dependency installation is a separate step, uses reviewed requirements/pins, and is not performed by this documentation task. Do not weaken pins or automatically upgrade dependencies.

If root later chooses uv, verify its local availability and document the exact 3.14 selection/environment path before use. This page does not pretend a second unverified workflow is configured.

## Source and review

Apply `implement-tyranny` to authorized new Python, not as a whole-repository formatting campaign. Its current template targets are 3.14; obsolete hook-version examples were removed rather than replaced with invented pins. Use `implement-sanity` on the actual diff: real defects, unnecessary scaffolding, hidden complexity and typing—not a mandate to split every legacy file over a line-count threshold. Type hints alone do not validate external input.

## Execution is a separate boundary

Do not import the application, run tests or even collect tests during the current cut-off. `config.py` loads dotenv at import time; the named live-provider test in `AGENTS.md` directly parses `.env` independently. A dummy environment-variable setting is not sufficient proof of isolation.

Future validation requires a separately agreed source-only environment, synthetic configuration/state, disposable databases, no private mounts or real Discord token, and no live provider/message/publisher side effects. No new tests are authorized, especially tests memorializing absence of removed features. Static source review is not runtime or image-build acceptance.
