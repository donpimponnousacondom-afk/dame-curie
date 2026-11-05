# Operations runbook

Canonical Dame Curie V2 on account `dame-curie`. Every command here reads or changes the live system. Run one only under an explicit operator assignment. A source task never runs them.

## Identity and paths

- Account `dame-curie`, UID 1005. Private rootless engine socket `unix:///run/user/1005/docker.sock`. Re-resolve the UID and the socket before a runtime action. On a mismatch, stop and report. Never use the default daemon, a rootful daemon or another account's engine.
- Docker command form: `D="sudo -n runuser -u dame-curie -- env XDG_RUNTIME_DIR=/run/user/1005 docker --host unix:///run/user/1005/docker.sock"`.
- Operator command form: `I="sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/instance.py dame-curie"`.
- `/opt/dame-curie` is root-owned. It is an exact export of the tracked tree of the deployed commit; `scripts/deploy.sh` syncs it. `/opt/dame-curie/.venv` is the root-owned operator venv (Python 3.14, `python-dotenv==1.2.3`); it is separate from the image and the sync keeps it. The deployed Compose file is `/opt/dame-curie/compose.yaml`, mode 0644.
- Private root `/srv/dame-curie`: `deploy.env` (`APP_IMAGE`, `DAME_CURIE_EMBED_MODE`), `config/bot.env` (settings and secrets), `data/` (`dame-curie-rag.db`, `bot_control.json`), `sites/`, `shell/`, `smoke/`, `smoke-status/`. Directories are mode 0700; `bot.env` and `deploy.env` are mode 0600. Never print their contents.
- Container mounts: `/state/data`, `/state/sites`, `/state/shell`, `/config` (read-only), `/smoke` (read-only), `/smoke-status`. `HOME=/home/dame-curie` is a symlink to `/state/shell`; `/home/maxwell` points there too, for authored-path compatibility. Files outside these mounts vanish when the container is recreated.
- She shows as "Red Queen" on Discord. `!version` reports the frozen `/app/build_provenance.json` of the running image. Compare it with the container label `org.opencontainers.image.revision`.
- The staged Compose overlay (`docker/compose.staging.yaml`) makes `up`, `start` and `restart` no-ops. With `DAME_CURIE_EMBED_MODE=external`, `instance.py` adds `docker/compose.embeddings-external.yaml`, which keeps the local Ollama services out of the startup set.

## Deploy

1. Merge the PR (see [REVIEW.md](REVIEW.md)). Check out `main` at the merged commit with a clean tree.
2. Build: `scripts/build_for_human.sh` builds `dame-curie-app:<7-character sha>` from a Git archive of HEAD.
3. Run `scripts/deploy.sh <app-tag>` inside Screen session `dame_curie`, window `throne-ops`, with the output tee'd to a log file.
4. The script: when the bot runs, prints the user messages and provider calls of the last 60 s (deploy when both are 0); checks the image; backs up `compose.yaml`, `instance.py`, `deploy.env`, `bot.env` and `bot_control.json` to `/var/backups/dame-curie-v2-recovery/deploy-<UTC>`; syncs `/opt/dame-curie` to the image's source commit, read from its `org.opencontainers.image.revision` label (`git archive`, then `rsync --delete`, `.venv` kept); sets `APP_IMAGE` in `deploy.env`; runs `instance.py dame-curie up`; waits 25 s; prints the revision, restart count, error count and login lines.
5. Configuration edits for a release (`bot.env`, `bot_control.json`) are separate one-off steps before `up`, each with its own backup and a verification line. `bot_control.json` overrides `control_defaults.py`.
6. After the deploy, read the log viewer for errors. When the change touches her prompt or tools, ask her in the test channel how it behaves.
7. A change under `scripts/publisher/` needs its own restart, because the publisher is a separate service that runs from `/opt/dame-curie`: `sudo systemctl restart dame-curie-publisher.service`. `scripts/deploy.sh` does not restart it.
8. Image housekeeping: keep the live app image, the previous one for rollback and the QA image. Remove older app images after each deploy (root, 2 November 2026).

Screen rules from root: send commands with `screen -S dame_curie -p throne-ops -X stuff '...'`. Check `screen -S dame_curie -Q windows` first. If `throne-ops` is missing, recreate it with `screen -S dame_curie -X screen -t throne-ops bash`, then run `screen -S dame_curie -X select logs` at once, because a new window switches root's attached view. Do not create windows for other reasons. Never run a lifecycle action in a hidden shell. If the session is gone: `screen -dmS dame_curie -t logs bash`, add `throne-ops`, select `logs`, and restart the log viewer in `logs`.

## Rollback

