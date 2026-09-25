# 05 — Implementer response — ready for independent round two

**Implementation handoff complete; auditor acceptance outstanding.** All52 finding blocks and6 implementer items have explicit dispositions, commits/evidence and deployment effects. Deferred items are **C-09 import-time dotenv semantics and P-08/I-05 unresolved historical provenance**, with named coordinator ownership and round-two gates in `../../TODO.md`; they are not claimed fixed. C-28 explicitly pushes back on a retired-name alias using the current contract and preserves the canonical migration hold. Independent Luna evidence and DeepSeek coverage reviews found documentation defects; their corrections were committed in `ddd2b2a` and narrowly rechecked without new findings. These reviews are not the external auditor's acceptance verdict.

Candidate `be28b85` is built, source/construction-verified and exercised in one bounded temporary happy-path case (QA67–69). The prior image and exact original controls were then restored; **the candidate is not the current running image**. Normal release, canonical/V1 activation, publisher and remote operations remain frozen.

Root's current grant and its limits are recorded in `../../AGENTS.md`, `../../TODO.md` and the verbatim entry in `../../phase-II_v2/SESSION_LOG.md`. It does not retroactively authorize older actions. Originals00–04 are unchanged. Keep this bundle and independent reviews through accepted round two; follow the retirement ledger afterward, preserving unresolved provenance and operating boundaries.

## Evidence keys and current commit boundary

- **V:** commit `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`, tree `bdd636d05898bcc41aafc4f3d75371c3991fbc5f`; Python3.14.4 isolated Ruff F821/F822/F823 passed; **185 passed**. Exact selection: `tests/test_log_console_render.py tests/test_log_console_robustness.py tests/test_log_console_events.py tests/test_log_console_history.py tests/test_log_console_integration.py tests/test_log_console_tty.py`.
- **L:** commit `551060dbb7d223e1f365c069fbff2db377406f17`, tree `c13f3d5a492069da1594ee3e61ebe0e82e0ba119`; same isolated Ruff selection passed; **117 passed**. Exact selection: `tests/test_dirac.py tests/test_dirac_operator.py tests/test_dirac_smoke.py tests/test_message_pipeline.py`.
- **S:** commit `e540be6772f76d906720b79b07947a60893c3b24`, tree `56062c02b3027ade1d58bd678ffc9efd1cc5fb48`; selected Ruff passed; **5 passed** in `tests/test_smoke_protocol.py`.
- **P (historical, uncommitted at measurement):** provider seam tree `9b3ec91e304d0bacaa2515f14fe9904710eee50a`; selected Ruff passed; **199 passed** in `tests/test_provider_error_reporting.py tests/test_providers.py tests/test_error_reporting.py tests/test_smoke_protocol.py`. This predates the newly identified request-shape correction and is NOT current caller or complete provider acceptance.
- **J (historical, uncommitted at measurement):** background seam tree `869157081116c6968c177e7f1954e0e56e418f37`; selected Ruff passed; **39 passed** in `tests/test_background_jobs.py`. Uses baseline bot plus existing doubles, not full real-bot integration.
- **First full-safe integration:** QA52 tree `21f57d4801720e33035f31b2353ed10d188d2844`: selected Ruff passed; **3894 passed,83 failed,9 errors,28 subtests passed**. QA53 preintegration `e540be6`: **3884 passed,42 failed,9 errors,1 deliberately deselected historical unsafe case,28 subtests passed**. QA54 fixture reconciliation tree `f38e3e400fa4c8036f0477a0d25cb1fe7a40a21d`: **970 passed,4 original unsupported-reasoning failures retained**. These are not whole-core acceptance. Case-level ownership and exact safe selections are in `qa52-53-triage.md`; full failed evidence remains retained.
- **Bounded integration recheck:** root directed divide-and-conquer; oversized Luna run was stopped, not restarted. Six fresh single-issue handoffs completed. QA55 tree `1354ca309efa6ffe24cdf7beb2905dfd45cb8760`: selected Ruff passed; **644 passed,13 failed** in the explicit core selection, including successful real foreground/provider cases but remaining fixture errors. QA56 tree `a58e8932abdc9009bde187060a90806a79ef5416` reran the same22-file selection after existing-fixture corrections: **657 passed**, selected Ruff passed, exit0. This is green bounded core integration, not a green full suite. At that intermediate checkpoint, independent acceptance, definition inventory, baseline/environment debt, artifact and bounded temporary acceptance remained open; subsequent receipts below close the completed execution gates, not historical failures. Exact commands/failures/corrections are retained in `validation.md`; no xfail-for-green or hidden discarded failures.

