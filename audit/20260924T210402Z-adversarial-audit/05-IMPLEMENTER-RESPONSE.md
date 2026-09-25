# 05 — Implementer response — WORKING DRAFT

**Not submitted for final acceptance.** Coordinator owns completion of every block below. `deferred` in this draft means **active remediation pending the stated evidence**, not a proposed permanent carve-out. Candidate `be28b85` is built and source/construction-verified; it has **not been deployed**. The per-finding blocks below still retain intermediate pending wording and require final reconciliation; the latest evidence summary supersedes those execution/commit-state claims, not their disclosed limitations. Normal release, canonical/V1 activation, publisher and remote operations remain frozen.

Root's current grant and its limits are recorded in `../../AGENTS.md`, `../../TODO.md` and the verbatim entry in `../../phase-II_v2/SESSION_LOG.md`. It does not retroactively authorize older actions. Originals00–04 are unchanged. Keep this bundle and independent reviews through accepted round two; follow the retirement ledger afterward, preserving unresolved provenance and operating boundaries.

## Evidence keys and current commit boundary

- **V:** commit `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`, tree `bdd636d05898bcc41aafc4f3d75371c3991fbc5f`; Python3.14.4 isolated Ruff F821/F822/F823 passed; **185 passed**. Exact selection: `tests/test_log_console_render.py tests/test_log_console_robustness.py tests/test_log_console_events.py tests/test_log_console_history.py tests/test_log_console_integration.py tests/test_log_console_tty.py`.
- **L:** commit `551060dbb7d223e1f365c069fbff2db377406f17`, tree `c13f3d5a492069da1594ee3e61ebe0e82e0ba119`; same isolated Ruff selection passed; **117 passed**. Exact selection: `tests/test_dirac.py tests/test_dirac_operator.py tests/test_dirac_smoke.py tests/test_message_pipeline.py`.
- **S:** commit `e540be6772f76d906720b79b07947a60893c3b24`, tree `56062c02b3027ade1d58bd678ffc9efd1cc5fb48`; selected Ruff passed; **5 passed** in `tests/test_smoke_protocol.py`.
- **P:** uncommitted provider seam tree `9b3ec91e304d0bacaa2515f14fe9904710eee50a`; selected Ruff passed; **199 passed** in `tests/test_provider_error_reporting.py tests/test_providers.py tests/test_error_reporting.py tests/test_smoke_protocol.py`. This predates the newly identified request-shape correction and is NOT current caller or complete provider acceptance.
- **J:** uncommitted background seam tree `869157081116c6968c177e7f1954e0e56e418f37`; selected Ruff passed; **39 passed** in `tests/test_background_jobs.py`. Uses baseline bot plus existing doubles, not full real-bot integration.
- **First full-safe integration:** QA52 tree `21f57d4801720e33035f31b2353ed10d188d2844`: selected Ruff passed; **3894 passed,83 failed,9 errors,28 subtests passed**. QA53 preintegration `e540be6`: **3884 passed,42 failed,9 errors,1 deliberately deselected historical unsafe case,28 subtests passed**. QA54 fixture reconciliation tree `f38e3e400fa4c8036f0477a0d25cb1fe7a40a21d`: **970 passed,4 original unsupported-reasoning failures retained**. These are not whole-core acceptance. Case-level ownership and exact safe selections are in `qa52-53-triage.md`; full failed evidence remains retained.
- **Bounded integration recheck:** root directed divide-and-conquer; oversized Luna run was stopped, not restarted. Six fresh single-issue handoffs completed. QA55 tree `1354ca309efa6ffe24cdf7beb2905dfd45cb8760`: selected Ruff passed; **644 passed,13 failed** in the explicit core selection, including successful real foreground/provider cases but remaining fixture errors. QA56 tree `a58e8932abdc9009bde187060a90806a79ef5416` reran the same22-file selection after existing-fixture corrections: **657 passed**, selected Ruff passed, exit0. This is green bounded core integration, not a green full suite. Final independent acceptance, definition inventory, remaining baseline/environment debt, artifact and bounded temporary acceptance remain open. Exact commands/failures/corrections are retained in `validation.md`; no xfail-for-green or hidden discarded failures.

