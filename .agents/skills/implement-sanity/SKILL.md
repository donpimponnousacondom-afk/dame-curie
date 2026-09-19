---
name: implement-sanity
description: Review agent output before PRs or big changes. Use when validating that recent work is clean, tests pass, no private helpers lack docstrings, no unnecessary try/except blocks, no hidden complexity, and the codebase is ready for review.
---

# Implement Sanity — Pre-PR Review

## Purpose
Review the last round of agent work before it becomes a PR. Catch the tricks agents use to pad code and avoid proper implementation.

## What this skill checks
- Private helpers without docstrings (lazy encapsulation)
- Unnecessary try/except wrapping
- Missing type annotations on public functions
- Functions that are too long or do too much
- Hidden complexity in "simple" helpers
- Test coverage for new code
- Linting and formatting compliance

## How to use
1. Run the review checklist against the current diff or recent changes
2. Flag violations with severity (blocker / warning / nit)
3. For each violation, show the exact file and line
4. Provide a summary: ready for PR / needs fixes / needs discussion

## Dead-code evidence

For an authorized dead-code audit or pruning diff, use the pinned Vulture **2.16** workflow in repository-root `docs/DEAD_CODE.md`, under isolated Python **3.14**. Review its report alongside caller/registration evidence; do not import the application, collect/run tests or read private configuration to validate a static finding. Initial evidence is in `phase-II_v2/DEAD_CODE_PASS.md`.

- Distinguish ordinary orphan candidates from callback signatures, decorators, dynamic dispatch, serializers and external interfaces. A 100% unused argument can still be required by its caller.
- Treat 60/90/100 confidence values as analyzer categories, not removal authority or production-usage probabilities. Inspect the reported code and its replacement/callers; name matching also has false negatives.
- A soft-pass report may legitimately exit 3 with findings. Missing/syntax-invalid input and broken tool execution are not clean results. Do not demand a zero-finding legacy tree or conceal it with blanket whitelists, dummy uses or cosmetic parameter renames.
- Confirm the diff removes only the assigned slice and preserves shared dependencies/manual compatibility patches. Record what was retained and why. No new tests, hooks or runtime checks are authorized by this checklist.

## Review Checklist

### Blockers (must fix before PR)
- [ ] No private helper (`_function`) without a docstring explaining WHY it exists
- [ ] No try/except blocks that catch `Exception` or bare `except:`
- [ ] All public functions have full type annotations (params + return)
- [ ] No functions exceeding 50 lines
- [ ] No commented-out code blocks
- [ ] All new functions are used somewhere (no dead code)
- [ ] No `# type: ignore` without an explanatory comment on the same line

### Warnings (review carefully)
- [ ] Private helpers under 20 lines (if longer, justify or inline)
- [ ] No unnecessary `Optional` types where the value is always present
- [ ] No defensive `if x is not None` checks where `x` is always set
- [ ] No redundant validation (e.g., checking `isinstance` after type annotation)
- [ ] Functions do one thing (Single Responsibility)
- [ ] No magic numbers — use named constants

### Nits (fix if you see them)
- [ ] Consistent naming conventions (snake_case for functions/vars, PascalCase for classes)
- [ ] No unused imports
- [ ] Files under 300 lines (split if longer)
- [ ] No `print()` for logging — use proper logging

## Anti-patterns to Flag

### 1. The "Helper Hoarder"
Creating private helpers to avoid writing logic inline. Each helper hides complexity.
```
# BAD: 5 private helpers, each 3 lines, no docstrings
def _validate_input(x): ...
def _transform_data(x): ...
def _format_output(x): ...
def _log_result(x): ...
def _handle_error(x): ...

# GOOD: One function, clear flow
def process(data):
    """Process input data and return formatted result."""
    validated = check_input(data)
    transformed = apply_rules(data)
    return format_result(transformed)
```

### 2. The "Try/Except Blanket"
Wrapping everything in try/except to "be safe."
```
# BAD
try:
    result = do_thing()
except Exception:
    result = None

# GOOD
result = do_thing()
```

### 3. The "Optional Everything"
Marking everything Optional when it's always present.
```
# BAD
def get_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name

# GOOD
def get_name(user: User) -> str:
    return user.name
```

### 4. The "Docstring Dodger"
Public functions without docstrings, or docstrings that just repeat the function name.
```
# BAD
def calculate_total(items):
    return sum(i.price for i in items)

# GOOD
def calculate_total(items: list[CartItem]) -> Decimal:
    """Sum of line-item prices before tax."""
    return sum(i.price for i in items)
```

### 5. The "Type Ghost"
Functions with no type annotations, forcing callers to guess.
```
# BAD
def fetch(url, timeout=30):
    ...

# GOOD
def fetch(url: str, timeout: int = 30) -> Response:
    ...
```

## Output Format

```
## Sanity Review: [branch/diff name]

### Blockers
- src/module.py:45 — `_process` has no docstring
- src/module.py:89 — bare `except:` clause

### Warnings
- src/module.py:120 — `_transform` is 35 lines, consider splitting

### Nits
- src/module.py:3 — unused import `json`

### Verdict: NEEDS FIXES (2 blockers)
```