- **Current accepted source/QA checkpoint:** `d198c37ee038e57e7cca4183b60eef0eaef6f1fc` commits the integrated application/test fixes; `3754a8a` checkpoints the full dated audit evidence. QA60 full-safe suite on tree`e2d639755f90bfb16ff8a834975ae704772cb6ae`: **3984 passed,28 subtests passed**. Two final fixture helper removals rechecked in QA61: **201 passed**. QA62: **4 constructor cases passed** after preventing copied-app imports from falling back to the original checkout. New helper definitions were removed, existing fetch cases renamed one-to-one, no xfail-for-green. Exact source/image/selector/environment limits and retained failures are in `validation.md`.
- **Candidate artifact:** packaging fix `be28b8598215ff6a0c72d7c3160403f2425a61f0`; image **`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`**, tag`dame-curie-app:be28b85`. All56 copied inputs match Git; baked/OCI commit and dirty=false match. Existing guarded constructor probe passed inside the actual image (QA64). This is artifact evidence, not live delivery/feature acceptance. Subsequently exercised only during QA67–69 and reverted; see the bounded acceptance receipt below.
- **Measured catalog:** QA61/65 synthetic real-builder measurements are in `06-TOOL-INVENTORY.md`, separating current15-tool admin core/74-tool full exposure from historical flat73. Metrics are chars/bytes, not token/billing or live-profile claims. Default schema-inclusive budget is96000 characters (`control_defaults.py:175`, source`d198c37`, C-16);36k is the history-tail bound.

- **Bounded temporary acceptance, QA67–69:** request`608cc14a42714fd58bafbf8084b09690`, approved channel`1550960386939817984`, operator root`1482143139828596916`, confirmed Discord identity`1504398705539944560`. One180s-deadline request completed in8s with returned=true, one delivery, exact marker body plus the configured marker-tagged runtime footer and zero readback failures. The initial logger-selector and whole-wire-equality checks failed and are retained/corrected transparently in `validation.md`; no second inference request was submitted. Prior image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` restored in container`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, running/embedding-ready, identity reverified, original controls byte-exact and private profile fingerprint unchanged. Low/12345/REMoff retained. The source-reviewed temporary operator files remain installed. Host viewer fixes were **not** installed into the existing Screen workflow. Normal embedding API usage occurred; no shared-service configuration/lifecycle mutation.

**Coverage convention:** this one real model/delivery/readback case is not a per-finding live scenario matrix. Isolated verification and disclosed residuals below remain the substantive coverage for unexercised adverse/tool/provider paths. Independent round-two acceptance is still outstanding; no normal release follows.

Isolated QA used the established Python3.14.4 image with network disabled, no private mounts or credentials, read-only root and synthetic configuration. No application imports/tests/collection ran on the host for this QA. The separately disclosed source-reviewer method violation is not erased by these receipts.

## Finding C-01 — Visible, terminal incomplete output

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Genuine partial text has a leading sanitizer-safe cutoff notice; empty/reasoning-only output gets an explanation without disclosing reasoning. Initial and follow-up typed incomplete outcomes terminate without recovery, tool dispatch or paid retry. Confirmed delivery only is persisted.
- **Verification performed:** Independent caller/source recheck in `review-provider-budget.md`; QA56 foreground/provider selection passed657 cases and QA60 full-safe suite, including the existing caller matrix, passed3984 plus28 subtests. This is synthetic isolated coverage, not live Discord/provider delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-02 — Native admission, history groups and replay

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Compact before eviction; retain whole native groups within36k characters/12 messages. Admission rejects malformed, duplicate, oversized and nonfinite JSON batches before effects; replay keeps matching IDs, original executed arguments as JSON strings and per-call failure results. The background shared-slot race is separately recorded under I-02.
- **Verification performed:** Independent frozen-source review `review-core-tool-contracts.md` identified earlier gaps subsequently integrated; QA56 bounded core657 passed and QA60 full-safe3984 passed plus28 subtests. No live tool/provider execution claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-03 — Bounded prompt readback and upload

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** New prompt writes use16KiB UTF-8, exports512KiB and inline readback1800 UTF-8 bytes. Setters acknowledge briefly without echo; response paths suppress mentions. Oversized legacy storage remains retained; readback/export is bounded rather than silently clipping model context.
- **Verification performed:** Existing longprompt/prompt-storage cases included in QA56 green core and QA60 full-safe selection; no live Discord delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-04 — Invalid image configuration and canonical migration

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed. Canonical activation intentionally held, not claimed fixed or deployed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Invalid image configuration disables only that capability even when forced on; native protocol, explicit endpoint and exact nonempty model-description mapping are required. `../../docs/IMAGE_GENERATION.md` and `../../phase-II_v2/PROVISIONING.md` retain the canonical migration/activation hold. No canonical private profile migrated or enabled.
- **Verification performed:** Existing synthetic image/config refusals and source review in `review-image-configuration.md`; QA60 full-safe3984 passed plus28 subtests. QA64 actual-image constructor passed with image generation disabled; it is not a live image-capability probe.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention; canonical activation held.