- **Current accepted source/QA checkpoint:** `d198c37ee038e57e7cca4183b60eef0eaef6f1fc` commits the integrated application/test fixes; `3754a8a` checkpoints the full dated audit evidence. QA60 full-safe suite on tree`e2d639755f90bfb16ff8a834975ae704772cb6ae`: **3984 passed,28 subtests passed**. Two final fixture helper removals rechecked in QA61: **201 passed**. QA62: **4 constructor cases passed** after preventing copied-app imports from falling back to the original checkout. New helper definitions were removed, existing fetch cases renamed one-to-one, no xfail-for-green. Exact source/image/selector/environment limits and retained failures are in `validation.md`.
- **Candidate artifact:** packaging fix `be28b8598215ff6a0c72d7c3160403f2425a61f0`; image **`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`**, tag`dame-curie-app:be28b85`. All56 copied inputs match Git; baked/OCI commit and dirty=false match. Existing guarded constructor probe passed inside the actual image (QA64). This is artifact evidence, not live delivery/feature acceptance. **Not deployed.**
- **Measured catalog:** QA61/65 synthetic real-builder measurements are in `06-TOOL-INVENTORY.md`, separating current15-tool admin core/74-tool full exposure from historical flat73. Metrics are chars/bytes, not token/billing or live-profile claims. Default schema-inclusive budget is96000 characters;36k is the history-tail bound.

QA used the established Python3.14.4 image with network disabled, no private mounts or credentials, read-only root and synthetic configuration. No application imports/tests/collection ran on the host for this QA. The separately disclosed source-reviewer method violation is not erased by these receipts.

## Finding C-01 — Visible, terminal incomplete output

- **Disposition:** deferred — coordinator/core owner; `../../TODO.md` provider/caller row.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Selected policy delivers genuine partial text with a leading, sanitizer-safe cutoff notice; reasoning-only/empty output gets an explanation, never reasoning. No recovery, tool dispatch or paid retry may follow either outcome. The initial and follow-up branches now exist; review caught a bracketed label being stripped and stale test fixtures, now corrected in moving source. Follow-up incomplete coverage and execution remain pending.
- **Verification performed:** P covers provider typing, not final Discord delivery. Independent source recheck in `review-provider-budget.md`; real foreground matrix unrun.
- **Deployment effect:** none.

## Finding C-02 — Native admission, history groups and replay

- **Disposition:** deferred — core integration owner/coordinator.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Compact before eviction, retain whole native groups within36k characters/12 messages, limit newest/older results and replay original execution arguments as JSON strings with matching IDs. Whole-batch malformed/duplicate/oversized admission must reject before effects. Independent review found byte/depth/argument gaps and lost per-call failure replay; corrections remain under review. The additional background shared-slot race is covered by J and implementer item I-02.
- **Verification performed:** moving-source review `review-core-tool-contracts.md`; complete native/history selection pending.
- **Deployment effect:** none.

## Finding C-03 — Bounded prompt readback and upload

- **Disposition:** deferred — core integration owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** New prompt writes use16KiB UTF-8, exports512KiB and inline readback1800 UTF-8 bytes. Setters acknowledge briefly without echo; response paths suppress mentions. Oversized legacy storage remains retained, with bounded export behavior and no silent context truncation.
- **Verification performed:** independent source review; existing `tests/test_longprompt_command.py` and prompt-storage cases adapted, integrated execution pending.
- **Deployment effect:** none.

## Finding C-04 — Invalid image configuration and canonical migration

- **Disposition:** deferred — image/coordinator integration and canonical hold ledger.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Image configuration errors disable that capability rather than crashing unrelated bot construction; forcing enablement cannot override invalid configuration. Native protocol, explicit endpoint and exact model-description mapping are required. `../../docs/IMAGE_GENERATION.md` and `../../phase-II_v2/PROVISIONING.md` retain the canonical migration/activation hold; no canonical private profile was migrated or enabled here.
- **Verification performed:** synthetic image/config subsets and independent source review recorded in validation/image review; final integrated artifact pending.
- **Deployment effect:** none; canonical remains held.

## Finding C-05 — Image quality default

- **Disposition:** deferred — coordinator, final documentation/source commit.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Code and examples choose low. Explicit private high/timeout settings are not silently replaced; the guide distinguishes defaults from the last recorded temporary profile.
- **Verification performed:** source/config review and synthetic image cases; no fresh private value inspection.
- **Deployment effect:** none.

## Finding C-06 — Aggregate foreground budget

- **Disposition:** deferred — confirmed request-shape hole still open; core owner/coordinator.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Selected task-local defaults are32768 reserved output tokens,12 actual generation POSTs and600 monotonic seconds; validated consistent explicit output alone may refund. Model-spawned descendants share spend; independently issued background jobs retain their separate limits. Review found `OPENAI_EXTRA_BODY n=2` could request twice the reserved output. Selected correction: foreground permits one completion only, rejects invalid multiplicity terminally before reserve/POST, and bounds recognized competing output-cap fields without raising lower values. Final source recheck is pending; this is not bot-wide expenditure or provider/billing compliance control.
- **Verification performed:** P predates the request-shape fix. `review-provider-budget.md` records the concrete bypass and policy; real wrapper deadline, cancellation and preparation cleanup cases remain unrun.
- **Deployment effect:** none.

