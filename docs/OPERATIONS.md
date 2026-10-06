# Dirac operations and recovery

## Scope and authority

This is the concise operating contract for the temporary Dirac instance. It is not an activation grant, deployment receipt, or assertion that current runtime state has been re-observed. The coordinator owns any authorized private/runtime checks and decides whether or when temporary normal use may resume, only after the required checks and review. The previous bounded acceptance grant remains distinct: it authorized one labelled test request, not general use. Normal release, canonical Dame/V1 activation, publisher/remote changes and general private inspection are not authorized here.

Use [STATUS.md](STATUS.md) and its linked validation ledger for source checkpoints, QA, and release disposition. Source QA/build status does not establish installed or deployed state. This checkout's current worktree/source checkpoint is recorded there; do not infer it from an older runtime image label. Do not make a fresh runtime claim from the historical receipt below.

## Identity, interpreter, and private roots

Temporary service identity: account `dame-curie`, UID 1005; private rootless engine ID `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`; explicit socket `unix:///run/user/1005/docker.sock`. These are known identity references, not proof the account, socket, or engine still resolves to those values. Before any newly authorized runtime action, re-resolve the account UID and verify the socket is a real socket owned by that account, then verify the rootless engine through that explicit socket. Never fall back to the caller's/default/rootful or another account's engine; on mismatch, missing socket, or permission failure, stop and report.

The operator entrypoint is the root-owned, service-user-non-writable installation `/opt/dame-curie`; resolve and verify its ancestors, interpreter symlink targets and venv metadata remain root-owned and non-writable by the service user before use. The isolated Python 3.14 operator interpreter is `/opt/dame-curie/.venv/bin/python`; it requires the pinned `python-dotenv==1.2.3`. Do not substitute host Python, activate the project environment, or install packages during operation. Use isolated mode and suppress bytecode:

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py status
```

Dirac state is under `/srv/dame-curie/dirac`, separate from canonical `/srv/dame-curie/config` and protected V1 state. Private directories are service-owned mode 0700; `bot.env` and the optional image selector are mode 0600. The application config bind is read-only; only the nested prompts bind is writable. Do not read or print private file contents. Runtime-path checks reject unsafe ownership/modes, symlinked runtime paths, and untrusted inputs; do not work around a refusal by weakening modes or redirecting paths. `/opt/dame-curie` and all writable ancestors/import targets must remain root-owned and not service-user-writable.

## Safe operation and lifecycle commands

Only a separately scoped coordinator runtime grant permits these commands. Re-resolve identity/engine first and inspect current state; a source/documentation task never authorizes them. Forms below are examples of the operator interface, not instructions to execute now:

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py status
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py logs [--no-keys] [--fresh]
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py stop
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py start [--image REF] [--replace] \
  [--smoke-root /srv/dame-curie/dirac/smoke] \
  [--smoke-status /srv/dame-curie/dirac/smoke-status]
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac.py restart
```

`status` is not metadata-only: while RAG is enabled, it performs the configured embedding readiness probe in the container. It does not establish Discord READY or identity. A skipped probe is not readiness. The container uses the reviewed ordinary `python bot.py` entrypoint, `--restart no`, no Docker socket, no additional mount/capability, and immutable local-image resolution with `--pull never`; a missing image fails rather than pulling. Do not add autorestart, pull, or use canonical `instance.py` for Dirac.

`start` refuses an existing owned container unless replacement is explicit. Before any authorized replacement, preserve/inspect evidence with logs and status; replacement emits bounded previous-state metadata to stderr before removing the old container. A stopped container's evidence is retained by `stop`; do not remove it casually or use replacement to hide log history. `restart` accepts **only a running owned container** and retains its Docker log history. It deliberately refuses an exited/stopped container; after preserving its evidence, use an explicitly authorized `start --replace`, not `stop` followed by `restart`. The Dirac lifecycle mutations (`start`, `stop`, `restart`, `--replace`) and canonical `instance.py` operations share `/srv/dame-curie/.operations.lock`; never take an outer lock around these commands or run a second operation concurrently. A stopped or ambiguous target is not a reason to bypass the lock/ownership checks.

The supplied minimum precheck context is low reasoning, 12,345 output cap, REM off, autonomy off, RAG on, and image quality high. The stored server prompt was measured as 1,939 UTF-8 bytes without disclosing its contents. These are not a fresh runtime verification or permission to edit controls. Before any release decision, recheck the current high-detail/image-generator disable controls and prompt byte size; never print prompt text. The prior acceptance changed only a temporary allowed-channel scope and restored original control bytes; it did not grant a broader profile change.

## Derived configuration and shared embeddings

The derived `/srv/dame-curie/dirac/config/bot.env` must retain these structural values:

```text
DATA_DIR=/state/data
DAME_CURIE_SITE_DIR=/state/sites
DAME_CURIE_PROMPTS_DIR=/config/prompts
```

