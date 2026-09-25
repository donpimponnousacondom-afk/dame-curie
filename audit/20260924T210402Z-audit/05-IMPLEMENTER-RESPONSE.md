# 05 — Implementer response — round-two correction closed internally

**Correction slice and documentation retirement complete; temporary Dirac promoted under root's delegated decision.** See `09-CLOSURE.md` for the coordinated receipt. This does not replace the original external auditor's conditional verdict. C-28 push-back is withdrawn; C-09 is an accepted development boundary and P-08/I-05 are permanently unattributable/quarantined, not new redesign/cache tasks. C-14 fallback and the C-23 shell trust choice remain unchanged policy. No canonical/V1/publisher/remote activation follows.

The correction source is `c2d6b0e` plus `89fb851`. QA76 on tree `511a355fabe792cc6ae844d26004de7c55c104b4` reports **3993 passed, 28 subtests**; QA75 reports **92 passed** with selected Ruff passing. Internal fresh Sol review `a6b627d2` is a diff-focused PASS, not the original auditor's acceptance. QA72/73 failures remain historical evidence; QA74 was diagnostic only, not closure.

Newest candidate image is `sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`, from `89fb851`. QA77 used an offline overlay on verified prior base `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`, without pull/install; QA78 verified copied inputs and provenance and passed the guarded constructor in-image, with no network/private reads/login. QA83's single bounded smoke passed in7seconds. The coordinator promoted this immutable image to temporary normal use; final container`ef618129341ed4b2b83dceebd2a92e3e0e3437585e53f96c488381a3ca23e2d5`, started16:46:31Z, fresh identity/readiness and original-control integrity verified by QA86. Original three channels/low/12345/REMoff restored; durable selector matches. Old image5e3… and private rollback evidence remain. QA84's mistaken restart-after-stop refusal and corrected replacement are retained in validation; no second smoke was submitted.

Current contracts and recovery boundaries are in `../../AGENTS.md`, `../../TODO.md` and `../../docs/`. The prior grant is retained verbatim at `git show eb188ac:phase-II_v2/SESSION_LOG.md`. Original auditor reports, child reports A–E/R1–R5, `08-ROUND2-REPORT.md`, quarantine, and companion `07-PROCESS-DISPOSITIONS.md` remain preserved; 39phase files and28internal notes have now been retired after contract/recovery consolidation; references to them below are historical citations recoverable in `89fb851`, not live paths.

## Evidence keys and current commit boundary

- **V:** commit `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`, tree `bdd636d05898bcc41aafc4f3d75371c3991fbc5f`; Python3.14.4 isolated Ruff F821/F822/F823 passed; **185 passed**. Exact selection: `tests/test_log_console_render.py tests/test_log_console_robustness.py tests/test_log_console_events.py tests/test_log_console_history.py tests/test_log_console_integration.py tests/test_log_console_tty.py`.
- **L:** commit `551060dbb7d223e1f365c069fbff2db377406f17`, tree `c13f3d5a492069da1594ee3e61ebe0e82e0ba119`; same isolated Ruff selection passed; **117 passed**. Exact selection: `tests/test_dirac.py tests/test_dirac_operator.py tests/test_dirac_smoke.py tests/test_message_pipeline.py`.
- **S:** commit `e540be6772f76d906720b79b07947a60893c3b24`, tree `56062c02b3027ade1d58bd678ffc9efd1cc5fb48`; selected Ruff passed; **5 passed** in `tests/test_smoke_protocol.py`.
- **P (historical, uncommitted at measurement):** provider seam tree `9b3ec91e304d0bacaa2515f14fe9904710eee50a`; selected Ruff passed; **199 passed** in `tests/test_provider_error_reporting.py tests/test_providers.py tests/test_error_reporting.py tests/test_smoke_protocol.py`. This predates the newly identified request-shape correction and is NOT current caller or complete provider acceptance.
- **J (historical, uncommitted at measurement):** background seam tree `869157081116c6968c177e7f1954e0e56e418f37`; selected Ruff passed; **39 passed** in `tests/test_background_jobs.py`. Uses baseline bot plus existing doubles, not full real-bot integration.
- **First full-safe integration:** QA52 tree `21f57d4801720e33035f31b2353ed10d188d2844`: selected Ruff passed; **3894 passed,83 failed,9 errors,28 subtests passed**. QA53 preintegration `e540be6`: **3884 passed,42 failed,9 errors,1 deliberately deselected historical unsafe case,28 subtests passed**. QA54 fixture reconciliation tree `f38e3e400fa4c8036f0477a0d25cb1fe7a40a21d`: **970 passed,4 original unsupported-reasoning failures retained**. These are not whole-core acceptance. Case-level ownership and exact safe selections are in `qa52-53-triage.md`; full failed evidence remains retained.
- **Bounded integration recheck:** root directed divide-and-conquer; oversized Luna run was stopped, not restarted. Six fresh single-issue handoffs completed. QA55 tree `1354ca309efa6ffe24cdf7beb2905dfd45cb8760`: selected Ruff passed; **644 passed,13 failed** in the explicit core selection, including successful real foreground/provider cases but remaining fixture errors. QA56 tree `a58e8932abdc9009bde187060a90806a79ef5416` reran the same22-file selection after existing-fixture corrections: **657 passed**, selected Ruff passed, exit0. This is green bounded core integration, not a green full suite. At that intermediate checkpoint, independent acceptance, definition inventory, baseline/environment debt, artifact and bounded temporary acceptance remained open; subsequent receipts below close the completed execution gates, not historical failures. Exact commands/failures/corrections are retained in `validation.md`; no xfail-for-green or hidden discarded failures.

