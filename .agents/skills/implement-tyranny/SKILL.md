---
name: implement-tyranny
description: Hardening Python projects with strict linting, formatting, and banning rules. Use when setting up or enforcing project quality standards — ruff config, banned patterns, type checking gates, pre-commit hooks, and structural enforcement.
---

# Implement Tyranny — Python Project Hardening

## Purpose
Enforce strict quality standards on Python projects. No mercy, no exceptions.

## What this skill covers
- Ruff configuration (rules, bans, formatting)
- Banned patterns and anti-patterns
- Type checking enforcement (mypy/pyright)
- Pre-commit hooks
- Project structure enforcement
- Import restrictions
- Naming conventions

## Scope and use

Python **3.14** is mandatory for dame-curie. Apply strict standards to authorized new or deliberately rewritten Python, not as a whole-repository conversion. Use `implement-sanity` to review the actual diff without turning untouched legacy size/style into another assignment. Host project work uses an isolated 3.14 venv or uv-managed environment, never the system package tree.

1. Establish the authorized file/change scope and the installed tool versions first.
2. Treat the configuration below as a reference, not permission to overwrite the project's existing settings, formatter width or dependency pins.
3. Change quality configuration or install hooks only when explicitly assigned. Select verified Python 3.14-capable tools with exact versions; do not invent pins or fetch tooling during a source-only task.
4. Run checks or scoped auto-fixes only when validation is authorized, and only on the assigned files. Never run a blanket `ruff check --fix` or reformat the legacy tree by loading this skill.
5. Report remaining violations and validation limits. This skill does not authorize application imports, tests, runtime access or new tests.

## Dead-code audit — report before pruning

Vulture **2.16** is the project's pinned Python 3.14-compatible static dead-code tool. Follow the repository-root `docs/DEAD_CODE.md` workflow when an audit is authorized: explicit tracked-source selection, isolated interpreter, no application imports or test execution. The first-pass evidence is in `phase-II_v2/DEAD_CODE_PASS.md`.

Start with the project configuration's 60% report and inspect the 100% view separately. Confidence is not safe-deletion proof: unused callback parameters may be required, framework/serializer consumers can be implicit, and name collisions can hide unused code. Classify findings before removing anything. Do not turn a soft report into a mandatory clean-tree gate, install hooks, generate blanket whitelists, change signatures, or add dummy references/suppressions to make counts disappear. Exit 3 means findings; syntax/input/tool failures must remain visible.

A later authorized pruning slice should record its baseline, actual caller/registration evidence and remaining unknowns. Retain shared infrastructure and root's manual compatibility patches unless that exact behavior is assigned. No new tests or runtime access are granted by this audit rule.

## Template: ruff.toml / pyproject.toml [tool.ruff]

```toml
[tool.ruff]
target-version = "py314"
line-length = 120
fix = true

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T10",  # flake8-debugger
    "EXE",  # flake8-executable
    "ISC",  # implicit-string-concatenation
    "ICN",  # import-conventions
    "PIE",  # flake8-pie
    "PT",   # flake8-pytest-style
    "RSE",  # flake8-raise
    "RET",  # flake8-return
    "SLF",  # flake8-self
    "SLOT", # flake8-slots
    "SIM",  # flake8-simplify
    "TID",  # flake8-tidy-imports
    "TCH",  # flake8-type-checking
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "TD",   # flake8-todos
    "FIX",  # flake8-fixme
    "ERA",  # eradicate (commented-out code)
    "RUF",  # ruff-specific rules
]

ignore = [
    "E501",   # line-too-long (formatter handles this)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["SLF001", "ARG001", "ARG002", "PT011"]

[tool.ruff.lint.isort]
known-first-party = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Banned Patterns

(to be filled — waiting for user's specific ban list)

### Template bans to add to ruff config:

```toml
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = []

[tool.ruff.lint.flake8-builtins]
builtins-ignorelist = []

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"
```

## Enforcement hooks

Hook installation is a separately scoped implementation step. Preserve existing exact project pins. The inherited hook-version template is intentionally omitted rather than presented as a verified Python 3.14 toolchain; no replacement versions have been selected or installed.

When hooks are explicitly requested, verify the selected tools' Python 3.14 support and configure only the agreed checks. A hook must not import the application, read private configuration, call providers or deploy/restart anything as an incidental effect of committing.

## Type checking enforcement

```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
```

## Project structure enforcement

- All public functions must have type annotations
- All public functions must have docstrings
- Private helpers (`_name`) must not exceed 20 lines
- No bare `except:` — always specify exception type
- No `# type: ignore` without explanation comment
- No commented-out code (ERA rules catch this)