## Finding C-05 — Image quality default

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Code and examples choose low. Explicit private high/timeout settings are not silently replaced; the guide distinguishes source defaults from the last recorded temporary profile. Next-boot private configuration has not been established by this evidence.
- **Verification performed:** Source/config review and existing synthetic image cases in QA60 full-safe3984 plus28 subtests; no fresh private value inspection or live image generation.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-06 — Aggregate foreground budget

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Task-local defaults are32768 reserved output tokens,12 actual generation POSTs and600 monotonic seconds; only validated consistent explicit output may refund. Model-spawned descendants share spend; independently issued background jobs retain separate limits. Foreground rejects invalid `n` and malformed recognized competing cap fields before reserve/POST, enforces one completion and clamps competing caps without raising lower values. This is not bot-wide expenditure, provider billing compliance, a hard bound on detached work or post-timeout cleanup; provider-specific competing-field precedence remains unproven live.
- **Verification performed:** `review-provider-budget.md` recorded the earlier alternate-first malformed-cap gap; subsequent source correction and existing provider/foreground cases are covered by QA56 green657 and QA60 full-safe3984 plus28 subtests. No live provider experiment.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-07 — Replayed reasoning argument

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Bound reasoning/arguments in retained history without changing actually executed arguments or canonical immediate native replay; preserve whole call/result pairs.
- **Verification performed:** Independent bounded source review; existing native/history cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live replay acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-08 — Unsafe dotenv/live-provider test

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source/test `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Historical live-provider case replaced in place with synthetic SSE bytes and fake progress channels. Historical version remains forbidden; no new test function/file survived final source inventory.
- **Verification performed:** Coordinator inspected replacement before isolated116-pass subset; QA60 full-safe3984 passed plus28 subtests, excluding only two manual live-provider programs with no collected cases. QA61 removed two newly introduced fixture constructors and passed201 cases; QA62 copied-app constructor passed4 cases. No host application import/test execution or live-provider acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-09 — Import-time dotenv boundary

- **Disposition:** deferred — import-time dotenv semantics remain unchanged; coordinator owns C-09 under `../../TODO.md` → “Retained items for round-two disposition.” Synthetic isolation and the separate bounded candidate exercise/restoration are verified; import safety itself is not fixed.
- **Commit(s):** no loading-semantics change; documentation `3754a8a`, `663749b`.
- **What changed / why not:** Import-time dotenv loading remains a real boundary. Preserve configured startup behavior and isolate application execution; shell environment filtering cannot prevent same-UID filesystem reads. Historical bytecode origin remains unresolved (P-08).
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

- **Disposition:** fixed — in source; isolated verification complete; no feature-specific live acceptance claimed.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Reasoning-only output is terminal with a clear notice, without promoting private reasoning into visible text or paying for automatic retry/recovery. No older private reasoning setting is rewritten by this cost policy.
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
- **What changed / why not:** Prompt input budget is96000 characters by default, including serialized native schemas and tool-call metadata/arguments;36k is the separate history-tail bound. Dedicated identity/native and custom tool contracts, including the `## Available tools\n` custom prefix, are protected; excess protected input fails visibly instead of silently clipping it. Prefix classification is not provenance-based: a system RAG block beginning with that exact prefix can also be protected.
- **Verification performed:** `review-core-tool-contracts.md` found the earlier custom-prefix gap; `micro-custom-prompt.md` checked its source correction and existing-case extension. QA56 green657 and QA60 full-safe3984 plus28 subtests cover the integrated prompt/native cases. `06-TOOL-INVENTORY.md` reports fixture-specific schema characters, not tokens or a live prompt.
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
- **What changed / why not:** Recovery bounds input, argument size and call count before synchronous parsing/dispatch; batches above eight calls are rejected whole, not partially executed. Strict native argument admission also rejects malformed/nonfinite JSON before effects.
- **Verification performed:** Independent core source review found earlier slice/nonfinite gaps; integrated corrections and existing recovery/native cases covered by QA56 green657 and QA60 full-safe3984 plus28 subtests. No live provider text-recovery claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-19 — Media admission across rounds