- **Historical source/QA checkpoint (not current correction coverage):** `d198c37ee038e57e7cca4183b60eef0eaef6f1fc` and QA60 tree `e2d639755f90bfb16ff8a834975ae704772cb6ae` recorded **3984 passed,28 subtests**; QA61/62 were narrowed rechecks. These predate the round-two correction slice. Current correction commits and QA75/76 receipts are summarized above; failed QA72/73 and all retained failures remain in `validation.md`.
- **Prior candidate artifact (historical):** packaging commit `be28b8598215ff6a0c72d7c3160403f2425a61f0`, image `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`; QA64 constructor and QA67–69 bounded case preceded round two. This historical candidate was stopped. Old image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` was restored in container`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46` and still runs at the QA78 checkpoint; neither candidate is then live.
- **Measured catalog (historical synthetic builder measurements):** QA61/65 records 15-tool admin core/74-tool full exposure. Metrics are chars/bytes, not token/billing or live-profile claims. The configured prompt-budget control default is96000 characters, but the effective enforced ceiling is72000; the separate newest-group cap is24k with shrink-to16k, not a guaranteed intact replay. The full history-tail cap remains36k/12messages, distinct from those per-group caps.

- **Bounded temporary acceptance, QA67–69:** request`608cc14a42714fd58bafbf8084b09690`, approved channel`1550960386939817984`, operator root`1482143139828596916`, confirmed Discord identity`1504398705539944560`. One180s-deadline request completed in8s with returned=true, one delivery, exact marker body plus the configured marker-tagged runtime footer and zero readback failures. The initial logger-selector and whole-wire-equality checks failed and are retained/corrected transparently in `validation.md`; no second inference request was submitted. Prior image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` restored in container`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, running/embedding-ready, identity reverified, original controls byte-exact and private profile fingerprint unchanged. Low/12345/REMoff retained. The source-reviewed temporary operator files remain installed. Host viewer fixes were **not** installed into the existing Screen workflow. Normal embedding API usage occurred; no shared-service configuration/lifecycle mutation.

**Coverage convention:** QA67–69's one historical model/delivery/readback case is not a per-finding live scenario matrix. Deployment-effect fields below describe that earlier remediation unless explicitly labelled round two; current image/decision always comes from STATUS and the closure receipt. Isolated verification and residuals remain substantive coverage for unexercised failure/tool/provider paths. The original external verdict remains its conditional snapshot; internal correction closure is separate. No canonical/V1/publisher/remote activation follows.

Isolated QA used the established Python3.14.4 image with network disabled, no private mounts or credentials, read-only root and synthetic configuration. No application imports/tests/collection ran on the host for this QA. The separately disclosed source-reviewer method violation is not erased by these receipts.

## Finding C-01 — Visible, terminal incomplete output

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Genuine partial text has a leading sanitizer-safe cutoff notice, and partial-display truncation is now announced. Empty/reasoning-only output gets an explanation without disclosing reasoning. Initial and follow-up typed incomplete outcomes terminate without recovery, tool dispatch or paid retry. Confirmed delivery only is persisted.
- **Verification performed (historical):** Independent caller/source recheck in `review-provider-budget.md`; QA56/60 predate round-two changes. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-02 — Native admission, history groups and replay

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** History trimming removes oldest transcript content first and records metadata about the trim. Newest tool-result group is capped at24k and can shrink to16k; it is not guaranteed intact, and replay is not verbatim: IDs/structure are retained while arguments are bounded/elided. Native admission rejects malformed, duplicate, oversized and nonfinite JSON batches before effects. The separate native-argument limits are16k per call,32k per batch and40k per envelope; an oversized batch is refused whole with bounded paired error results. Foreground controls are32768 output tokens,12 POSTs and600 seconds; the deadline dominates the3600-second controls and bounds descendant jobs. The background shared-slot race is separately recorded under I-02.
- **Verification performed (historical):** Frozen-source review `review-core-tool-contracts.md` and QA56/60 predate this correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance; no live tool/provider execution claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-03 — Bounded prompt readback and upload

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** New prompt writes use16KiB UTF-8, exports512KiB and inline readback1800 UTF-8 bytes. Setters acknowledge briefly without echo; response paths suppress mentions. Oversized legacy storage remains retained. Context omits a prompt over16KiB whole with a warning; export preserves exact text up to512KiB and warns when larger, rather than clipping it.
- **Verification performed:** QA56/60 prompt cases are historical and predate these corrections. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance; no live Discord delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-04 — Invalid image configuration and canonical migration

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed. Canonical activation intentionally held, not claimed fixed or deployed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Invalid image configuration disables only that capability even when forced on; native protocol, explicit endpoint and exact nonempty model-description mapping are required. `../../docs/IMAGE_GENERATION.md` and `../../docs/OPERATIONS.md` document the surviving operating boundaries; canonical migration/activation remains held. No canonical private profile migrated or enabled.
- **Verification performed:** Existing synthetic image/config refusals and source review in `review-image-configuration.md`; QA60 full-safe3984 passed plus28 subtests. QA64 actual-image constructor passed with image generation disabled; it is not a live image-capability probe.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention; canonical activation held.

## Finding C-05 — Image quality default

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Code and examples choose low. Parent's minimum pre-release check found the temporary profile at high quality, with neither `hd_image` nor `image_generator` disabled; this is not canonical migration or image-generation acceptance. Explicit private high/timeout settings are not silently replaced.
- **Verification performed:** Source/config review and historical synthetic image cases in QA60; parent performed the fresh minimum profile check cited above. This did not test live image generation or canonical configuration.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-06 — Aggregate foreground budget

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Task-local controls are32768 reserved output tokens,12 actual generation POSTs and600 monotonic seconds. Non-200 attempts refund reservation even when an error body exists; absent response bodies and cached-200 responses with no body also refund. A partial 200 response body keeps its reservation. Reserve exhaustion captures the incident. Model-spawned descendants share spend; independently issued background jobs retain separate limits. Foreground rejects invalid `n` and malformed recognized competing cap fields before reserve/POST, enforces one completion and clamps competing caps without raising lower values. The 600-second deadline dominates3600-second controls and bounds descendant jobs. This is not bot-wide expenditure, provider billing compliance, or a hard bound on detached work or post-timeout cleanup; provider-specific competing-field precedence remains unproven live.
- **Verification performed:** `review-provider-budget.md` is earlier source review; QA56/60 predate this correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance; no live provider experiment.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-07 — Replayed reasoning argument

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Retained-history reasoning is capped at300 characters and call arguments are bounded/elided. The next round can therefore see elided arguments for its own executed batch; replay is not intact. Executed call/result pairing and IDs are preserved. Mandatory `reasoning` policy remains unchanged.
- **Verification performed:** QA56/60 native/history cases predate this correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance; no live replay acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-08 — Unsafe dotenv/live-provider test

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source/test `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Historical live-provider case replaced in place with synthetic SSE bytes and fake progress channels. Historical version remains forbidden; no new test function/file survived final source inventory.
- **Verification performed:** Coordinator inspected replacement before isolated116-pass subset; QA60 full-safe3984 passed plus28 subtests, excluding only two manual live-provider programs with no collected cases. QA61 removed two newly introduced fixture constructors and passed201 cases; QA62 copied-app constructor passed4 cases. No host application import/test execution or live-provider acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-09 — Import-time dotenv boundary

