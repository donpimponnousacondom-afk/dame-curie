#!/bin/sh
set -eu
checkout="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
exec "$checkout/.venv/bin/python" "$checkout/scripts/instance.py" "$@"
