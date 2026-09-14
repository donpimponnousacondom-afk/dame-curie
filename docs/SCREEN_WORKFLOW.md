# Dame Curie — shared Screen and container operations

Read [STATUS.md](STATUS.md) for verified runtime state and [DOCKER.md](DOCKER.md) for the isolation boundary. Root authorized the host-native → private-rootless cutover. The original `152732.dame_curie` session was retained during rollout, but later disappeared. At root's request, `1292921.dame_curie` was launched with the filtered log follower in window0; no other Screen session/display was displaced.

## Current process ownership

- Exactly one real identity: Compose project `maxwell-curie`, service user `maxwell-curie`, private engine `/run/user/1003/docker.sock`.
- The source-only operational checkout is `/opt/maxwell`. The development checkout remains `/home/codexy/Dame_Curie/Maxwell-bot`; do not run its legacy `./run.sh` alongside Compose.
- Screen hosts the Compose log follower under the existing advisory `/tmp/dame-curie-maxwell.lock`. Starting or refreshing that view does not start/restart the bot. The bot runs in its rootless container, not as a host Python child of Screen.
- The lock discourages the old wrapped launch but is not a universal supervisor. Direct host Python execution bypasses it. Never delete the lock file or launch a second copy of these credentials/state.
- Rootless Docker uses its per-user systemd unit and lingering. Container restart policy, not Screen, owns recovery. Root authorizes routine development restarts after commits or explicitly requested pushes, even for documentation-only changes, to refresh checkout-at-boot. Rebuild/select a new image for application changes; documentation-only changes can restart the existing image.

The logging-only Screen command is:

```sh
flock -n /tmp/dame-curie-maxwell.lock sudo -n /usr/local/bin/python3.14 -B /opt/maxwell/scripts/instance.py curie logs
```

Use the separate lifecycle commands below when the stack actually needs starting. `up` waits for configured service health; independently verify Discord/provider startup and the dashboard's fresh Discord snapshot. A successful `screen -X stuff` only proves input delivery.

## Join without displacing root

```sh
screen -ls
screen -x dame_curie
screen -S dame_curie -Q windows
```

