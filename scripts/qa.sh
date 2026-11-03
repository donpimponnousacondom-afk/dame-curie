#!/bin/bash
# Run the test suite of a commit in an isolated container.
# The container has no network, no private mount, a read-only root and a synthetic environment.
# Usage: QA_IMAGE=dame-curie-qa:<tag> scripts/qa.sh <tree-ish> <outfile> [pytest arguments]
# Default pytest arguments: tests. The output and the line "exit=<code>" go to <outfile>.
# Build the image with scripts/build_qa_image.sh. Give a full commit SHA, not a short one.
set -uo pipefail
if [[ $# -lt 2 ]]; then
  echo "usage: QA_IMAGE=dame-curie-qa:<tag> $0 <tree-ish> <outfile> [pytest arguments]" >&2
  exit 2
fi
: "${QA_IMAGE:?QA_IMAGE is not set; build an image with scripts/build_qa_image.sh <app-tag>}"
tree=$1
out=$2
shift 2
if [[ $# -eq 0 ]]; then set -- tests; fi
selection=$(printf '%q ' "$@")
account=dame-curie
uid=$(id -u "$account") || exit 1
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel) || exit 1
git -C "$repo" rev-parse --verify --quiet "$tree^{tree}" >/dev/null || { echo "unknown tree-ish: $tree" >&2; exit 2; }
git -C "$repo" archive "$tree" | sudo -n runuser -u "$account" -- env XDG_RUNTIME_DIR="/run/user/$uid" \
  docker --host "unix:///run/user/$uid/docker.sock" run --rm -i \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 3g --cpus 2 \
  --tmpfs /suite:rw,exec,size=768m --tmpfs /tmp:rw,exec,size=1g --tmpfs /state:rw,size=256m \
  -e DAME_CURIE_ENV_FILE=/tmp/synthetic.env -e PYTHONDONTWRITEBYTECODE=1 -e HOME=/state/home \
  -e DATA_DIR=/state/data -e DISCORD_TOKEN=synthetic-never-used \
  -e OPENAI_BASE_URL=http://provider.invalid/v1 -e OPENAI_API_KEY=synthetic-no-network \
  -e OPENAI_MODEL=synthetic-model -e ENABLE_RAG=false -e ENABLE_IMAGE_GEN=false \
  --entrypoint bash "$QA_IMAGE" -c "
    set -e
    mkdir -p /state/home /state/data
    : > /tmp/synthetic.env
    cd /suite && tar -x
    git init -q .
    git -c user.name=qa -c user.email=qa@qa.invalid add -A
    git -c user.name=qa -c user.email=qa@qa.invalid commit -qm qa
    python -B -m pytest -o addopts=-ra -q --tb=short --show-capture=no -p no:cacheprovider \
      --ignore=tests/test_streaming.py --ignore=tests/test_streaming_primary.py $selection" >"$out" 2>&1
code=$?
echo "exit=$code" >>"$out"
exit "$code"
