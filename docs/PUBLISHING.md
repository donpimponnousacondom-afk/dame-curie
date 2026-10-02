# Publishing and site authoring

How local authored files become remote static files. The publisher is an independent
process that mirrors a local directory tree outward over SSH/rsync. It is not a
deployment mechanism, not a runtime sync, and not something the model administers.

This is the durable guide for both instances, **not a publisher/private/remote operating grant**. Source handoff support is not proof of migrated state or activated services. The old phase record is recoverable through `git show eb188ac:phase-II_v2/DIRAC_PUBLISHING.md`; the protected template's historical citation is left unchanged, not treated as a live documentation link.

## Authoring

There is no site-authoring tool. The shell tool is the only writer, and its contract is
to author files locally and never to administer remote publication.

- The model's shell runs `bash --noprofile --norc -c` with `cwd`/`HOME` of `/home/dame-curie`, which is a
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

Publisher file contents are transported unchanged, without credential-pattern inspection
or content-based publication refusal. Root removed that filter on 2026-09-30 after an
API-documentation example blocked publication. Explicit path exclusions and filesystem,
SSH and remote-ownership protections remain in force.

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
claimed site directory, or `.curie-publisher-owner` with the explicit legacy namespace.
Do not create, edit or delete it. A remote directory that exists
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
| `marker_namespace` | `"dame-curie"` by default; only explicit `"curie"` selects V1 owner/claim names. Pinned in ownership state. |
| `rescan_seconds`, `settle_seconds`, `timeout_seconds` | Watch cadence and transfer timeout. Optional. |

The publisher needs a `python3` **and** an `rsync` on the remote host. It invokes the
remote `python3 -I -S -c` as its rsync transfer guard; that is not the remote hosting a
Python application.

Instances are isolated by directory, not by code: use disjoint `source`, `staging` and `state` and distinct remote `site_root`/`image_root`. The SSH host/user/port or key may be shared under an explicit grant; that does not separate destinations.
Ownership state pins the source path/device/inode, remote target tuple/root identities,
and marker namespace. A configuration mismatch is refused, not an invitation to clear
state. A **fresh** state directory pins the configured destination as-is, with no check
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

## Claim-preserving V1 handoff — coordinator only

For the Queen's existing remote claims, set `marker_namespace = "curie"` explicitly.
This selects `.curie-publisher-owner` and `.curie-publisher-claim-<token>` without
renaming, replacing, chowning or adopting remote markers. There is no namespace search
or fallback. Default V2 exclusions remain; the selected namespace's internal owner/claim
names are also excluded locally and its owner marker is protected during rsync deletion.
SSH host-key verification, remote UID/mode/link checks, token bytes, directory identity
checks and atomic claim/removal rules are unchanged. Local service UIDs do not determine
the remote SSH UID.

Keep both publishers quiesced while preparing the complete new local source tree and
preserving the old installed publisher/config/state for recovery. The coordinator must
verify the unchanged Queen SSH tuple/trust material, distinct destinations, remote root
and site identities, and existing marker ownership/token bindings before activation.
Privately project the Queen's saved state, changing only `source`, its verified
`source_identity`, and explicit `marker_namespace = "curie"`; retain version, target,
remote roots, every site's identity/token/deleting flag, and all other state. Do not
clear state, borrow Dirac state, or reset tokens. Local private files/directories still
need the new process user's existing required ownership/modes; this is not permission
to alter remote ownership or broaden access.

A state file without `marker_namespace` means `"dame-curie"`, preserving existing V2
behavior; it cannot silently enter legacy mode. The explicit projection is required
for V1 state, not automatic rebinding. Source preparation, parent-run isolated tests,
remote verification and bounded publication acceptance are separate gates; this guide
is not an execution or activation receipt.

## Dirac-specific layout and retained limits

The template is `scripts/publisher/config.dirac.example.toml`; the separate unit is `scripts/publisher/dirac-publisher.service`. Its intended account is `dame-curie`, working directory `/opt/dame-curie`, source `/srv/dame-curie/dirac/sites`, and private configuration/staging/state under `/srv/dame-curie/dirac/publisher/{config,staging,state}`. This is layout, not fresh service/destination verification. Real host, user, key and remote roots must never be guessed from the placeholders or copied wholesale from another instance.

An explicitly authorized existing-key reuse needs a private regular copy owned by the process user, mode0600, link count1; symlink/hardlink reuse is refused. The publisher entry is `python -B -m scripts.publisher --config <private TOML>`; `--once` reconciles once, otherwise it watches/rescans. These are interfaces, not commands authorized by this page.

The historical source review reported an **unresolved out-of-band remote-site deletion gap**: service mode can retain a cached binding to the missing directory, fail/restart and starve later sites. Its proposed `--once` re-claim recovery and any code change require a separate publisher assignment; neither was exercised or applied in this closure. Preserve that limitation rather than interpreting a prior running-service receipt as deletion-recovery acceptance. Full diagnosis and earlier lane-specific grants remain in the immutable phase record above, not as renewed authority.

## Verifying a publication — separate grant required

These examples access service/private state or the remote host. They are not permitted by the current source/Dirac-remediation assignment. Under a suitable publisher grant, local checks include:

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
| `ownership configuration changed` | Source path, remote target tuple or marker namespace no longer matches the saved state. |
| `publisher marker namespace refused` | `marker_namespace` is neither `"dame-curie"` nor `"curie"`. |
| `remote filesystem root refused` / `remote roots overlap` | `site_root` and `image_root` overlap or nest, or one of them is `/`. |
| `SSH host refused` / `SSH user refused` | The value fails the strict host/user pattern. |
| `SSH credential path expansion refused` | A `%`, `${` or newline in the key, `known_hosts` or `state` path. |
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

The project provides no PHP/Perl/CGI hosting setup or local web-server feature; Compose publishes no ports. This does not certify the absence of incidental language utilities in inherited distribution packages, or constrain everything an authorized same-UID shell can execute. There is no supported opt-in executable-hosting mode.

## What the publisher never does

It never starts a local server, never installs a language runtime, never rewrites remote
web-server configuration, never follows symlinks, never copies devices or specials, and
never adopts a remote directory it did not create. It does not read
`DAME_CURIE_PUBLIC_BASE_URL` or `DAME_CURIE_SITE_PUBLIC_BASE_URL`; the latter has no
reader in production code at all, so configuring it does nothing. Destination selection is
the TOML only — there are no environment keys for it.
