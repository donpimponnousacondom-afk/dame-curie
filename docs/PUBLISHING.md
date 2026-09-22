# Publishing and site authoring

How local authored files become remote static files. The publisher is an independent
process that mirrors a local directory tree outward over SSH/rsync. It is not a
deployment mechanism, not a runtime sync, and not something the model administers.

Dirac's specific instance record, its template and its untested gaps are in
`phase-II_v2/DIRAC_PUBLISHING.md`. This file is the durable operator guide for either
instance.

## Authoring

There is no site-authoring tool. The shell tool is the only writer, and its contract is
to author files locally and never to administer remote publication.

- The model's shell runs `bash -lc` with `cwd`/`HOME` of `/home/dame-curie`, which is a
  symlink to the persistent `/state/shell` bind.
- The authoring root is **not** under `HOME`. Reach it as `/state/sites`, or as
  `"$DAME_CURIE_SITE_DIR"` (the container value; `config.py` defaults it to `public/bot`
  outside a container).
- On the host the same tree is `<instance root>/sites`.

```
/state/sites/<site>/...        one first-level directory per site
/state/sites/_images/<name>    generated images, flat
/state/sites/_images/<stem>.txt  prompt sidecar for that image
```

Sidecars are stem-matched to the image (`X.png` → `X.txt`), written atomically, and their
content is redacted when stored. The publisher publishes a `.txt` only when a matching
image with a publishable suffix exists.

## What gets published

| Local | Remote | Deletion |
| --- | --- | --- |
| `<root>/<site>/**` | `site_root/<site>/**` | `rsync --delete-delay`, ownership marker protected |
| `<root>/_images/*.{png,jpg,jpeg,gif,webp}` and matching `.txt` | `image_root/*` (flat) | **never deleted** |

Only **first-level directories** of the authoring root become sites. A loose file at the
top level is skipped entirely.

Never published: loose top-level files, first-level dotfiles, `_data`, `_build`, `.env`,
`.git`, the ownership marker, `.publisher-link`, and anything under a configured
`private_paths` entry. A dotfile *inside* a site directory **is** published — only
first-level dotfiles are excluded. That is how a per-site `.htaccess` can be shipped.

## The two rules that explain most surprises

1. **The publisher owns the whole site directory.** Anything present remotely inside a
   site directory it has claimed, but absent from the local source, is **deleted** on the
   next sync. An operator-installed file survives only if it also exists in the local
   source tree. Files the publisher does not own — other site directories, and anything
   in `site_root` itself — are left alone.
2. **The image archive never deletes.** Removing a local image does not remove the
   archived remote copy. Over time the archive accumulates; pruning it is a manual,
   explicit operation.

Ownership is enforced with a private marker `.dame-curie-publisher-owner` inside each
claimed site directory. Do not create, edit or delete it. A remote directory that exists
but is not owned is **refused**, never adopted, so a hand-made directory at a site name
will block that site rather than be overwritten.

## Configuration

One TOML file per instance, passed with `--config`. It must be mode 0600, owned by the
running user, and must not sit inside `source`, `staging` or `state`. Templates:
`scripts/publisher/config.example.toml` and `scripts/publisher/config.dirac.example.toml`.

| Key | Must be |
| --- | --- |
| `source` | Local authoring root. |
| `staging`, `state` | Private, mode 0700, owned by the running user, pairwise non-overlapping with each other and with `source`. |
| `key`, `known_hosts` | Mode 0600, regular files, `st_nlink == 1`, owned by the running user. A symlink or hardlink is refused. |
| `host`, `user`, `port` | Remote endpoint. `StrictHostKeyChecking=yes` is unconditional; the host key must already be in `known_hosts`. |
| `site_root`, `image_root` | Remote destinations, disjoint from each other in both directions. Neither may be `/`. |
| `private_paths` | Local subtrees to never publish. Optional. |
| `rescan_seconds`, `settle_seconds`, `timeout_seconds` | Watch cadence and transfer timeout. Optional. |

The publisher needs a `python3` **and** an `rsync` on the remote host. It invokes the
remote `python3 -I -S -c` as its rsync transfer guard; that is not the remote hosting a
Python application.

Instances are isolated by directory, not by code. Two instances must differ in every one
of `source`, `staging`, `state`, and in `host`/`user`/`port`/`site_root`/`image_root`.
`state.py` refuses to start if any of those differs from the saved state, so an existing
instance cannot be repointed without clearing its state directory — but on a **fresh**
state directory the configured destination is adopted and pinned as-is, with no check
that it belongs to this project. Verify the destination before the first write.

The isolation between instances is not uniform, and the difference matters:

