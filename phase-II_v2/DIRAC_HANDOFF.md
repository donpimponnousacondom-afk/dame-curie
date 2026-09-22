# Temporary Dirac V2 — scoped hardening handoff

Verified 2026-09-22. **Temporary Dirac is live; canonical Dame is not activated.** This is bounded operational acceptance, not whole-application or security certification.

## Use it

- Discord identity: `1504398705539944560`.
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
| Application and installed operator code | `65fe79e262fb6f7a385ef5e07530bc432d888185`; Python 3.14.4 |
| Image | `dame-curie-app:65fe79e`, `sha256:0b18300d4c1f5614c1bf9822cd944310b527949b4ec16eb673c5c8a085f2b1a6`; selector remains digest-pinned |
| Container | `dirac-v2`, `d534d4f538a76269f3b650375ac093dbcea4b0549759b509a7162976deeedb70` |
| Account / engine | `dame-curie`, UID 1005, `/run/user/1005/docker.sock`; engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d` |
| Embedding endpoint | `http://172.23.0.1:11434`, embedding-only relay inside V2's namespace; no host 11434 listener |
| Shared backend | Existing V1 Ollama; `qwen3-embedding:0.6b`, 1,024 dimensions; no duplicate model launched |
| Services | Relay and separate publisher active, **not enabled for boot** |
| Restart policy | Bot **restart=no**; no boot/crash auto-recovery promise |
| Canonical services | Dame bot/Ollama/pull remain Created, never started; canonical selector/config untouched |

Private persistent root remains `/srv/dame-curie/dirac`. Config, inference profiles, credentials, prompts, data, sites, shell and receipt ledger were retained. No V1 database/history copy, model-management operation, REM retuning or memory purge was performed.

Rollback evidence is private: `/var/backups/dirac-v2/20260922T124707Z-901200d` contains the pre-hardening state, old units and Docker log; `20260922T131039Z-65fe79e` contains the subsequent application-state/log snapshot. Previous source/venvs remain at `/opt/dame-curie-pre-hardening-469a356` and `/opt/dame-curie-pre-hardening-65fe79e`, alongside the earlier pre-Dirac copies. Do not restore an entire snapshot casually over newer human activity.

## Current evidence

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
