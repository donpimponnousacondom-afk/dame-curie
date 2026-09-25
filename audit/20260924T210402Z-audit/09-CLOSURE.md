# Round-two closure — documentation checkpoint

## Coordinator decision

**Proceed to one bounded temporary-Dirac acceptance case; promotion is conditional on fresh identity, delivery/readback and control-integrity checks. The corrected candidate is not live at this checkpoint.** Root delegated that temporary-only decision. Canonical/V1 activation, publisher/shared-service lifecycle changes and remote operations remain held. Source readiness does not authorize those operations.

The correction slice is accepted internally: reviewed source, safe isolated QA, actual-image input/construction checks and corrected documentation. This is **not a replacement verdict from the original external auditor**; `08-ROUND2-REPORT.md` and its follow-ups remain verbatim.

## Source and artifact

- Source corrections: `c2d6b0e` and `89fb851`; all final application/test blobs match QA75/76 tree`511a355fabe792cc6ae844d26004de7c55c104b4`.
- QA75:92focused passes and Ruff F821/F822/F823. QA76:**3993passed+28subtests**, safe selection, Python3.14.4/network-none/synthetic state/no private mounts. Excluded live-coupled modules and synthetic catalog-test limits are explicit in `validation.md`; no new test files/functions. Counts overlap, do not sum.
- Fresh independent Sol`a6b627d2` diff-focused source closure: pass. Source-only review is not an independent test run.
- Actual candidate **`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`**, source`89fb851144dbd9c0bd661a67c5937161d1b58b52`.
- QA77 inherited previously verified `be28b85` dependency layers because the local Python-base tag was absent. No pull/install; normal recipe and pins unchanged. Explicit offline source overlay, **not a fresh dependency rebuild**.
- QA78:56copied inputs matched the committed archive; baked commit/branch/dirty and OCI revision checked. Existing guarded actual-image constructor passed without network/private state/login. Not feature-complete live acceptance.

## Actual documentation retirement

**39phase files and28internal audit notes removed**, after their surviving contracts and immutable recovery references were consolidated. Root's audit rename is adopted. All16external originals were byte-verified against `eb188ac`; the28retired internal files were byte-verified against `89fb851` before deletion. No uncommitted changes were discarded.

| Retired material | Durable destination / recovery |
| --- | --- |
| Phase design, cuts, jobs, source boundaries | `../../docs/ARCHITECTURE.md`, root README/AGENTS |
| Runtime, relay, smoke, logging, provisioning/identity boundaries | `../../docs/OPERATIONS.md`, `../../docs/STATUS.md` |
| Publishing layout and unexercised deletion-recovery limitation | `../../docs/PUBLISHING.md`; protected publisher source/template unchanged |
| Development/Vulture/validation limits | `../../docs/DEVELOPMENT.md`, `../../docs/DEAD_CODE.md`, this retained validation ledger |
| Prompt/image/provider contracts | LONGPROMPT/IMAGE_GENERATION/PROVIDER_RELOAD guides |
| Intake/inventory/implementation/micro/review notes | Findings in05, commands/failures/measurements in validation, current contracts in the nine guides |

Exact phase recovery, including the **verbatim prior human grant**: `git show eb188ac:phase-II_v2/SESSION_LOG.md`; all other phase files exist at that revision. Internal-note recovery: `git ls-tree -r --name-only 89fb851 -- audit/`, then `git show 89fb851:<listed-original-path>`. Historical citations in original reports were deliberately not rewritten.

Retained: original00–04/A–E/08/R1–R5,05response,07historical process companion, quarantine, validation/this receipt, QA image recipe and failed-QA triage/gzip. Independent document reviewer Sol`6585cc5a` checked the small current guides, response/ledger and live links. Incorrect candidate/current-image wording, obsolete retirement gates and ledger-wide offline claims were corrected and narrowly rechecked; final temporal wording was corrected afterward. No independent runtime/byte-identity verification is attributed to that source-only reviewer.

The only Python edits in this documentation slice are **two module-docstring pointers** in `scripts/dirac.py` and `scripts/dirac_relay.py`; executable operator logic and application-image inputs are unchanged. Installed operators still match reviewed source`89fb851`, not those new docstrings. Host viewer/Screen were not updated or exercised.

All existing refs/worktrees/caches and root's unrelated ignored audit material, `reports/` and skill work remain untouched. Five new immutable QA evidence refs preserve failed/intermediate/final snapshots; old inventory totals remain dated, not current physical-cleanliness claims.

## Fresh temporary preflight — QA79

AccountUID1005, designated socket/engine and installed trusted operator hashes reverified; interpreter symlink targets are root-owned and not service-writable. Old image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` still runs in container`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`; durable selector matches. Embedding readiness passed and pending smoke list is empty; status alone is not fresh Discord identity proof.

Minimum private check again found one1939-byte stored server prompt, none over16KiB; external prompt mount verified, base personality uninspected. Reasoninglow/output12345/REMoff, autonomy control off, RAGon, image qualityhigh and neither image alias disabled. Three allowed channels include the approved smoke channel. Profile, controls, prompts and smoke configuration fingerprints are unchanged; preserve human settings and recheck before restoring anything. Normal shared embedding requests are permitted, not an isolation failure.

## Retained limits

Reasoning-only fallback/mandatory tool-reasoning policies remain unchanged pending root. Same-UID writable-control trust remains explicit. C09 dotenv deferral is accepted; P08/I05 historical provenance is permanently unattributable and quarantined, not a cache-cleanup task. Viewer oversized-record continuity loss stays fail-closed until viewer restart, including affected canonical interactive paths. Jobs do not resume workers after restart; SDK buffering/TOCTOU and unverified voice/full-feature/multi-instance/load/remote-recovery limits remain disclosed.

**Still to record:** bounded current-candidate runtime result, final live/no-live decision, exact rollback reference and final documentation/receipt commit. The earlier QA67–69 happy-path receipt belongs to `be28b85`, not this candidate.
