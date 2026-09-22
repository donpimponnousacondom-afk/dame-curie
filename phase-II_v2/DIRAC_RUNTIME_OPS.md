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

`DAME_CURIE_SHELL_DIR` is not a `config.py` field (the shell tool reads it
directly, defaulting to `/state/shell`), so it is not required - but if the
derived file sets it, it must be `/state/shell`. Likewise, if present,
`DAME_CURIE_CONTAINER_MODE` must be `true` and `DAME_CURIE_INSTANCE_ID` must be
`dame-curie-dirac`. While RAG is enabled (anything but `0/false/no/off`; absent
means on), `DAME_CURIE_EMBED_BASE_URL` must be exactly
`http://<outbound-bridge-gateway>:11434`. Anything else fails before a container
is created. `DAME_CURIE_EMBED_MODE` is the RAG lane's setting, not this
operator's: if the integrated check needs it, it belongs in this private file,
which the operator passes through untouched.

## Container shape

`dirac-v2`, label `dame-curie.dirac=dirac-v2`, no `dame-curie.instance` label
and no `dame-curie-` name prefix, so the canonical wrapper's `select_owned`
cannot adopt it. `init`, `--user 0:0`, `--restart no`, `--cap-drop ALL`,
`no-new-privileges`, `--memory 4g`, `--pids-limit 256`, `local` log driver,
writable app filesystem and bounded `/tmp` + `/app/temp` tmpfs exactly like the
approved Compose service. No Docker socket, no extra mount, no added capability.

Entry is the reviewed chain `python /opt/dame-curie/check_embeddings.py && exec
python bot.py`; the image's own `HOME=/home/dame-curie` symlink is used as-is.
The container joins the canonical instance's outbound bridge
(`<INSTANCE_ID>_outbound`, labels `com.docker.compose.project`/`network`
validated) and needs no host alias: the integrated in-image check preflights the
configured endpoint, which the CLI requires to be the bridge gateway the relay
binds. Nothing pulls: an image reference is resolved with `image inspect` and the
immutable ID is used, or the command fails.

## Operator interface

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py start  [--image REF] [--replace]
sudo -n -H -u dame-curie -- ... dirac.py status     # JSON; 0 only when running and ready
sudo -n -H -u dame-curie -- ... dirac.py stop       # keeps the container and its evidence
sudo -n -H -u dame-curie -- ... dirac.py restart
sudo -n -H -u dame-curie -- ... dirac.py logs [--no-keys]   # existing follow_logs(format=screen)
```

`start`/`stop`/`restart` serialize on the canonical
`/srv/dame-curie/.operations.lock`, so a Dirac mutation and an `instance.py`
operation fail loudly instead of interleaving. `stop` never removes. `start`
reports an existing owned container's state (status, exit code, OOM flag,
finished time, image) and refuses; recreate needs the explicit
`start --replace` after `logs`. Ownership needs both the reserved label and the
reserved name: a container carrying `dame-curie.dirac=dirac-v2` under any other
name is refused, and a foreign container squatting on the name `dirac-v2`
surfaces as a Docker create conflict rather than as a silent removal. `status`
is read-only: container state, bridge, endpoint, config verdict and the reviewed
embedding readiness; it exits non-zero when the container is absent, stopped,
misconfigured or not ready.

Smoke mounts are opt-in and need smoke-lane confirmation of the host root:
`start --smoke-root HOST` mounts `HOST` read-only at `/dirac-smoke`, so
`/dirac-smoke/config.json` and `/dirac-smoke/requests/` appear as the agent's
from-env parser expects, and sets
`DAME_CURIE_DIRAC_SMOKE_CONFIG=/dirac-smoke/config.json` (a file path).
`start --smoke-status HOST` mounts `HOST` writable at `/dirac-smoke-status`;
there is no second status variable - the runtime settings may carry
`status_path`, which the smoke agent and coordinator agreed to keep inside the
settings object. No synthetic catalog and no 235-second time bomb exist here.

## Shared RAG relay (root, separate process)

V2 and V1 are separate rootless engines: neither the host loopback nor the
other engine's bridge is reachable from the Dirac container.

```sh
sudo install -m 0644 docker/dirac-relay.service /etc/systemd/system/dirac-relay.service
sudo systemctl daemon-reload && sudo systemctl enable --now dirac-relay.service
```

The unit runs `scripts/dirac_relay.py` as root (required for `setns` and
`nsenter`), with `--network dame-curie_outbound`, `--engine-pid-file
/run/user/$(id -u dame-curie)/docker.pid` and `--v1-container
maxwell-curie-ollama-1`. It resolves both service accounts through `pwd`, reads
the gateway from the V2 engine, checks the daemon PID is owned by the V2
account, refuses a namespace identical to its own, `setns` into the V2 daemon's
network namespace and binds only `<gateway>:11434`. Per connection it re-inspects
the V1 container read-only (running, `com.docker.compose.project=maxwell-curie`,
`com.docker.compose.service=ollama`) and forks the one fixed helper
`nsenter --net=/proc/<pid>/ns/net -- socat - TCP4:127.0.0.1:11434`. There is no
proxy command, no arbitrary target, no V1 mutation and no published port; the
bind lives inside the V2 daemon namespace, so it is not exposed to the host or
the LAN. The relay is durable and independent of the bot PID: it survives
Dirac restarts, and a V1 container recreate is followed per connection.

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
4. `/run/user/<uid>/docker.pid` ownership and the namespace/PID mapping were
   verified by the coordinator, not by this lane. `--engine-netns` exists for a
   deployment that has no usable pid file.
5. Readiness assumes the integrated `check_embeddings.py` preflights the
   configured endpoint (the RAG lane's change). On an image that still hardcodes
   `http://ollama:11434`, the entry check and `status` readiness fail loudly -
   that is a stale image, not a silent pass.
6. The smoke host paths and the `status_path` convention need smoke-agent `cf3`
   confirmation; `/dirac-smoke` and `/dirac-smoke-status` are fixed here so both
   lanes can agree on one contract.
7. `check_embeddings.py` skips its probe when `ENABLE_RAG` is false; `status`
   reports that as `skipped`, not as proof of a working relay.

## Validation performed

`ast.parse`/`compile` of the new modules and tests with the parent checkout's
Python 3.14 venv only. No import of the application, no test execution, no
dependency install, no engine or container access. `tests/test_dirac_operator.py`
and `tests/test_dirac_relay.py` are provided unexecuted and use scripted engines
only.