## Finding C-07 — Replayed reasoning argument

- **Disposition:** deferred — core/history owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Bound reasoning/arguments in retained history without changing the arguments actually executed or the canonical immediate native replay. Preserve whole call/result pairing.
- **Verification performed:** independent bounded source review; integrated existing native/history cases pending.
- **Deployment effect:** none.

## Finding C-08 — Unsafe dotenv/live-provider test

- **Disposition:** deferred — final integration/no-new-test audit.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Replaced the existing historical live-provider case with synthetic SSE bytes and fake progress channels, not an opt-in real-provider probe. The historical version remains forbidden to execute; no new test function/file was authorized.
- **Verification performed:** coordinator inspected the replacement before the116-pass isolated progress/error selection recorded in `validation.md`; final full safe suite pending.
- **Deployment effect:** none.

## Finding C-09 — Import-time dotenv boundary

- **Disposition:** no-change-needed for loading semantics; residual explicitly retained.
- **Commit(s):** no loading-semantics change; documentation pending.
- **What changed / why not:** Import-time configuration loading remains a real boundary, not a claim that imports are harmless. Preserve configured startup behavior; isolate application execution instead. Shell environment filtering does not prevent same-UID filesystem reads, and current QA says nothing about the origin of historical bytecode.
- **Verification performed:** QA receipts specify synthetic env selection and no private mounts/network; P-08 provenance remains unresolved. No host application import used for this verification.
- **Deployment effect:** none.

## Finding C-10 — Build-context exclusions

- **Disposition:** deferred — coordinator artifact/commit stage.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Root `.dockerignore` excludes `audit/` and `reports/`; application COPY lists include the new required policy/budget modules. Context exclusion is not itself artifact provenance.
- **Verification performed:** source inspection; actual candidate artifact inspection pending.
- **Deployment effect:** none.

## Finding C-11 — Actual reasoning content, not raw truthiness

- **Disposition:** deferred — provider/core commit stage.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Reasoning-only classification uses normalized actual reasoning content, not merely a nonempty `reasoning_details` container. No reasoning is promoted into user-visible text.
- **Verification performed:** P and independent provider recheck; current full integration pending.
- **Deployment effect:** none.

## Finding C-12 — Preserve explicit incomplete usage

- **Disposition:** deferred — caller verification outstanding.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Bounded SSE usage drainage retains explicit counters and producing metrics. Explicit Gemini total was lost by merge and is now preserved; total-minus-input is never an output refund. Review also found canonical input/output keys were ignored by the daily tracker; moving source now accepts those aliases.
- **Verification performed:** P proves the SSE correction. Caller tracker and producing-call assertions await the real foreground selection.
- **Deployment effect:** none.

## Finding C-13 — Bounded diagnostic captures

- **Disposition:** deferred — final provider/error commit stage.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Raw diagnostic capture is byte-bounded; decoded payload is bounded plus fixed omission-marker overhead; persisted details/traceback are capped at256KiB characters. This does not bound network ingress or successful response assembly. Nested re-truncation lengths describe their intermediate input, not original provider bytes.
- **Verification performed:** P and independent provider review; final exact-tree suite pending.
- **Deployment effect:** none.

## Finding C-14 — Reasoning-only terminal policy

- **Disposition:** deferred — selected behavior, caller verification pending.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Keep reasoning-only output terminal with a clear notice. Do not pay for automatic retry/recovery or reveal reasoning. Root's broad remediation grant allowed this cost policy; no older private reasoning setting is rewritten by it.
- **Verification performed:** P plus source review; initial/follow-up final delivery coverage pending.
- **Deployment effect:** none.

## Finding C-15 — Truthful, idempotent history omission

- **Disposition:** deferred — history integration owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Preserve already-bounded omission summaries instead of repeatedly recounting a truncated intermediate as the original result. Keep native groups intact while shrinking.
- **Verification performed:** independent history review; existing custom/tool-tail cases adapted, integrated execution pending.
- **Deployment effect:** none.

## Finding C-16 — Schema-inclusive protected prompt budget

- **Disposition:** deferred — core integration owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Count native schemas and serialized tool arguments/metadata in prompt input. Protect identity and tool protocol, preserve native pairing, and fail visibly if the protected core cannot fit. Review caught an early scan break that allowed earlier system contracts to be clipped; source correction and precise protected-block classification are under final review.
- **Verification performed:** `review-core-tool-contracts.md`; existing prompt-budget/native cases awaiting execution.
- **Deployment effect:** none.

