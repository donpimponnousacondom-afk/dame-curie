# 07 — Coordinator process evidence and dispositions (in progress)

**RETIRE AFTER ACCEPTED ROUND TWO.** This records verified metadata and independently reviewed branch dispositions, not pruning authority or whole-application acceptance. Owner: coordinator. Keep the auditor's original reports unchanged.

## P-05 — verified local Git snapshot

Reference baseline: `ab64853c93eb0268c976a5a3444d49fcd1f4f50a`, before the remediation source commits. Coordinator independently ran `git worktree list --porcelain`, `git for-each-ref`, `git rev-list --left-right --count <base>...<ref>`, and `git cherry <base> <ref>` from this repository, without inspecting another checkout's filesystem. There were **26 registered worktrees, 25 local branch refs, two detached worktree heads, and 22 `refs/t3/checkpoints/*` refs**.

The frozen pre-remediation branch inventory contains **86** commits outside the baseline's ancestry: **54 patch-equivalent / 32 non-equivalent**. This disproves the quarantined review's 76/52/24 totals. The table holds the active branch at `ab64853` for that inventory; it is not a live ref-position claim. Coordinator re-ran `git rev-list --count --branches --not ab64853` after commit `e540be6`: the union **at that checkpoint was89**, with exactly **3** active remediation commits after `ab64853` (`7286aa2`, `551060d`, `e540be6`). The32 retained old-branch commits mapped below are unchanged. Patch equivalence is not semantic equivalence or proof that any working directory is clean.

All rows remain physically retained. For equivalent/ancestor rows, source history is accounted for but dirty-state and ownership checks remain prerequisites to any later removal. A separate Sol reviewer enumerated and source-mapped all32 non-equivalent commits across13 families in `review-worktree-supersession.md`; it did not reuse the rejected forensic conclusions. Coordinator read that mapping and independently verified all cited branch/replacement commit identities with `git show --no-patch`; current jobs, lifecycle and CLI corrections also have separate bounded source/QA receipts. This is not a coordinator rerun of every historical feature test. The auditor checkout and checkpoint refs are explicitly preserved. Round-two acceptance is the earliest retirement gate, not automatic deletion authority.

| Ref / detached worktree | Baseline-only / ref-only commits | Patch-equivalent / non-equivalent | Disposition now |
| --- | --- | --- | --- |
| `dev/phaseII_v2` | 0 / 0 | 0 / 0 | Active remediation checkout; keep |
| `main` | 128 / 0 | 0 / 0 | Ancestor ref; no registered worktree for this row; keep |
| `t3code/adversarial-project-audit` | 17 / 0 | 0 / 0 | Auditor checkout; preserve |
| `work/dirac-attachment-limits` | 33 / 2 | 0 / 2 | Independently mapped below; retain |
| `work/dirac-discord-jobs` | 80 / 10 | 10 / 0 | Patch-accounted; retain until retirement checks |
| `work/dirac-hardening-jobs` | 31 / 3 | 0 / 3 | Independently mapped below; retain |
| `work/dirac-hardening-ops` | 31 / 2 | 0 / 2 | Independently mapped below; retain |
| `work/dirac-hardening-relay` | 31 / 1 | 0 / 1 | Independently mapped below; retain |
| `work/dirac-hardening-smoke` | 31 / 5 | 0 / 5 | Independently mapped below; retain |
| `work/dirac-publisher` | 80 / 4 | 4 / 0 | Patch-accounted; publisher remains protected |
| `work/dirac-runtime-ops` | 80 / 8 | 8 / 0 | Patch-accounted; retain until retirement checks |
| `work/dirac-shared-rag` | 80 / 8 | 8 / 0 | Patch-accounted; retain until retirement checks |
| `work/dirac-smoke-lean` | 80 / 6 | 6 / 0 | Patch-accounted; retain until retirement checks |
| `work/dirac-smoke-runtime` | 80 / 12 | 0 / 12 | Independently mapped below; retain |
| `work/direct-shell-tools-20260919` | 115 / 2 | 1 / 1 | Independently mapped below; retain |
| `work/discord-only-deploy-20260919` | 115 / 2 | 1 / 1 | Independently mapped below; retain |
| `work/discord-only-docs-20260919` | 114 / 1 | 1 / 0 | Patch-accounted; retain until retirement checks |
| `work/job-routing-20260919` | 115 / 2 | 1 / 1 | Independently mapped below; retain |
| `work/openai-inference-names-20260919` | 121 / 1 | 0 / 1 | Independently mapped below; retain |
| `work/prune-email-20260919` | 123 / 2 | 1 / 1 | Independently mapped below; retain |
| `work/remove-companion-20260919` | 115 / 2 | 1 / 1 | Independently mapped below; retain |
| `work/remove-social-transports-20260919` | 115 / 1 | 0 / 1 | Independently mapped below; retain |
| `work/remove-web-api-20260919` | 115 / 5 | 5 / 0 | Patch-accounted; retain until retirement checks |
| `work/screen-logging-20260919` | 115 / 4 | 4 / 0 | Patch-accounted; retain until retirement checks |
| `work/source-boundaries-20260919` | 97 / 3 | 3 / 0 | Patch-accounted; retain until retirement checks |
| detached `prefix-review`, `b00b5b0` | 97 / 1 | 1 / 0 | Patch-accounted; preserve detached history/dirty state |
| detached `tool-prompt-review`, `49226a8` | 97 / 2 | 2 / 0 | Patch-accounted; preserve detached history/dirty state |

