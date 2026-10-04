#!/bin/bash
# Refuse em dashes (U+2014) and en dashes (U+2013). Root's rule, 2026-10-04.
# Usage: check_dashes.sh --staged   check lines added to the index
#        check_dashes.sh [REV]      check all tracked files at REV (default HEAD)
# audit/ holds preserved original reports and is excluded.
set -euo pipefail
pattern='[\x{2013}\x{2014}]'
if [ "${1:-}" = "--staged" ]; then
  found=$(git diff --cached --no-color -U0 -- . ':!audit' | grep -P "^\+(?!\+\+ ).*$pattern" || true)
else
  found=$(git grep -nIP "$pattern" "${1:-HEAD}" -- . ':!audit' || true)
fi
if [ -n "$found" ]; then
  printf '%s\n' "$found" | head -40 >&2
  printf 'Refused: em dash or en dash found. Use "-" or ";".\n' >&2
  exit 1
fi
