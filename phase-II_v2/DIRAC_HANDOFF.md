# Temporary Dirac V2 — provider reload and role wake-up handoff

Updated 2026-09-23. **Temporary Dirac is live on `d43e4bf`; this rollout did not activate canonical Dame or mutate V1.** This is bounded operational acceptance, not whole-application or security certification.

## Use it

- Discord identity: `1504398705539944560`.
- **V2 command prefix: `?`** — use `?help`, `?version`, `?prompt`. V1's `!` prefix and the repository's default were not changed.
- Assign the queen to the shared Discord role, then ping that role in an allowed channel. Assigned human role pings wake her even with conversation watch off; `@everyone`/`@here` stay soft and role-only pings do not cancel an ongoing turn.
- Root's newly enabled room `1548588998983946290` remains allowlisted.
- Approved smoke parent: `1550960386939817984`, including its bot-owned test threads.
- Root's group DM: `1545158306404892753`; group replies remain enabled, ordinary private-DM replies disabled.
- Viewer: **`screen -r dirac-v2`** as codexy. `q` quits the viewer, not the bot; `Ctrl-a d` detaches.
- Published test: [Dirac's Relay Station](https://redroom.zombiedawn.net/dirac/sites/dirac-smoke/index.html).

```bash
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py status
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py restart
sudo -n /opt/dame-curie/.venv/bin/python -I -B /opt/dame-curie/scripts/dirac.py stop
```

`restart` retains the container/image. Replacement requires a stop, digest-selector update and explicit `start --replace`; building or committing is not deployment. Do not manage temporary Dirac with canonical `instance.py up`.

## What is running

| Item | Verified state |
| --- | --- |
| Application and installed operator code | `d43e4bf3f963655e4f9ac7b1d690549256c9fb53`; Python 3.14.4; later documentation commits do not change the app image |
| Image | `dame-curie-app:d43e4bf`, `sha256:102805e039ec4d32f689308e5a086b837f321559ff89117787de5183fa22ff0a`; selector remains digest-pinned |
| Container | `dirac-v2`, `030fb63b9c54e9f00eb6c4ccd2db900149cb94141a6adc5fa24b835b0ef0340d` |
| Account / engine | `dame-curie`, UID 1005, `/run/user/1005/docker.sock`; engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d` |
| Embedding endpoint | `http://172.23.0.1:11434`, embedding-only relay inside V2's namespace; no host 11434 listener |
| Shared backend | Existing V1 Ollama; `qwen3-embedding:0.6b`, 1,024 dimensions; no duplicate model launched |
| Services | Relay and separate publisher active, **not enabled for boot** |
| Restart policy | Bot **restart=no**; no boot/crash auto-recovery promise |
| Canonical services | Dame bot/Ollama/pull remain Created, never started; canonical selector/config untouched |

Application/image/container/READY observations above are current to September 23. The canonical/publisher/host-listener inventory rows retain the September 22 receipt; those protected surfaces were not re-inventoried or changed in this rollout.

Private persistent root remains `/srv/dame-curie/dirac`. Config, inference profiles, credentials, prompts, data, sites, shell and receipt ledger were retained. No V1 database/history copy, model-management operation, REM retuning or memory purge was performed.

Rollback evidence is private: `/var/backups/dirac-v2/20260922T124707Z-901200d` contains the pre-hardening state, old units and Docker log; `20260922T131039Z-65fe79e` contains the subsequent application-state/log snapshot. Previous source/venvs remain at `/opt/dame-curie-pre-hardening-469a356` and `/opt/dame-curie-pre-hardening-65fe79e`, alongside the earlier pre-Dirac copies. Do not restore an entire snapshot casually over newer human activity.

## September 23 provider-reload acceptance

- `d43e4bf`'s exact committed tree passed **825 focused isolated tests**, expanded Ruff F821/F822/F823 checks and independent source review. One stale README-row assertion was deselected after reproducing it on `dba8359`; no whole-suite claim. Actual-image testing verified source blobs, frozen manifest, reload imports and sanitized invalid-port rejection without network/private mounts.
- Replacement passed embedding readiness and the intended Discord identity reached READY. Prefix `?`, 20 MiB and the new room survived. No private environment profile was changed by deployment. The replacement's viewer is `3198825.dirac-v2` (`screen -r dirac-v2`).
- **Live receipt `74d4aa30ddc0463c8162207491c46a80`**, in existing bot-owned thread `1551880062251442216`: labeled shell/model smoke `dirac-reload-proof-171d3a302a97`, delivered reply `1552346262622441603`. A temporary one-second cooldown override stayed unapplied for **14.9 seconds of observed tool work**, then applied as generation 2. Only the owned override was removed; the environment matched its original bytes exactly, and restoration applied as generation 3. This is a live deferral/restoration receipt, not exhaustive live validation of every profile or a human role-ping receipt.
- Private rollback copies: `/var/backups/dirac-v2/20260923T153711Z-d43e4bf` and `/opt/dame-curie-pre-provider-reload-d43e4bf`. Keep current settings/data on an image-only rollback.
- Scope, precedence and restart-only settings: `../docs/PROVIDER_RELOAD.md`. General Gateway-command admission during shutdown remains a preexisting limit; idle reload does not claim to redesign shutdown.

## Prompt failure diagnosis — read-only

- The two reported producer timestamps map to preserved Docker timestamps **2026-09-23T13:16:49.869939985Z** and **2026-09-23T13:17:04.751778908Z**, on the earlier `65fe79e` runtime. Both explicitly report HTTP400/Discord50035 and **`In content: Must be 2000 or fewer in length`**. No prompt contents or private messages were printed.
- Current `bot.py:6570–6582` still sends the entire prompt as one `channel.send`, both when viewing it and acknowledging an update. The setter persists the prompt before sending its acknowledgement; an acknowledgement failure is not a rollback. The bounded evidence does not distinguish which branch those two requests used.
- Smallest proposed fix: route both responses through the existing bounded `send_command_response` helper (or attach long text), including code-fence/footer overhead; make the empty-prompt usage hint follow the configured prefix. Validate oversized/Unicode/fenced prompts in isolated synthetic tests. **No prompt-handler patch, replay, provider call or restart was performed for this diagnosis.**

## Earlier September 23 role/provenance evidence

- **298 focused isolated tests passed at `2f159e9`**, plus independent source review. The actual image's bot blob matches that commit; its baked manifest reports the same commit despite runtime build-variable/socket overrides. `?version` freezes that manifest at startup; changing the host checkout does not change the running version.
- Initial replacement failed its embedding gate with HTTP 503 while the shared V1 Ollama target was stopped (exit 0, not OOM). Root restored V1 externally; the coordinator then restarted only Dirac. Embedding readiness and the intended Discord identity's READY were confirmed. Startup was not bypassed and RAG was not disabled.
- **65 focused tests passed at documentation/test-only commit `dba8359`**, covering real constructor setup with both prefixes, role routing and foreground provenance. The application source in that run is unchanged from deployed `2f159e9`; this is not a new image or a live human command receipt.
- Dirac's private prefix alone changed to `?`, with a private backup and comparison confirming other effective settings unchanged. Incoming 20 MiB and the new room were rechecked. The log viewer was recreated as `2993753.dirac-v2` after replacement ended the old viewer.
- Additional rollback material: `/var/backups/dirac-v2/20260923T142241Z-2f159e9` and `/opt/dame-curie-pre-role-wakeup-2f159e9`. The state snapshot predates the `?` prefix edit: prefer image-only rollback and preserve newer human settings.
- A human Discord role-ping receipt is still separate from isolated routing tests. The earlier `2f159e9` image excluded provider reload; the later `d43e4bf` rollout and prompt diagnosis are recorded above.

## Previous hardening evidence

- **341 focused tests passed at `65fe79e`**, in frozen Python 3.14.4 QA without network, credentials or private mounts. Selected Ruff F821/F822/F823 checks passed with target `py314`. This is not a full-suite claim: 19 failures in three additional, unchanged test files also reproduced on baseline `eca42e0`.
- Relay on `901200d`: real POST `/api/embed` returned one finite, nonzero 1,024-dimensional vector; harmless unknown POST returned 403 and GET `/api/embed` returned 405. The relay code/unit are unchanged in `65fe79e`; the final container's startup embedding check also passed. Management-route rejection is tested in isolation, not by live destructive probes.
- Model-only smoke `7782a27c1ced4ccc834049047da5abc2` on `901200d` completed and independently read back the exact requested marker. Its notice was `1551939327678877787`, answer `1551939346486136843`; actual Gateway identity matched temporary Dirac.
- Final-source smoke `d45ee9cab96145d4b3f9ab828bb5b87c` completed; real job `c25d1824` finished in allowed origin thread `1551880062251442216` while its parent was both allowlisted and explicitly blocked. The runner recorded the parent refusal and no new progress thread. Its marker file matched exactly; the [published marker](https://redroom.zombiedawn.net/dirac/sites/dirac-smoke/hardening-65fe79e.txt) returned HTTP 200. Original channel policy was restored and its hot reload observed; the 20 MiB limit remained intact.
- Publisher's running mount namespace denied direct reads of canonical/Dirac bot roots while retaining its own config, read-only sites and writable staging/state. Effective relay command retained both engine pins and uses `-I -S -B`.

Exact closure receipts and corrections: **`DIRAC_INTEGRATION.md`**. Earlier shell, ordinary job/thread routing, game/media, PHP/Perl/CGI, browser-counter and retained-context acceptance belonged to `9a3fa43` (351 tests + 28 subtests); those scenarios were not all repeated here.

## Limits and explicit decisions

1. The relay blocks management routes, **not all resource effects of permitted embedding requests**. Client-selected embedding arguments remain intact. It is not an independent model server or resource quota. Full-API exposure was a defect, not an accepted trade.
2. Daemon PID/start-time/namespace retirement is watched and triggers rebinding through systemd. Lifecycle retirement and continuous-traffic handling were tested with synthetic process/listener scenarios, not a real engine restart.
3. Smoke completion requires a returned turn, usable own-task model output and a non-notice delivery. It does not certify the requested goal. Failed notice-only turns retain delivery/readback evidence. Final edits arriving after turn closure can conservatively grade failed. Synthetic context is retained with bot-poster attribution, not purged or presented as human facts; broader REM work was explicitly dropped.
4. Publisher direct-path masks are not a separate-UID security boundary. Canonical publisher reverse isolation and out-of-band remote deletion recovery remain outside this round; its held unit and core mirroring logic were not changed.
5. Job metadata persists; unfinished workers are cancelled on reload, not resumed. Both a missing parent allowance and an explicit parent block prevent a new sibling, with output kept in the allowed origin thread. Plain-channel command semantics are unchanged.
6. **Incoming limit stays 20 MiB (20,971,520 bytes), root's explicit override.** The authorized earlier check found V1 at 10 MiB, disproving the report's asserted higher value. No broad control migration was done. Inherited unsupported-archive classification remains; raising the limit does not implement `.7z` extraction. See `DIRAC_ATTACHMENT_LIMITS.md`.
7. No live voice, exhaustive media/admin/replica, sustained-load or whole-repository acceptance is claimed. No Git push occurred. Keep terminal receipts with their requests: deleting only receipts can replay old requests.
