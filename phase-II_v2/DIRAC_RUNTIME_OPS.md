# Dirac runtime operator (host lifecycle)

Host lifecycle reference. Current deployment and dated checks are recorded in
`DIRAC_HANDOFF.md`; this document is not itself an activation grant. Re-resolve
the mapped account, socket and engine before an authorized operation.

## What this lane owns

`scripts/dirac.py` operates one durable debug instance, `dirac-v2`, on the
`dame-curie` account's private rootless engine. It is **host lifecycle only**:
starting the ordinary bot entrypoint with a private derived configuration. It is
not bot-side injection, not a second Discord login and not a replacement
supervisor.

Implementation: `scripts/dirac.py`, `scripts/dirac_relay.py` and
`docker/dirac-relay.service`. The Dirac publisher has its own unit. Canonical
lifecycle and Compose configuration are not changed by this hardening.

## Operator installation and parent-created runtime layout

| Path | Mode | Role |
| --- | --- | --- |
| `/opt/dame-curie`, including `.venv` | root-owned; not service-user writable | Operator code/interpreter installation; deployment invariant, not a `require_private` runtime-root check |
| `/srv/dame-curie/dirac` | 0700 | Dirac state root |
| `/srv/dame-curie/dirac/config` | 0700 | bind source for `/config` (read-only) |
| `/srv/dame-curie/dirac/config/prompts` | 0700 | bind source for `/config/prompts` (writable) |
| `/srv/dame-curie/dirac/config/bot.env` | 0600 | Dirac-only derived configuration |
| `/srv/dame-curie/dirac/data`, `sites`, `shell` | 0700 | bind sources for `/state/*` |
| `/srv/dame-curie/dirac/image` | 0600 | optional one-line image selector |
| `/srv/dame-curie/dirac/smoke`, `smoke-status` | 0700 | optional smoke root and status |

The operator installation invariant includes writable ancestors, `pyvenv.cfg` and the resolved `bin/python` target; Python 3.14's `-S` does not remove that trust. The September 22 ownership receipt is in `DIRAC_INTEGRATION.md`; this layout entry is not a fresh runtime observation. The CLI validates the parent-created runtime roots below rather than creating them.

`require_private` from `scripts/instance.py` enforces owner and mode: no group
or other bits beyond execute on directories, so 0750 fails. Credentials are
never copied from `/srv/dame-curie/config/bot.env`; the CLI reads only Dirac's
own derived file, and never prints a value, an environment dump or a secret.

### Derived-config contract

Required in `config/bot.env`, exact values:

```
DATA_DIR=/state/data
DAME_CURIE_SITE_DIR=/state/sites
DAME_CURIE_PROMPTS_DIR=/config/prompts
```

If present, `DAME_CURIE_CONTAINER_MODE` must be `true` and
`DAME_CURIE_INSTANCE_ID` must be `dame-curie-dirac`. While RAG is enabled
(anything but `0/false/no/off`; absent means on), `DAME_CURIE_EMBED_BASE_URL`
must be exactly `http://<outbound-bridge-gateway>:11434`. Anything else fails
before a container is created. `DAME_CURIE_SHELL_DIR` is the shell tool's own
setting with its own `/state/shell` default, so this operator neither requires
nor validates it.

`DAME_CURIE_EMBED_MODE=external` is a structural container variable, not a
credential: the integrated readiness check reads process environment only, so
the operator injects it alongside `DAME_CURIE_CONTAINER_MODE`,
`DAME_CURIE_INSTANCE_ID`, `DAME_CURIE_ENV_FILE=/config/bot.env`,
`HOME=/home/dame-curie` and `TZ=:/etc/dame-curie-localtime`. The full derived
`bot.env` stays a read-only bind and is passed through untouched.

## Container shape

