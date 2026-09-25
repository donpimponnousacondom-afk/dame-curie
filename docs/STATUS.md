# dame-curie status — 2026-09-25

## Closure and release state

**Round-two corrections and documentation retirement are complete. Corrected source `89fb851` is live on temporary Dirac.** The coordinator exercised root's delegated temporary-only decision after source/QA/artifact checks and one bounded smoke case. Canonical/V1 activation, publisher/shared-service lifecycle changes and remote operations remain held. This is not standing permission for future agents to repeat runtime operations.

Start with the [closure receipt](../audit/20260924T210402Z-audit/09-CLOSURE.md). [AGENTS](../AGENTS.md) preserves authority/boundaries; [Operations](OPERATIONS.md) covers recovery; [TODO](../TODO.md) distinguishes completed work from held decisions. Internal independent closure is not a replacement sign-off by the original external auditor; its conditional verdict and originals remain unchanged.

## Source and QA

| Checkpoint | Evidence |
| --- | --- |
| `eb188ac` | External round-two verdict/five follow-ups preserved verbatim |
| `c2d6b0e` | Provider reservation/incident, autonomy actor/logging and taskless-smoke corrections; QA70:345 focused passes |
| `89fb851` | Prompt/catalog/native-call/media/follow-up/readback corrections and existing-case adaptation; final QA source/test blobs match |
| QA75/76 tree`511a355fabe792cc6ae844d26004de7c55c104b4` |92focused passes and selected Ruff F821/F822/F823; **3993passed+28subtests** in the full safe suite |
| `f815857` | Consolidated guides, root-confirmed audit rename,39phase and28internal-note retirements; only Python edits are two operator-docstring pointers |

QA used Python3.14.4, synthetic configuration/state, network-none and no private mounts. The safe suite excludes `tests/test_streaming.py` and `tests/test_streaming_primary.py`; it is not unrestricted/live-provider testing. Counts overlap, do not sum. The catalog-loop case uses padded synthetic descriptions and fake dispatch/initial assembly while exercising real expansion/loop/budget logic, not production schema-size or full transport acceptance.

Exact commands, failures, corrections and immutable evidence refs: [validation](../audit/20260924T210402Z-audit/validation.md). Finding dispositions: [response](../audit/20260924T210402Z-audit/05-IMPLEMENTER-RESPONSE.md). Original conditional verdict: [round two](../audit/20260924T210402Z-audit/08-ROUND2-REPORT.md).

## Verified and deployed artifact

Image **`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`**, local tag`dame-curie-app:89fb851`, source revision`89fb851144dbd9c0bd661a67c5937161d1b58b52`.

QA77 built an explicit offline source overlay onto previously verified `be28b85` image`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`, because the local Python-base tag was absent. No pull/install; normal recipe and dependency lock unchanged, dependency layers inherited, **not freshly rebuilt**. QA78 matched all56copied inputs to the committed archive and checked baked commit/branch/dirty plus OCI revision. The existing guarded constructor passed in the actual image without network/private state/login. Later documentation commits do not change its application inputs.

## Current temporary runtime — checked16:47:48Z

- Account`dame-curie`, UID1005; rootless engine`12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`, socket`/run/user/1005/docker.sock`.
- Container **`ef618129341ed4b2b83dceebd2a92e3e0e3437585e53f96c488381a3ca23e2d5`**, running the immutable image above; started**16:46:31.285765518Z**. Durable image selector matches.
- Fresh startup evidence verified Discord identity**1504398705539944560** at**16:46:35.602714316Z**. Embedding readiness passed; pending smoke list empty. Docker status alone was not used as identity proof.
- Request**`857116de560f4054b261202d7272dcab`** completed in **7seconds**, one delivery, exact21-character marker body plus configured29-character footer, zero readback failures. It ran on the immediately prior smoke-scoped container using the **same immutable image**, not on the final recreated container. No second inference was submitted. This is happy-path acceptance, not a failure/feature matrix.
- Original controls restored **byte-exact**, including all three allowed channels. Low reasoning/output12345/REMoff/autonomy-control-off/RAGon and image qualityhigh preserved; neither image alias disabled. Profile, REM, prompt and smoke-config fingerprints unchanged. One stored server prompt1939UTF-8 bytes, none over16KiB; external prompt mount verified, base personality uninspected.
- Coordinator mistakenly requested `restart` after stopping the smoke candidate; the operator correctly refused, exit1. Evidence was preserved privately, then approved `start --replace` recreated it with original controls. This invocation error remains in the ledger; no source bypass or repeated smoke was used.

Rollback: retained old image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` (source6859025), root-only evidence`/var/backups/dame-curie-dirac/round2-release-20260925T163646Z/`. Future rollback is image-only under a compatible grant; do not overlay these dated controls on later human edits. Keep each smoke request with its terminal receipt. Host viewer/Screen were **not** updated/exercised; installed operators still match reviewed89fb851 logic, not later docstring edits.

## Retained decisions and limits

Reasoning-only terminal/fallback and mandatory tool-reasoning policies remain unchanged pending root. Shell remains admin-or-allowlisted with same-UID writable-control trust explicit. Viewer oversized-record/redaction-continuity loss stays fail-closed until viewer restart, including affected canonical interactive paths; source is not host-installation evidence.

C09 import-time dotenv redesign is an accepted deferral, not an open task. P08/I05 historical provenance is permanently unattributable and quarantined, with no cache cleanup. Canonical native-image reconciliation remains held; its private profile was not inspected. Voice, exhaustive media/admin/plugin/provider combinations, replicas, sustained load and publisher remote-deletion recovery remain unverified. Jobs do not resume workers after restart; runtime footer markers are not authentication. Ordinary shared embedding requests are permitted and occurred; no shared-service lifecycle/configuration change followed.

## Documentation and history

Current guidance is README/AGENTS/SECURITY/TODO plus the nine guides. `f815857` retired39unchanged phase files and28unchanged internal notes after migration/recovery preservation. All16external originals remain byte-identical to `eb188ac` in root's renamed audit directory; response/validation/closure, quarantine/process companion, QA recipe and failed-QA evidence remain.

`git show eb188ac:phase-II_v2/SESSION_LOG.md` recovers the verbatim prior grant; that revision retains all phase files. Internal notes remain in`89fb851` under the original audit path; list its Git tree to recover them. These are historical evidence, not renewed operating instructions. Earlier status is recoverable at`ab64853:docs/STATUS.md`.

All existing refs/worktrees/caches remain. Historical inventory26worktrees/25branches/22checkpoint refs and86commits (54equivalent/32non-equivalent across13families) is dated mapping, not current counts/cleanliness proof. Five new QA evidence refs preserve intermediate/final trees. Root's unrelated ignored audit material, `reports/` and skill work remain untouched.