- **Disposition:** fixed — in source for bounded admission; isolated verification complete; no feature-specific live acceptance claimed, with explicit ingress limit.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** New media is bounded/deduplicated without slicing base64 or repeatedly reattaching the retained set. Returned attachment bytes are checked before decode/use; archive/MIME contradictions are refused. SDK `.read()` still fully allocates before post-read rejection: no hard peak-memory or streaming-ingress guarantee. See I-03; the20MiB setting does not add `.7z` extraction support or prove V1 10MiB parity.
- **Verification performed:** Independent source observations and existing forwarded/media cases in QA61's201-pass fixture subset and QA60 full-safe3984 plus28 subtests. No live attachment acceptance.
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
- **What changed / why not:** New writes are limited to16KiB UTF-8 before storage. Oversized legacy prompts stay stored but are omitted whole from foreground/background model context with a configured-prefix diagnostic; canonical identity/tool contracts are not silently clipped for room. Readback and export have their separate bounds.
- **Verification performed:** Background source/fixture review, independent protected-prompt recheck and existing foreground/background prompt cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live prompt-delivery acceptance.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding C-23 — Shell authorization and environment

- **Disposition:** fixed — in source for actor/advertisement gating and subprocess environment; isolated verification complete; no feature-specific live acceptance claimed, not secret isolation.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Shared policy permits admins or existing string-ID shell whitelist; unknown actors fail closed. Direct execution and advertised catalog gate privilege. Bash uses explicit cwd, no profile/rc startup and a minimal environment. Same-UID filesystem access remains possible; this is not a secret sandbox. Exact eligible plugin names retain precedence over aliases subject to builtin and actor/platform gates.
- **Verification performed:** Independent authorization/core/plugin reviews and existing shell/gate cases in QA56 green657 and QA60 full-safe3984 plus28 subtests. No live shell execution or private isolation claim.
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

- **Disposition:** push-back — the proposed retired-name alias is not adopted; the current tool contract is retained and the observed temporary disable controls need no mapping. Coordinator owns this policy decision under `../../TODO.md` → “Retained items for round-two disposition”; canonical private migration remains held.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; image documentation checkpoint `3754a8a`, `663749b`.
- **What changed / why not:** Only `image_generator` remains registered/discoverable. The counter-argument to a name-only alias is the current explicit contract: `bot_tools.py:1255–1278` and `tool_schemas.py:101–125` distinguish omitted/empty image input and default to saving rather than auto-posting. A retired name forwarded without an explicit argument/behavior migration is not equivalent compatibility; stale calls fail rather than being silently reinterpreted. This is the coordinator's selected clean-cut policy under root's remediation grant, not a claim that root separately dictated this alias decision. No automatic transfer of quality/model/disabled-tool settings is performed; explicit private high quality remains unchanged and canonical migration stays held.
- **Verification performed:** `review-image-configuration.md` traced registration, tool-name aliases, schema and the private-control residual; QA60 full-safe3984 passed plus28 subtests and QA64 actual-image constructor passed with image generation disabled. Parent's separate QA67 preparation observed neither `hd_image` nor `image_generator` disabled in the temporary profile, and explicit quality=high; profile bytes were preserved. This settles that observed temporary disable ambiguity, not canonical migration or live image generation.
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

