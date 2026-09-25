# Dirac V2 — remediation and retirement ledger

## Authority and remaining work — 2026-09-25

Root approved complete remediation of `audit/20260924T210402Z-adversarial-audit/`, independent Luna/Sol/DeepSeek review, coherent local commits, isolated QA and bounded temporary-Dirac acceptance. Normal release and canonical/V1/publisher/remote changes remain frozen. Ordinary use of the existing shared embedding API is permitted; separate profile stores are not merged by sharing computation. No shared-service configuration/lifecycle changes, dependency-pin relaxation or new test files/functions. Coordinator owns runtime/private access; source children do not.

Primary deliverable: `audit/20260924T210402Z-adversarial-audit/05-IMPLEMENTER-RESPONSE.md`:52 findings plus6 implementer-raised items. It remains a working draft until the final consistency pass, and is not the independent auditor's acceptance verdict.

**Remaining:** independently check final evidence/disposition consistency, then checkpoint the completed response and handoff. All52 finding blocks and6 implementer items are now reconciled. Do not manufacture historical authorization/bytecode provenance or equate one live happy path with comprehensive feature acceptance. Retirement is gated on accepted round two, not this implementation pass.

## Checkpoints and demonstrated results

- Root correctly rejected the four-hour uncommitted accumulation. Commit every completed bounded slice before beginning another; preserve an explicitly labeled WIP checkpoint at a handoff if unfinished. No more giant single-agent assignments. Preserve unrelated `reports/` and `.agents/skills/root-review-reports/`.
- `d198c37`: integrated application/test/build-input fixes. `3754a8a`: full dated audit evidence checkpoint, including unchanged originals and failed-run evidence. `be28b85`: missing Docker allowlist entries and constructor-probe import isolation corrected. Later bounded doc checkpoints: `663749b`, `61111fe`, `99118dc`, `5023c8c`, `4c80d4c`.
- QA60 frozen tree`e2d639755f90bfb16ff8a834975ae704772cb6ae`: **3984 passed,28 subtests passed**, selected Ruff passed. Only two inspected manual live-provider scripts with no collectible cases were ignored. Earlier QA52–55 failures remain retained; no xfail-for-green.
- QA61: **201 passed** after two fixture-constructor removals; QA62: **4 passed** with the copied application as the constructor child's only added import path. Independent tracked-test definition inventory reconciles three approved one-to-one fetch-case renames; no new definitions in the narrowed final diff.
- Candidate `dame-curie-app:be28b85`, immutable **`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`**:56 copied input blobs and baked/OCI provenance match Git; existing guarded constructor passed inside the actual image. QA61/65 measured real synthetic catalogs:70 builtins+4 plugins; admin core15/full74, not the historical flat73. Counts/characters are not model token or billing measurements.
- QA67–69: one180s-deadline request`608cc14a42714fd58bafbf8084b09690` in approved channel`1550960386939817984`, operator root`1482143139828596916`, confirmed Dirac identity`1504398705539944560`. Completed in8s with one exact marker body plus configured runtime footer and no readback failure. Initial coordinator logger-selector and whole-wire-equality failures are retained; no inference retry. This is one happy-path model/delivery case, not adverse-path or all-feature acceptance.
- **Current runtime is the old image**, restored after the case: `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`, container`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`. Identity/readiness reverified; original controls restored byte-for-byte, private profile fingerprint unchanged; low reasoning/12345 cap/REMoff preserved. Three temporary-operator files remain updated; host viewer/Screen not installed, operated or reattached. Exact receipts/limits: `validation.md`; operating handoff: `phase-II_v2/DIRAC_HANDOFF.md`.

## Slice ownership and acceptance boundary