## Finding C-17 — Progressive tool discovery

- **Disposition:** deferred — core and coordinator jobs owners.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Default core15 plus explicit groups, actor/config/platform eligibility and idempotent per-turn catalog rebuilding. Each background job has its own catalog set without resetting inherited spend. Exact eligible plugin names must precede legacy aliases, including `tool_`-prefixed names; forbidden background recursion must not be re-advertised. Full registered capability retention and actual schema-size measurement still need final evidence.
- **Verification performed:** J proves scoped job refresh/reset and source rechecks cover coupling. Real core/plugin/custom/native selections and post-discovery size measurements pending.
- **Deployment effect:** none.

## Finding C-18 — Bounded text recovery

- **Disposition:** deferred — core/history owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Bound recovery input, argument sizes and call count before synchronous parsing/dispatch. Reject the whole recovered batch above eight calls; do not execute its first eight and discard the rest. Independent review found that old slicing still survived one path; correction remains unaccepted.
- **Verification performed:** source review; existing `tests/test_text_tool_call_recovery.py` and native cases pending integrated execution.
- **Deployment effect:** none.

## Finding C-19 — Media admission across rounds

- **Disposition:** deferred — core/media owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Bound/dedupe newly admitted media without slicing base64 or repeatedly reattaching the full retained set. Check actual returned attachment bytes before decode/use and reject archive/MIME contradictions. SDK `.read()` still buffers before post-read rejection; no hard peak-memory/streaming-ingress guarantee is claimed.
- **Verification performed:** existing forwarded/media cases adapted; independent source observations, integrated execution pending. See I-03 for the explicit read-memory limit.
- **Deployment effect:** none.

## Finding C-20 — Persisted tool-result metadata

- **Disposition:** deferred — core owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Cap persisted result/argument metadata truthfully. Review found raw embedded-media markers were persisted before replay stripping; whole-media omission must replace clipped base64 fragments in storage.
- **Verification performed:** moving-source review; final storage/media selection pending.
- **Deployment effect:** none.

## Finding C-21 — Dead expansion flag and misleading prompts

- **Disposition:** deferred — core/tool-prompt owner.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Replace the ineffective Message expansion flag with actual task-local discovery state. Hidden workflow/inbox/game instructions must discover their group first, rather than demand unavailable tools immediately. Background prompts/catalogs exclude recursive spawning.
- **Verification performed:** independent source review; real native/custom prompt parity cases pending.
- **Deployment effect:** none.

## Finding C-22 — Server-prompt integrity

- **Disposition:** deferred — core prompt owner/coordinator jobs.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** New16KiB writes are bounded before storage; oversized legacy prompts remain stored but are omitted whole from foreground/background model context with a configured-prefix diagnostic. No clipping of canonical identity/tool contracts to make room; export limits remain explicit.
- **Verification performed:** J covers background omission and preservation; real foreground/protected-core cases pending.
- **Deployment effect:** none.

## Finding C-23 — Shell authorization and environment

- **Disposition:** deferred — final integrated source commit/recheck.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Shared actor policy permits admins or the existing string-ID shell whitelist; unknown actors fail closed. Direct execution and advertisement both gate privilege. Bash has explicit cwd, no profile/rc startup and a minimal environment. This is not same-UID filesystem secret isolation. Exact plugin/builtin/alias precedence is part of the remaining integration review.
- **Verification performed:** independent authorization review and synthetic shell/gate subsets; full current integration pending.
- **Deployment effect:** none.

## Finding C-24 — Persistent rewrite authorization

- **Disposition:** deferred — final integrated source commit.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Persistent personality/server-prompt mutation is admin-gated at execution and in advertised capabilities; missing actor fails closed. Removing the old taint-confirmation mechanism did not authorize arbitrary users to persist prompts.
- **Verification performed:** independent source review and existing mutation/gate cases; exact full-tree result pending.
- **Deployment effect:** none.

## Finding C-25 — Image availability detection

- **Disposition:** deferred — image/core integration.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Auto advertisement requires valid native image configuration, explicit endpoint and nonempty exact model-description map containing the selected model. Explicit blank API key remains distinct from missing required endpoint/model data. Templates document the image settings; invalid forced-on still remains unavailable.
- **Verification performed:** synthetic image/config/schema subsets and independent source review; final integrated candidate pending.
- **Deployment effect:** none.

## Finding C-26 — Image path resolution and edits