- **Disposition:** deferred-accepted — import-time dotenv semantics remain unchanged as a current development boundary; no lazy-loading task is requested. Synthetic isolation does not establish intrinsic import safety.
- **Commit(s):** no loading-semantics change; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Import-time dotenv loading remains a real development boundary. Preserve configured startup behavior and isolate application execution; shell environment filtering cannot prevent same-UID filesystem reads. P-08 provenance is accepted as permanently unattributable and quarantined, not an open lazy-loading/cache task.
- **Verification performed:** QA60/61/62 used synthetic configuration without private mounts/network; QA64 guarded constructor ran inside actual candidate image with synthetic `/state`, not on the host. These receipts do not prove imports intrinsically harmless or resolve historical provenance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-10 — Build-context exclusions

- **Disposition:** fixed — in source; isolated artifact verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0`.
- **What changed / why not:** Root `.dockerignore` excludes `audit/` and `reports/`; Dockerfile COPY and Dockerfile-specific allowlist include new policy/budget modules. Context exclusion alone is not artifact provenance.
- **Verification performed:** QA63 built `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214` from packaging commit; all56 copied files matched Git, baked/OCI commit and dirty=false matched. QA62 copied-app constructor4 passed; QA64 existing guarded constructor passed in the actual image. No live service acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-11 — Actual reasoning content, not raw truthiness

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Reasoning-only classification uses normalized actual reasoning content rather than nonempty `reasoning_details` container truthiness; reasoning is not promoted into user-visible text.
- **Verification performed:** Provider source recheck, existing provider/core cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live provider acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-12 — Preserve explicit incomplete usage

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Bounded SSE usage drainage retains explicit counters and producing-call metrics, including Gemini total; total-minus-input never grants output refund. Daily tracker accepts canonical input/output aliases. Missing counters are not synthesized.
- **Verification performed:** `review-provider-budget.md` traced producing-call and initial/follow-up caller cases; QA56 foreground/provider green657 and QA60 full-safe3984 plus28 subtests executed existing caller coverage. No live provider/billing claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-13 — Bounded diagnostic captures

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed, with explicit scope limits.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Raw diagnostic capture is byte-bounded; decoded payload is bounded plus fixed omission-marker overhead; persisted details/traceback are capped at256KiB characters. Network-body ingress and successful response assembly are not capped here. Nested re-truncation lengths describe intermediate input rather than original provider bytes.
- **Verification performed:** Independent provider review and existing provider/error cases in QA56 green657 and QA60 full-safe3984 plus28 subtests; no live ingress/incident acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-14 — Reasoning-only terminal policy

- **Disposition:** retained by decision — reasoning-only output remains terminal; this is not a defect fix or external acceptance.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Reasoning-only output is terminal with a clear notice, without promoting private reasoning into visible text or paying for automatic retry/recovery. Root still decides whether fallback should be allowed. No older private reasoning setting is rewritten by this cost policy.
- **Verification performed:** Independent provider/caller source review and existing initial/follow-up cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live provider or delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-15 — Truthful, idempotent history omission

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Already-bounded omission summaries are retained rather than recounting truncated intermediates as original results; native call/result groups stay intact during shrinkage.
- **Verification performed:** Independent history review; existing custom/tool-tail/native cases included in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live history replay claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-16 — Schema-inclusive protected prompt budget

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** The control default remains96000 characters, but enforcement is72000. The planner accounts for exact serialized schema plus a24k newest-group allowance only when the tool prompt is present. History transcript is trimmed oldest-first before deletion and metadata records trimming; if pressure remains, expanded-group schemas are dropped before core and matching native/custom protocol blocks. Memory drops are logged. Newest-group replay is not intact: IDs/structure remain, but arguments may be elided. Tool-prompt refresh uses generated-prefix selectors; the earlier substring selectors that could overwrite persona/server prompt content containing `## Tool contract` were corrected. Prefix protection remains source-defined, not provenance-based.
- **Verification performed:** Earlier `review-core-tool-contracts.md`/`micro-custom-prompt.md` and QA56/60 are historical for the corrected planner/selectors. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. Catalog inventory values are fixture-specific characters, not tokens or live prompts.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-17 — Progressive tool discovery

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Default eligible core catalog is15 tools for the measured synthetic admin actor; named groups expand task-locally on following rounds. Background jobs have separate catalog scope without resetting inherited foreground spend; schemas and prompts refresh together. Exact eligible plugin names, including `tool_` names, take precedence over legacy aliases even before plugin-group discovery, while builtin collisions, actor/config/platform gates and background-spawn exclusion remain enforced. Discovery hiding is not execution authorization.
- **Verification performed:** Independent core and plugin-precedence reviews, integrated corrections and QA56 green657/QA60 full-safe3984 plus28 subtests. QA61/65 real-builder synthetic measurements:70 builtins plus4 checkers tools, admin core15 versus full74, with core14413 and full54608 serialized schema characters; actor/gate/plugin-specific numbers and limits in `06-TOOL-INVENTORY.md`. No live-profile or tool-execution acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-18 — Bounded text recovery

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Recovery bounds input, argument size and call count before synchronous parsing/dispatch; batches above eight calls are rejected whole, not partially executed. Native argument admission limits calls to16k bytes each,32k per batch and40k per envelope; an oversized batch is refused whole with bounded paired `Error` results rather than a generic turn failure. Repeat media is admitted once per extraction, while already-admitted payloads can recur across stages. These are admission bounds, not chunked authoring.
- **Verification performed:** QA56/60 recovery/native cases predate this correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance; no live provider text-recovery claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-19 — Media admission across rounds

