# Dirac runtime operator (host lifecycle)

Status: **source-only**. Nothing here has been executed: no engine call, no
container, no unit install, no relay start. Every runtime step below is the
coordinator's to run with a fresh account/socket/engine resolution.

## What this lane owns

`scripts/dirac.py` operates one durable debug instance, `dirac-v2`, on the
`dame-curie` account's private rootless engine. It is **host lifecycle only**:
starting the ordinary bot entrypoint with a private derived configuration. It is
not bot-side injection, not a second Discord login and not a replacement
supervisor.

New files: `scripts/dirac.py`, `scripts/dirac_relay.py`,
`docker/dirac-relay.service`, `tests/test_dirac_operator.py`,
`tests/test_dirac_relay.py`. Untouched: `scripts/instance.py`, `compose.yaml`,
`bot.py`, `jobs.py`, publisher files, `config.py`, the Dockerfile and every
smoke-protocol file.

## Parent-created layout (the CLI validates, never creates)

| Path | Mode | Role |
| --- | --- | --- |
| `/srv/dame-curie/dirac` | 0700 | Dirac state root |
| `/srv/dame-curie/dirac/config` | 0700 | bind source for `/config` (read-only) |
| `/srv/dame-curie/dirac/config/prompts` | 0700 | bind source for `/config/prompts` (writable) |
| `/srv/dame-curie/dirac/config/bot.env` | 0600 | Dirac-only derived configuration |
| `/srv/dame-curie/dirac/data`, `sites`, `shell` | 0700 | bind sources for `/state/*` |
| `/srv/dame-curie/dirac/image` | 0600 | optional one-line image selector |
| `/srv/dame-curie/dirac/smoke`, `smoke-status` | 0700 | optional smoke root and status |

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
importing its sibling `instance`/`log_filter` modules.

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

No synthetic catalog and no 235-second time bomb exist in this lane.

## Shared RAG relay (root, separate process)

V2 and V1 are separate rootless engines: neither the host loopback nor the
other engine's bridge is reachable from the Dirac container.

```sh
sudo install -m 0644 docker/dirac-relay.service /etc/systemd/system/dirac-relay.service
sudo systemctl daemon-reload && sudo systemctl enable --now dirac-relay.service
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
and forks the one fixed helper
`nsenter --net=/proc/<pid>/ns/net -- socat - TCP4:127.0.0.1:11434`, capped at 32
live helpers with per-connection re-resolution, so a V1 recreate is followed
rather than cached. Helpers are reaped by polling the live set on the next
connection; there is no signal-handler trickery that could make a failed Docker
call look successful. There is no proxy command, no arbitrary target, no V1
mutation and no published port; the bind lives inside the V2 daemon namespace,
so it is not exposed to the host or the LAN. The unit restarts forever with a
10-second delay, so a daemon that starts later does not leave it permanently
failed.

The relay is a raw TCP forward, so anything that can reach the bridge can speak
to Ollama's full local API, including its unauthenticated destructive endpoints.
Only V2-engine containers can reach it, and that is the coordinator's accepted
trade for the shared RAG design; if that changes, the fix belongs in the
bridge/firewall, not in a request filter here.

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

## Unverified assumptions (coordinator confirms)

1. `172.23.0.1:11434` on `dame-curie_outbound` was observed; the CLI re-derives
   it. If that bridge is recreated with a different subnet, the derived endpoint
   goes stale - `start`/`status` then fail loudly, and recovery is updating
   `bot.env` plus `start --replace`.
2. `{{(index .IPAM.Config 0).Gateway}}` assumes one subnet on that bridge.
3. Reachability from the container's veth to that gateway inside the same
   namespace is design-verified only; the coordinator's exercise must confirm it.
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

`ast.parse`/`compile` of the new modules and tests with the parent checkout's
Python 3.14 venv only. An independent adversarial source review of the diff was
run and its findings are folded in (sibling-import path, read-only smoke root,
smoke path containment, relay helper reaping and cap, engine/target ownership
checks, unit restart policy), followed by the coordinator's own review fixes
(per-account Docker calls with a scrubbed environment, socket/rootless/Docker
root validation, no SIGCHLD trickery, `--pull never`, class-only status text,
`embedding_readiness` naming). No import of the application, no test execution,
no dependency install, no engine or container access.
`tests/test_dirac_operator.py` and `tests/test_dirac_relay.py` are provided
unexecuted and drive scripted engines only.
