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

## How to use
1. Apply ruff rules from the Banned Patterns section below
2. Generate or update `pyproject.toml` / `ruff.toml` with the rules
3. Set up pre-commit hooks to enforce on every commit
4. Run `ruff check --fix` and `ruff format` on the codebase
5. Report violations that can't be auto-fixed

## Template: ruff.toml / pyproject.toml [tool.ruff]

```toml
[tool.ruff]
target-version = "py312"
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

### Pre-commit template (.pre-commit-config.yaml):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']
```

## Type checking enforcement

```toml
[tool.mypy]
python_version = "3.12"
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