If set, `DAME_CURIE_CONTAINER_MODE=true` and `DAME_CURIE_INSTANCE_ID=dame-curie-dirac` are required. The operator injects structural process variables including `DAME_CURIE_EMBED_MODE=external`, `DAME_CURIE_ENV_FILE=/config/bot.env`, `HOME=/home/dame-curie`, and `TZ=:/etc/dame-curie-localtime`; the derived file is passed through unchanged. With RAG enabled, its effective `DAME_CURIE_EMBED_BASE_URL` must exactly match the current outbound bridge gateway at port 11434. Never guess or reuse a stale gateway address: the operator derives and validates it. `DAME_CURIE_SHELL_DIR` retains its own `/state/shell` default. Readiness is fail-closed and exposes selected endpoint/status metadata, not credentials or an unfiltered configuration dump.

Dirac uses the existing shared Ollama embedding service; it does not run its own Ollama/model-pull. The relay forwards only `POST /api/embed`, `POST /api/embeddings`, and `POST /v1/embeddings`; other paths/methods are rejected locally. This is an endpoint/method boundary, not independent same-UID or model-resource isolation: permitted embedding arguments remain client-controlled and no body-size quota was added. No canonical/V1/shared service mutation, model administration, publisher, remote destination, or activation follows from this contract.

## V2 shell tools and authored-path compatibility

The image retains the measured shell CLI packages, including ordinary Debian Git and its approved normal Perl dependencies, with `--no-install-recommends`. It builds the exact `docker/shell-requirements.lock` packages into `/opt/dame-curie/shell-wheelhouse`, without installing them into app Python or changing `docker/requirements.lock`. Shell tools retain NumPy 2.5.3 and setuptools 78.1.1 (`py-mini-racer` imports `pkg_resources`); app NumPy 2.5.2 and setuptools 84.0.0 remain unchanged. `phply` is a Python parser, not a PHP interpreter or hosting service. No removed hosting features or model-facing tool menu is restored.

The coordinator prepares a fresh persistent shell venv inside the verified V2 image, with only the shell mount, no credentials/data mounts, network disabled and the bot entrypoint overridden. This is explicit preparation, not an image startup bootstrap:

```sh
/usr/local/bin/python3.14 -m venv --copies --system-site-packages /home/dame-curie/.venv
/home/dame-curie/.venv/bin/python -m pip install --no-index --no-deps \
  --find-links /opt/dame-curie/shell-wheelhouse -r /opt/dame-curie/shell-requirements.lock
```

Only shell-command subprocesses prepend `/home/dame-curie/.venv/bin` to their existing minimal PATH; the app interpreter, CMD and environment remain unchanged. This explicitly approved shell venv shares app site-packages while its pinned tools take precedence. Copies avoid the old absolute interpreter symlink rejected by restore. Do not transplant the old empty `.venv`, `.ssh`, Ubuntu `/usr` or incidental vendor/platform packages. The coordinator must verify native wheels, offline installation and backup/restore admissibility; source changes alone establish none of those results.

Preserve authored scripts/docs byte-for-byte: image-internal `/home/maxwell` and `/home/dame-curie` both point to `/state/shell`. The former is authored-path compatibility with V2 shell state, not alternate data ownership, an old environment alias or a V1/host mount. File-tool confinement is unchanged; use canonical `/home/dame-curie` paths for attachments.

## Smoke requests and receipts

The smoke harness is opt-in and scoped to the approved test channel or a bot-owned thread within it. The bot-authored notice names the test, says no human typed the request, mentions the bot and makes clear that permission actor and text author differ. Injection uses the configured real SDK user as permission actor; notice author remains the bot and is preserved as provenance. Normal bot enable/blacklist/allowlist/sleep gates still apply. Never impersonate a human gateway message or describe a smoke task as a human request.

Submit requests on the host because the request mount is read-only in the container. The CLI forms are:

```sh
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac_smoke.py --config /srv/dame-curie/dirac/smoke/config.json submit --task 'LABELLED TEST TASK'
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac_smoke.py --config /srv/dame-curie/dirac/smoke/config.json result REQUEST_ID
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac_smoke.py --config /srv/dame-curie/dirac/smoke/config.json pending
sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B \
  /opt/dame-curie/scripts/dirac_smoke.py --config /srv/dame-curie/dirac/smoke/config.json health
```

A request is immutable and exclusively created; its terminal receipt belongs with that request. Keep both request and receipt together: deleting receipts alone can make old requests eligible to run again. A deadline covers resolution, notice, injection and turn. On expiry, only that input is cancelled. A known registered task that fails to stop blocks the next request until that exact task exits. When no owned task exists and stop cannot be confirmed, the worker stops polling and publishes `stop_unconfirmed`; it cannot wait on an invented task or silently resume. Do not call either outcome settled or launch another request around it.

