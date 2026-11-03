#!/bin/bash
# Restore the live seat from a backup folder that scripts/deploy.sh wrote.
# The script restores each file the folder holds: compose.yaml, instance.py, deploy.env, bot.env,
# bot_control.json, and dame-curie-rag*.db when present. The current files go to a new rollback folder first.
# deploy.env holds APP_IMAGE, so the old image comes back with it. The /opt source export is not restored;
# run scripts/deploy.sh <old tag> for that.
# Usage: scripts/rollback.sh <backup folder>
set -uo pipefail
backup=${1:?usage: $0 <backup folder>}
account=dame-curie
uid=$(id -u "$account") || exit 1
D=(sudo -n runuser -u "$account" -- env XDG_RUNTIME_DIR="/run/user/$uid" docker --host "unix:///run/user/$uid/docker.sock")
I=(sudo -n -H -u "$account" -- /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/instance.py "$account")
sudo -n test -f "$backup/deploy.env" || { echo "STOP: $backup/deploy.env is missing" >&2; exit 1; }
echo "=== $(date -u +%FT%TZ) rollback from $backup"
db=$(sudo -n find "$backup" -maxdepth 1 -name 'dame-curie-rag*.db' -printf '%f\n' | head -1)
"${I[@]}" stop 2>&1 | tail -2
keep=/var/backups/dame-curie-v2-recovery/rollback-$(date -u +%Y%m%dT%H%M%SZ)
sudo -n install -d -m 0700 "$keep" || exit 1
sudo -n cp -a /opt/dame-curie/compose.yaml /opt/dame-curie/scripts/instance.py /srv/dame-curie/deploy.env \
  /srv/dame-curie/config/bot.env /srv/dame-curie/data/bot_control.json "$keep/" || exit 1
[[ -n "$db" ]] && { sudo -n cp -a /srv/dame-curie/data/dame-curie-rag.db* "$keep/" || exit 1; }
echo "current state kept in $keep"
restore() {
  # Install one backed-up file over its live path with the given owner and mode.
  local name=$1 target=$2 owner=$3 mode=$4
  sudo -n test -f "$backup/$name" || return 0
  sudo -n install -o "$owner" -g "$owner" -m "$mode" "$backup/$name" "$target" && echo "restored $target"
}
restore compose.yaml /opt/dame-curie/compose.yaml root 0644 || exit 1
restore instance.py /opt/dame-curie/scripts/instance.py root 0755 || exit 1
restore deploy.env /srv/dame-curie/deploy.env "$account" 0600 || exit 1
restore bot.env /srv/dame-curie/config/bot.env "$account" 0600 || exit 1
restore bot_control.json /srv/dame-curie/data/bot_control.json "$account" 0600 || exit 1
if [[ -n "$db" ]]; then
  sudo -n rm -f /srv/dame-curie/data/dame-curie-rag.db-wal /srv/dame-curie/data/dame-curie-rag.db-shm
  restore "$db" /srv/dame-curie/data/dame-curie-rag.db "$account" 0600 || exit 1
fi
sudo -n -u "$account" grep '^APP_IMAGE=' /srv/dame-curie/deploy.env
"${I[@]}" up 2>&1 | tail -3
sleep 25
"${D[@]}" inspect "$account-bot-1" --format 'rev={{index .Config.Labels "org.opencontainers.image.revision"}} restarts={{.RestartCount}} status={{.State.Status}}'
echo "=== rollback done; the state from before the rollback is in $keep"