`dirac-v2`, label `dame-curie.dirac=dirac-v2`, no `dame-curie.instance` label
and no `dame-curie-` name prefix, so the canonical wrapper's `select_owned`
cannot adopt it. `init`, `--user 0:0`, `--restart no`, `--cap-drop ALL`,
`no-new-privileges`, `--memory 4g`, `--cpus 4`, `--pids-limit 256`,
`--stop-timeout 45`, `local` log driver, writable app filesystem and bounded
`/tmp` + `/app/temp` tmpfs exactly like the approved Compose service. No Docker
socket, no extra mount, no added capability.

Entry is the reviewed chain `python /opt/dame-curie/check_embeddings.py && exec
python bot.py`, so a broken embedding path blocks the start instead of being
discovered after login; the image's own `HOME=/home/dame-curie` symlink is used
as-is. The container joins the canonical instance's outbound bridge
(`<INSTANCE_ID>_outbound`, labels `com.docker.compose.project`/`network`
validated) and needs no host alias: the integrated in-image check preflights the
configured endpoint, which the CLI requires to be the bridge gateway the relay
binds. Nothing pulls: an image reference is resolved with `image inspect` to its
immutable ID and the create carries `--pull never`, so a vanished image fails
loudly instead of being fetched.

## Operator interface

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py start  [--image REF] [--replace] \
  [--smoke-root /srv/dame-curie/dirac/smoke] [--smoke-status /srv/dame-curie/dirac/smoke-status]