- **Disposition:** deferred — image integration/documentation owner.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Local references use realpath bounds; escaping symlinks are refused. Same-UID path replacement between check/use is not eliminated. Edit behavior/latency and explicit remote settings remain documented rather than silently claiming old downscaling behavior.
- **Verification performed:** existing synthetic image/path cases and independent review; no live image request.
- **Deployment effect:** none.

## Finding C-27 — Omitted versus empty image input

- **Disposition:** deferred — final image/core commit.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Only `image is None` may fall back to incoming attachments. Empty string or empty JSON list means generation from scratch; schema descriptions must say so.
- **Verification performed:** existing image/schema cases adapted; final integrated execution pending.
- **Deployment effect:** none.

## Finding C-28 — Retired hd_image and private controls

- **Disposition:** deferred — coordinator final source rationale/private acceptance check.
- **Commit(s):** no alias planned; final integrated documentation pending.
- **What changed / why not:** Selected clean contract retains only `image_generator`; do not silently map retired high-quality/model behavior onto the new low-default generic capability. Retained capability is discoverable under its actual name; old traces are not restored as instructions. Final response must give the exact dispatch/schema counter-argument and minimal temporary disabled-tools observation; no fresh private-control claim yet. Canonical migration remains held.
- **Verification performed:** independent image review; exact final anchors and authorized temporary metadata check pending.
- **Deployment effect:** none.

## Finding C-29 — Empty optional model/quality

- **Disposition:** deferred — final image integration commit.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Empty optional model/quality uses configured defaults rather than becoming an invalid explicit selection. Nonempty unknown selections remain errors.
- **Verification performed:** existing synthetic image cases; final current-tree integration pending.
- **Deployment effect:** none.

## Finding C-30 — Configured runtime command prefix

- **Disposition:** deferred — command-case verification/commit stage.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Runtime usage/errors now interpolate the configured prefix, including command and solo/voice/context/REM/autonomy helpers. Background parsing takes the configured prefix. Canonical documentation examples/comments remain `!`; dated runtime receipts are explicitly historical.
- **Verification performed:** coordinator bang-command grep leaves only comments/docstrings in bot.py; existing command cases being adapted, not yet executed in current integration.
- **Deployment effect:** none.

## Finding C-31 — Incoming-message viewer latch trigger

- **Disposition:** deferred — producer/core commit outstanding.
- **Commit(s):** V covers viewer containment; producer anchor is pending integrated source commit.
- **What changed / why not:** Incoming INFO logging uses IDs/length rather than arbitrary message content. Complete bounded JSON records use local redaction state while genuine outer spans/loss remain fail-closed. Do not mistake a consumer fix alone for a committed producer fix.
- **Verification performed:** V plus independent viewer/authorization review; producer integration pending.
- **Deployment effect:** none.

## Finding C-32 — Visible viewer omissions

- **Disposition:** fixed — source scope only.
- **Commit(s):** V.
- **What changed / why not:** Viewer diagnostics have their own always-visible scope and cannot disappear behind normal scope/error/replay filtering or health coalescing. Legitimate producer ERROR-group continuation semantics are preserved.
- **Verification performed:** exact V selection and independent viewer source review; no live viewer operation for this remediation.
- **Deployment effect:** none.

## Finding C-33 — Proportionate redaction continuity

- **Disposition:** fixed — source scope only.
- **Commit(s):** V.
- **What changed / why not:** Bounded complete JSON is record-local; active outer PEM/config spans remain masked. Rejected fragments are scanned once, with correct last BEGIN/END ordering and sensitive-field span effects. Genuine framing loss still fails closed rather than claiming safe recovery.
- **Verification performed:** exact V selection and independent viewer review.
- **Deployment effect:** none.

## Finding C-34 — Final delivery settlement result

- **Disposition:** deferred — progress/core integration commit stage.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Propagate actual final settlement success/failure to callers rather than awaiting and discarding the result. Persist only confirmed delivered chunks/IDs; an acknowledgement loss does not prove no Discord side effect.
- **Verification performed:**116-pass synthetic progress/error subset; real final-delivery/caller matrix pending. L separately verifies receipt uncertainty, not this uncommitted progress source.
- **Deployment effect:** none.

## Finding C-35 — Cancellation must not delete a possibly delivered final answer

- **Disposition:** deferred — progress/core integration commit stage.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Once a final edit is issued, cancellation/uncertainty must not trigger deletion of the possibly delivered answer. Settlement remains bounded and uncertainty remains explicit.
- **Verification performed:** synthetic progress/error subset and independent source review; current integrated caller/cleanup coverage pending.
- **Deployment effect:** none.

## Finding C-36 — Operator status and restart evidence