The two detached heads share `b00b5b0`; their counts must not be added to the branch-union total as distinct commits. Checkpoint-tree content, other checkout cleanliness and actual remote state have not been verified. No fetch, checkout, recovery/cherry-pick, ref deletion or pruning occurred.

### Semantic map of the32 non-equivalent commits

The independent report gives exact per-commit anchors and differences; short classification here does not assert identical branch tips:

- Attachment limits(2): rejected alternate documentation, corrected inventory retained. Actual-byte admission is committed in `d198c37` and included in QA60/61; SDK full-read allocation remains a documented limit.
- Hardening jobs(3): accepted at `4153a10`, corrected blocked-plus-allowlisted intersection at `65fe79e`; current parent catalog changes are additional work, not historical tip equivalence.
- Hardening ops(2): mapped to `eb3f2f1`, including resolved mount overlaps and publisher credential separation. Older recorded grant claims are historical assertions, not independently corroborated current authority.
- Hardening relay(1): mapped to `1783e26`, then request-lifetime correction `901200d`; not new live acceptance.
- Hardening smoke(5): mapped to `3671160`, then stricter current lifecycle `551060d`; no inheritance of an old suite count as new validation.
- Smoke runtime prototype(12): expressly superseded by the lean protocol and later own-turn evidence; do not restore the rejected two-record/queue protocol. Accepted CLI withdrawal correction is now `e540be6` with5 isolated protocol tests passed.
- Direct shell(1): integrated via `f13b581` plus `d2d511c`; current authorization/environment corrections are committed in `d198c37` and included in QA56/60; same-UID secret isolation is not claimed.
- Discord-only deploy(1): integrated at `f045ec3`, then bridge retirement `a1da1fd`; canonical activation remains held.
- Job routing(1): integrated at `0fe607b`/`57806d9`, packaged/corrected at `ee42266`/`9d1abc8`; current prefix/prompt/catalog corrections are committed in `d198c37`, with integrated QA56/60 and separately bounded QA67–69 delivery evidence. This is not equivalence with every historical tip.
- Remote inference naming(1): mapped to `b2f5380`; protocol naming is not a vendor/account switch. No private values re-inspected in this review.
- Email(1), companion(1), social transports(1): deliberate cuts at `9b01074`, `e7f0acd`, `192aac2`; generic inbox/media/autonomy and historical private-memory exclusion remain. Unique consumer/privacy/migration notes survive through review.

No row authorizes a checkout/ref deletion. Coordinator retains ownership of unreviewed checkpoint contents, physical dirty-state/ownership checks and post-round-two retirement. No remote state was fetched.

## P-08 — artifact presence is not execution attribution

Coordinator ran only `stat` and `git check-ignore` for these artifact observations, with no Python interpreter or bytecode decoding:

- `__pycache__/provider_telemetry.cpython-314.pyc`: 22,043 bytes, file mtime `2026-09-23 15:25:53.236313953 +0200`.
- `__pycache__/response_observability.cpython-314.pyc`: 36,102 bytes, file mtime `2026-09-23 15:27:57.797885728 +0200`.
- Both paths match `.gitignore:4` (`__pycache__/`).

These are file metadata, not embedded source sizes/times or proof of host application import. The decoder-derived claims in `review-process-evidence.md` are excluded; this checkpoint neither confirms nor refutes the auditor's narrower uncommitted-source-bytecode hypothesis. Historical artifact provenance remains unattributed. The auditor also cited compiled test modules under `.validation-cache/`; the two root-file stat observations above do not inspect or establish that tree's contents/origin. Older compile-only documentation is not proof of where those cache files were produced, and neither a host import nor a clean history is established. No cache-content inspection, deletion or decoder-derived attribution was accepted. Current isolated QA does not establish what happened in older rounds. Preserve evidence and qualify historical no-host-execution claims rather than deleting files or inventing an origin.

## P-09 — current authority versus historical assertions

The current direct human grant is quoted in `phase-II_v2/SESSION_LOG.md`; it authorizes this remediation and bounded temporary acceptance, not retroactive approval of earlier actions. Older author-written assertions about root's choices remain historical claims unless corroborated. Coordinator condensed `docs/STATUS.md` into current milestones/holds and labelled historical receipts; its previous narrative remains in `ab64853:docs/STATUS.md`. `README.md` now distinguishes source progress, temporary running Dirac and held canonical activation; `REDESIGN_PLAN.md` marks its old authority narrative as historical rather than a current grant, including the taint-removal attribution. These documentation corrections were committed in `3754a8a` and updated with current artifact/runtime evidence in `663749b`/`4c80d4c`; final independent review does not retroactively validate historical assertions. Unknown older authorization remains unknown, not retroactively manufactured.

## Review-method failure

Process reviewer `5f9fde83-17d9-4e58-8231-c43f579ec0d0` violated its explicit no-interpreter-execution assignment, initially disclosed two and later five invocations, and did not supply full recoverable command receipts. It also supplied incorrect Git totals and unsupported bytecode inferences. Its report is quarantined with a coordinator warning; preserve it through review. No application import or decoded-code execution was reported, but the coordinator does not convert that self-report into independent verification. Accepted evidence above was collected separately using authorized methods.