`health`, `pending`, and a missing `result` receipt are advisory only. The snapshot can be stale/unavailable; `worker_liveness` is always `unknown`; `no_record` does not prove a request never ran or that a worker is healthy. A terminal `completed` record requires returned turn, usable output from its own model call, and a non-notice delivery to the target channel. It does not certify that the task goal was met; `reply_verified` remains false. Do not clear status storage to recover service or replay requests.

## Logs and viewer recovery

Dirac's `dirac.py logs` uses append-only `screen` mode; it has no `--format` option. The separate canonical `instance.py logs` interface selects `screen`/`console`/`auto`/`plain`/`jsonl` with `--format`; canonical operation remains held. Append mode preserves Screen scrollback without repainting or alternate-screen entry; `--no-keys` disables its keyboard controls. Do not apply append-mode keys to the interactive console. In append mode, `q`/Ctrl-C exits the viewer/follower, not the bot; unmarked pasted ASCII can trigger keys, so choose `--no-keys` where paste safety matters.

**Retained policy: an oversized record latches evidence off until viewer restart**, not merely until its newline. The record is discarded with an omission notice; lost redaction continuity means all subsequent records are omitted. This fail-closed behavior also applies to the affected canonical interactive viewer paths, not only Dirac's append viewer. Incomplete terminal-control input disables keyboard dispatch until viewer restart; Ctrl-C still exits. Dirac's `--fresh` requests tail zero to avoid replaying retained poisoned history (it is not a canonical `instance.py` option); it does not delete logs, repair the redaction chain, or clear the evidence latch in an already-running viewer. Restart the viewer after continuity loss and use `--fresh` when replaying old records is unsafe. A new viewer can tail a replacement container; old logs need authorized private preservation before replacement. The viewer does not automatically follow a recreated container, and history is not proof of successful operation.

When using persistent GNU Screen, Screen must own an interactive Bash; run the logger as a foreground command inside Bash, not as Screen's sole process. This keeps a shell available after viewer exit. Canonical variants, viewer event details and source limits are summarized in [STATUS.md](STATUS.md); current log/viewer source is not evidence of installation or runtime acceptance. The host viewer was not installed or exercised in the current round; do not claim otherwise.

## Jobs and intentional limits

Background jobs persist metadata, but unfinished workers are cancelled on bot restart; they do not resume. A provider-file warm reload waits for active jobs to finish. Parent allowance and explicit parent block both gate sibling progress-thread creation; refusal or thread-creation failure leaves job output in the allowed origin thread, and the job can continue. A missing progress thread is not itself proof the job failed. No broader job-resumption guarantee exists.

Separate account/engine identity is only one boundary. It does not prove isolation of same-UID state, host resources, remote credentials, or shared embedding resource residency. Smoke delivery/readback, readiness, focused QA, and dated identity receipts each establish only their stated scope. Do not infer full feature, sustained-load, voice, media, replica, or whole-repository acceptance. See [STATUS.md](STATUS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) for current status and boundaries.

## Dated runtime and rollback reference — historical, not current

Last specified old-runtime observation: container `495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, image `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`, source label `6859025`, started `2026-09-25T12:30:41Z`. Account `dame-curie` UID 1005, socket `/run/user/1005/docker.sock`, engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`. Temporary Discord identity `1504398705539944560`; canonical Dame identity `1545541390392369165`; root identity `1482143139828596916`; smoke channel `1550960386939817984`; temporary command prefix `?`. This is a dated recorded observation, not a fresh inventory, current release assertion, or activation instruction. Current source checkpoint, QA and completed temporary-only release decision are linked in [STATUS.md](STATUS.md).

The earlier private rollback root `/var/backups/dame-curie-dirac/audit-acceptance-20260925T121644Z/` is retained. Current round-two rollback evidence is `/var/backups/dame-curie-dirac/round2-release-20260925T163646Z/`, with opaque original controls/selector and stopped-container logs. The accepted image is now running on temporary Dirac with its original controls; current container, identity, selector and smoke result are in STATUS/09-CLOSURE, not the old-runtime snapshot above. Preserve it and do not print/read private contents or restore stale controls. Rollback is coordinator-only, image-only unless specifically authorized otherwise; do not casually overlay historical state. Keep each smoke receipt with its request.

Temporary historical operating contracts were retired after their unique contracts were migrated. For source recovery only, `git show eb188ac:phase-II_v2/<name>` retrieves an older dated file; that historical content is evidence, not current state or operating authority. `git show eb188ac:phase-II_v2/SESSION_LOG.md` recovers the verbatim prior human grant; later delegation is quoted in [AGENTS.md](../AGENTS.md). External publishing remains outside this runbook; see [PUBLISHING.md](PUBLISHING.md).