| Slice / findings | Review ownership | Current evidence / limit |
| --- | --- | --- |
| Provider outcomes, usage and budget, C01/06/11–14; I06 | Luna implementation, independent Sol, coordinator integration/QA | Committed; independent gap corrections and QA56/60 passed. Explicit-only reservation/refunds and terminal incomplete policy; no universal billing/provider-compliance guarantee. |
| Native history, arguments, recovery and prompt budgeting, C02/07/15/16/18 | Sol source, Luna integration, independent bounded Sol/Luna reviews | Committed; integrated QA56/60 passed. Custom protected prefix correction included; prefix classification is not provenance authentication. |
| Delivery/cancellation and unsafe live test, C08/34/35 | Sol source, coordinator integration/QA | Synthetic replacement and caller/settlement coverage passed. QA67–69 adds one happy-path real delivery, not cancellation/response-loss injection. |
| Discovery/job catalog and replay, C17/21; I02/04 | Luna core, coordinator jobs, independent Sol and micro reviewers | Committed and QA56/60 passed; actual synthetic catalog sizes measured. Per-job discovery is separate from inherited spend. |
| Prompt limits/prefixes, C03/22/30 | Luna core, coordinator prefix/jobs/docs, independent reviews | Committed; existing caller/background cases executed. Bounded readback/export and whole legacy omission retained. |
| Image configuration/inputs, C04/05/25–29 | Sol source, independent Flash checked by coordinator | Synthetic QA60 and artifact construction passed; no live image generation. Temporary quality high and no retired/current image disable ambiguity observed; canonical migration held. Same-UID realpath/read TOCTOU remains. |
| Media/result persistence, C19/20; I03 | Luna source, bounded independent review, coordinator QA | Actual-byte checks and media scrubbing committed; QA60/61 passed. SDK full allocation before rejection is not streaming/peak-memory protection; no new .7z support. |
| Shell/persistent rewrite policy, C23/24 | Coordinator, independent Luna and plugin review | Actor/direct/catalog gates and subprocess environment tested. Same-UID filesystem access remains; no secret-sandbox claim. |
| Viewer/producer, C31–33 | Coordinator, independent Luna | Viewer `7286aa2`:185 focused passes plus QA60. Producer in application candidate; host viewer is not bundled in that image or installed in the existing Screen workflow. |
| Operator/smoke, C36/37; I01 | Sol source, independent Luna/Sol, coordinator runtime | `551060d`:117 focused passes; `e540be6`:5 protocol passes; QA60. Three temporary operator files installed/verified; real readiness and one receipt passed. Negative lifecycle/cancellation cases remain isolated coverage. |
| Import/build boundaries, C09/10 | Coordinator plus independent packaging review | Artifact verified after allowlist/import-isolation correction. Import-time dotenv remains; no host application imports/test execution. |
| Process/history, P01–P09; I05 | Coordinator plus independent source/metadata reviewers | Current grants, failed attempts and checkpoints recorded; retained history and unresolved attribution are not erased. All refs/worktrees retained. |
| Docs and final reply, D01–D06 | Coordinator plus bounded Sol reconciliation; rotated final reviewer pending | Finish remaining blocks and final consistency review. No normal release or external audit acceptance claimed. |

## Review continuity — do not reopen oversized or unsafe lanes

- Retired oversized Luna session **`9a83b781-cf05-414c-b824-e2401be2ff2d` must not be resumed**. Its work was preserved, decomposed and integrated, not discarded.
- Six bounded handoffs: provider admission`d2f63607`, strict native JSON`b3d1baec`, plugin precedence`c73f34cb`, result-media persistence`7daa720d`, custom prompt protection`cd141c75`, longprompt export`fd64b84b`. Reports preserve parent corrections, including the false notice-length claim and tree-versus-HEAD confusion.
- Earlier frozen core reviews`59118c63`/`2b977fdc` exposed gaps subsequently corrected; viewer/actor review`017888d0`, lifecycle/viewer review`36696484`, image review`2ed8359d` and packaging review`77e0c7a7` remain dated evidence, not self-executing authority.
- Unsafe viewer handoff`67b1d3b7` and method-violating process review`5f9fde83` remain quarantined/frozen. No accepted decoder-derived bytecode attribution; original reports/retractions remain retained.
- Frozen branch inventory:26 worktrees,25 branches,2 detached heads,22 checkpoint refs;86 pre-remediation commits outside baseline ancestry split54 patch-equivalent/32 non-equivalent. Independent review`19bc4ed9` mapped32 across13 families. The earlier union89 belonged to the snapshot with three added remediation commits, not today's HEAD. No ref/worktree removal or other-checkout filesystem inspection; checkpoint contents/physical dirty-state remain separate gates.
- Child authors do not self-accept their work. Use fresh bounded contexts, explicit file ownership and no overlapping writes. Runtime/QA remain coordinator-only. Exact selections, failures and corrections live in `validation.md`.

## Selected behavior and retained limitations