- **Disposition:** fixed — in viewer source; isolated verification complete; no feature-specific live acceptance claimed, with explicit line-omission privacy tradeoff.
- **Commit(s):** viewer `7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`.
- **What changed / why not:** Complete bounded JSON uses record-local redaction; active outer PEM/config spans remain masked. Rejected fragments are scanned, including sensitive-field state and last BEGIN/END order. Genuine framing loss/overflow fails closed; not every redacted/rejected line receives its own visible omission marker.
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
- **What changed / why not:** Cancel/settle the exact input task, retaining cleanup receipts before awaits; known tasks hold admission until settled, taskless uncertainty fails closed, and stop may recover receipts after queue registration disappears. Cleanup of an unregistered task stays conservative. Confirmed IDs identify acknowledged sends only; unacknowledged sends may still reach Discord. A failed status write cannot guarantee an on-disk terminal receipt.
- **Verification performed:** `review-lifecycle.md` source trace; exact L four-suite117 passed, S smoke-protocol5 passed, QA60 full-safe3984 passed plus28 subtests. No live Discord/task settlement claim.
- **Deployment effect:** candidate exercised temporarily and prior image/controls restored (QA67–69); see coverage convention.

## Finding P-01 — Temporary live instance used as a test bed

- **Disposition:** fixed — current validation-before-activation cadence corrected; the historical violation remains acknowledged. One separately authorized bounded happy-path acceptance completed and rolled back; independent round-two review pending.
- **Commit(s):** current grant recorded in `../../phase-II_v2/SESSION_LOG.md`; source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`, packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0`.
- **What changed / why not:** Earlier live-testing cadence is not retroactively authorized. Remediation QA was isolated and credential-free; candidate image `sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214` was built and checked before the separately authorized temporary case. Coordinator alone exercised the candidate with one benign180s-deadline request in the approved smoke channel, scoped smoke-only; the request completed in8s and old-image/original-control restoration was verified. Ordinary use of the shared embedding API is expected; the profile stores remain separate and no shared-service mutation is authorized. This is one successful bounded delivery/body-readback case, not normal release, canonical/V1 activation or broad live feature acceptance.
- **Verification performed:** QA60 full-safe3984 passed plus28 subtests; QA61 fixture201 and QA62 constructor4 passed; QA63 copied-input/image provenance and QA64 actual-image constructor passed. QA67–69 record exact request/identity/channel, successful exact body plus runtime-footer readback, initial failed checker assertions and byte-exact control/profile preservation after restoration. Historical cadence remains recorded.
- **Deployment effect:** candidate ran only for bounded temporary acceptance; prior image is running again. Three temporary-operator source files remain updated. No normal release.

## Finding P-02 — No-new-tests contract

