# Dirac publishing workflow (isolated static publisher instance)

Updated 2026-09-22. This is the lane record for the Dirac publishing workflow in
`scripts/publisher/**`. It is **not** activation permission, a remote-destination
selection or proof that any publication succeeded. Dirac's real SSH host, SSH user and
remote roots are **not established** here; this checkout contains no verified values for
them. Protected V1 (`maxwell-curie`), the dame-curie V1/V2 destinations and every
existing remote folder are outside this lane.

Authorization for this lane: the direct human authorized syncer/publisher work for
Dirac, a separate Dirac remote subfolder using the existing SSH key, and end-to-end
authoring/mirroring checks. That grant supersedes the earlier publisher-immutability
restriction **only** for this assigned workflow. Runtime/private configuration, SSH
material, keys, server access and actual remote folder creation remain coordinator-only.

## What was added, and what was deliberately not

| Path | Status | Note |
| --- | --- | --- |
| `scripts/publisher/config.dirac.example.toml` | **new** | Dirac instance template. Reserved `.invalid` host, no private values. |
| `scripts/publisher/dirac-publisher.service` | **new** | Second publisher instance unit. |
| `scripts/publisher/**` (the 15 pre-existing files) | **unchanged** | Byte-identical to the reviewed baseline. |
| `config.py`, `compose.yaml`, Dockerfile/packaging, runtime/smoke modules, shared ledgers | **untouched** | Not this lane. |

No source-behavior change was made. A candidate `refused_roots` config key (a
source-level refusal that would stop one instance from naming another project's remote
roots) was written, reviewed and then **withdrawn on the coordinator's decision**: an
explicit operator configuration is not itself a product bug, and the boundary is
enforced by verifying the distinct remote destination before any write plus the existing
ownership-marker checks. The gap it would have closed is recorded under "Gaps" rather
than silently patched.

## Current publication contract

Verified by source inspection only. No publisher process, SSH connection, Docker
operation, application import or test execution was performed in this lane.

1. **Entry.** `python -B -m scripts.publisher --config <private toml>`. `--once` runs a
   single full reconcile; without it the process watches with inotify and also rescans
   every `rescan_seconds` (default 60) with a `settle_seconds` (default 0.3) debounce.
2. **Scope.** `source` is the local authoring root. Each first-level directory under it
   is a *site* and is mirrored to `site_root/<site>`. The flat `_images` directory is
   mirrored to `image_root`.
3. **Ownership.** Each remote site directory is claimed by writing a private mode-0600
   marker `.dame-curie-publisher-owner` holding `{token, device, inode}`. Creation goes
   through a hidden `.dame-curie-publisher-claim-<uuid>` directory plus
   `renameat2(RENAME_NOREPLACE)`; there is no ordinary-rename fallback. A colliding or
   unmanaged remote directory is **refused**, never adopted or overwritten.
4. **Deletion.** A site sync runs `rsync --delete-delay` with only the ownership marker
   protected (`P`/`H /=.dame-curie-publisher-owner`). The publisher therefore owns the
   **entire** site subdirectory. The `_images` archive sync passes **no** delete flag.
   Deletion is additionally gated to `action == "site"` with a non-empty name and token.
5. **Scan tripwire.** Local scanning refuses symlinks, hardlinks, credential-looking
   content (PEM headers and assignment patterns), and any change detected between two
   passes. The source root's device/inode is pinned and a replacement root is refused.
6. **Remote pinning.** Local state (mode 0600, `flock`-guarded) stores
   `target = [host, user, port, site_root, image_root]`, the source path, the source
   device/inode and both remote root device/inode pairs. The remote guard refuses a
   mismatch, and a marker/token mismatch refuses any directory the publisher does not
   own.
7. **SSH.** `ssh -F /dev/null -i <key>` with `IdentityAgent=none`, `IdentityFile=none`,
   `IdentitiesOnly=yes`, `BatchMode=yes`, `StrictHostKeyChecking=yes`,
   `GlobalKnownHostsFile=/dev/null`, `ClearAllForwardings=yes`, `ForwardAgent=no`, and a
   per-instance `ControlPath=<state>/ssh-%C`. The remote guard is invoked as
   `python3 -I -S -c <guard source> <json>`, changes directory into the target and then
   `execvp`s `rsync`. The remote host needs a `python3` and an `rsync`; it is not a
   Python application server.

## Isolation boundary

Two publisher instances are isolated by **directory**, not by code paths. Each is keyed
on, and must differ in, all of:

- `source`, `staging`, `state` (local, pairwise non-overlapping — `validate()` refuses
  overlap),
- `key` / `known_hosts` (private files, and they must not sit inside a managed root),
- `host`, `user`, `port`, `site_root`, `image_root` — `state.py` refuses to start if any
  of these differs from the saved state, and `validate()` refuses `/` and any
  `site_root`/`image_root` overlap in either direction.

