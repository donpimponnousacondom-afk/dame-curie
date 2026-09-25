# Dirac V2 — remediation and retirement ledger

## Current authority — 2026-09-25

Root approved complete autonomous remediation of `audit/20260924T210402Z-adversarial-audit/`, independent Luna/Sol/DeepSeek review, isolated QA and bounded automated temporary-Dirac acceptance. Normal releases remain frozen until the final audit is accepted. No canonical/V1/publisher/remote changes; no dependency upgrades or new test files/functions. Coordinator owns all runtime/private access and exact-tree QA. Historical integration checklists remain in Git and `phase-II_v2/`; they are not current grants.

Primary audit response: `audit/20260924T210402Z-adversarial-audit/05-IMPLEMENTER-RESPONSE.md` (to be completed from the auditor's template). Do not use an intake note, a child's self-review or a passing subset as final closure. Every C-01…C-37, P-01…P-09 and D-01…D-06 requires a disposition and evidence.

## Work ownership and acceptance

| Slice / finding IDs | Owner | Status / required evidence |
| --- | --- | --- |
| Provider incomplete outcomes, C-01/11/12/13/14 | Luna; coordinator caller integration | In progress: terminal typed outcomes, bounded safe partial content and available usage, bounded drain/capture, no reasoning promotion or truncated tool execution. |
| Native history, public arguments and recovery bounds, C-02/07/15/16/18 | Sol; coordinator budgets/call sites | In progress: useful whole-group retention, bounded newest batches, idempotent compaction and input/schema accounting. |
| Delivery/stream cancellation and unsafe live test, C-08/34/35; partial-delivery memory | Sol; coordinator memory/call sites | In progress: real settlement, no deleted successful answer, deterministic synthetic replacement for the existing live-provider case. |
| Viewer redaction, C-31/32/33 | DeepSeek Flash; coordinator producer | In progress: distinguish scanned rejection from actual continuity loss; no secret-state reset; omissions visible independent of scope. |
| Shell/rewrite authorization and environment, C-23/24 | Coordinator | Pending implementation and bypass review. Actor whitelist/admin policy; environment filtering is not same-UID secret isolation. |
| Turn spend/deadline, catalog selection, C-06/17/21 | Coordinator | Pending integration with provider attempts and turn-local discovery; retries/missing usage cannot count as free. |
| Prompt upload/readback/core integrity/prefixes, C-03/22/30 | Coordinator | Pending bounded content and configured runtime prefixes; never middle-trim identity/tool contracts. |
| Image config/defaults/inputs, C-04/05/25/26/27/28/29 | Coordinator, subsequent source lane | Pending feature-scoped config failure, consistent low quality, usable-registration gate, realpath handling, explicit scratch generation and clean-cut name policy. |
| Media and persisted tool-result bounds, C-19/20 | Coordinator | Pending bounded new-media follow-ups and truthful capped metadata. |
| Operator/smoke lifecycle, C-36/37 | Coordinator, subsequent source lane | Pending honest status/restart semantics and every opened turn settled on failure/cancellation. |
| Config import/environment boundary and build exclusions, C-09/10 | Coordinator | Pending actual isolation evidence and explicit build exclusions. |
| Validation debt/process/old worktrees, P-01/02/03/05/07/08/09 | Coordinator + independent reviewers | Pending complete baseline failure ownership, exact-tree credential-free QA, safe branch disposition, grant/provenance reconciliation and pre-acceptance checklist. No xfail-for-green. |
| Archive removal, P-04 | Coordinator | Completed at `aad36e6`: 24 files removed, active references corrected, no runtime change. |
| Current docs and evidence retirement, D-01…D-06 / P-06 | Coordinator | In progress; see mandatory cleanup schedule below. |
| Final independent review and auditor template | Coordinator + rotated reviewers | Pending all source slices, integrated QA, bounded acceptance and cross-review of each lane. |

### Active source children

- Luna `19167867-5542-434b-99de-f3a2cbdd6b47`: provider/telemetry/error capture and owned existing tests.
- Sol `3bdbf163-811b-40a1-a8a7-48f3b7d5e392`: tool schemas/progress and owned existing tests.
- DeepSeek Flash `67b1d3b7-1c2e-4c2a-adf0-31f6fbd0ebb5`: log-console package and owned existing tests.

Shared working tree; no overlapping writes, child commits, child runtime or child test execution. Coordinator owns `bot.py`, `bot_tools.py`, policy integration and docs. Every new lane must be assigned before edits.

## Decisions under the current implementation grant

- Partial genuine answer text may be displayed with an explicit incomplete notice through a terminal-error path; never recover or execute its tools. Reasoning-only output stays terminal, without paid automatic retry/fallback.
- Wire shell execution to admins plus the existing shell whitelist; persistent prompt rewrite tools are admin-only. Apply the same policy to advertised names and execution, including aliases.
- Runtime usage strings use the configured prefix. Documentation examples retain the canonical `!` convention.
- Image configuration failure should disable/refuse image capability, not unrelated bot startup; canonical activation still needs explicit, separate readiness/migration acceptance.
- Keep all retained product capabilities; reduce ordinary catalog exposure through genuine turn-local discovery rather than silently removing games/voice/admin tools. Image generation remains ordinarily visible when usable, as previously requested.
- Preserve the existing-case-only test rule; replace unsafe/flawed existing cases rather than suppress them. New verification means new inputs/assertions in existing cases, not new test files/functions.
- Normal releases remain frozen. Isolated candidate QA and strictly temporary test-channel acceptance are not general rollout approval. Do not repeatedly replace the temporary runtime after each slice.

## Mandatory document retirement — owner: coordinator

**Root explicitly asked for this cleanup. Do not keep multiplying status documents or let another agent treat old notes as active instructions.** Temporary evidence may be extensive during remediation; it must be consolidated and removed after the final review is accepted. Do not delete audit evidence before the reviewer has consumed it.

| Material | Lifetime / removal action |
| --- | --- |
| `audit/20260924T210402Z-adversarial-audit/05-IMPLEMENTER-INTAKE.md` | Temporary intake, superseded by the final response. Remove after accepted round two. |
| `audit/20260924T210402Z-adversarial-audit/06-TOOL-INVENTORY.md` | Temporary baseline catalog, not the post-fix contract. Fold only surviving user-facing capability/discovery documentation into current docs, then remove after accepted round two. |
| `audit/20260924T210402Z-adversarial-audit/implementation-*.md` and additional lane/QA/review artifacts | Temporary work evidence. Summarize final commit/QA/acceptance references in the response; remove after accepted round two. All new notes in this bundle inherit this rule. |
| Auditor originals `00`…`04`, `child-reports/`, filled implementer response and final round-two report | Preserve verbatim until final acceptance. Then consolidate the final outcome/provenance into one compact release receipt; remove the working bundle. Do not rewrite the auditor's originals during remediation. |
| Loose historical `audit/` reports | Do not create more loose reports. Inventory for useful unresolved facts, consolidate them, then retire during final cleanup; never infer that a historical finding disappeared. |
| `phase-II_v2/` working plans, ledgers and handoffs | Consolidate surviving architecture, isolation, operator/rollback instructions and unresolved activation holds into current `docs/`; retire superseded phase notes at final closure. No loss of unique recovery/identity boundaries. |
| Long historical sections in `docs/STATUS.md` and superseded TODO checklists | Current status must be brief. Keep dated evidence in the temporary bundle until accepted, then one final release receipt rather than duplicated narratives. Old TODO history remains in Git. |
| This `TODO.md` | Keep while implementation/review/retirement is open. At closure replace with only real outstanding product work, or remove if none; remove completed checklists and this expired retirement schedule. |
| Unrelated `reports/` and `.agents/skills/root-review-reports/` | Preserve root's pre-existing untracked work. Not implicitly part of audit cleanup. |

Durable set: `AGENTS.md`, concise `README.md`, `docs/STATUS.md`, current development/operations/architecture/security and genuinely useful feature references. Consolidate overlap; do not convert every scratch note into a permanent page. Build contexts must exclude audit/report artifacts.

## Carry-forward facts that must not disappear during cleanup

- Coordinator owns the earlier unsupported-archive/image-limit misclassification report. The last recorded 20 MiB incoming override was a setting change, not a repair. Reconcile the attachment path and give this an implementer-raised disposition rather than silently dropping it with the old TODO.
- Shared embedding endpoint filtering and publisher path masks are not independent same-UID resource/secret isolation. Preserve those limits and canonical activation holds in the surviving operations/security docs; do not expand this assignment into publisher changes.
- Preserve the current temporary-Dirac personality/state during acceptance; do not claim an earlier tmpfs-only prompt was recovered or reconstruct private text from memory.

## Before requesting the final audit

- [ ] Every finding has a source-backed disposition, local commit(s) and exact QA selection/result.
- [ ] Provider/tool/history/authorization/delivery/logging interfaces were reviewed across lanes, not only inside files.
- [ ] Complete safe existing-suite results and baseline comparisons have named outcomes; no known defect is hidden behind a green subset.
- [ ] Independent reviewers challenged the integrated candidate and fixes were revalidated.
- [ ] Temporary acceptance, if performed, records exact identity/channel, tree/image, bounded scenarios, delivery and cleanup; no canonical/V1/publisher mutation.
- [ ] Auditor template is complete, temporary notes carry their removal lifecycle, and no contradictory active assignment remains.
- [ ] No uncollected relevant jobs, accidental source changes or unstaged intended fixes remain; no remote push.