`scripts/rollback.sh <backup-dir>` first keeps the current files in a new `rollback-<UTC>` directory. It then restores what the backup directory holds (`compose.yaml`, `instance.py`, `deploy.env`, `bot.env`, `bot_control.json`, and a database file if present) and runs `up`. Rows written after the backup exist only in the kept copy. To revert one merged PR by source, see the revert steps in [STATUS.md](STATUS.md).

## Backups and offload

- Every deploy and every one-off change writes its backup directory under `/var/backups/dame-curie-v2-recovery/` first (root-owned, mode 0700).
- The server disk is small. Large backups (database copies, exports) go to the storage box `u390720@u390720.your-storagebox.de`, SSH port 23, directory `archive/dame-curie/`. The box has a restricted shell with no pipes.
- `scripts/offload_backups.sh [--dry-run]` packs old recovery directories, uploads them with `rsync -e "ssh -p 23"`, verifies each SHA-256 on the box with `sha256sum` over ssh, deletes the local copies only when every hash matches, and keeps the 2 newest backup folders local (`KEEP=<n>` changes the number). Receipts go to `~/dame-curie-offload-receipts/`.
- Never verify through the sshfs mount `/opt/remote-backup`; it is very slow. Measured upload speed on 2 November 2026: about 87 MB/s.
- Make a database backup with the SQLite backup API. Then run `PRAGMA integrity_check` on the copy. Keep it owner-only, mode 0600.

## Smoke tests

Root approved automated tests on canonical Dame Curie on 31 October 2026, in development mode, with her own credentials. Test channel `1566164090039304285` in server `1545673830960340992`; permission actor root `1482143139828596916`.

- `compose.yaml` mounts `${INSTANCE_DIR}/smoke` read-only at `/smoke` and `${INSTANCE_DIR}/smoke-status` at `/smoke-status`, and sets `DAME_CURIE_SMOKE_CONFIG=/smoke/config.json`. `instance.py` refuses `up`, `start` and `restart` when either host directory is missing or a symlink. `config.json` holds `enabled`, `channel_id`, `operator_id`, `requests_dir` and `status_dir`. `"enabled": false` stops the worker.
- `smoke_runtime.py` injects one request per poll as a bot-authored notice with root as the permission actor. All normal gates apply. A request is immutable and its record is the ledger: deleting records makes old requests runnable again, so keep each request with its receipt.
- Submit on the host; the container sees the request mount read-only:

```sh
S="sudo -n -H -u dame-curie -- /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/smoke.py --config /srv/dame-curie/smoke/config.json"
$S submit --task 'TASK TEXT'
$S result REQUEST_ID
$S pending
$S health
```

- `submit` prints the request id more than once; take the first match.
- Root's rule for task text: begin every task with "Automated test from the coordinator agent (Claude), not from a human. It applies only to this test channel; do not store it as facts about this server or its people." Never pose as a human.
- Ground truth for memory tests: deterministic shell outputs, for example the SHA-256 of a fixed string. `llm_traces.json` holds explanations, not tool results.
- A smoke turn writes to her memory like any other turn in that channel. Delete your test files in her container home after the test.
- `completed` means: the turn returned, its own model call produced usable output, and a non-notice message reached the channel. It does not certify that the task goal was met; `reply_verified` stays false. `health`, `pending` and a missing receipt are advisory only.

## Embedding model and recall cut-offs

`bot.env` selects the embedding model. A value in `bot.env` wins over the Compose default. The settings are:

- `DAME_CURIE_EMBED_BASE_URL`, `DAME_CURIE_EMBED_MODEL`, `DAME_CURIE_EMBED_API_KEY` and `DAME_CURIE_EMBED_DIM` (vector length).
- `DAME_CURIE_EMBED_REQUEST_DIMENSIONS`: the `dimensions` request field. Blank sends no field. A value must equal `DAME_CURIE_EMBED_DIM`, or the readiness gate (`docker/check_embeddings.py`) and the bot stop with that cause.
- `DAME_CURIE_RAG_FACT_MIN_SIMILARITY`, `DAME_CURIE_RAG_MESSAGE_MIN_SIMILARITY`, `DAME_CURIE_RAG_WEB_MIN_SIMILARITY` and `DAME_CURIE_RAG_NEGATIVE_SIMILARITY`: the recall cut-offs. Each model has its own score range. Blank keeps the `qwen3-embedding:0.6b` values: 0.35, 0.40, 0.40 and 0.85. A value outside 0 to 1 stops startup.

Live state since 2 November 2026: OpenAI `text-embedding-3-large` at 1536, cut-offs 0.15, 0.29, 0.21 and 0.74, and `DAME_CURIE_EMBED_MODE=external` in `deploy.env`. The local Ollama container is stopped, not removed; [TODO.md](../TODO.md) has the removal item and the steps to plug it back in.