| Keys | Effect |
| --- | --- |
| Ctrl-a d | Detach your display; containers and log follower continue |
| Ctrl-a [ | Enter scrollback; Esc exits |
| Ctrl-a 0 | Select existing window 0 |
| Ctrl-c | Stop the foreground log follower, **not the containerized bot** |

Do not use `screen -d -r`, kill the window/session, or type concurrently with another operator. Logs can contain private conversations; do not dump scrollback into chat/Git.

## Log views and local controls

`logs` defaults to `--format auto`: a full-screen console only when both input and output are TTYs and the terminal provides the required capabilities. `--format console` uses the same noninteractive fallback. `--format plain` forces the original coalesced stream; `--format jsonl` emits one normalized, redacted JSON object per received line without coalescing. JSONL is a stream, not an automatically created archive. Check [STATUS.md](STATUS.md) for the installed rollout milestone.

| Console key | Effect |
| --- | --- |
| `s` / `b` / `p` / `d` | Toggle system / bot / provider / Discord scopes independently |
| `t` / `c` / `w` / `a` | Toggle tool / context / web / positively identified subagent scopes |
| `T` / `P` | Cycle tool / provider detail: 0 summary, 1 metadata, 2 full |
| `f` | Fold/unfold live details; **subagents remain folded** |
| `+` / `-` | More / less local display verbosity; cannot create un-emitted DEBUG records |
| `r` / `e` | Recent 20-row window / retained errors; these lists ignore live filters |
| `[` / `]` | Select an older / newer retained entry |
| Enter | Inspect the selected history entry, including its complete admitted prompt/trace; without selection, first opens the list |
| `n` / `N` | Next / previous evidence or help page |
| Esc | Return to live view |
| `i` | Inspect **local console state only**; no bot/container/provider probe |
| `0` / `?` | Reset local controls without clearing history / show help |
| `q` / Ctrl-c | Exit the follower only; Curie continues running |

- Timestamps are always shown for visible events. Compact live clocks use `P` (producer), `P?` (producer timezone unspecified), `D` (Docker) or `O` (observed/collection time). Full dates, original precision and timezone provenance remain in selected evidence and JSONL; do not identify a startup epoch from time-of-day alone.
- Core Compose producers inherit the host timezone through a read-only timezone file. Older naive `P?` records remain exactly as emitted; Docker/collection UTC facts are not rewritten. The viewer does not guess a timezone for historical or separately configured producers.
- Colors decorate timestamps. `NO_COLOR` disables colors, not controls. Through sudo, set it in the privileged command environment, for example `sudo -n /usr/bin/env NO_COLOR=1 /usr/local/bin/python3.14 /opt/maxwell/scripts/instance.py curie logs`. The logs-only service-user reexec preserves `TERM`, the presence of `NO_COLOR` and no-bytecode behavior—not arbitrary caller environment variables or credentials.
- History retains up to 500 line-records and 2MiB of serialized evidence, evicting whole entries/error groups. Oversized events and partial/evicted traces are explicitly marked. The TTY reader also discards a physical input record over 2MiB with an explicit omission notice; JSONL mode is independent of that input limit. These are evidence/input bounds, not a total-process RSS promise.
- Screen scrollback is not a log archive for this repainting view. Use `r`/`e` and selected-history paging; use bounded original Docker history for evicted/omitted material. Successful Ollama health repetitions are coalesced only in live presentation; admitted history still records them individually.
- Error history includes explicit failed image outcomes, known HTTP failures and parser diagnostics as well as logged errors/tracebacks. A console parse error is not automatically a bot incident. The existing private `!error N` incident store is separate.
- Only positively attributed worker records get the always-folded policy. Existing provider/tool descendants without job identity are not guessed into that scope. `f`, verbosity and depth controls never expand recognized subagents in live/list views; explicit selected-history inspection can.
- All layers remain private: normalized evidence is credential-redacted and terminal-safe, not byte-identical raw Docker output and not guaranteed to recognize every opaque secret. Never dump a JSONL capture, prompt, trace or Screen buffer into chat/Git. Use private captures and sanitized handoffs.

For extensions, `scripts/log_console/recognizers.py` owns envelope/event recognizers, `scopes.py` owns metadata attribution, and `render.py` owns summary renderers and presentation. History/grouping, paging/input and terminal ownership are separate modules. Add synthetic fixtures for a new producer instead of guessing ownership/severity from arbitrary prompt words. The repository skill `curie-readonly-debug` documents read-only incident handoffs.

## Stop, start, restart

Use another terminal, or stop the log follower with Ctrl-c before typing in Screen:

```sh
sudo -n /usr/local/bin/python3.14 /opt/maxwell/scripts/instance.py curie stop
sudo -n /usr/local/bin/python3.14 /opt/maxwell/scripts/instance.py curie start
sudo -n /usr/local/bin/python3.14 /opt/maxwell/scripts/instance.py curie restart
```

- `stop` quiesces bot/API before owned shell/sites/web/Ollama; state and containers remain.
- `start` and `up` are exact aliases: same full Compose startup, including Ollama, same ownership/operation-lock checks, same health wait. Either works after `stop` or when dependencies are not running.
- `restart` reconnects **only bot/API** to reload private configuration; it does not start stopped Ollama/web dependencies. Do not use it to recover a fully stopped stack—use `up`. Coordinate it; autonomous work can resume.
- `down` also removes owned containers/networks, not persistent state or the model volume. Shell packages outside its mounted workspace are disposable.
- `logs` first replays the last 100 Compose log lines, including earlier process failures, then follows new output. Successful localhost Ollama `HEAD /` and `POST /api/show` health checks are coalesced into bounded30-second repeat summaries showing the latest original occurrence; first occurrences, errors, non200 responses and other traffic remain visible. Raw Docker logs and health-check cadence are unchanged. Compare failures with current container start times before concluding a recovered service is still broken.
- To refresh only the console after updating the log filter, stop the verified log follower with Ctrl-c and run `flock -n /tmp/dame-curie-maxwell.lock sudo -n /usr/local/bin/python3.14 -B /opt/maxwell/scripts/instance.py curie logs` in the same window. This does not run `up`, reconnect the bot or create another Screen session.

No host PM2 commands, rootful Docker fallback, direct host `python bot.py`, or duplicate deployments writing the same state. The wrapper verifies identity, private socket, source-path ownership labels and a per-instance operations lock. Do not mix it with concurrent direct Docker lifecycle commands.

## Dashboard and private files

Dashboard: `http://localhost:8081/admin/`, using the original dashboard username/password. Only loopback is published. For a remote host, forward it with `ssh -L 8081:127.0.0.1:8081 codexy@YOUR_HOST`.

- Private runtime configuration: `/srv/maxwell/curie/config/bot.env`.
- Live personality/server prompts: `/srv/maxwell/curie/config/prompts/`.
- Memory and runtime state: `/srv/maxwell/curie/data/`.
- Selected application/web images and latest verified startup: see [STATUS.md](STATUS.md). This operating guide is not an image selector; do not deploy an older tag copied from historical rollout notes.
- Edit `/srv/maxwell/curie/config/bot.env`, not the development checkout `.env`, for live credentials/provider settings. Bot/API restart is required while dependencies are running; after a full stop use `start`/`up`. Rollouts preserve root's current settings; historical provider snapshots are not configuration authority. Save and close root-owned editors before state backup: unreadable swap files in this directory intentionally make the rootless backup fail; do not delete recovery files or weaken permissions to bypass this.
- Live `!reasoning`/`!effort` changes do not require restart. Current image profiles use the local proxy's private bridge address, not container loopback; see [image configuration and proxy recreation](CONFIGURATION.md#independent-normal-and-hd-image-configuration). No dashboard UI changes were part of this rollout.

Do not paste credentials, process environments, raw memory, or container environment arrays into diagnostics. Generated-site public URLs remain loopback-only until root configures an approved TLS origin.

## Rollback and history

The tested same-identity restore procedure is in [DOCKER.md](DOCKER.md#backup-and-restore). It requires all owned containers removed and four **empty** target state directories; never overwrite a running/nonempty target. Reapply mapped-site ACLs and verify health after restoration.

The deferred incident rollout exposed one existing external interpreter symlink. Its raw `/srv/maxwell-backups/curie/pre-incidents-e306a22.tar` is preserved but **does not pass the standard restorer's validation**; the old build was restarted without restoring any data. For a compatibility snapshot, retain raw archive, strict derived tar, companion metadata and tested adapter together. Follow the [exact interpreter-link procedure](DOCKER.md#exact-interpreter-link-compatibility), including pair validation and link reconstruction only after complete extraction. Never treat the derived tar alone as a full backup, delete the live link, or restore an older snapshot over current state. See STATUS for the actual latest cutover and fresh backup evidence.

- Latest pre-numeric/incident rollout: raw `/srv/maxwell-backups/curie/pre-incidents-c010a37.tar`, strict derived `/srv/maxwell-backups/curie/pre-incidents-c010a37-compat.tar`, companion `/srv/maxwell-backups/curie/pre-incidents-c010a37-compat-link.json`, tested operator/reconstruction source `/srv/maxwell-backups/curie/recovery-c010a37/`. All are required for the documented complete two-artifact recovery. Private prior config/control/source, state hashes and managed-image manifest: `/srv/maxwell-rollback/curie/incidents-c010a37/`. Previous working image `maxwell-app:36e5eab` is retained. No data was restored during cutover. An old-image rollback after root changes effort to an integer needs explicit review: that older provider rejects numeric controls; do not silently overwrite root's new setting.
- Earlier pre-formatting-rollout state: `/srv/maxwell-backups/curie/pre-formatting-36e5eab.tar`; private prior config/control/source: `/srv/maxwell-rollback/curie/formatting-36e5eab/`. Prior working app `36122a4` is retained. This rollout changed no private settings; preserve the currently authorized settings and credentials during any rollback.
- Earlier pre-capability-rollout state: `/srv/maxwell-backups/curie/pre-capabilities-36122a4.tar`; private prior config/control/source: `/srv/maxwell-rollback/curie/capabilities-36122a4/`. Prior app `677d2e4` is retained. Keep `usage` disabled when reverting to that old implementation: it sends the chat key to an unrelated gateway. Never restore a superseded key after root rotates credentials; use the current ledger and an explicitly reviewed rollback.
- Earlier image-repair state: `/srv/maxwell-backups/curie/pre-images-677d2e4.tar`, with private `/srv/maxwell-rollback/curie/images-677d2e4/`. The older `99fd7fa` image additionally requires HD disabled because of its unsafe image routing/retry behavior.
- Historical pre-login state: `/srv/maxwell-backups/curie/pre-login-01e8cbb.tar` (mode 0600, credentials included).
- Original private state/config and starting source: `/srv/maxwell-rollback/curie/pre-cutover/` (root-only). Deployment image/settings are recorded separately there because normal state backups exclude `deploy.env`.
- Original host data, configuration and Python 3.13.5 venv remain in place. Do **not** run the new Python 3.14 source with that old venv. A host-native rollback requires deliberately restoring the matching archived source after stopping Compose; it is not an automatic fallback.
- The complete previous Screen contract and dated PIDs remain in Git at `96b4803:docs/SCREEN_WORKFLOW.md`. Those PIDs are historical, never stop targets.

Development and application tests stay in source-only isolated checkouts with private-read/network barriers. Always exclude the credential-reading live progress test. No test Discord/email/X/CAPTCHA actions were sent during this rollout.