What is **not** enforced in source: there is no notion of "this remote root belongs to
another project". Isolation of the remote destination rests on the operator configuring a
distinct `site_root`/`image_root` and on the ownership markers, which protect only the
subdirectories the publisher itself created. See "Gaps".

## Configuration recipe

The template `scripts/publisher/config.dirac.example.toml` is the recipe. Copy it to
`/srv/dame-curie/dirac/publisher/config/publisher.toml`, set it mode 0600, and make it
owned by the Dirac publisher's service user. Values already fixed for Dirac by the
coordinator:

| Key | Value | Note |
| --- | --- | --- |
| `source` | `/srv/dame-curie/dirac/sites` | Container path `/state/sites`. |
| `staging` | `/srv/dame-curie/dirac/publisher/staging` | Must exist, mode 0700. |
| `state` | `/srv/dame-curie/dirac/publisher/state` | Must exist, mode 0700. |
| (config dir) | `/srv/dame-curie/dirac/publisher/config/` | Holds `publisher.toml` and the key material. |

Values the coordinator must populate with private facts (**no real values are recorded
in this checkout**):

| Key | Must satisfy |
| --- | --- |
| `host` | Remote SSH host. Strict host-key checking is unconditional. |
| `user` | Remote SSH user, readable as an ordinary username. |
| `port` | Remote SSH port. |
| `site_root` | Dirac's own remote site root, outside every other project's subtrees. |
| `image_root` | Dirac's own remote image archive root, disjoint from `site_root`. |
| `key` | Private key file. See the constraint below. |
| `known_hosts` | Host key file for that host. |
| `private_paths` | Local subtrees never to publish. |

**Existing-key constraint.** Reusing the existing publisher SSH key is supported, but
`config.private_file()` requires the configured `key` to be a regular file with
`st_nlink == 1`, mode 0600, owned by the process user. A **symlink or hardlink** to the
dame-curie key is refused, and so is a key owned by another account. Reuse therefore
means a private **copy** placed at the Dirac path with those permissions, or running the
Dirac publisher as the account that already owns the key.

## Authoring workflow

Files are authored **locally**; the publisher copies them out. The model never
administers the remote. There is no site-authoring tool: the shell tool is the only
writer, and the tool contract tells the model to author files locally and not to
administer remote publication.

1. The model's shell runs `bash -lc` with `cwd` and `HOME` both `/home/dame-curie`, which
   is a symlink to the persistent `/state/shell` bind (`bot_tools.py:5455-5462`;
   `docker/app.Dockerfile:25-27`). The authoring root is **not** under `HOME`; reach it as
   `/state/sites` or `"$DAME_CURIE_SITE_DIR"` (`config.py:451`, container value
   `/state/sites`; mount `${INSTANCE_DIR}/sites` → `/state/sites`).
2. Only **first-level directories** of the authoring root become sites. A loose file at
   the top level is skipped entirely (`scan.py:139` restricts file collection to
   `path != Path(".")`) — it is neither published nor treated as a site. `_images` is
   excluded from the site set and refused as a site name.
3. Generated images and their prompt sidecars live in `<root>/_images` and are published
   to `image_root` as a flat archive. Sidecars are `<image stem>.txt`, written
   atomically, and their content is redacted before it is stored
   (`bot_tools.py:1057-1066`).
4. Publish by running the instance once (`--once`) or by leaving the watcher running.
5. Verify locally against the staging tree and the publisher journal. A public URL is not
   evidence that publication succeeded.

Two rules decide most surprises:

- **The publisher owns the whole site directory.** Anything present remotely inside a
  claimed site directory that is not present in the local source is deleted on the next
  sync. Operator-installed files (including `.htaccess`) survive only if they also exist
  in the local source tree.
- **The image archive never deletes.** Removing a local image does not remove the
  archived copy remotely.

Not published: loose top-level files, first-level dotfiles, `_data`, `_build`, `.env`,
`.git`, the ownership marker, `.publisher-link`, and anything under a configured
`private_paths` entry. A dotfile *inside* a site directory **is** published; only
first-level dotfiles are excluded. A credential tripwire refuses the **whole** scan if a
site file contains credential-looking content or a PEM header, so one bad file blocks
publication of every site until it is removed.

## PHP, Perl and CGI on the remote host

The direct human asked whether PHP/Perl/CGI are properly available. The honest answer
from this checkout is **not determined, and not determinable here**.

- `scripts/publisher/static.htaccess` is a static-only template: it sets
  `Options -Indexes -ExecCGI -Includes`, forces `default-handler`, and forces PHP, CGI,
  Perl, Python, shell and ASP extensions to `text/plain`.
