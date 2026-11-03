#!/bin/bash
# Build the QA image dame-curie-qa:<app-tag> from the app image dame-curie-app:<app-tag>.
# The QA image adds the test tools pinned in docker/qa-requirements.lock.
# Usage: scripts/build_qa_image.sh <app-tag>
set -euo pipefail
tag=${1:?usage: $0 <app-tag>}
account=dame-curie
uid=$(id -u "$account")
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
tar -C "$repo/docker" -c qa.Dockerfile qa-requirements.lock | sudo -n runuser -u "$account" -- \
  env XDG_RUNTIME_DIR="/run/user/$uid" docker --host "unix:///run/user/$uid/docker.sock" \
  build --pull=false --build-arg "APP_IMAGE=dame-curie-app:$tag" -f qa.Dockerfile -t "dame-curie-qa:$tag" -
echo "built dame-curie-qa:$tag"
