#!/bin/sh
set -eu
exec python3.14 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/instance.py" "$@"