- **Disposition:** fixed — final narrowed definition inventory reconciled; historical additions/authorization remain separate, independent round-two acceptance pending.
- **Commit(s):** integrated source/tests `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; packaging `be28b8598215ff6a0c72d7c3160403f2425a61f0`.
- **What changed / why not:** Existing cases/fixtures were adapted; no new test file, function, helper or absence-asserting test survives the narrowed final inventory. Three approved fetch-case changes are one-to-one renames, not additional cases. The attempted nested drain helper and two newly introduced fixture constructors were removed. This does not retroactively authorize earlier additions or erase the audit's original contract finding.
- **Verification performed:** independent tracked-test definition inventory in `micro-test-definitions.md`; QA61 passed201 after constructor removals and QA62 passed4 copied-app constructor cases. Inventory covers the inspected tracked test diff, not untracked files or all historical test authorship; QA60's3984/28 run preceded the final removals, which received the narrowed rechecks.
- **Deployment effect:** test/source checkpoint only; no separate runtime permission.

## Finding P-03 — Owned validation failures

- **Disposition:** fixed — safe-suite and narrowed rechecks green with failed attempts retained; one bounded live case verified, independent round-two acceptance pending.
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

- **Disposition:** fixed — evidence tracked; retirement deferred until accepted round two, not an accepted permanent document set.
- **Commit(s):** audit checkpoint `3754a8a`; documentation checkpoints `663749b`, `61111fe`, `99118dc`, `5023c8c` (see current ledger for individual scope).
- **What changed / why not:** Original audit00–04 and failed-QA evidence are tracked and unchanged. `../../TODO.md` names temporary evidence, durable destinations, owners and the accepted-round-two gate. Do not delete or move unaccepted evidence, unresolved provenance or protected unrelated `reports/`/skill work to make the tree look finished.
- **Verification performed:** dated bundle/retirement ledger and documented checkpoints reviewed; final consolidation and removal have not occurred.
- **Deployment effect:** none.

## Finding P-07 — Reviewer route naming drift

- **Disposition:** fixed — current routing documented and used; final independent round-two verdict pending.
- **Commit(s):** current governance in `../../AGENTS.md` and `../../TODO.md`; documentation checkpoints `663749b`, `61111fe`, `99118dc`, `5023c8c`.
- **What changed / why not:** Assignments use discovered `openai-codex/gpt-6-luna`, `openai-codex/gpt-6-sol` and `deepseek-official/deepseek-flash` routes, explicit ownership and rotated independent review instead of obsolete historical labels. A named route or draft review alone is not acceptance.
- **Verification performed:** current guidance and dated independent review receipts; final integrated round-two decision not yet received. No provider credential inspection.
- **Deployment effect:** none.

## Finding P-08 — Host bytecode provenance

- **Disposition:** deferred — historical attribution remains unresolved; coordinator owns P-08 under `../../TODO.md` → “Retained items for round-two disposition.” Preserve artifacts and quarantined method-failure evidence; later QA does not resolve their origin.
- **Commit(s):** process record `3754a8a`; no cache deletion or provenance-rewrite commit.
- **What changed / why not:** Coordinator verified only presence,size/mtime and Git-ignore status of the two root `.pyc` files named in `07-PROCESS-DISPOSITIONS.md`, not the content/origin of all caches. Auditor also cited compiled test modules under `.validation-cache/`; their provenance remains unattributed. Historical compile-only notes do not prove origin, host application import or safety. A reviewer violated its no-interpreter assignment and advanced invalid decoder-derived conclusions; those remain quarantined, without retroactive authorization or a manufactured clean history.
- **Verification performed:** authorized stat/Git-ignore observations for two root files only; no accepted decoder/header inference, cache-content read or deletion. Full literal receipts for the violating review remain unavailable; current isolated QA says nothing about the older artifacts.
- **Deployment effect:** none.

## Finding P-09 — Direct grants versus author assertions

- **Disposition:** fixed — current grant documented; older corroboration gaps retained, final round-two review pending.
- **Commit(s):** audit checkpoint `3754a8a`; documentation checkpoints `663749b`, `61111fe`, `99118dc`, `5023c8c` (individual changes in the dated ledger).
- **What changed / why not:** `../../phase-II_v2/SESSION_LOG.md` quotes the current direct root grants; current STATUS/README/plan text qualifies older author-written choices, including taint-removal attribution, as historical rather than independently proven grants. The current authority covers bounded temporary acceptance but not retroactive approval of earlier rollouts, shared-service mutation, normal release or canonical/V1 activation. No missing older root words are invented.
- **Verification performed:** `07-PROCESS-DISPOSITIONS.md` grant comparison, `review-response-docs.md` narrow corrected-doc recheck and current checkpoint ledger. Historical authorization unknowns remain explicit; independent final round-two acceptance is pending.
- **Deployment effect:** documentation only; separately granted temporary case and restoration are documented in QA67–69.

## Finding D-01 — Security posture after taint-gate removal

- **Disposition:** fixed — current source/documentation reconciliation recorded; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`; documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** SECURITY/architecture distinguish removed taint confirmation from retained independent authorization/redaction and actor-gated shell/rewrite access. The same-UID filesystem risk remains real: neither the actor gate nor a minimal subprocess environment is a secret sandbox.
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

