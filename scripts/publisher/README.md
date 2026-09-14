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
- Complete scans precede transfer/deletion. Only owned site children can be deleted; root landing pages and unmanaged children are not mirror targets.
- Remote guard requires Linux directory flock and `renameat2(RENAME_NOREPLACE)` plus Python3.12 or later. It runs inline through isolated Python, not an installed receiver.
- `static.htaccess` is the scoped Apache policy used for static source downloads; verify actual HTTP behavior on the target host before publishing generated files.

The Curie service unit uses `/opt/maxwell-publisher` for code and `/srv/maxwell-publisher/curie` for private configuration, staging and state. It watches changes and periodically reconciles; transient failure exits for systemd restart. It does not restart or log into the bot.

```sh
systemctl status maxwell-curie-publisher.service
journalctl -u maxwell-curie-publisher.service
```

Current deployment and acceptance evidence: `docs/STATUS.md`.