sudo -n -H -u dame-curie -- ... dirac.py status     # JSON; 0 only when running and embedding-ready
sudo -n -H -u dame-curie -- ... dirac.py stop       # keeps the container and its evidence
sudo -n -H -u dame-curie -- ... dirac.py restart
sudo -n -H -u dame-curie -- ... dirac.py logs [--no-keys]   # existing follow_logs(format=screen)
```

`-I` is safe here: the operator restores its own script directory before
importing its sibling `instance`/`log_filter` modules. Invoked as root, the
operator re-executes **its own** script as the service account (the shared
`service_account(entrypoint=...)` helper, whose default keeps `instance.py`
re-entering itself), so `sudo ... dirac.py status` stays in `dirac.py` instead of
being handed to the canonical wrapper's parser. The operator venv must provide
`python-dotenv` - the image lock pins `python-dotenv==1.2.3`, and the staged
operator venv was given exactly that package; without it the operator fails at
import rather than doing anything.

`start`/`stop`/`restart` serialize on the canonical
`/srv/dame-curie/.operations.lock`, so a Dirac mutation and an `instance.py`
operation fail loudly instead of interleaving. `stop` never removes. `start`
reports an existing owned container's state (status, exit code, OOM flag,
finished time, image) and refuses; recreate needs the explicit
`start --replace` after `logs`, and that replacement writes the same bounded
previous-state JSON to **stderr** immediately before the removal, so stdout
stays the machine-readable result of the command. Ownership needs both the
reserved label and the
reserved name: a container carrying `dame-curie.dirac=dirac-v2` under any other
name is refused, and a foreign container squatting on the name `dirac-v2`
surfaces as a Docker create conflict rather than as a silent removal. `status`
is read-only: container state, bridge, endpoint, config verdict and the reviewed
embedding check; it exits non-zero when the container is absent, stopped,
misconfigured or not ready. Its `embedding_readiness` field means exactly that -
a running container whose embedding path works - and is **not** Discord
readiness; the coordinator confirms the actual temporary identity on the first
turn. A bad derived configuration is reported as a fixed reason class and a
failed embedding check as its exit code only, so no configuration value, URL or
credential can appear in `status` output; investigate a failure privately.

### Smoke mounts

Both flags are start-only and opt-in; each host path must be a real private
directory **inside the Dirac state root**, so canonical configuration can never
be mounted into or written from this container.

* `--smoke-root /srv/dame-curie/dirac/smoke` -> read-only at `/smoke`, giving
  the agent `/smoke/config.json` and `/smoke/requests/`, with container
  variable `DAME_CURIE_DIRAC_SMOKE_CONFIG=/smoke/config.json` (a file path).
* `--smoke-status /srv/dame-curie/dirac/smoke-status` -> writable at
  `/smoke-status`. No second variable exists; the settings object carries the
  status location as `status_dir='../smoke-status'`, resolved from the config
  file's parent so both lanes agree on one host pair.

The writable status path cannot be the Dirac root or overlap the read-only
configuration or smoke-request tree in either direction. Comparisons resolve
both sides, so `..` spelling does not bypass the boundary; symlinked paths are
refused by the private-path checks.

These checks are not a dedicated-directory allowlist: existing writable `data`, `sites` or `shell` sources can still be selected when they do not overlap a read-only source. The read-only `--smoke-root` does not run the writable-root rejection loop. Operators must use the dedicated pair shown above, not a broad Dirac root or unrelated state directory; this records the current limitation, not a newly tightened mount policy.

## Shared RAG relay (root, separate process)

V2 and V1 are separate rootless engines: neither the host loopback nor the
other engine's bridge is reachable from the Dirac container.

```sh
sudo install -m 0644 docker/dirac-relay.service /etc/systemd/system/dirac-relay.service
sudo systemctl daemon-reload && sudo systemctl start dirac-relay.service
```

The unit runs `scripts/dirac_relay.py` with the operator venv interpreter as
root (required for `setns` and `nsenter`), with `--network dame-curie_outbound`,
`--engine-pid-file /run/user/$(id -u dame-curie)/docker.pid` and
`--v1-container maxwell-curie-ollama-1`. Only the relay process itself keeps
host root; every Docker call it makes runs as the mapped service account through
`runuser` with a scrubbed environment (`env -i`, `HOME`, `PATH`,
`DOCKER_CONFIG=/nonexistent`) and an explicit `--host` for that account, so no
root client and no inherited Docker context can leak in. Each account's socket
is checked as a real, unsymlinked socket owned by that account, and its `info`
must report rootless plus its own expected `DockerRootDir`; `--v2-engine-id` and
`--v1-engine-id` optionally pin each engine identity, and there is no fallback
engine. It then validates the bridge's compose project/network labels, reads its
gateway, resolves the daemon PID (owning account checked, or an explicit
`/proc/<pid>/ns/net` whose PID must be owned by that account), refuses a
namespace identical to its own, `setns` into the V2 daemon's network namespace
and binds only `<gateway>:11434`. Per connection it re-inspects the V1 container
read-only (running, `com.docker.compose.project=maxwell-curie`,
`com.docker.compose.service=ollama`, and the resolved PID owned by V1's account)
and starts a fixed `nsenter --net=/proc/<pid>/ns/net -- python -I -S -B`
standard-library pipe helper aimed only at `127.0.0.1:11434`. At most 32 connection
workers run. Lookup failures return 503 for that connection; the accept loop
survives a disconnected client. Client reads time out after 60s idle, Docker
queries after 30s, and upstream socket waits after 180s (the readiness probe's
existing timeout). These are relay transport bounds, not migrated V1 controls.

Only **POST `/api/embed`, `/api/embeddings`, `/v1/embeddings`** are forwarded.
Methods and paths outside that set receive local 405/403 responses. Strict header
validation prevents line-injection; framing becomes one Content-Length and
Connection: close. Exactly one request body is streamed and any pipelined bytes
are discarded. Transfer-Encoding is refused with 411; Expect handshakes with
417. The configured JSON clients use Content-Length. Body/query/auth values are
not replaced, and no body-size cap was invented.

The daemon PID, process start time and namespace are checked before every accept,
including under continuous traffic; idle checks occur every 5s. A stale binding
exits 75 so systemd restarts in the current namespace. The unit uses `-I -S -B`
and restarts after 10s. Temporary deployment does **not** enable it for boot.

This is an endpoint boundary, not independent model/resource isolation: permitted
embedding arguments remain client-controlled. It blocks administrative routes,
but does not claim embeddings cannot affect backend resource residency. The old
full-API exposure was not an accepted trade; it was a defect addressed here.

## Known interaction with canonical teardown

A Dirac container holds an endpoint on `dame-curie_outbound` in **any** state,
running or stopped, so Docker refuses to remove that bridge while `dirac-v2`
exists: canonical `instance.py dame-curie down` cannot complete until the debug
container is removed. Capture evidence first (`dirac.py logs`, `dirac.py
status`), then remove the container (`docker rm dirac-v2`, or
`dirac.py start --replace` when a replacement is wanted).

## Old launcher defects this replaces

| Old launcher | Now |
| --- | --- |
| tmpfs wipe of `/config`, `/state` | durable binds from `/srv/dame-curie/dirac` |
| 22-key whitelist injecting a provider packet | complete private `bot.env`, no injection |
| supervisor `rm --force` in `finally` losing crash evidence | `stop` keeps it; `--replace` reports state first |
| relay tied to the bot PID | root systemd unit, per-connection V1 PID resolution |
| `-c` program with monkeypatched events and a temporary identity | ordinary `python bot.py` |
| read-only `/` probe with `--user 0:0` tmpfs config | writable app filesystem like normal Compose |

## Deployment-specific checks

1. `172.23.0.1:11434` on `dame-curie_outbound` was observed; the CLI re-derives
   it. If that bridge is recreated with a different subnet, the derived endpoint
   goes stale - `start`/`status` then fail loudly, and recovery is updating
   `bot.env` plus `start --replace`.
2. `{{(index .IPAM.Config 0).Gateway}}` assumes one subnet on that bridge.
3. Reachability and HTTP policy must be checked on the deployed relay revision;
   an earlier raw-TCP success is not evidence for the replacement filter.
4. The daemon PID file, its ownership and the namespace mapping were verified by
   the coordinator, not by this lane. The relay's per-connection V1 PID check
   assumes V1 container PIDs are visible in the host PID namespace with V1's
   account as owner - true for the engines observed here, and a hard failure
   (refused connections, journal line) if that ever stops holding.
5. Readiness assumes the integrated `check_embeddings.py` preflights the
   configured endpoint and reads `DAME_CURIE_EMBED_MODE` from process
   environment. On an image that still hardcodes `http://ollama:11434`, the entry
   check and `status`'s `embedding_readiness` fail loudly - that is a stale
   image, not a silent pass. Neither result says anything about Discord; the
   coordinator verifies the real temporary identity on the first turn.
