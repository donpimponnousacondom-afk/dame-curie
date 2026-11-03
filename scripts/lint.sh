#!/bin/bash
# Quality gate: no em or en dashes, ruff check, and ruff format on Python files that a change adds.
# Formatting is not enforced on existing files; do not reformat code that a change does not touch.
# Usage: scripts/lint.sh [--base REV]   check tracked files; format-check files added in REV..HEAD
#        scripts/lint.sh --staged       check the index (the commit hook runs this)
# REV defaults to origin/main. ruff must be the version pinned in requirements-dev.txt.
# Set RUFF to another command, for example RUFF="uvx ruff@0.17.3".
set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
want=$(sed -n 's/^ruff==//p' requirements-dev.txt)
read -ra ruff <<<"${RUFF:-ruff}"
have=$("${ruff[@]}" --version 2>/dev/null | awk '{print $2}' || true)
if [[ "$have" != "$want" ]]; then
  echo "lint: ruff $want is required, found ${have:-no ruff}. Run: pip install -r requirements-dev.txt" >&2
  exit 1
fi

mode=tree
base=origin/main
case "${1:-}" in
  --staged) mode=staged ;;
  --base) base=${2:?--base needs a revision} ;;
  "") ;;
  *) echo "lint: unknown argument: $1" >&2; exit 2 ;;
esac

if [[ $mode == staged ]]; then
  scripts/check_dashes.sh --staged
  mapfile -t lint_files < <(git diff --cached --name-only --diff-filter=ACMR -- '*.py')
  mapfile -t new_files < <(git diff --cached --name-only --diff-filter=A -- '*.py')
else
  scripts/check_dashes.sh HEAD
  git rev-parse --verify --quiet "$base^{commit}" >/dev/null || { echo "lint: unknown base revision: $base" >&2; exit 2; }
  mapfile -t lint_files < <(git ls-files -- '*.py')
  mapfile -t new_files < <(git diff --name-only --diff-filter=A "$base" HEAD -- '*.py')
fi

if [[ ${#lint_files[@]} -gt 0 ]]; then
  "${ruff[@]}" check --force-exclude --quiet "${lint_files[@]}"
fi
if [[ ${#new_files[@]} -gt 0 ]]; then
  "${ruff[@]}" format --check --force-exclude "${new_files[@]}"
fi
echo "lint: pass (${#lint_files[@]} files checked, ${#new_files[@]} new files format-checked)"
