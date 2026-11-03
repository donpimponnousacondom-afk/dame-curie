#!/bin/bash
# Deploy dame-curie-app:<app-tag> to the live seat.
# Run it in GNU Screen session dame_curie, window throne-ops. Build the image first with scripts/build_for_human.sh.
# Steps: activity check, image check, backup, sync /opt/dame-curie, set APP_IMAGE, up, health lines.
# /opt/dame-curie becomes an exact export of the image's source commit; /opt/dame-curie/.venv stays.
# Release configuration edits are separate steps. Do them after the backup and before "up".
# Usage: scripts/deploy.sh <app-tag>
# Rollback: scripts/rollback.sh <backup folder printed below>
set -uo pipefail
tag=${1:?usage: $0 <app-tag>}
account=dame-curie
uid=$(id -u "$account") || exit 1
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel) || exit 1
D=(sudo -n runuser -u "$account" -- env XDG_RUNTIME_DIR="/run/user/$uid" docker --host "unix:///run/user/$uid/docker.sock")
I=(sudo -n -H -u "$account" -- /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/instance.py "$account")
image="dame-curie-app:$tag"
echo "=== $(date -u +%FT%TZ) deploy $image"

rev=$("${D[@]}" image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') || exit 1
git -C "$repo" cat-file -e "$rev^{commit}" 2>/dev/null || { echo "STOP: image revision $rev is not a commit in $repo" >&2; exit 1; }
echo "image source commit: $rev"

recent=$("${D[@]}" logs --since 60s "$account-bot-1" 2>&1)
echo "last 60 s: $(grep -c 'MSG from user' <<<"$recent") user messages, $(grep -c 'Provider timing start' <<<"$recent") provider calls"

backup=/var/backups/dame-curie-v2-recovery/deploy-$(date -u +%Y%m%dT%H%M%SZ)
sudo -n install -d -m 0700 "$backup" || exit 1
sudo -n cp -a /opt/dame-curie/compose.yaml /opt/dame-curie/scripts/instance.py \
  /srv/dame-curie/deploy.env /srv/dame-curie/config/bot.env /srv/dame-curie/data/bot_control.json "$backup/" || exit 1
echo "backup: $backup"

stage=$(mktemp -d /var/tmp/dame-curie-deploy.XXXXXX) || exit 1
trap 'rm -rf -- "$stage"' EXIT
chmod 0755 "$stage" || exit 1
git -C "$repo" archive "$rev" | tar -x -C "$stage" || exit 1
sudo -n rsync -a --delete --chown=root:root --exclude=/.venv/ "$stage/" /opt/dame-curie/ || exit 1
echo "/opt/dame-curie synced to $rev"

sudo -n -u "$account" sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$image|" /srv/dame-curie/deploy.env || exit 1
sudo -n -u "$account" grep '^APP_IMAGE=' /srv/dame-curie/deploy.env
"${I[@]}" up 2>&1 | tail -3
sleep 25
"${D[@]}" inspect "$account-bot-1" \
  --format 'rev={{index .Config.Labels "org.opencontainers.image.revision"}} started={{.State.StartedAt}} restarts={{.RestartCount}} status={{.State.Status}}'
started=$("${D[@]}" logs --since 40s "$account-bot-1" 2>&1)
echo "errors and tracebacks since start: $(grep -cE 'Traceback|ERROR' <<<"$started")"
grep -E 'Logged in|setup complete|smoke runtime|Smoke runtime' <<<"$started" | tail -3 | cut -c1-200
echo "=== done; rollback: $repo/scripts/rollback.sh $backup"
