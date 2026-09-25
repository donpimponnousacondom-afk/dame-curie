# dame-curie status — 2026-09-25

## Authority and release state

Root delegated the **temporary Dirac** rollout decision to the current coordinator after checks/review. Canonical/V1 activation, publisher/shared-service lifecycle changes and remote operations remain held. [AGENTS](../AGENTS.md) records the authority and recovery reference for the verbatim prior grant; [Operations](OPERATIONS.md) defines the operating boundary. [TODO](../TODO.md) is the short remaining-work list.

**Source correction is complete; this candidate is not yet live.** The independent diff-focused closure recheck found no remaining source blocker. That is an internal assessment, not a new sign-off by the original external auditor. Documentation consolidation/retirement and actual-image verification are complete; bounded current-candidate acceptance and the final temporary live decision remain. See the [closure receipt](../audit/20260924T210402Z-audit/09-CLOSURE.md).

## Current source and evidence

| Checkpoint | Evidence |
| --- | --- |
| `eb188ac` | Original external round-two verdict and five follow-up reports preserved verbatim |
| `c2d6b0e` | Provider reservation/incident, autonomy actor/logging and taskless-smoke corrections; QA70:345 focused passes |
| `89fb851` | Prompt/catalog/native-call/media/follow-up/readback corrections and existing-case adaptation; matches final QA source/test blobs |
| QA75/76 tree `511a355fabe792cc6ae844d26004de7c55c104b4` | 92 focused passes, selected Ruff F821/F822/F823; **3993 passed +28 subtests** in the full safe suite |

All QA above used Python3.14.4, synthetic configuration/state, network-none and no private mounts. The safe suite excludes `tests/test_streaming.py` and `tests/test_streaming_primary.py`; it is not unrestricted or live-provider testing. Counts overlap and must not be summed. The new catalog-loop case uses deliberately padded synthetic schemas and a fake dispatcher/initial message builder while exercising real group expansion, loop and budget enforcement. It is not production-schema-size or full transport acceptance.

Exact commands, failures/corrections, source reviews and immutable snapshot refs: [validation ledger](../audit/20260924T210402Z-audit/validation.md). Finding-level dispositions: [implementer response](../audit/20260924T210402Z-audit/05-IMPLEMENTER-RESPONSE.md). Original external verdict: [round two](../audit/20260924T210402Z-audit/08-ROUND2-REPORT.md).

## Candidate artifact — verified, not live-accepted or deployed

`dame-curie-app:89fb851`, image **`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`**, carries source revision `89fb851144dbd9c0bd661a67c5937161d1b58b52`.

The locally tagged Python base was absent. Rather than pull/install dependencies, QA77 layered the committed application inputs onto the previously verified `be28b85` artifact `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`, using network-none and pull=false. The dependency lock and normal Docker recipe are unchanged between those source revisions; dependency layers are inherited, **not freshly rebuilt**. The temporary overlay recipe recopies application inputs and regenerates provenance. QA78 matched all56declared copied inputs to the committed archive and checked baked commit/branch/dirty plus OCI revision. The existing guarded constructor passed inside the actual image with external prompts and `?`, no network/private mounts/login. Fresh identity and bounded live delivery are still pending; a constructor is not that acceptance.

## Last observed temporary runtime

The coordinator's latest metadata check still found **old source `6859025`**, not the corrected candidate:

- Account `dame-curie`, UID1005; rootless engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`, socket `/run/user/1005/docker.sock`.
- Container `495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, running image `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`, started2026-09-25T12:30:41Z.
- Prior startup receipt verified temporary Discord identity1504398705539944560. The fresh Docker metadata check alone is **not** a new Discord identity proof.
- Minimum round-two private precheck: low reasoning/output12345/REMoff/autonomyoff/RAGon, image qualityhigh, neither `hd_image` nor `image_generator` disabled; three allowed channels include the prepared smoke channel. One stored server prompt:1939UTF-8 bytes, none over16KiB. Base personality was not read. Recheck before rollout; do not restore these dated values over later human changes.

Earlier QA67–69 ran `be28b85` only for one180s-deadline smoke request, completed in8s with an exact marker body plus the configured footer, then restored the old image and original control bytes. It did not accept the new `89fb851` candidate. The three temporary-specific operator files remain installed; **host viewer/Screen were not updated or exercised**. Recovery lives in Operations and the private rollback root there, not in copied stale profiles.

## Retained decisions and limits

- Reasoning-only results remain terminal; fallback and mandatory tool-reasoning policy changes await root. Shell remains admin-or-allowlisted with the documented same-UID writable-control risk.
- Viewer oversized-record/redaction-continuity loss remains fail-closed until viewer restart, including affected canonical interactive paths. Current source is not host installation evidence.
- C09 import-time dotenv redesign is an accepted deferral, not an open task. P08/I05 historical provenance is permanently unattributable; quarantine remains retained, with no cache cleanup.
- Canonical native-image profile reconciliation remains held. No canonical private profile was inspected. Voice, exhaustive media/admin/plugin combinations, replicas, sustained load and remote-deletion recovery are not established by these tests or a happy-path READY/smoke receipt. Jobs do not resume workers after restart. Runtime footer markers are not cryptographic authentication.
- All existing refs/worktrees remain retained. Historical inventory26worktrees/25branches/22checkpoint refs and86commits (54patch-equivalent/32non-equivalent across13families) is a dated mapping, not current counts or proof of physical cleanliness. Five new QA evidence refs preserve exact intermediate/final trees; no pruning occurred.

## Documentation recovery

Current contracts belong in the nine `docs/` guides indexed by README. Root renamed the retained audit directory to `20260924T210402Z-audit`; original report text and historical path spellings stay unchanged. The obsolete `legacy/` removal was separately authorized (24files/3970lines), not a publisher or runtime change. 39phase files and28accepted internal notes were physically retired after contracts/recovery migration; original reports, quarantine and failed-run evidence remain. The closure receipt records their destinations and immutable recovery.

`git show eb188ac:phase-II_v2/SESSION_LOG.md` recovers the verbatim prior human grant; the same immutable revision retains all phase plans, provisioning/inventory, operating receipts and Vulture inputs. Historical status is also recoverable at `ab64853:docs/STATUS.md`. These are recovery references, not instructions to restore old files or reuse old authority. Root's unrelated ignored audit material, `reports/` and skill work remain untouched.
