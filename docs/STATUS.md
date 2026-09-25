# dame-curie status

## Current authority — 2026-09-25

**Normal releases and canonical/V1 activation remain frozen.** Root authorized the complete local audit remediation, independent review, credential-free isolated QA and bounded automated acceptance in the prepared **temporary Dirac** test channel. Candidate testing is not release to normal use. Coordinator alone owns authorized runtime/private access; publisher, protected V1, canonical identity/state and remotes remain untouched.

[AGENTS.md](../AGENTS.md) defines the boundary; [TODO.md](../TODO.md) owns current assignments and retirement gates. The current human grant is quoted in [SESSION_LOG.md](../phase-II_v2/SESSION_LOG.md). Earlier author-written assertions about root's instructions are historical claims, not new or retroactive authority.

## Verified source milestones

| Slice | Local commit / exact tested tree | Isolated result |
| --- | --- | --- |
| Viewer C-32/C-33 | `7286aa2` / `bdd636d05898bcc41aafc4f3d75371c3991fbc5f` | 185 passed across six existing suites |
| Lifecycle C-36/C-37 | `551060d` / `c13f3d5a492069da1594ee3e61ebe0e82e0ba119` | 117 passed across four existing suites |
| Pending smoke-request withdrawal race | `e540be6` / `56062c02b3027ade1d58bd678ffc9efd1cc5fb48` | 5 protocol tests passed |

All used Python 3.14.4 with no external network/private mounts; selected Ruff `F821,F822,F823` and independent source reviews passed. These are **separate focused selections**, not whole-repository or deployment acceptance. Exact commands, trees, failed attempts and corrections: [current validation ledger](../audit/20260924T210402Z-adversarial-audit/validation.md).

Current checkpoints: `d198c37` commits integrated application/test remediation; `3754a8a` preserves docs and the complete dated audit bundle; `be28b85` fixes Docker allowlisting and constructor-probe import isolation. Full-safe QA60 passed **3984 tests plus28 subtests**; final fixture corrections passed201 and isolated copied-app construction passed4. Earlier failed runs remain retained. This closes the previously unexecuted core/full-safe-suite gate, not every operating combination.

Candidate **`dame-curie-app:be28b85`**, image **`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`**, is built from the committed archive. All56 copied input blobs and baked/OCI provenance match `be28b8598215ff6a0c72d7c3160403f2425a61f0`; the existing guarded constructor probe passed inside the actual image without network/private mounts/login. **QA67–69 exercised the candidate temporarily, then restored the prior image and original controls.** One180s-deadline request completed in8s with one exact marker-body delivery plus the configured runtime footer. Initial identity-selector/wire-equality checker failures remain documented. Current temporary container is `495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, running old image `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`; identity/readiness and byte-exact control/profile preservation reverified. Three temporary-operator files are updated; host viewer/Screen unchanged. The complete52-finding/6-item response and retirement ledger are ready for independent auditor round two. Rotated Luna/DeepSeek document reviews and narrow correction rechecks are complete; originals, failures and unresolved limits remain retained. This bounded happy path is not feature-complete live acceptance or a normal release.

The authorized `legacy/` cleanup is committed separately: 24 obsolete files, 3,970 text lines. It did not change active publisher source or root's unrelated `reports/` and `.agents/skills/root-review-reports/` work. Historical source is evidence, not a restoration instruction.

## Historical temporary runtime — 2026-09-24

The prior 2026-09-24 receipt records temporary Dirac `1504398705539944560` on source **`685902588f8c9e4d3aacd340b4d8b15f10e5af19`**:

- Image `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`; container `0b1ba5fd43d75319d4908ba01cf32dce6cf87c5df5b5a145c0540c1175cb4ef6`.
- Recorded controls: reasoning **low**, output cap **12,345**, **REM off**, prefix **`?`**, 20 MiB incoming override; private profile/state and smoke mounts retained. These are historical observations, not a fresh inventory or current source defaults.
- That release bounded producer tool-result logging and added `logs --fresh`; it did not certify all viewer paths, successful tool-result storage bounds or attachment classification. Raising the incoming limit alone did not fix archive handling.
- Recorded Screen `830408.dirac-v2` / Bash `830410` and rollback `/var/backups/dame-curie-dirac/console-fix-20260924T190446Z/` are recovery references, **not permission to access or manipulate them**. Do not restore stale profile/state snapshots during image rollback.

### Consolidated same-day historical receipts

These are prior reported results, not current reruns, proof of every historical method, or authorizations. Detailed records remain in the linked local audit evidence; the complete former status narrative is preserved in Git at `ab64853:docs/STATUS.md`.

| Source | Reported QA / qualification | Evidence |
| --- | --- | --- |
| `6859025` — bounded tool logging | 368 passed / 5 baseline-reproduced failures / 1 excluded; two failed build attempts were not deployed; no coordinator inference or oversized-output probe | `audit/dirac-console-freeze.md`, `audit/dirac-reasoning-audit.md` |
| `74d827d` — incomplete provider outcomes | 1,321 passed / 4 baseline-reproduced failures / 2 deselected; trailing SSE usage and partial delivery remained audit subjects | `audit/provider-incomplete-validation.md` |
| `4e4027a` — unified native images | 1,219 passed / 24 baseline-reproduced failures / 2 deselected; synthetic image checks and READY were **not live generation/edit acceptance** | `audit/image-unification-validation.md` |

Earlier role/reload, source-review, provisioning, transport, memory and tool receipts remain in [SESSION_LOG.md](../phase-II_v2/SESSION_LOG.md), [DIRAC_HANDOFF.md](../phase-II_v2/DIRAC_HANDOFF.md), [DIRAC_INTEGRATION.md](../phase-II_v2/DIRAC_INTEGRATION.md) and [RUNTIME_VALIDATION.md](../phase-II_v2/RUNTIME_VALIDATION.md). Their dated grants, scope limits and failures do not establish present runtime state. Historical bytecode provenance remains unattributed; the process review's prohibited-method and incorrect-count claims are quarantined in the current audit bundle.

## Activation and retirement holds

- Canonical image activation requires review of the native image profile and retired-key migration first; see [IMAGE_GENERATION.md](IMAGE_GENERATION.md) and [PROVISIONING.md](../phase-II_v2/PROVISIONING.md). No canonical private profile was inspected or changed in this remediation.
- Separate accounts/engines are the intended isolation boundary. Endpoint filtering and publisher path masks do not provide independent same-UID resource/secret isolation. Preserve these limits; no V1/shared-service repair or publisher redesign is authorized.
- Voice, exhaustive media/admin/plugin combinations, replicas, sustained-load behavior and remote-deletion recovery are not inferred from focused tests or historical READY receipts. Existing jobs are not claimed to resume after restart.
- Final audit acceptance is still required. Preserve originals, failed runs, unresolved findings and retractions until round two is accepted. Then consolidate surviving contracts into the small current docs set and retire the temporary bundle/phase notes according to [TODO.md](../TODO.md); do not erase unresolved evidence to claim completion.

Work remains local on `dev/phaseII_v2`. A local commit never synchronizes a runtime or authorizes a release.
