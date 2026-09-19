#!/bin/bash
set -euo pipefail

rev=$(git rev-parse HEAD)
image="dame-curie-app:${rev:0:7}"
uid=$(id -u dame-curie)
socket="/run/user/$uid/docker.sock"
home=$(getent passwd dame-curie | cut -d: -f6)
private=(sudo -n runuser -u dame-curie -- env -i PATH=/usr/local/bin:/usr/bin:/bin
  HOME="$home" XDG_RUNTIME_DIR="/run/user/$uid")
if [ "$uid" -eq 0 ] || ! "${private[@]}" test -S "$socket" || "${private[@]}" test -L "$socket" || [ "$("${private[@]}" stat -c %u "$socket")" != "$uid" ]; then
  printf 'Refusing an absent, redirected or foreign private engine socket.\n' >&2
  exit 1
fi
engine=("${private[@]}" docker --host "unix://$socket")
security=$("${engine[@]}" info --format '{{json .SecurityOptions}}')
case "$security" in
  *'"name=rootless"'*|*'"name=rootless,'*) ;;
  *) printf 'Refusing a non-rootless engine.\n' >&2; exit 1 ;;
esac

git archive "$rev" |
  "${engine[@]}" build --target app -f docker/app.Dockerfile \
    --build-arg DAME_CURIE_BUILD_COMMIT="$rev" \
    --build-arg DAME_CURIE_BUILD_BRANCH="$(git branch --show-current)" \
    --build-arg DAME_CURIE_BUILD_DATE="$(git show -s --format=%cI "$rev")" \
    --build-arg DAME_CURIE_BUILD_SUBJECT="$(git show -s --format=%s "$rev")" \
    --build-arg DAME_CURIE_BUILD_DIRTY=false \
    -t "$image" -

printf 'Built %s only; checkout, private settings and container lifecycle are unchanged.\n' "$image"
