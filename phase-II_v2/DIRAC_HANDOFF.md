# Temporary Dirac V2 — ready for battle testing

Verified 2026-09-22. **Temporary Dirac is live; canonical Dame is not activated.** This is scoped operational acceptance, not whole-application or security certification.

## Use it

- Discord identity: `1504398705539944560`.
- Allowed guild test parent: `1550960386939817984`, including its allowed threads.
- Root's additional group DM: `1545158306404892753`. Group replies enabled and hot-reloaded; other groups remain outside the whitelist. Ordinary private-DM replies remain disabled.
- Viewer: **`screen -r dirac-v2`** as codexy. `q` quits the viewer, not the bot; `Ctrl-a d` detaches.
- Published test: [Dirac's Relay Station](https://redroom.zombiedawn.net/dirac/sites/dirac-smoke/index.html).

```bash
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py status
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py restart
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py stop
```

`restart` restarts the same container/image. An image replacement is a separate stop, selector update and explicit `start --replace` operation; it is not implied by building or committing source. Do not use canonical `instance.py up` to manage this temporary bot.

## What is running

| Item | Verified state |
| --- | --- |
| Application and installed source | `9a3fa43`; Python 3.14.4 |
| Image | `dame-curie-app:9a3fa43`, `sha256:077db691648c0e98af7a4d0c54cd3b4c240d11018b140da3666ff04b1ad2147c` |
| Container | `dirac-v2`, `6036186ac04afb39cb7db2a32ef0bea304dbb2c36799ce0a607dbc0244d14f88` |
| Account / engine | `dame-curie`, UID 1005, `/run/user/1005/docker.sock` |
| Embedding endpoint | `http://172.23.0.1:11434`, relay inside V2's network namespace; no host listener on 11434 |
| Shared backend | Existing healthy V1 Ollama; `qwen3-embedding:0.6b`, 1,024 dimensions; no duplicate model launched |
| Services | `dirac-relay.service` and `dirac-publisher.service` active, **not enabled for boot** |
| Restart policy | Bot is **restart=no**; no boot/crash auto-recovery promise |
| Canonical services | Dame bot/Ollama/pull still Created, never started; canonical config/selector preserved |

Private persistent root: `/srv/dame-curie/dirac`. Its `config`, `data`, `sites`, `shell`, `smoke`, `smoke-status` and `publisher` trees are separate from V1. Container paths are `/config`, `/config/prompts`, `/state/data`, `/state/sites`, `/state/shell`, `/smoke` and `/smoke-status`.

The personality is an explicitly new test seed, not a recovered tmpfs prompt. Config retains the supplied inference profiles, auth/header/body/fallback settings and unset-versus-blank semantics. Prior installed source/venvs are retained at `/opt/dame-curie-pre-dirac-734c050` and `/opt/dame-curie-pre-dirac-9a3fa43`.

## Passed, with independent evidence

- **351 isolated tests + 28 subtests**, selected Ruff F checks, actual Compose overlay merges and frozen-image build. Not a full-repository test/lint claim.
- Actual Gateway identity, native shell execution and exact durable file contents.
- Two real background jobs: parent-origin thread and thread-origin standalone sibling, verified by Discord API and actual outputs.
- Published HTML matched local bytes. PHP, CGI and Perl returned their exact constant bodies over HTTPS; no local site server or global remote configuration change.
- Isolated Chromium loaded the actual remote page: three clicks changed 0→3, status updated, no horizontal overflow at the sampled viewport. This was independent browser verification, not a claimed bot tool action.
- Native checkers start/move/state/resign. Three actual Discord PNGs independently fetched and visually inspected: red c3-d4, black b6-c5, matching final boards.
- Actual embedding vectors, populated LTM and scheduled REM activity. Eight REM run records had accumulated at inspection; the latest recorded two LTM additions and one shared-context addition.
- Replacement persistence: eight fixed files, both completed jobs, all 65 prior vector IDs and all five old terminal receipts survived. No old request replay was observed.
- Cross-thread recall after replacement returned the exact earlier PHP marker without supplying it in the new request or fetching it again. Bounded logs show only the native `send_message` delivery call, not a file/search/fetch tool. This proves usable retained context, not isolated retrieval-ranking quality.
- Viewer quit left the bot alive; the current viewer was recreated against the replacement container and verified.

## Failures were not erased

The ledger retains the missing-personality startup failure, root CLI re-exec bug, QA/controller errors, a timed-out diagnostic and a separate taint-refused rerun. The final identical-task rerun passed after the narrow automatic-search classifier correction. The taint gate and real-confirmation requirement remain enabled and unchanged.

`BackgroundJob.model=null` records the absence of a requested override; it is not evidence of which upstream model served a request. Spawn returns before asynchronous thread creation, so its immediate acknowledgement need not contain a thread link. The human status command is `!job`; there is no invented native job-status tool.

## Limits worth knowing

1. **The embedding relay forwards the full Ollama API, not an HTTP endpoint allowlist.** V1 databases are not mounted into Dirac, but callers on the private bridge can reach model-management endpoints. Only embedding/inventory operations were tested; do not treat this as a security boundary protecting model administration.
2. A V2 daemon network-namespace replacement requires relay restart. Ordinary V1 container recreation is followed by per-connection PID lookup.
3. The publisher's ordinary watcher/publication path passed. Out-of-band deletion of a pinned remote site has a source-traced watch-recovery caveat; that recovery scenario and its proposed one-shot repair were not live-tested.
4. Job metadata persists, but unfinished workers are cancelled on reload, not resumed. Smoke completion certifies a returned turn plus delivery, not the truth of its claims. **Do not delete receipt files while retaining their requests:** that can replay them.
5. Automatic-search classification still uses heuristics; the cross-sentence false positive is fixed, not every possible false positive. Checkers retains legacy Maxwell labels and describes an intermediate turn in its move acknowledgement; the actual final state and board were correct.
6. Root's live archive report exposed a separate existing limitation: the media limit applies to all non-text attachments, including archives; a 16,220,247-byte `.7z` was skipped at the original 10 MiB setting and wrongly suggested to `see_image`. **Root subsequently requested 20 MB: the live setting is now 20 MiB (20,971,520 bytes), hot-loaded at 10:24:13.562281263 UTC without restarting.** This removes that file's size rejection, not the unsupported-archive classification. No archive download/extraction or source patch was performed. A source-based attachment-limit inventory is being prepared for root's comparison; no 500 MB aggregate allowance is assumed.
7. No live voice, exhaustive media/admin/replica, long-duration load or whole-repository acceptance is claimed. No Git push occurred.

Exact request/job/thread/message IDs, changes and failed-versus-passing receipts: `DIRAC_INTEGRATION.md`. Historical chronology: `SESSION_LOG.md` and `REDESIGN_PROGRESS.md`.
