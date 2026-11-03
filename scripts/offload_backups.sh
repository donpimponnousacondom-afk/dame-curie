#!/bin/bash
# Move old recovery backups from /var/backups/dame-curie-v2-recovery to the Hetzner storage box.
# Order: pack, test locally, upload, verify SHA-256 on the storage box, then delete the local copies.
# The script deletes local copies only when every remote hash matches.
# The KEEP newest backup folders (default 2) stay local for a fast rollback.
# Usage: [KEEP=2] scripts/offload_backups.sh [--dry-run]
set -euo pipefail
dry_run=0
[[ "${1:-}" == "--dry-run" ]] && dry_run=1
keep=${KEEP:-2}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
host=u390720@u390720.your-storagebox.de
ssh_cmd=(ssh -n -p 23 -o BatchMode=yes "$host")
rsync_ssh="ssh -p 23 -o BatchMode=yes"
rdir=archive/dame-curie/recovery-offload-$stamp
base=/var/backups/dame-curie-v2-recovery
work=/var/tmp/dame-curie-offload-$stamp
zstd_level=(-19 --long=31 -T6)
log() { echo "$(date -u +%FT%TZ) $*"; }

mapfile -t all < <(sudo -n find "$base" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %f\n' | sort -rn | cut -d' ' -f2-)
kept=("${all[@]:0:$keep}")
moved=("${all[@]:$keep}")
log "kept local: ${kept[*]:-none}"
[[ ${#moved[@]} -gt 0 ]] || { log "nothing to move"; exit 0; }
log "to move: ${#moved[@]} folders"

sudo -n install -d -m 0700 -o "$(id -u)" -g "$(id -g)" "$work"
cd "$work"
(cd "$base" && sudo -n du -sh "${moved[@]}") > sizes-before.txt

# 1. Files that are already compressed go into a plain tar; compressing them again gains nothing.
(cd "$base" && sudo -n find "${moved[@]}" \( -type f -o -type l \) \( -name '*.zst' -o -name '*.gz' \)) | sort > precompressed.list
while IFS= read -r f; do
  case "$f" in
    *.zst) sudo -n zstd -t -q --long=31 "$base/$f" ;;
    *.gz) sudo -n gzip -t "$base/$f" ;;
  esac
done < precompressed.list
log "precompressed files tested: $(wc -l < precompressed.list)"
sudo -n tar -C "$base" --numeric-owner -cvf precompressed.tar --files-from=precompressed.list > precompressed.created.txt
sudo -n chown "$(id -u):$(id -g)" precompressed.tar

# 2. All other files go into one solid archive with long-range matching (similar database copies).
sudo -n tar -C "$base" --numeric-owner --exclude='*.zst' --exclude='*.gz' -cvf - "${moved[@]}" 2> rest.created.txt |
  zstd "${zstd_level[@]}" -q -o rest.tar.zst

# 3. Local checks: each archive decodes and lists the members that were written.
zstd -t -q --long=31 rest.tar.zst
zstd -dc --long=31 rest.tar.zst | tar -tf - > rest.listed.txt
diff <(sort rest.created.txt) <(sort rest.listed.txt) > /dev/null || { log "FAIL: rest.tar.zst member list differs"; exit 1; }
tar -tf precompressed.tar > precompressed.listed.txt
diff <(sort precompressed.created.txt) <(sort precompressed.listed.txt) > /dev/null || { log "FAIL: precompressed.tar member list differs"; exit 1; }
log "local checks pass"

cat > README.txt <<TXT
dame-curie recovery backups moved from $(hostname):$base on $stamp.
Folders: ${moved[*]}
precompressed.tar: the original .zst and .gz files. Restore: sudo tar -xpf precompressed.tar --numeric-owner -C <target>
rest.tar.zst: all other files. Restore: zstd -dc --long=31 rest.tar.zst | sudo tar -xpf - --numeric-owner -C <target>
The --long=31 flag is necessary to decompress rest.tar.zst.
Some members are private configuration files with credentials. Keep this folder private.
TXT
sha256sum precompressed.tar rest.tar.zst README.txt precompressed.listed.txt rest.listed.txt sizes-before.txt > SHA256SUMS
ls -l "$work"
if [[ $dry_run == 1 ]]; then log "dry run: stop before upload; work folder $work"; exit 0; fi

# 4. Upload, then verify every hash with the storage box's own sha256sum.
"${ssh_cmd[@]}" mkdir -p "$rdir"
for f in README.txt sizes-before.txt precompressed.listed.txt rest.listed.txt SHA256SUMS precompressed.tar rest.tar.zst; do
  rsync -t --partial -e "$rsync_ssh" "$f" "$host:$rdir/"
done
fail=0
while read -r sum name; do
  remote=$("${ssh_cmd[@]}" sha256sum "$rdir/$name" | awk '{print $1}')
  if [[ "$remote" == "$sum" ]]; then log "remote hash ok: $name"; else log "FAIL remote hash: $name"; fail=1; fi
done < SHA256SUMS
[[ $fail == 0 ]] || { log "FAIL: local copies kept; work folder $work"; exit 1; }

# 5. Delete the moved folders and the work folder.
for d in "${moved[@]}"; do sudo -n rm -rf -- "${base:?}/$d"; done
receipts="$HOME/dame-curie-offload-receipts/$stamp"
mkdir -p "$receipts" && cp SHA256SUMS README.txt sizes-before.txt "$receipts/"
cd / && rm -rf -- "${work:?}"
log "remote folder: $rdir; receipts: $receipts"
df -h / | tail -1
