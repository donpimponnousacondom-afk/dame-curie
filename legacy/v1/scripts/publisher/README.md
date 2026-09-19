# Standalone publisher

Python 3.14, Linux inotify, SSH and rsync. No bot imports, hooks, receiver service or new dependency.

```sh
python3.14 -B -m scripts.publisher --config /absolute/private/publisher.toml --once
python3.14 -B -m scripts.publisher --config /absolute/private/publisher.toml
```

Copy `config.example.toml` to a private configuration file. Source, staging and state roots must be separate. Staging/state directories must exist with mode0700; configuration, dedicated SSH key and host pin must be owner-private files outside those roots. Run as the image owner so0600 prompt sidecars are readable.

- Public site directories mirror to their corresponding remote child directories, including ordinary data/config/source assets.
- `_images` is a flat, retained archive: image bytes/names and matching prompt-only TXT files. No remote archive deletion.
- Local generation, backends and image reply URLs are unchanged. A static mirror does not execute the local Python/API backend.
- Stable, two-pass scans of the selected site precede its transfer/deletion. Only owned site children can be deleted; root landing pages and unmanaged children are not mirror targets. `--once` still performs a complete reconciliation.
- Remote guard requires Linux directory flock and `renameat2(RENAME_NOREPLACE)` plus Python3.12 or later. It runs inline through isolated Python, not an installed receiver.
- `static.htaccess` is the scoped Apache policy used for static source downloads; verify actual HTTP behavior on the target host before publishing generated files.

The Curie service unit uses `/opt/maxwell-publisher` for code and `/srv/maxwell-publisher/curie` for private configuration, staging and state. Deploy publisher changes there and restart **only** `maxwell-curie-publisher.service`; rebuilding the bot does not update this installation. The publisher does not restart or log into the bot.

## Event-driven scheduling

- The main thread continuously drains inotify and maintains directory watches. A single transfer thread owns scanning, staging, ownership state and SSH/rsync. The watcher never waits for a network transfer.
- Events identify the affected top-level site (or `_images`) and debounce that scope for `settle_seconds` (0.3 seconds in Curie). A continuously changing scope is capped at `rescan_seconds`; other scopes retain their own deadlines. Changes arriving during a scan/transfer stay queued for another pass.
- Dirty sites run ahead of background reconciliation. `rescan_seconds` (30 seconds in Curie's private configuration) controls low-priority local discovery, not an end-to-end upload deadline. Overflow requests discovery of both present and previously observed/owned sites; transient watch-tree renames retain the old watches and retry.
- Unchanged scopes skip file hashing and SSH after a successful publication. Metadata checks include inode, mode, link count, size, nanosecond mtime and ctime; changed metadata triggers full scoped screening/hashing. Content and empty-directory manifests decide whether another transfer is needed. A failed remote mutation invalidates its prior success cache.
- Existing owned sites reuse their bound identity; the remote guard still verifies ownership/root/inode on every actual operation. SSH reuses a pinned connection for up to 60 idle seconds via a control socket under the owner-private state directory. File and directory upload modes remain 0755; ownership markers remain private.
- Startup has an empty success cache and republishes through the priority queue. Remote-only edits are **not** detected by unchanged-local-content checks; restart the publisher or use `--once` with the service stopped when an explicit full remote repair is required. The ownership lock prevents simultaneous publishers.
- Inotify detection is immediate; debounce, the currently active single-site job, scanning and network latency still bound delivery. No zero-time remote-delivery guarantee. Fatal source/ownership/transport errors remain visible through process failure and systemd restart; ordinary changes during a scoped scan are requeued when a newer event is pending.

```sh
systemctl status maxwell-curie-publisher.service
journalctl -u maxwell-curie-publisher.service
```

Current deployment and acceptance evidence: `docs/STATUS.md`.