6. `check_embeddings.py` skips its probe when `ENABLE_RAG` is false; `status`
   reports that as `skipped`, not as proof of a working relay.
7. Readiness polling can overshoot `READY_TIMEOUT` by one check attempt, because
   a single in-image attempt has its own 180-second request timeout.
8. Engine identity is not pinned by default: the shipped unit relies on account,
   socket, rootless and `DockerRootDir` checks, and `--v2-engine-id` /
   `--v1-engine-id` exist for a deployment that wants the observed IDs
   (`12fb714d-...` V2, `91b4c99d-...` V1) enforced explicitly.

## Validation performed

At `65fe79e`, the coordinator ran **341 focused tests** in the frozen Python
3.14.4 QA image, with no network, credentials or private mounts. Selected Ruff
F821/F822/F823 checks passed with target `py314`. Relay tests exercise the real
parser and pipe helper against an isolated loopback stand-in; namespace retirement
uses synthetic lifecycle checks, not a live V1/V2 daemon restart.

Three extra, unchanged test files produced 19 failures which reproduced on
baseline `eca42e0` (incomplete mention/instance doubles and an old backup identity
assertion). They remain outside the 341-pass claim. No whole-repository green
claim is made. Deployment, real embedding replies and identity receipts belong
in `DIRAC_HANDOFF.md` / `DIRAC_INTEGRATION.md`.