- **Disposition:** fixed — source scope only.
- **Commit(s):** L.
- **What changed / why not:** Report owned container state before expected configuration/layout failures; do not hide unexpected Docker failures. Refuse stopped/dead restart before private preparation, retaining stop evidence. Docs distinguish status metadata/probe limits and retained log replay.
- **Verification performed:** exact L selection and independent lifecycle review; documentation final commit pending, installed operator behavior not re-accepted.
- **Deployment effect:** none.

## Finding C-37 — Opened smoke turn cleanup and settlement

- **Disposition:** fixed — source scope only.
- **Commit(s):** L.
- **What changed / why not:** Cancel/settle the exact input task, retain cleanup receipts before awaits, keep admission closed until a known task truly settles and fail-stop taskless uncertainty. Stop can recover retained receipts after queue registration disappears. Unacknowledged sends may still have reached Discord; known IDs mean acknowledgement observations only.
- **Verification performed:** exact L selection and independent lifecycle review; bounded live acceptance pending.
- **Deployment effect:** none.

## Finding P-01 — Temporary live instance used as a test bed

- **Disposition:** deferred — coordinator acceptance stage.
- **Commit(s):** current authority baseline `ab64853c93eb0268c976a5a3444d49fcd1f4f50a`; source commits above.
- **What changed / why not:** All remediation QA so far is credential-free isolated validation, not a live test. Root separately authorized bounded automated acceptance in the prepared temporary test channel; that is not a normal release or permission to touch canonical/V1/publisher resources. Historical live use is not retrospectively reclassified as isolated QA.
- **Verification performed:** validation receipts; candidate build and bounded temporary acceptance not yet performed.
- **Deployment effect:** none.

## Finding P-02 — No-new-tests contract

- **Disposition:** deferred — coordinator final definition inventory.
- **Commit(s):** current constraints at `ab64853`; final integration pending.
- **What changed / why not:** Existing cases/fixtures may be adapted; no new test files/functions/helpers or absence-asserting tests. Earlier unauthorized additions are not retroactively blessed or erased by current work. Review caught a new nested drain helper during this remediation; it was removed and the existing iterator extended instead.
- **Verification performed:** scoped source checks; complete baseline-to-candidate definition inventory and disposition of historical test additions pending.
- **Deployment effect:** none.

## Finding P-03 — Owned validation failures

- **Disposition:** deferred — coordinator complete safe-suite/baseline stage.
- **Commit(s):** pending final integration and evidence receipt.
- **What changed / why not:** Preserve every failed QA attempt and assign its correction rather than normalizing debt. Current ledger includes undefined helper, wrong selector, missing SSE total and reviewed fixture defects. Historical README/provider failures still require exact baseline ownership or correction; no xfail-for-green.
- **Verification performed:** `validation.md`; no whole-suite-green claim.
- **Deployment effect:** none.

## Finding P-04 — Unassigned legacy deletion

- **Disposition:** fixed — current cleanup scope, not retroactive historical authority.
- **Commit(s):** `aad36e657dd04b436630604caebd58e905253753`.
- **What changed / why not:** Root explicitly authorized removal of obsolete V1 archive/documentation;24 files and3970 text lines were committed coherently with the freeze record. Do not restore old source from another checkout or stage unrelated work. This did not change active publisher code.
- **Verification performed:** local commit/explicit scope review; no application execution required for deleted archived material.
- **Deployment effect:** none.

## Finding P-05 — Retained worktrees and unintegrated branch histories

- **Disposition:** deferred — coordinator final disposition acceptance; all physical removal held.
- **Commit(s):** no ref/pruning changes; source equivalents enumerated in `07-PROCESS-DISPOSITIONS.md`.
- **What changed / why not:** Independently verified26 worktrees/25 branches/two detached heads/22 checkpoints. Frozen old-branch inventory86 commits splits54 equivalent/32 non-equivalent; current union89 includes three new remediation commits. Separate Sol review mapped all32 across13 families, distinguishing rejected prototypes and corrected integration. Preserve all refs/checkouts pending round two plus dirty-state/ownership checks; checkpoint content and remote state are not verified.
- **Verification performed:** authorized Git metadata/source review and separately verified cited commit identities; no other checkout filesystem inspection/fetch/prune.
- **Deployment effect:** none.

## Finding P-06 — Audit/document sprawl

- **Disposition:** deferred — coordinator post-acceptance retirement ledger.
- **Commit(s):** schedule baseline `ab64853`; current documentation updates pending.
- **What changed / why not:** New evidence stays under this dated bundle. `../../TODO.md` names temporary evidence, durable destinations, owners and the accepted-round-two gate. Do not move/delete unresolved or unaccepted evidence to make the tree look finished; root's unrelated `reports/`/skill work is preserved.
- **Verification performed:** source/document inventory; consolidation/removal intentionally awaits acceptance.
- **Deployment effect:** none.