- **Disposition:** fixed — in source for bounded admission; isolated verification complete; no feature-specific live acceptance claimed, with explicit ingress limit.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** New media is bounded/deduplicated without slicing base64; each extraction admits a repeated media item once, while an already-admitted payload may recur across stages. Returned attachment bytes are checked before decode/use; archive/MIME contradictions are refused. SDK `.read()` still fully allocates before post-read rejection: no hard peak-memory or streaming-ingress guarantee. See I-03; the20MiB setting does not add `.7z` extraction support or prove V1 10MiB parity.
- **Verification performed:** QA60/61 media cases are historical and predate the correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. No live attachment acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-20 — Persisted tool-result metadata

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Persisted argument and result metadata are bounded; framed image/audio payloads and data URIs are replaced with whole-media type/size labels before result head/tail capping. This sanitizes the stored copy, not the execution result used for media extraction and delivery.
- **Verification performed:** `review-core-tool-contracts.md` identified the earlier raw-result gap; `micro-result-media.md` confirmed the corrected source and existing stored-result assertions. QA56 green657 and QA60 full-safe3984 plus28 subtests cover integrated cases; no live media-delivery claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-21 — Dead expansion flag and misleading prompts

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Ineffective Message expansion state is replaced by task-local discovery. Hidden workflow/inbox/game instructions first direct group discovery rather than demand unavailable tools; background prompts and catalogs exclude recursive spawning.
- **Verification performed:** Independent core source review and existing native/custom prompt and discovery cases in QA56 green657 and QA60 full-safe3984 plus28 subtests; QA61/65 synthetic catalogs measured group changes. No live semantic/tool-use acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-22 — Server-prompt integrity

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** New writes are limited to16KiB UTF-8 before storage. Oversized legacy prompts stay stored but are omitted whole from foreground/background model context with a warning; canonical identity/tool contracts are not silently clipped for room. Readback and export have separate bounds (512 KiB export, with an omission warning for an oversized prompt). The coordinator's fresh private precheck found one stored server prompt at1939 UTF-8 bytes and none above16 KiB; this observation is not a deployment or final-release decision.
- **Verification performed:** Earlier source/fixture reviews and QA56/60 predate the correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. Parent's prompt-size observation is source/runtime precheck only, not deployment; no prompt-delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-23 — Shell authorization and environment

- **Disposition:** retained by decision — admin-or-allowlist shell trust is the selected policy, not a security defect fix; actor/advertisement gating and subprocess environment are source changes, not secret isolation.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Shared policy permits admins or existing string-ID shell whitelist; unknown actors fail closed. Direct execution and advertised catalog gate privilege, including autonomy catalog filtering through the shared actor gate. Bash uses explicit cwd, no profile/rc startup and a minimal environment. The admin-or-allowlist trust model is retained by decision: same UID can write controls, including the allowlist/admin file, within ordinary filesystem permissions. This is not a sandbox or a guarantee against same-UID access. Exact eligible plugin names retain precedence over aliases subject to builtin and actor/platform gates.
- **Verification performed:** Earlier authorization/plugin reviews and QA56/60 predate the correction slice. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. No live shell execution or private isolation claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-24 — Persistent rewrite authorization

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Persistent personality/server-prompt writes are admin-gated both at execution and advertisement; missing actor fails closed. Removal of taint confirmation does not grant arbitrary users persistent rewrite access.
- **Verification performed:** Independent authorization review and existing mutation/gate cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live administration acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-25 — Image availability detection

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed; canonical activation still held.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Auto advertisement requires valid native image protocol, explicit endpoint and a nonempty exact model-description map containing the selected model. An explicitly blank API key remains distinct from absent required endpoint/model data. Invalid forced-on configuration still does not expose the capability; templates document image settings. No canonical private profile was migrated or enabled.
- **Verification performed:** Independent image/config review and existing synthetic image/config/schema cases in QA60 full-safe3984 plus28 subtests. QA64 guarded constructor passed inside the actual candidate image with image generation disabled; it is not an image-capability or provider request.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention; canonical activation held.

## Finding C-26 — Image path resolution and edits