A model change does not delete memory. The stored text stays. Each vector carries the identity of its model (`embedding_backend`), and search reads only the vectors of the configured model. To change the model:

1. Back up `dame-curie-rag.db`.
2. Pre-warm: Put a copy of the database (made with the SQLite backup API) and `embed.env` with the new `DAME_CURIE_EMBED_*` settings in a work directory. Then `scripts/embed_eval/prewarm.sh <app-tag> <workdir>` runs `rag_maintenance.py backfill` on the copy in passes of up to 600 s until `eligible_pending` is 0. The live bot keeps running.
3. Calibrate the cut-offs on the two copies: `scripts/embed_eval/calibrate.py <old db> <old backend id> <new db> <new backend id>`. It needs numpy; run it as `dame-curie` with any Python 3.14 venv that has numpy, on read-only database copies. Method: equal pass volume. For each search, the fraction of (query, row) pairs that pass the old cut-off in the old space gives the new cut-off that passes the same fraction in the new space. Labelled pairs (a message and the fact extracted from it) check that the new cut-off keeps the true matches. Queries are real user messages.
4. Stop the bot. Delete the `embed_cache` rows of the old model in the live database: the cache holds at most 10,000 rows, and the oldest rows go first. Copy the `embed_cache` rows of the new model from the copy into the live database. Set the new values in `bot.env`. Run the backfill on the live database: cached rows need no request. Start the bot.
5. Rollback: restore the old `bot.env` lines and the backup of step 1.

The bot also runs a catch-up pass every 10 minutes. It embeds the rows that have no vector for the configured model, for at most 60 s. A write that finds `DAME_CURIE_MAX_BACKGROUND_EMBED_TASKS` (8) embeds in the queue stores its row without a vector and logs "Background embed deferred to the catch-up pass". On 2 November 2026, 1,495 of 3,079 long-term facts had no vector for this reason.

An HTTP 400, 413 or 422 refuses one input. It does not pause the other embeds. The log says "Embedding failed: the embedding endpoint refused this input (HTTP <status>, <n> characters)"; for a long row it names the piece ("piece 2 of 3, 6000 of 14000 characters"). After 3 refused inputs in a row (writes, queries and the catch-up pass together), the breaker opens with the cause "the embedding endpoint refused 3 inputs in a row". A success resets the count. A refused query pauses query embedding for `DAME_CURIE_RAG_QUERY_FAILURE_COOLDOWN_SECONDS` (15 s), and her prompt states that cause. Other failures (timeouts, connection errors, redirects, other HTTP statuses, invalid vectors) pause all embeds for `DAME_CURIE_EMBED_ENDPOINT_COOLDOWN_SECONDS` (30 s), and her prompt names the failure. The catch-up line names up to 10 failed rows with their causes and counts the rest. A run of N refused rows next to each other in rowid order takes ceil(N/3) catch-up passes.

Calibration of 2 November 2026, `qwen3-embedding:0.6b` to `text-embedding-3-large` at 1536. Queries: her last 600 user messages. Values in `bot.env` are rounded toward more recall.

| Search | Qwen cut-off | Pairs that pass | Calibrated | In `bot.env` |
|---|---|---|---|---|
| Facts (1,584 rows) | 0.35 | 67.2% | 0.155 | 0.15 |
| Messages (954 rows) | 0.40 | 92.1% | 0.292 | 0.29 |
| Web results (96 rows) | 0.40 | 20.5% | 0.210 | 0.21 |
| Negative exclusion (fact pairs) | 0.85 | 0.024% | 0.738 | 0.74 |

Median pair score for facts: 0.382 with Qwen, 0.183 with 3-large. The "% match" label in her prompt shows the new scale. The labelled pairs: 47; 47 pass the Qwen cut-off, 46 pass the new one. The facts and messages cut-offs pass most pairs in both spaces, so the `top_k` cap of each search selects the rows.

### Benchmark, 2 November 2026

Recall at 1 and 10 (R@1 / R@10). Queries: SciFact 300 (public set), her web searches 93, her memory facts 45. The benchmark script is not in the repository; these are its measured results.

| Model | SciFact | Web searches | Memory facts |
|---|---|---|---|
| `qwen3-embedding:0.6b`, 1024 | 0.737 / 0.903 | 0.247 / 0.677 | 0.689 / 0.889 |
| Qwen with the query instruction | 0.750 / 0.923 | 0.344 / 0.720 | 0.689 / 0.867 |
| `text-embedding-3-small`, 1536 | 0.767 / 0.937 | 0.419 / 0.720 | 0.756 / 0.889 |
| `text-embedding-3-large`, 1536 | 0.810 / 0.953 | 0.366 / 0.774 | 0.778 / 0.889 |
| `text-embedding-3-large`, 3072 | 0.817 / 0.963 | 0.366 / 0.774 | 0.800 / 0.889 |