## Finding P-07 — Reviewer route naming drift

- **Disposition:** deferred — final governance/documentation commit.
- **Commit(s):** current route guidance at `ab64853`; remaining docs pending.
- **What changed / why not:** Current assignments use discovered Luna/Sol/DeepSeek routes with explicit ownership and rotated independent review, not obsolete historical model labels. A route name alone is not review evidence.
- **Verification performed:** delegation receipts and current AGENTS/TODO routing entries; no provider credential inspection.
- **Deployment effect:** none.

## Finding P-08 — Host bytecode provenance

- **Disposition:** deferred — unresolved historical attribution, owner coordinator in `07-PROCESS-DISPOSITIONS.md`.
- **Commit(s):** no deletion or provenance-rewrite commit.
- **What changed / why not:** Coordinator verified presence, size/mtime and ignore rules for the two root `.pyc` paths listed in07, not all cache files or their origin. Metadata cannot distinguish host import, explicit compile or copied output. The separately cited `.validation-cache/` compiled test modules remain unattributed too: historical compile-only documentation exists, but neither their origin nor host execution is established here, and no cache-content read/deletion or decoder inference is accepted. A reviewer violated its no-interpreter assignment and supplied unsupported inferences; that report is quarantined, not acceptance evidence. No clean-history claim is manufactured.
- **Verification performed:** authorized stat/Git-ignore observations only; decoder-derived conclusions excluded. Full literal receipts for the violating review remain unavailable.
- **Deployment effect:** none.

## Finding P-09 — Direct grants versus author assertions

- **Disposition:** deferred — final documentation review/commit; older gaps stay explicit.
- **Commit(s):** current grant baseline `ab64853`; STATUS/README/plan qualifications pending.
- **What changed / why not:** Quote the current direct human grant and distinguish it from earlier author-written assertions. Current status is concise; older receipts and taint-removal attribution are labelled historical. Current authority is not retroactive permission, and absent older evidence is not invented.
- **Verification performed:** current session grant and documentation reconciliation; historical unknowns preserved in07.
- **Deployment effect:** none.

## Finding D-01 — Security posture after taint-gate removal

- **Disposition:** deferred — final source/documentation consistency review.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** SECURITY/architecture distinguish removed taint confirmation from retained independent authorization/redaction, current shell/rewrite actor gates and the same-UID filesystem limitation. No claim that a minimal subprocess environment is a secret sandbox.
- **Verification performed:** source review; final current-code/document cross-check pending.
- **Deployment effect:** none.

## Finding D-02 — Text output example default

- **Disposition:** deferred — documentation commit stage.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** `.env.example` uses16384 like source defaults. This does not rewrite the last recorded temporary12345 cap.
- **Verification performed:** source/example comparison; no private edit.
- **Deployment effect:** none.

## Finding D-03 — Canonical prompt-guide examples

- **Disposition:** deferred — documentation commit stage.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** LONGPROMPT uses canonical `!` examples and explains configured runtime prefix, bounded readback/upload/export and whole legacy omission. Historical temporary runtime receipts remain labelled, not generic examples.
- **Verification performed:** documentation/source review; caller cases pending.
- **Deployment effect:** none.

## Finding D-04 — Obsolete confirmation language

- **Disposition:** deferred — documentation commit stage.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** Current job guidance reflects independent authorization rather than the retired taint-confirmation gate. PRUNING_MAP and redesign/handoff records are marked historical; they cannot assert today's resource readiness, security guarantees or human authority.
- **Verification performed:** source/document review; final residual wording scan pending.
- **Deployment effect:** none.

## Finding D-05 — Condensed current status

- **Disposition:** deferred — documentation commit stage.
- **Commit(s):** pending integrated source/documentation commit.
- **What changed / why not:** STATUS now contains current authority, verified source milestones, holds and short dated receipt rows. The previous full narrative remains in `ab64853:docs/STATUS.md`; no uncertain history was rewritten as a fresh observation.
- **Verification performed:** coordinator rewrite/review; final independent consistency check pending.
- **Deployment effect:** none.

## Finding D-06 — Restart and log replay

