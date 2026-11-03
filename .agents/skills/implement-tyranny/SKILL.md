---
name: implement-tyranny
description: Rules and the enforced quality gate for new or rewritten Python in dame-curie. Use when writing Python, before a commit, or when a lint or format check fails.
---

# Implement Tyranny - Python rules for dame-curie

Python 3.14 is mandatory. The project standard is `[tool.ruff]` in `pyproject.toml`. This skill does not change that configuration and does not authorize application imports, test runs or runtime access.

## The enforced gate

`scripts/lint.sh` runs in the commit hook (`scripts/lint.sh --staged`) and in CI (`.github/workflows/quality.yml`). It needs `ruff==0.17.3` from `requirements-dev.txt`; a missing or different version is an error that names the cause.

| Check | Scope | Result |
| --- | --- | --- |
| Dash check (`scripts/check_dashes.sh`) | Every tracked file except `audit/` | Em or en dash refuses the commit |
| `ruff check` | Whole tree in CI; staged `.py` files in the hook (their working-tree copies) | Any finding refuses the commit |
| `ruff format --check` | Added `.py` files only | An unformatted new file refuses the commit |

Legacy files are never reformatted by the gate. Do not run `ruff format` or `ruff check --fix` on files you did not change. Mypy is not run and has no configuration. Vulture is report-only; its workflow is in `docs/DEVELOPMENT.md`.

## Rules for new Python

1. Full type annotations on every function you add: parameters and return.
2. A docstring on every function, including private helpers. The docstring of a private helper states why it exists.
3. No helper under five lines that only hides logic. Write the logic inline.
4. No `except Exception` and no bare `except`. Catch the exception you handle, and handle it visibly. An error names what failed and why.
5. No `# type: ignore` and no `# noqa` without a reason on the same line.
6. No commented-out code. No `print()` for logging.
7. No new guard, retry, fallback or logging that the task did not ask for.
8. No fixed time zone, offset or `ZoneInfo` literal.
9. Use the process local time zone, the configured values and the existing modules. Do not grow `bot.py` or `bot_tools.py` for a new subsystem; put it in its own module.
10. Keep strict dependency pins. Do not add a package without a pin and an entry in the matching lock file.

## Before you commit

1. `scripts/lint.sh --staged` passes.
2. Every behaviour change has a regression test that fails on the old code. Run tests only with `scripts/qa.sh`.
3. Load `implement-sanity` and review your own diff with its checklist.