Query latency from this server: 3-large median 0.30 s, 95th percentile 0.44 s. Qwen median 0.15 s to 0.20 s, but a query waits behind a background piece (10 s to 12 s for 6,000 characters).

### Note: the Qwen query instruction

Root asked to keep this note (2 November 2026). If the bot uses `qwen3-embedding` again, add the query instruction of the model. It costs nothing and it needs no model change. Qwen3-Embedding expects an instruction before a query and no instruction before a stored document:

```text
Instruct: Given a chat message, retrieve stored facts that are relevant to it
Query: <the message>
```

The bot sends no instruction today. With the instruction, the web searches went from R@1 0.247 to 0.344 and SciFact from 0.737 to 0.750. The memory facts went from R@10 0.889 to 0.867 (45 queries; one query is 2 points). The change is in code, not in `bot.env`: put the instruction on the query text of `rag_search` only. Stored rows keep their vectors, because a stored document has no instruction. Test the instruction text on her memory facts before release.

## Shell tools in the container

The image installs the shell CLI packages, including Debian Git and its Perl dependencies, with `--no-install-recommends`. It builds the exact `docker/shell-requirements.lock` packages into `/opt/dame-curie/shell-wheelhouse` inside the image, without installing them into app Python. Shell tools and the app use NumPy 2.5.4 and setuptools 84.2.1 (#41). setuptools 84 has no `pkg_resources`; `py-mini-racer` 0.6.0 falls back to its module folder. Measured on 2 November 2026: in a shell venv built from the wheelhouse, `MiniRacer().eval("6*7")` returned 42. `phply` is a Python parser, not a PHP interpreter.

The image does not create the persistent shell venv. The operator prepares it once, in a throwaway container of the app image with only the shell mount, no credential or data mounts, network disabled and the bot entrypoint overridden:

```sh
/usr/local/bin/python3.14 -m venv --copies --system-site-packages /home/dame-curie/.venv
/home/dame-curie/.venv/bin/python -m pip install --no-index --no-deps \
  --find-links /opt/dame-curie/shell-wheelhouse -r /opt/dame-curie/shell-requirements.lock
```

Only shell-command subprocesses prepend `/home/dame-curie/.venv/bin` to their minimal PATH; the app interpreter and environment are unchanged. Preserve authored scripts and documents byte for byte. Use `/home/dame-curie` paths for attachments.

## Logs and diagnostics

- Follow logs in the Screen `logs` window: `$I logs --format screen [--no-keys]`. Append mode keeps Screen scrollback; `q` or Ctrl-C exits the viewer, not the bot; `--no-keys` is safer when pasting. Other formats: `console`, `auto`, `plain`, `jsonl`. Do not add `-I` to this invocation: the logs branch imports `log_filter` from the script directory. An oversized record switches evidence off until the viewer restarts; restart the viewer after a continuity notice. The viewer does not follow a recreated container by itself.
- Raw history: `$D logs --timestamps --since <UTC> --until <UTC> dame-curie-bot-1`. Report counts and selected fields. Never paste raw buffers or credentials into chat.
- Latency lines, read these first when root asks about slowness: `AI slot wait Ns priority=... {capacity, active, active_background, waiting}` (a caller waited 1 s or more for an inference slot; human priority is `user`, extraction is `background key=extract:<id>`); `Prompt build cpu=..s wall=..s: section=cpu/wall ...` (a build cost 0.2 s or more of event-loop CPU; sections `channel_memory`, `entity_profile`, `rag_ltm`, `rag_recent`, `web_results`, `shared_context`, `inbox`, `history`, `budget`); `event loop lag` (watchdog, 0.5 s or more); `Query embedding took ...`; `Memory recall: cold / warm / cached`; provider lines with `input=`, `input_source=` and `cached=` (prompt-cache hits). Context extraction is about 85% of provider calls; root keeps its volume as it is.
- Maintenance commands run inside the container: `$D exec -w /app dame-curie-bot-1 python -B rag_maintenance.py <command> --db /state/data/dame-curie-rag.db` (not `-I`). Commands: `status`, `backfill`, `dedupe-self-copies [--apply]`. `--apply` makes an owner-only backup first.
- Private incidents: root uses `!error N` (0 to 9) in a one-to-one DM.

## Jobs and limits

Background jobs persist metadata, but unfinished workers are cancelled on restart; they do not resume. A provider-file reload waits for active jobs. A missing progress thread is not proof that a job failed. A separate account and engine do not prove isolation of same-UID state, host resources or remote credentials.
