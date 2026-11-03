#!/bin/bash
# Re-embed a copy of the memory database with new embedding settings before a model switch.
# <workdir> holds the copy dame-curie-rag.db and embed.env (the new DAME_CURIE_EMBED_* settings).
# The script runs backfill passes of up to 600 s until no eligible row is pending.
# It stops when a pass fails or a pass embeds nothing.
# Usage: scripts/embed_eval/prewarm.sh <app-tag> <workdir>
set -uo pipefail
tag=${1:?usage: $0 <app-tag> <workdir>}
work=$(realpath -e "${2:?usage: $0 <app-tag> <workdir>}") || exit 1
account=dame-curie
uid=$(id -u "$account") || exit 1
D=(sudo -n runuser -u "$account" -- env XDG_RUNTIME_DIR="/run/user/$uid" docker --host "unix:///run/user/$uid/docker.sock")
for pass in $(seq 1 20); do
  echo "=== $(date -u +%FT%TZ) pass $pass"
  out=$("${D[@]}" run --rm --network bridge --user 0:0 -w /app -v "$work:/work" \
    -e DAME_CURIE_ENV_FILE=/work/embed.env -e PYTHONDONTWRITEBYTECODE=1 -e DATA_DIR=/work \
    --entrypoint python "dame-curie-app:$tag" -B rag_maintenance.py backfill --db /work/dame-curie-rag.db \
    --limit 10000 --batch-size 64 --max-seconds 600 2>&1)
  code=$?
  last=$(tail -1 <<<"$out")
  tail -3 <<<"$out" | cut -c1-600
  echo "exit=$code"
  pending=$(python3 -I -c 'import json, sys; print(json.loads(sys.argv[1])["counts"]["eligible_pending"])' "$last") ||
    { echo "=== stop: the last output line is not a backfill report"; exit 1; }
  echo "eligible_pending=$pending"
  [[ "$pending" == "0" ]] && { echo "=== done"; exit 0; }
  [[ $code == 0 || $code == 2 ]] || { echo "=== stop: exit=$code"; exit 1; }
  grep -q '"embedded": 0,' <<<"$last" && { echo "=== stop: a pass embedded nothing"; exit 1; }
done
echo "=== stop: 20 passes and rows are still pending"
exit 1