- Genuine partial answers may be delivered with a clear cutoff notice; no subsequent recovery/tool dispatch/paid retry. Reasoning-only stays terminal and private.
- Foreground defaults:32768 reserved output tokens,12 actual generation POSTs,600 monotonic seconds; positive controls via `ForegroundTurn.from_controls`. Only validated explicit output refunds reservation. Descendants share spend; independent jobs do not. Unknown usage retains reservation; no bot-wide/billing guarantee.
- Foreground extras: absent `n` or exact integer1 only; recognized competing cap fields must be positive integers and are clamped without raising lower values. Admission occurs before fallback/vision selection or POST. Nonforeground semantics remain distinct; no universal provider precedence claim.
- New server prompt writes16KiB UTF-8; inline readback1800 bytes; file export512KiB. Oversized stored legacy prompts remain stored and are omitted whole from model context with a configured-prefix diagnostic. Default schema-inclusive prompt budget96000 characters; history tail36000 characters. No silent clipping of protected identity/tool contracts.
- Genuine task-local discovery preserves all registered capabilities; ordinary image visibility requires usable configuration. Shell admins/whitelist and persistent-rewrite admins are gated separately from discovery. Minimal shell environment is not same-UID secret isolation.
- Runtime usage follows configured prefix; canonical documentation uses `!`. Image low is the source default, not an override of private high. Invalid image settings disable that capability; canonical migration/activation remains held.
- Preserve existing-case-only verification, historical grant/provenance uncertainty, SDK allocation/TOCTOU/ingress limits and the unsupported-archive correction. The20MiB override did not implement extraction or establish V1 10MiB parity.

## Mandatory document retirement — coordinator owns the accepted-round-two gate

Do not delete unaccepted evidence or turn every scratch report into permanent documentation. The original auditor files remain unchanged. Historical TODO versions stay in Git; failed-run details remain in the dated audit bundle.

| Material | Action after accepted round two |
| --- | --- |
| `05-IMPLEMENTER-INTAKE.md` | Remove superseded intake. |
| `06-TOOL-INVENTORY.md` | Fold surviving capability/discovery contract into current docs; remove historical/current measurement working sheet. |
| `07-PROCESS-DISPOSITIONS.md` | Consolidate unresolved provenance, retained-history and ownership gates; it is not pruning authority. |
| Dated `implementation-*.md`, `review-*.md`, `micro-*.md`, `validation.md`, QA recipe and failed-output archive | Preserve all failures/retractions/quarantine until review; consolidate exact accepted commit/QA/runtime references, then remove temporary copies. New notes in this bundle inherit this rule. |
| Originals00–04, `child-reports/`, filled response and final audit verdict | Preserve verbatim through review; consolidate final result/provenance into one compact receipt before retiring the working bundle. |
| Loose historical `audit/` reports | No new loose reports. Retain unresolved facts; consolidate before retirement. |
| `phase-II_v2/` plans/ledgers/handoffs | Move surviving identity/isolation/operator/rollback boundaries and activation holds into current docs before retiring superseded notes. |
| Long STATUS/TODO history | Keep current status brief; historical detail is retained in Git and accepted evidence, not duplicated indefinitely. |
| This `TODO.md` | At closure retain only real outstanding work, or remove if none; retire the expired checklist. |
| Root's unrelated `reports/` and `.agents/skills/root-review-reports/` | Not part of this cleanup; preserve. |

Durable set: `AGENTS.md`, concise `README.md`/`docs/STATUS.md`, current development/operations/architecture/security and useful feature references. Private rollback material stays private and is not automatically deleted by documentation retirement. No worktree/ref/cache removal without its separate ownership/dirty-state/provenance gate.

## Before sending the final auditor handoff

- [x] Finish all52 findings and6 implementer items with exact commits/evidence; final consistency review remains the explicit active gate.
- [x] Cross-lane source corrections independently reviewed and revalidated; real bugs not hidden behind subset counts.
- [x] Complete safe suite and narrowed final corrections recorded with baseline failures retained.
- [x] Artifact source/provenance and actual-image construction checked.
- [x] Bounded temporary acceptance, identity/channel, checker failures, cleanup/restoration and limits recorded.
- [ ] Rotated final response/evidence consistency review completed and findings addressed.
- [ ] Final response/handoff checkpointed; no relevant jobs or intended uncommitted changes left.
- [ ] External round-two acceptance received before any evidence retirement or normal release.