- **No file in this repository references, copies or installs it.** A scoped search for
  `htaccess` across the source returns no hit outside the file itself. The existence of
  that template therefore does **not** imply the remote site's effective policy, and
  nothing in the publisher applies it.
- The publisher uploads everything with `--chmod=D755,F755`: published files land mode
  0755, i.e. executable. It transports bytes and permission bits and nothing else. It
  neither enables nor disables server-side execution.
- Nothing in this checkout serves site files at all: the Compose file declares no
  published ports and only `bot`/`ollama`/`ollama-pull`, the bot image installs no PHP,
  Perl or CGI, and no web framework remains in the dependency lock. The remote
  `python3 -I -S -c` the publisher invokes is its rsync transfer guard, not hosting.

Consequence: whether a Dirac site can execute PHP/Perl/CGI is decided by the remote
host's own configuration and by what the operator places in the Dirac remote root — for
example, opting *out* of the static policy by not deploying that `.htaccess`, if the host
honours per-directory overrides at all. None of that is proven by this checkout, and no
executable-hosting mode was added. Verifying the remote capability is a coordinator step.

## Verification

Local checks actually run in this lane are listed in "What was checked" below. The
following remote checks are **proposed for the coordinator**, contain no credentials, and
were **not** run here:

```sh
# Read-only: do the two instances really have distinct remote roots?
ssh -i <private key> -o StrictHostKeyChecking=yes <user>@<host> \
  'stat -c "%d %i %n" <dirac site_root> <dirac image_root> <other project site_root>'

# Read-only: confirm the Dirac roots exist, are directories, and are not symlinks.
ssh -i <private key> -o StrictHostKeyChecking=yes <user>@<host> \
  'ls -ld <dirac site_root> <dirac image_root>; readlink -f <dirac site_root>'

# Read-only: confirm the remote tooling the guard actually needs.
ssh -i <private key> -o StrictHostKeyChecking=yes <user>@<host> \
  'command -v python3; command -v rsync; python3 -V; rsync --version | head -1'

# Read-only: inspect the host's real PHP/Perl/CGI and override policy.
ssh -i <private key> -o StrictHostKeyChecking=yes <user>@<host> \
  'ls -l <dirac site_root>/.htaccess 2>/dev/null; apache2ctl -M 2>/dev/null | head'
```

Local, no credentials:

```sh
systemctl status dirac-publisher.service
journalctl -u dirac-publisher.service -n 50 --no-pager
# Staged tree that will be mirrored, and the pinned ownership state:
ls -la /srv/dame-curie/dirac/publisher/staging/current
cat /srv/dame-curie/dirac/publisher/state/ownership.json
```

`ownership.json` records the pinned `target` and both remote root identities. It is the
local half of the destination binding; compare it against the remote `stat` output above
before concluding that a destination is the intended one.

## Gaps and not-established items

1. **Dirac's remote destination is unverified.** No host, user, port, root or key was
   inspected. Every value in the template marked PRIVATE FACT is still a placeholder.
2. **First-run destination binding is unguarded.** `state.py` refuses a config whose
   `site_root`/`image_root` differs from saved state, but on a *fresh* state directory
   the probe result is adopted as-is and pinned. A copy-paste error in Dirac's
   `site_root` would be accepted on the first run; there is no source-level refusal, by
   the coordinator's decision recorded above. Verify the destination before the first
   write.
3. **Remote PHP/Perl/CGI capability and per-directory override policy are untested**, and
   no executable-hosting mode exists.
4. **The unit is not installed, enabled or started.** Service identity is confirmed by
   the coordinator: it runs as the existing `dame-curie` account with no new service
   account, `WorkingDirectory=/opt/dame-curie`, and the Dirac roots under
   `/srv/dame-curie/dirac`.
5. **No end-to-end mirroring was performed.** Authoring, staging, transfer and remote
   result were not exercised; this lane is source and documentation only.
6. **The unit is not installed, enabled or started**, and the remote folders do not
   exist as a result of this lane.

## What was checked, and how

- Full read of all 15 `scripts/publisher/**` files and all six `tests/test_publisher_*.py`
  files (≈1680 lines) as the intended contract.
- Scoped searches confirming no source references `static.htaccess`, and that
  `eligible()` excludes only first-level dotfiles (so `<site>/.htaccess` is publishable).
- `git status` / `git diff` review of every changed path; `config.py` was reverted to
  `HEAD` after the coordinator's decision and the diff is empty.
- Python 3.14 AST compilation of the changed Python files.

Not performed, and not claimed: no application import, no test collection or execution,
no publisher process, no SSH, no network, no Docker, no `/srv`, `/opt` or private
configuration access. Compilation is not import or runtime acceptance.

**Deployment effects of this lane: none.** Two new unstaged-in-baseline files plus
documentation. No service, container, remote folder or existing configuration was
created, modified or started.
