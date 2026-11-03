---
name: implement-sanity
description: Review a diff before it becomes a PR. Use when validating that recent work is clean - no undocumented helpers, no blanket try/except, no hidden complexity, no hidden failures - and ready for review.
---

# Implement Sanity - pre-PR diff review

Review the actual diff, not the whole repository. Untouched legacy size and style are not findings. This checklist does not authorize application imports, test runs or runtime access; tests run only through `scripts/qa.sh`.

## How to use

1. Run the checklist against the diff.
2. Flag each violation with severity (blocker, warning, nit), file and line.
3. Give one verdict: ready for PR, needs fixes, or needs discussion.

## Blockers

- [ ] A private helper (`_name`) without a docstring that states why it exists.
- [ ] `except Exception` or a bare `except`.
- [ ] A caught error that is logged, swallowed or replaced by a warning. Failures stay visible.
- [ ] Model output or user input filtered, rewritten or matched by words to change behaviour.
- [ ] A request parameter added, removed or changed outside operator configuration.
- [ ] A fixed time zone, offset or `ZoneInfo` literal.
- [ ] A public function without full type annotations.
- [ ] A function over 50 lines that the task did not require.
- [ ] Commented-out code.
- [ ] A new function with no caller.
- [ ] `# type: ignore` or `# noqa` without a reason on the same line.
- [ ] A behaviour change without a regression test that fails on the old code.
- [ ] `scripts/lint.sh --staged` fails.

## Warnings

- [ ] A private helper over 20 lines; justify or inline it.
- [ ] `Optional` where the value is always present; `if x is not None` where `x` is always set.
- [ ] Redundant validation, for example `isinstance` after a type annotation.
- [ ] A function that does more than one thing.
- [ ] A magic number without a named constant.
- [ ] New code added to `bot.py` or `bot_tools.py` that belongs in its own module.

## Nits

- [ ] Naming: `snake_case` functions and variables, `PascalCase` classes.
- [ ] Unused imports.
- [ ] `print()` for logging.
- [ ] A comment or docstring with an em or en dash, or a date written month-first.

## Anti-patterns to flag

**Helper hoarder.** Five three-line private helpers with no docstrings instead of one readable function.

**Try/except blanket.** `try: result = do_thing() except Exception: result = None`. The caller now gets `None` and a hidden cause. Let the error propagate, or handle the one exception you expect and state the cause.

**Optional everything.** `def get_name(user: User | None) -> str | None`. If the user is always present, write `def get_name(user: User) -> str`.

**Docstring dodger.** A docstring that repeats the function name. Write what the function returns and why it exists.

**Type ghost.** `def fetch(url, timeout=30)`. Write `def fetch(url: str, timeout: int = 30) -> Response`.

## Output format

```
## Sanity review: <branch>

### Blockers
- module.py:45 - `_process` has no docstring
- module.py:89 - bare `except`

### Warnings
- module.py:120 - `_transform` is 35 lines

### Nits
- module.py:3 - unused import `json`

### Verdict: NEEDS FIXES (2 blockers)
```