- **Disposition:** fixed — current guidance reconciled while historical attribution limits remain; independent response consistency review and narrow correction recheck complete; external round-two acceptance outstanding.
- **Commit(s):** documentation `3754a8a`, `663749b`, `4c80d4c`; source `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Current job guidance uses independent authorization rather than the retired taint-confirmation gate. PRUNING_MAP and redesign/handoff assertions are labelled historical; their wording is not proof of present security, readiness or earlier human authorization.
- **Verification performed:** source/document review and QA56/QA60 isolated cases; no retroactive grant or final independent verdict inferred.
- **Deployment effect:** documentation/source checkpoint and bounded temporary candidate exercise only; prior image/controls restored.

## Finding D-05 — Condensed current status

- **Disposition:** fixed — current milestone/status record reconciled; independent document consistency review/recheck complete; external round-two acceptance remains outstanding.
- **Commit(s):** documentation `3754a8a`, `663749b`, `4c80d4c`.
- **What changed / why not:** STATUS records current source/QA, candidate artifact, one bounded temporary acceptance and verified old-image/control restoration, alongside normal-release and canonical holds. Its dated historical receipts are not fresh observations; full earlier narrative remains at `ab64853:docs/STATUS.md`.
- **Verification performed:** current `docs/STATUS.md` and handoff compared against the QA67–69 summary; independent round-two verdict has not arrived.
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
- **What changed / why not:** Background catalog scope is separate from spend inheritance; schema/protocol and system prompt refresh together. Independent jobs begin with their own discovery state; model-spawned descendants inherit foreground spend. Catalog construction failure is terminal, not a silent no-tools fallback.
- **Verification performed:** J and independent source recheck; QA56 bounded core657, QA60 full-safe3984 plus28 subtests and QA61/65 real-builder synthetic catalog measurements. These do not prove every actor/plugin or live job combination.
- **Deployment effect:** candidate exercised in one bounded smoke case and prior image/controls restored.

### I-05 — Review-method violation and unsupported provenance

- **Disposition:** deferred — method-failure evidence is quarantined, but historical provenance remains unknown. Coordinator owns I-05 alongside P-08 in `../../TODO.md` → “Retained items for round-two disposition”; no forensic conclusions from the rejected method are accepted.
- **Commit(s):** process record `3754a8a`; no source change attributed to the violating analysis.
- **What changed / why not:** Reviewer5f9fde83 performed prohibited interpreter metadata analysis, disclosed two then five invocations and could not provide complete literal receipts. Its Git totals and bytecode origin inferences were not accepted. Coordinator recomputed authorized metadata; a separate reviewer mapped retained histories. Preserve failure and retractions alongside replacement analysis.
- **Verification performed:** `07-PROCESS-DISPOSITIONS.md`, quarantined `review-process-evidence.md` and independent branch report. No application import/decoded execution was reported by that reviewer; its self-report is not independent proof. QA60 does not attribute historical caches.
- **Deployment effect:** none; unresolved evidence remains retained for independent review.

### I-06 — Newly discovered request multiplicity/cap ambiguity

- **Disposition:** fixed — corrected and source-rechecked in integrated foreground admission; isolated verification complete, no universal provider-billing or alternate-cap-precedence claim.
- **Commit(s):** source/test `d198c37ee038e57e7cca4183b60eef0eaef6f1fc`.
- **What changed / why not:** Foreground admission rejects `n` other than exact integer1 and invalid recognized positive competing cap fields before fallback selection, reservation or POST. Each selected payload is validated/clamped to reserved `max_tokens`; lower positive aliases are preserved. A single reservation cannot bound `n>1` compliant completions, so that bypass is rejected rather than blamed on provider behavior.
- **Verification performed:** `micro-provider-admission.md` traced generation entry, fallback-first selection and final POST; existing case rejects malformed extras before any request/spend and checks clamping. QA56 bounded core657 and QA60 full-safe3984 plus28 subtests; no live provider experiment or universal precedence claim.
- **Deployment effect:** candidate exercised only in bounded smoke case and prior image/controls restored; no normal release.

## Open questions for root

None requiring an immediate new grant for the remaining authorized source/isolated work. Historical authorization/bytecode gaps remain unknown. Any operation outside the existing temporary-only acceptance boundary stays held; lack of evidence is not permission.

## Completion gates and next handoff

- Completed: frozen committed core, corrected/reviewed admission and caller paths, full safe suite plus narrowed final rechecks, tracked definition inventory, candidate artifact verification, bounded temporary delivery/body-readback case and verified restoration. Failed attempts and original auditor evidence remain retained.
- Completed: all52 findings and6 implementer-raised items carry dispositions, commits, verification and deployment effects. Unresolved historical provenance/authority and intentional safety/coverage limits are not relabelled as fixed defects.
- Completed: rotated independent consistency/coverage reviews (`review-final-evidence.md`, `review-final-coverage.md`), corrections in `ddd2b2a`, and narrow reviewer follow-ups with no remaining finding in their scopes. Final handoff includes their original findings and addenda; it is not self-certified external acceptance. Frozen candidate code and originals00–04/child reports were also compared against their committed checkpoints without differences.
- External gate: auditor round-two acceptance before retiring temporary evidence or considering normal release. This implementer response is not that verdict. Canonical activation/private migration and host viewer rollout remain separate operating gates; no additional deployment follows automatically.
- Retirement owner/destinations are explicit in `../../TODO.md`. Preserve originals00–04, all failed/retracted/quarantined evidence, retained refs/worktrees and private rollback material until their respective acceptance/ownership gates. No zero-defect guarantee.
