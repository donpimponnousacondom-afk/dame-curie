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