- **Site trees are ownership-checked.** Each remote site directory carries a private
  marker, and the guard refuses to transfer into or delete a directory whose marker and
  device/inode identity do not match. A second instance pointed at another instance's
  `site_root` therefore **fails closed** on a name collision — it cannot corrupt an
  existing owned site.
- **The image archive is not.** The `archive` action writes straight into `image_root`
  with no marker, no token and no per-instance namespace; the only protection is the
  root device/inode pin held in the owning instance's state. Two instances configured
  with the same `image_root` will both write there and silently overwrite same-named
  images and prompt sidecars. The archive is flat by design (one `_images` destination
  serves all sites), so it cannot be namespaced per site — a distinct `image_root` per
  instance is the only separation.
- **Creation is not restricted.** A second instance pointed at another instance's
  `site_root` can still create *new* directories there, because a claim succeeds for any
  name that does not already exist. Names it never claimed are never removed by it, but
  they will be served.

## Verifying a publication

Local, no credentials:

```sh
systemctl status dame-curie-publisher.service
journalctl -u dame-curie-publisher.service -n 50 --no-pager
ls -la /srv/dame-curie/publisher/staging/current      # exactly what will be mirrored
cat /srv/dame-curie/publisher/state/ownership.json    # pinned target + remote root ids
```

`ownership.json` records the pinned `target` and both remote root device/inode pairs. It
is the local half of the destination binding; compare it with the remote roots before
concluding a destination is the intended one.

Remote, read-only:

```sh
ssh -i <key> -o StrictHostKeyChecking=yes <user>@<host> \
  'stat -c "%d %i %n" <site_root> <image_root>'
ssh -i <key> -o StrictHostKeyChecking=yes <user>@<host> \
  'command -v python3; command -v rsync'
```

A public URL is **not** evidence that publication succeeded. Nor is the absence of an
error: the publisher reports remote failures as a single refusal string by design.

## Troubleshooting

The publisher reports failures as short fixed messages and never prints remote output,
credentials or file contents.

| Message | Usual cause |
| --- | --- |
| `private file permissions refused` / `private directory permissions refused` | Config, key, `known_hosts`, `staging` or `state` is not mode 0600/0700, is a symlink/hardlink, or is owned by another account. |
| `private configuration changed` | The TOML was replaced or altered while being read. |
| `ownership configuration changed` | `host`/`user`/`port`/`site_root`/`image_root` no longer match the saved state. |
| `remote filesystem root refused` / `remote roots overlap` | `site_root` and `image_root` overlap or nest, or one of them is `/`. |
| `SSH host refused` / `SSH user refused` | The value fails the strict host/user pattern. |
| `SSH credential path expansion refused` | A `%`, `${` or newline in the key, `known_hosts` or `state` path. |
| `credential tripwire refused scan` | A source file matches a credential pattern or PEM header. Blocks **all** publishing until removed. |
| `hardlinked source refused` | A source file has `st_nlink != 1`. |
| `source root replacement refused` | The authoring root was moved or replaced under the running publisher. |
| `remote operation refused or failed` | Any remote-side refusal or transport failure, including a root identity mismatch or an unowned directory at a site name. |
| `publisher: configuration or filesystem operation failed` | Startup failure before the watcher began. |

## PHP, Perl and CGI

Whether the remote host can execute PHP/Perl/CGI is **not** determined by this repository,
and cannot be.

`scripts/publisher/static.htaccess` is a static-only template: `Options
-Indexes -ExecCGI -Includes`, `default-handler`, and `ForceType text/plain` for PHP, CGI,
Perl, Python, shell and ASP extensions. **No code in this repository references, copies or
installs it** — a scoped search finds no hit outside the file itself. Its presence proves
nothing about the remote site's effective policy, and the publisher does not apply it.

The publisher uploads with `--chmod=D755,F755`, so published files land mode 0755
(executable). It transports bytes and permission bits; it neither enables nor disables
server-side execution. Whether a site can execute anything is decided by the remote
host's configuration, by whether it honours per-directory overrides, and by what the
operator places in that remote root — for example opting out of the static policy by not
deploying that `.htaccess` inside the site directory.

Nothing here installs or provides PHP/Perl/CGI, and no local server exists: the Compose
file publishes no ports, and the bot image contains no web framework or interpreter for
these languages. There is no opt-in executable-hosting mode.

## What the publisher never does

It never starts a local server, never installs a language runtime, never rewrites remote
web-server configuration, never follows symlinks, never copies devices or specials, and
never adopts a remote directory it did not create. It does not read
`DAME_CURIE_PUBLIC_BASE_URL` or `DAME_CURIE_SITE_PUBLIC_BASE_URL`; the latter has no
reader in production code at all, so configuring it does nothing. Destination selection is
the TOML only — there are no environment keys for it.