- **Disposition:** fixed — in source for path containment and documented edit behavior; isolated verification complete; no feature-specific live acceptance claimed. Same-UID realpath-to-read TOCTOU remains.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0` for the candidate artifact.
- **What changed / why not:** Local references and allowed roots use realpath bounds; escaping symlinks are refused, but path replacement between check and read is not prevented. Edits use explicit image settings without a claim of old downscaling, equivalent latency or same-UID filesystem isolation.
- **Verification performed:** `review-image-configuration.md` source/path trace and existing synthetic image/path cases in QA60 full-safe3984 passed plus28 subtests; QA64 actual-image constructor passed with image generation disabled. No live image request or TOCTOU elimination.
- **Deployment effect:** candidate source/construction-verified and exercised only in the bounded QA67–69 case, then prior image restored; canonical migration held.

## Finding C-27 — Omitted versus empty image input

- **Disposition:** fixed — in source and schema; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Only omitted/`None` image falls back to incoming attachments. Explicit `""`, `[]` or `"[]"` selects generation from scratch; schema/description clarify the distinction. This is not a live image-provider acceptance claim.
- **Verification performed:** Independent image/config review traced attachment and generations paths; existing image/schema cases in QA60 full-safe3984 passed plus28 subtests. QA64 constructor had image generation disabled.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-28 — Retired hd_image and private controls

- **Disposition:** push-back rejected and withdrawn — generic `Tool <name>: Error` follow-up handling is implemented, and `hd_image` is an alias subject to eligible-plugin precedence. This closes the cited no-follow-up scenario in source; it does not imply live acceptance.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; image documentation checkpoint `3754a8a`, `663749b`.
- **What changed / why not:** The rejected push-back is withdrawn. The generic follow-up check now recognizes dispatcher results in the `Tool <name>: Error` form, and `hd_image` resolves as an alias unless an eligible plugin claims that exact name first. Existing image-input semantics remain unchanged; no automatic transfer of quality/model/disabled-tool settings is performed, and canonical migration stays held.
- **Verification performed:** Earlier alias/schema review and QA60/64 predate the correction. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. Parent's fresh minimum precheck found neither image tool disabled and quality high; no canonical migration or image generation acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention; no canonical activation claim.

## Finding C-29 — Empty optional model/quality

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Empty optional model/quality falls back to configured defaults; nonempty unknown selections remain errors. Explicit private high quality is not silently overwritten by the new low source default.
- **Verification performed:** Independent image/config review traces fallback and existing synthetic generation/edit case; QA60 full-safe3984 passed plus28 subtests. No live image-provider or private next-boot check.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-30 — Configured runtime command prefix

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Runtime usage/errors and background parsing honor the configured prefix across command and solo/voice/context/REM/autonomy paths. Canonical docs use `!`; dated runtime receipts are historical rather than evidence of a deployed prefix change.
- **Verification performed:** Existing command/solo/REM and background cases in QA56 bounded core657 passed and QA60 full-safe3984 passed plus28 subtests. No live command invocation.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-31 — Incoming-message viewer latch trigger

- **Disposition:** fixed — producer fixed in source; viewer containment separately verified; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** producer source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; viewer `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`.
- **What changed / why not:** Incoming INFO logging uses IDs and character count rather than arbitrary message text. Bounded complete JSON redaction uses record-local state, preserving outer-span protection and genuine framing-loss fail-closed behavior; do not conflate producer removal with consumer repair.
- **Verification performed:** `review-viewer-authorization.md` traces producer and viewer paths; V six-suite185 passed; QA60 full-safe3984 passed plus28 subtests. No live viewer acceptance. Rejected scanned lines may affect span state without a separate marker for every redacted line.
- **Deployment effect:** application producer was in the bounded acceptance candidate, then the prior image was restored; host viewer fixes are not bundled in that image and have not been installed or exercised in the existing Screen session.

## Finding C-32 — Visible viewer omissions

- **Disposition:** fixed — in viewer source; isolated verification complete; no feature-specific live acceptance claimed, with bounded-retention/privacy limits.
- **Commit(s):** viewer `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`.
- **What changed / why not:** Viewer-owned omissions survive normal scope/error/replay filters and health coalescing; legitimate producer ERROR continuation remains intact. Tiny caller-supplied evidence budgets may not retain even a marker; scanned rejected/redacted lines do not each guarantee an individual marker.
- **Verification performed:** Independent viewer/authorization review; exact V six-suite185 passed and QA60 full-safe3984 passed plus28 subtests. No live viewer operation.
- **Deployment effect:** host viewer source only; not bundled in the application image, not installed into or exercised through the existing Screen session.

## Finding C-33 — Proportionate redaction continuity

- **Disposition:** fixed for bounded redaction/line handling; viewer R2-10 policy is retained by parent decision, with fail-closed oversize latch until restart. No live viewer acceptance claimed.
- **Commit(s):** viewer `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`.
- **What changed / why not:** Complete bounded JSON uses record-local redaction; active outer PEM/config spans remain masked. Rejected fragments are scanned, including sensitive-field state and last BEGIN/END order. Genuine framing loss/overflow fails closed; not every redacted/rejected line receives its own visible omission marker. The parent retains the fail-closed oversize-record latch until restart, including in canonical interactive viewer source (`instance.py logs`); this does not mean that source was installed in the host Screen workflow.
- **Verification performed:** `review-viewer-authorization.md` and narrow `review-lifecycle.md` redactor spot-check; exact V six-suite185 passed and QA60 full-safe3984 passed plus28 subtests. No live log/privacy acceptance.
- **Deployment effect:** host viewer source only; not bundled in the application image, not installed into or exercised through the existing Screen session.

## Finding C-34 — Final delivery settlement result

- **Disposition:** fixed — in source; isolated verification complete; one happy-path delivery observed in QA67–69, adverse settlement/cancellation cases remain isolated.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; lifecycle receipt `551060dbb7d223e1f365c069fbff2db377406f17` is separate.
- **What changed / why not:** Callers use the actual final settlement result; success is recorded only for confirmed delivery. Confirmed chunks/IDs are retained, while lost acknowledgements remain uncertain rather than proof of no Discord side effect.
- **Verification performed:** Synthetic progress/error subset116 passed; QA56 bounded caller/core657 passed and QA60 full-safe3984 passed plus28 subtests. L four-suite117 passed addresses lifecycle receipt uncertainty, not substitute proof of live final delivery.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-35 — Cancellation must not delete a possibly delivered final answer

- **Disposition:** fixed — in source; isolated verification complete; one happy-path delivery observed in QA67–69, adverse settlement/cancellation cases remain isolated.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; lifecycle receipt `551060dbb7d223e1f365c069fbff2db377406f17` is separate.
- **What changed / why not:** Cancellation after issuing a final edit preserves the possibly delivered final answer, including confirmed final delivery; bounded settlement retains uncertainty where acknowledgement is lost. No blanket assertion of external Discord delivery follows.
- **Verification performed:** Synthetic progress/error subset116 passed; QA56 caller/cleanup selection657 passed and QA60 full-safe3984 passed plus28 subtests. No live cancellation/delivery outcome.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-36 — Operator status and restart evidence

- **Disposition:** fixed — in source/documentation scope; isolated verification complete; temporary-only operator installed and positive readiness verified (QA66).
- **Commit(s):** lifecycle `551060dbb7d223e1f365c069fbff2db377406f17`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Owned container metadata survives expected bridge/private-layout configuration failures; unexpected Docker/ownership failures remain failures. Stopped/dead restart is refused before private preparation, retaining stop evidence. Documentation distinguishes metadata/probe limits and retained log replay.
- **Verification performed:** Independent `review-lifecycle.md`, exact L four-suite117 passed and QA60 full-safe3984 passed plus28 subtests. QA66 separately reverified the trusted3.14.4 operator interpreter/ownership and exact installed temporary-operator source; actual old-instance status returned config=ok and embedding_readiness=ok. Negative failure/refusal paths remain synthetic coverage, not live fault injection.
- **Deployment effect:** temporary-only `dirac.py`, `dirac_smoke.py` and `smoke_protocol.py` installed from reviewed source, with root-only rollback copies. Shared `instance.py`, `log_filter.py` and existing Screen session untouched. Application candidate subsequently exercised and reverted in QA67–69; the three temporary-operator files remain installed.

## Finding C-37 — Opened smoke turn cleanup and settlement

- **Disposition:** fixed — in source for exact-task settlement and conservative cleanup; isolated verification complete; bounded happy-path receipt verified in QA67–69, adverse cancellation/uncertain-delivery cases remain isolated.
- **Commit(s):** lifecycle `551060dbb7d223e1f365c069fbff2db377406f17`; smoke CLI withdrawal race `e540be6772f76d906720b79b07947a60893c3b24` is a distinct fix.
- **What changed / why not:** Cancel/settle the exact input task, retaining cleanup receipts before awaits; known tasks hold admission until settled, taskless uncertainty fails closed, and stop may recover receipts after queue registration disappears. A taskless `stop_unconfirmed` path writes terminal health state and stops rather than silently leaving stale `running`. Cleanup of an unregistered task stays conservative. Confirmed IDs identify acknowledged sends only; unacknowledged sends may still reach Discord. A failed status write cannot guarantee an on-disk terminal receipt.
- **Verification performed:** L/S and QA60 checks are historical. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. No live Discord/task settlement claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding P-01 — Temporary live instance used as a test bed

- **Disposition:** fixed — current validation-before-activation cadence corrected; the historical violation remains acknowledged. One separately authorized bounded happy-path acceptance completed and rolled back; internal correction recheck passed; original external verdict remains its conditional snapshot.
- **Commit(s):** prior grant recoverable at `git show eb188ac:phase-II_v2/SESSION_LOG.md`; source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`, packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0` (the QA67–69 historical candidate).
- **What changed / why not:** Earlier live-testing cadence is not retroactively authorized. Remediation QA was isolated and credential-free; candidate image `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214` was built and checked before the separately authorized temporary case. Coordinator alone exercised the candidate with one benign180s-deadline request in the approved smoke channel, scoped smoke-only; the request completed in8s and old-image/original-control restoration was verified. Ordinary use of the shared embedding API is expected; the profile stores remain separate and no shared-service mutation is authorized. This is one successful bounded delivery/body-readback case, not normal release, canonical/V1 activation or broad live feature acceptance.
- **Verification performed:** QA60 full-safe3984 passed plus28 subtests; QA61 fixture201 and QA62 constructor4 passed; QA63 copied-input/image provenance and QA64 actual-image constructor passed. QA67–69 record exact request/identity/channel, successful exact body plus runtime-footer readback, initial failed checker assertions and byte-exact control/profile preservation after restoration. Historical cadence remains recorded.
- **Deployment effect:** candidate ran only for bounded temporary acceptance; prior image is running again. Three temporary-operator source files remain updated. No normal release.

## Finding P-02 — No-new-tests contract

- **Disposition:** fixed — final narrowed definition inventory reconciled; historical additions/authorization remain separate, internal correction recheck passed without replacing the original external verdict.
- **Commit(s):** integrated source/tests `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0`.
- **What changed / why not:** Existing cases/fixtures were adapted; no new test file, function, helper or absence-asserting test survives the narrowed final inventory. Three approved fetch-case changes are one-to-one renames, not additional cases. The attempted nested drain helper and two newly introduced fixture constructors were removed. This does not retroactively authorize earlier additions or erase the audit's original contract finding.
- **Verification performed:** independent tracked-test definition inventory in `micro-test-definitions.md`; QA61 passed201 after constructor removals and QA62 passed4 copied-app constructor cases. Inventory covers the inspected tracked test diff, not untracked files or all historical test authorship; QA60's3984/28 run preceded the final removals, which received the narrowed rechecks.
- **Deployment effect:** test/source checkpoint only; no separate runtime permission.

## Finding P-03 — Owned validation failures

- **Disposition:** fixed — safe-suite and narrowed rechecks green with failed attempts retained; one bounded live case verified, internal correction recheck passed without replacing the original external verdict.
- **Commit(s):** source/test checkpoint `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; dated audit evidence `3754a8a`; packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0`.
- **What changed / why not:** `validation.md`, `qa52-53-triage.md` and preserved QA52 stdout retain the failed attempts, selectors, owners and fixture corrections rather than suppressing failures or applying xfail-for-green. Historical README/provider/environment failures are classified in those receipts; a later green selection does not rewrite the earlier results. No live-provider/manual-script or all-runtime green claim follows.
- **Verification performed:** QA52 3894 passed/83 failed/9 errors/28 subtests; QA53 baseline3884 passed/42 failed/9 errors/1 unsafe historical case deselected/28 subtests; QA54 970 passed/4 failed; QA55 644 passed/13 failed; QA56 bounded core657 passed. QA60 exact full-safe selection3984 passed/28 subtests, selected Ruff passed, exit0; QA61 final-fixture201 and QA62 copied-constructor4 passed. Two inspected manual live-provider scripts were excluded; this is the safe automated suite, not an unrestricted suite.
- **Deployment effect:** none from isolated QA; separate temporary acceptance and restoration are recorded in QA67–69.

## Finding P-04 — Unassigned legacy deletion

- **Disposition:** fixed — for current cleanup scope, not retroactive historical authority.
- **Commit(s):** `aad36e657dd04b436630604caebd58e905253753`.
- **What changed / why not:** Root explicitly authorized removal of obsolete V1 archive/documentation;24 files and3970 text lines were committed coherently with the freeze record. Do not restore old source from another checkout or stage unrelated work. This did not change active publisher code.
- **Verification performed:** local commit/explicit scope review; no application execution required for deleted archived material.
- **Deployment effect:** none.

## Finding P-05 — Retained worktrees and unintegrated branch histories

- **Disposition:** fixed — mapped but physically retained; retirement awaits accepted round two and separate dirty-state/ownership checks.
- **Commit(s):** no ref deletion or pruning; independently checked source-equivalence anchors in `07-PROCESS-DISPOSITIONS.md` and `review-worktree-supersession.md`.
- **What changed / why not:** Frozen baseline inventory:26 registered worktrees,25 local branches,two detached heads,22 checkpoint refs;86 pre-remediation branch commits outside baseline ancestry split54 patch-equivalent/32 non-equivalent. Separate Sol review mapped all32 across13 families, including rejected prototypes and corrected integrations; the earlier union89 referred to a snapshot with three remediation commits, not today's source HEAD. Preserve branch refs, auditor checkout, detached/checkpoint history and unverified working-directory content. Patch equivalence does not establish clean worktrees or authorize deletion; checkpoint-tree content and real remote state remain unverified.
- **Verification performed:** authorized local Git metadata/source review and independent cited commit-identity checks, without other-checkout filesystem inspection, fetch, prune or removal. Quarantined review's76/52/24 totals and semantic conclusions are not accepted.
- **Deployment effect:** none.

## Finding P-06 — Audit/document sprawl

- **Disposition:** fixed — durable contracts consolidated and accepted working-note sprawl physically retired under root's later delegation; final receipt/commit records the completed document gate.
- **Commit(s):** consolidation/retirement`f815857`; immutable internal-note recovery`89fb851`; phase/prior-grant recovery`eb188ac`; coordinated receipt in09.
- **What changed / why not:**39unchanged tracked phase files and28unchanged internal intake/inventory/implementation/micro/review notes were removed after migration into README/AGENTS and the nine current guides. Root's shorter audit directory was adopted. The16external originals remain byte-identical to `eb188ac`; response/validation, process companion/quarantine, QA recipe and failed-QA triage/gzip remain. Existing refs/worktrees and unrelated ignored audit/reports/skill material were not removed.
- **Verification performed:** coordinator compared original and retired-note blobs before removal; immutable grant/recovery objects exist; independent docs review found live-ledger inconsistencies and coordinator corrected them. Worktree/ref retirement remains a separate held operation, not this documentation cleanup.
- **Deployment effect:** none; documentation retirement is not rollout authority.

## Finding P-07 — Reviewer route naming drift

- **Disposition:** fixed — current routing documented and used; internal correction recheck passed; original external verdict preserved.
- **Commit(s):** current governance in `../../AGENTS.md` and `../../TODO.md`; documentation checkpoints `663749b`, `61111fe`, `99118dc`, `5023c8c`.
- **What changed / why not:** Assignments use discovered `openai-codex/gpt-6-luna`, `openai-codex/gpt-6-sol` and `deepseek-official/deepseek-flash` routes, explicit ownership and rotated independent review instead of obsolete historical labels. A named route or draft review alone is not acceptance.
- **Verification performed:** current guidance and dated independent review receipts; no new original-auditor acceptance is asserted; the original conditional verdict is preserved and internal correction recheck passed. No provider credential inspection.
- **Deployment effect:** none.

## Finding P-08 — Host bytecode provenance

- **Disposition:** deferred-accepted as permanently unattributable — preserve the quarantined method-failure record; do not clean caches or claim provenance resolved.
- **Commit(s):** process record `3754a8a`; no cache deletion or provenance-rewrite commit.
- **What changed / why not:** Coordinator verified only presence,size/mtime and Git-ignore status of the two root `.pyc` files named in `07-PROCESS-DISPOSITIONS.md`, not the content/origin of all caches. Auditor also cited compiled test modules under `.validation-cache/`; their provenance remains unattributed. Historical compile-only notes do not prove origin, host application import or safety. A reviewer violated its no-interpreter assignment and advanced invalid decoder-derived conclusions; those remain quarantined, without retroactive authorization or a manufactured clean history.
- **Verification performed:** authorized stat/Git-ignore observations for two root files only; no accepted decoder/header inference, cache-content read or deletion. Full literal receipts for the violating review remain unavailable; current isolated QA says nothing about the older artifacts.
- **Deployment effect:** none.

## Finding P-09 — Direct grants versus author assertions

- **Disposition:** fixed — current grant documented; older corroboration gaps retained, internal correction recheck passed; historical external verdict unchanged.
- **Commit(s):** audit checkpoint `3754a8a`; documentation checkpoints `663749b`, `61111fe`, `99118dc`, `5023c8c` (individual changes in the dated ledger).
- **What changed / why not:** The prior verbatim grant is recoverable at `git show eb188ac:phase-II_v2/SESSION_LOG.md`; current root instructions and durable `../../docs/` distinguish current authority from historical author assertions. The grant covers bounded temporary acceptance, not retroactive approval of earlier rollouts, shared-service mutation, normal release or canonical/V1 activation. No missing older root words are invented.
- **Verification performed:** `07-PROCESS-DISPOSITIONS.md` grant comparison, `review-response-docs.md` narrow corrected-doc recheck and current checkpoint ledger. Historical authorization unknowns remain explicit; internal correction recheck passed; the original external verdict is not rewritten.
- **Deployment effect:** documentation only; separately granted temporary case and restoration are documented in QA67–69.

## Finding D-01 — Security posture after taint-gate removal

- **Disposition:** fixed — current source/documentation reconciliation recorded; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** SECURITY/architecture distinguish removed taint confirmation from retained independent authorization/redaction and actor-gated shell/rewrite access. The admin-or-allowlist shell trust decision is retained; same-UID actors can write controls within ordinary filesystem permissions. Neither the actor gate nor a minimal subprocess environment is a sandbox or guarantee against same-UID access.
- **Verification performed:** source/document review and QA56 bounded core657/QA60 full-safe3984 plus28 subtests; no same-UID isolation or live shell acceptance claim. Independent document consistency review and narrow correction recheck are recorded in `review-final-evidence.md` and `review-final-coverage.md`; neither reran source/runtime verification.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); no normal release.

## Finding D-02 — Text output example default

- **Disposition:** fixed — source/example mismatch corrected; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** `.env.example` and source use16384; the private temporary12345 cap was preserved, not replaced by the example default.
- **Verification performed:** source/example comparison and QA67–69 byte-exact original-control restoration; no canonical private configuration migration.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored; private cap remains12345.

## Finding D-03 — Canonical prompt-guide examples

- **Disposition:** fixed — canonical guidance reconciled; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** LONGPROMPT uses canonical `!` examples and distinguishes configured runtime prefix, bounded readback/upload/export and whole legacy omission. Historical temporary prefix receipts remain historical, not generic command examples.
- **Verification performed:** documentation/source review and existing prompt/caller cases in QA56 bounded core657 and QA60 full-safe3984 plus28 subtests; no live command invocation.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored; temporary runtime prefix was not rewritten.

## Finding D-04 — Obsolete confirmation language

- **Disposition:** fixed — current guidance consolidated;39phase files and28accepted internal notes physically retired after immutable recovery references and surviving contracts were preserved. Final document commit/receipt records the review gate; historical wording is not current authority.
- **Commit(s):** documentation `3754a8a`, `663749b`, `4c80d4c`; source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Current job guidance uses independent authorization rather than the retired taint-confirmation gate. PRUNING_MAP and redesign/handoff assertions are labelled historical; their wording is not proof of present security, readiness or earlier human authorization.
- **Verification performed:** source/document review and QA56/QA60 isolated cases; no retroactive grant or final independent verdict inferred.
- **Deployment effect:** documentation/source checkpoint and bounded temporary candidate exercise only; prior image/controls restored.

## Finding D-05 — Condensed current status

- **Disposition:** fixed — current milestone/status record reconciled; independent document consistency review/recheck complete; internal correction recheck passed without replacing the original external verdict.
- **Commit(s):** documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** STATUS records current source/QA, candidate artifact, one bounded temporary acceptance and verified old-image/control restoration, alongside normal-release and canonical holds. Its dated historical receipts are not fresh observations; full earlier narrative remains at `ab64853:docs/STATUS.md`.
- **Verification performed:** current `docs/STATUS.md` and handoff compared against the QA67–69 summary; no new original-auditor acceptance is asserted; the original conditional verdict is preserved and internal correction recheck passed.
- **Deployment effect:** documentation only; the separately authorized candidate exercise was reverted.

## Finding D-06 — Restart and log replay

- **Disposition:** fixed — operator/handoff semantics reconciled; no host viewer or Screen acceptance claimed.
- **Commit(s):** lifecycle `551060dbb7d223e1f365c069fbff2db377406f17`; documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** Restart retains the container and Docker log history; ordinary `logs` tails100 and can replay old lines. Only `logs --fresh` selects tail0 without deleting history, and is not a restart flag. Replacement starts a new container/log stream, not a way to erase evidence. Stopped/dead restart is refused before private preparation.
- **Verification performed:** source parser/logs/restart and handoff review, L four-suite117 and QA60 full-safe3984 plus28 subtests. QA67–69 preserved opaque old/candidate logs before replacement and verified restoration, not live restart fault handling or viewer behavior.
- **Deployment effect:** three temporary operator files installed; host viewer/Screen untouched, prior application image/controls restored.

## Implementer-raised items

### I-01 — Pending smoke request withdrawn between discovery and stat

- **Disposition:** fixed — in installed temporary operator/protocol source; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** smoke-protocol `e540be6772f76d906720b79b07947a60893c3b24`.
- **What changed / why not:** Catch only FileNotFoundError at the second stat; preserve other filesystem failures. Keep the accepted pending protocol, not the rejected prototype queue.
- **Verification performed:** exact S five protocol cases and independent Sol source check; QA60 full-safe3984 plus28 subtests. The earlier incorrect selector ran no tests and remains in validation evidence. No live withdrawal race injection.
- **Deployment effect:** temporary `dirac_smoke.py` and `smoke_protocol.py` installed; prior application image/controls restored.

### I-02 — Background native replay overwritten while posting progress

- **Disposition:** fixed — in integrated source; isolated verification complete, no live background-race acceptance.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Snapshot native followups immediately after direct dispatch, before the progress-post await; the shared slot can otherwise be overwritten by another job/channel. No broad state/API refactor was necessary for this assignment-based race.
- **Verification performed:** J's existing fake-send case overwrites the slot and checks paired replay; independent publication/return/await-order review, QA56 bounded core657 and QA60 full-safe3984 plus28 subtests. No live concurrent-background probe.
- **Deployment effect:** candidate exercised in one smoke-only case and prior image/controls restored; no normal release.

### I-03 — Attachment actual bytes and SDK allocation boundary

- **Disposition:** fixed — post-read admission fixed in source; allocation/archive/parity residuals retained, no live media acceptance.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Check actual bytes before text decode/media use and refuse archive suffix/image-MIME contradictions. The incoming20MiB override changes a setting, not archive/extraction support: `.7z` remains unsupported and V1 10MiB parity unverified. SDK `.read()` fully allocates before the post-read check; this is not streaming or hard peak-memory containment.
- **Verification performed:** independent source observations, existing forwarded/media cases in QA61's201-pass fixture recheck and QA60 full-safe3984 plus28 subtests. No live attachment or peak-memory experiment.
- **Deployment effect:** candidate exercised only in a text smoke case, then prior image/controls restored.

### I-04 — Catalog state coupled to foreground spend

- **Disposition:** fixed — in integrated source; isolated/synthetic catalog verification complete, no live background-job matrix.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Background catalog scope is separate from spend inheritance; schema/protocol and system prompt refresh together. Autonomy's shared actor catalog gate filters advertised tools to match execution authorization. Independent jobs begin with their own discovery state; model-spawned descendants inherit foreground spend. Raw planner-log counts are now recorded without exposing planner text. Catalog construction failure is terminal, not a silent no-tools fallback.
- **Verification performed:** Earlier J and catalog measurements are historical. Current correction commits `c2d6b0e` + `89fb851`; QA76 tree `511a355fabe792cc6ae844d26004de7c55c104b4`:3993 passed,28 subtests; QA75:92 passed and selected Ruff passed. Internal Sol diff review `a6b627d2` PASS is not original-auditor acceptance. Synthetic data does not prove every actor/plugin or live job combination.
- **Deployment effect:** candidate exercised in one bounded smoke case and prior image/controls restored.

### I-05 — Review-method violation and unsupported provenance

- **Disposition:** deferred-accepted as permanently unattributable — preserve the quarantined method-failure evidence; no forensic conclusions from the rejected method are accepted, and no cache cleanup is authorized.
- **Commit(s):** process record `3754a8a`; no source change attributed to the violating analysis.
- **What changed / why not:** Reviewer5f9fde83 performed prohibited interpreter metadata analysis, disclosed two then five invocations and could not provide complete literal receipts. Its Git totals and bytecode origin inferences were not accepted. Coordinator recomputed authorized metadata; a separate reviewer mapped retained histories. Preserve failure and retractions alongside replacement analysis.
- **Verification performed:** `07-PROCESS-DISPOSITIONS.md`, quarantined `review-process-evidence.md` and independent branch report. No application import/decoded execution was reported by that reviewer; its self-report is not independent proof. QA60 does not attribute historical caches.
- **Deployment effect:** none; the method-failure record remains quarantined, with historical provenance accepted as permanently unattributable.

### I-06 — Newly discovered request multiplicity/cap ambiguity

- **Disposition:** fixed — corrected and source-rechecked in integrated foreground admission; isolated verification complete, no universal provider-billing or alternate-cap-precedence claim.
- **Commit(s):** source/test `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Foreground admission rejects `n` other than exact integer1 and invalid recognized positive competing cap fields before fallback selection, reservation or POST. Each selected payload is validated/clamped to reserved `max_tokens`; lower positive aliases are preserved. A single reservation cannot bound `n>1` compliant completions, so that bypass is rejected rather than blamed on provider behavior.
- **Verification performed:** `micro-provider-admission.md` traced generation entry, fallback-first selection and final POST; existing case rejects malformed extras before any request/spend and checks clamping. QA56 bounded core657 and QA60 full-safe3984 plus28 subtests; no live provider experiment or universal precedence claim.
- **Deployment effect:** candidate exercised only in bounded smoke case and prior image/controls restored; no normal release.

## Remaining decisions and gates

- C-14 fallback behavior and the C-23 shell trust/control-write boundary remain root policy decisions; no new decision is inferred here.
- C-09 is an accepted development boundary. P-08/I-05 are accepted as permanently unattributable; preserve the quarantine and make no cache-cleanup/provenance task from them.
- Documentation contracts are consolidated;39phase and28internal-note files were physically retired after recovery preservation. The coordinator's final receipt records the corrected independent document review and local commit; no ref/worktree or unrelated-work cleanup is implied.
- Image`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc` is now live on temporary Dirac after QA77/78 artifact checks, QA83 smoke and QA86 identity/readiness/control verification. Original controls were restored and the selector pinned; exact receipt/rollback is in09. Canonical/V1 activation and host viewer rollout remain held and unclaimed.
- Preserve auditor originals00–04/A–E/08/R1–R5 and the quarantine verbatim. Retain07's dated process evidence, response/validation/closure and failed-run artifacts. Internal notes are historical Git recovery references; current contracts live in `../../docs/`. Internal Sol review and this response do not rewrite the original external verdict.