- **Disposition:** deferred — documentation commit stage.
- **Commit(s):** L for lifecycle behavior; handoff clarification pending.
- **What changed / why not:** Handoff states that restart retains Docker history; subsequent ordinary logs tails100. Only `logs --fresh` means tail0, without deletion; it is not a restart flag. Replacement starts a new container/log stream and must not be used to hide evidence. Current source refuses stopped/dead restart before private preparation.
- **Verification performed:** inspected scripts/dirac.py parser/logs/restart/main and handoff text; L covers operator behavior, no live command run.
- **Deployment effect:** none.

## Implementer-raised items

### I-01 — Pending smoke request withdrawn between discovery and stat

- **Disposition:** fixed — source scope only.
- **Commit(s):** S.
- **What changed / why not:** Catch only FileNotFoundError at the second stat; preserve other filesystem failures. Keep the accepted pending protocol, not the rejected prototype queue.
- **Verification performed:** exact S selection; independent Sol source check. The earlier incorrect selector ran no tests and remains in validation evidence.
- **Deployment effect:** none.

### I-02 — Background native replay overwritten while posting progress

- **Disposition:** deferred — integration commit outstanding.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Snapshot native followups immediately after direct dispatch, before the progress-post await. Otherwise another job/channel can overwrite the shared slot and cross-contaminate the next model request. No broad state/API refactor was necessary for this assignment-based race.
- **Verification performed:** J plus independent publication/return/await-order review; existing fake send deliberately overwrites the slot and asserts own paired replay survives.
- **Deployment effect:** none.

### I-03 — Attachment actual bytes and SDK allocation boundary

- **Disposition:** deferred — processing fix verification and explicit residual.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Check actual bytes before text decode/media use; refuse archive suffix/image-MIME contradictions. This does not repair the coordinator's earlier unsupported-archive/image-limit misclassification: the incoming20MiB override was a setting change, not archive/extraction support. `.7z` extraction remains unsupported; V1 10MiB parity remains unverified. SDK full-body allocation still precedes the post-read check. Do not advertise it as streaming/peak-memory containment; bounded URL reads and bounded admission are different claims.
- **Verification performed:** independent source observations; existing forwarded cases adapted, current execution pending.
- **Deployment effect:** none.

### I-04 — Catalog state coupled to foreground spend

- **Disposition:** deferred — integration commit outstanding.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Separate background catalog scope from spend inheritance and rebuild both schema/protocol and system prompt each step. Independent jobs begin with their own discovery state; model-spawned descendants still share the originating spend envelope. Catalog construction failure is terminal, not a silent no-tools fallback.
- **Verification performed:** J and independent source recheck; real core15/plugin/native/custom integration pending.
- **Deployment effect:** none.

### I-05 — Review-method violation and unsupported provenance

- **Disposition:** deferred — evidence retained for auditor; coordinator owns unresolved facts.
- **Commit(s):** no source change attributed to the violating analysis.
- **What changed / why not:** Reviewer5f9fde83 performed prohibited interpreter metadata analysis, disclosed two then five invocations and could not provide complete literal receipts. Its Git totals and bytecode origin inferences were not accepted. Coordinator recomputed authorized metadata; a separate reviewer mapped retained histories. Preserve the failure/retractions, not merely the replacement report.
- **Verification performed:** `07-PROCESS-DISPOSITIONS.md`, quarantined `review-process-evidence.md`, independent branch report. No application import/decoded execution was reported by that reviewer; that self-report is not independent proof.
- **Deployment effect:** none.

### I-06 — Newly discovered request multiplicity/cap ambiguity

- **Disposition:** deferred — confirmed C-06 correction and independent recheck pending.
- **Commit(s):** pending integrated source commit.
- **What changed / why not:** Generic primary extra-body JSON can retain n>1 and competing output fields. One max_tokens reservation cannot bound multiple compliant completions. The selected one-completion/positive-cap admission policy is recorded under C-06; do not dismiss the n bypass as provider dishonesty.
- **Verification performed:** independent source path from config through constructor, request/retry and final POST; synthetic existing-case extension pending. No provider experiment or universal alternate-cap precedence claim.
- **Deployment effect:** none.

## Open questions for root

None requiring an immediate new grant for the remaining authorized source/isolated work. Historical authorization/bytecode gaps remain unknown. Any operation outside the existing temporary-only acceptance boundary stays held; lack of evidence is not permission.

## Required before this draft becomes the final reply

1. Freeze the core; close/recheck current admission, incomplete-caller and request-shape findings.
2. Run the complete safe isolated selection and definition inventory; own every baseline/current failure.
3. Commit coherent reviewed source/docs and replace every pending commit/evidence field above.
4. Verify artifact and perform only safely established bounded temporary acceptance; preserve containment and record exact rollback/identity/channel evidence without private contents.
5. Complete final independent dispositions and retain unresolved limitations; do not claim release or zero remaining defects.
