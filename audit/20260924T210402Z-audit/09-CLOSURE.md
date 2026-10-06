# Round-two closure — 2026-09-25

## Decision and current state

**Accepted internally; corrected source`89fb851` is live on temporary Dirac.** Root delegated the coordinator's temporary-only decision; source/QA/artifact checks and one bounded smoke passed before promotion. Canonical/V1 activation, publisher/shared-service lifecycle changes and remote operations remain held. This receipt creates no standing runtime grant and does not replace the original external auditor's conditional verdict.

- Image **`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`**; source revision`89fb851144dbd9c0bd661a67c5937161d1b58b52`.
- Final container **`ef618129341ed4b2b83dceebd2a92e3e0e3437585e53f96c488381a3ca23e2d5`**, started**16:46:31.285765518Z**. Fresh startup identity**1504398705539944560** verified at**16:46:35.602714316Z**; running/embedding-ready, pending smoke listempty. Durable selector matches.
- QA83 request**`857116de560f4054b261202d7272dcab`** completed in **7seconds**, one delivery, exact21-character marker body plus configured29-character footer, zero readback failures. This ran on the immediately prior smoke-scoped container with the **same immutable image**; no second inference after recreation. Protocol`reply_verified=false` was preserved; coordinator's exact-body assessment is separate.
- QA86 at**16:47:48Z** confirmed original controls restored **byte-exact**, all three channels, low reasoning/output12345/REMoff/autonomy-control-off/RAGon/high image quality, neither image alias disabled. REM/profile/prompts/smoke config unchanged. One stored server prompt1939UTF-8 bytes, none over16KiB; base personality uninspected.

**Operator mistake retained:** coordinator stopped the smoke candidate, then incorrectly called running-only`restart`. The operator refused, exit1, preserving evidence. Logs were saved privately and approved`start --replace` recreated the same image with original controls; no source bypass or repeated smoke. The runbook now makes that command distinction explicit.

Rollback: old image **`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`** remains; opaque controls/selector/logs and fingerprints are in root-only **`/var/backups/dame-curie-dirac/round2-release-20260925T163646Z/`**. Future rollback is image-only under a compatible grant, not permission to restore stale controls. Keep requests and terminal receipts together. Host viewer/Screen were not updated or exercised.

## Source, QA and artifact provenance

Corrections: **`c2d6b0e` +`89fb851`**. Final application/test blobs match QA75/76 tree`511a355fabe792cc6ae844d26004de7c55c104b4`. QA75:92focused passes and Ruff F821/F822/F823. QA76:**3993passed+28subtests**, Python3.14.4/network-none/synthetic state/no private mounts. Existing cases adapted, no new test files/functions. Counts overlap. Live-coupled exclusions, failed runs and deliberately synthetic catalog-test limits remain in`validation.md`.

Independent Sol`a6b627d2` diff-focused source closure passed; it did not run its own QA or act as the original external auditor. QA77 used an explicit offline source overlay on the previously verified `be28b85` artifact because the local Python-base tag was absent. No pull/install; normal recipe and pins unchanged, dependency layers inherited, **not freshly rebuilt**. QA78 matched all56copied inputs and checked baked commit/branch/dirty plus OCI revision; the existing actual-image guarded constructor passed without network/private state/login.

## Documentation checkpoint

**`f8158571fe05a63e783193792f60010806e57e4d`** consolidated current contracts and physically retired **39phase files +28internal audit notes** (about6000net lines). Root's shorter audit directory is adopted. All16external originals were byte-verified against`eb188ac`; retired internal notes matched`89fb851`, and phase files had no uncommitted changes. Original blobs were rechecked after the commit.

Current contracts live in README/AGENTS/SECURITY/TODO and the nine guides: Architecture, Operations, Status, Development, Dead Code, Images, Longprompt, Provider Reload and Publishing. The only Python changes in this documentation slice are two operator module-docstring pointers; executable logic/application-image inputs are unchanged. Installed operators remain verified against reviewed`89fb851` logic, not those later docstrings.

Retained evidence: originals00–04/A–E/08/R1–R5; response, validation and this receipt;07historical process companion/quarantine; QA recipe and failed-QA triage/gzip. Independent Sol`6585cc5a` reviewed current guides/links and response/ledger; stale image/retirement/offline-scope claims were corrected and narrowly rechecked. Original report text/historical citations were deliberately not rewritten.

Recovery: `git show eb188ac:phase-II_v2/SESSION_LOG.md` preserves the **verbatim prior human grant**; that revision retains every phase file. `git ls-tree -r --name-only 89fb851 -- audit/` locates retired internal notes under the old directory name; recover them with`git show 89fb851:<listed-path>`. Historical text is evidence, not renewed operating authority.

All existing refs/worktrees/caches and root's unrelated ignored audit material, `reports/` and skill work remain untouched. Five new QA evidence refs preserve exact failed/intermediate/final trees; dated inventory counts are not current cleanliness claims.

## Closed assignment, retained boundaries

No assigned correction/document-retirement item remains open. **C09 dotenv deferral is accepted; P08/I05 historical provenance is permanently unattributable and quarantined**, not a new import-isolation/cache-cleanup task. Reasoning-only fallback and mandatory tool-reasoning policies remain unchanged pending root. Same-UID writable-control trust stays explicit; oversized viewer records latch evidence off until viewer restart, including affected canonical interactive paths.

One smoke does not establish adverse cancellation/exhaustion, live image/voice/admin behavior, exhaustive providers/features, replicas, load or publisher remote-deletion recovery. Jobs do not resume workers after restart; SDK buffering/TOCTOU and packaging/voice limitations remain disclosed. Footer markers are not authentication. Ordinary configured embedding requests occurred; no shared-service configuration/lifecycle change followed.

For future work, start with`../../docs/STATUS.md` and`../../AGENTS.md`; exact commands, failures, hashes and runtime chronology are in`validation.md`. This is the final coordinated receipt, not another per-child report.
