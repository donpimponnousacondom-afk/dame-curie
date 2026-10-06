# Full-safe integration / baseline triage — QA52–53

Temporary evidence. Retire only after accepted round two and consolidation. These are synthetic, credential-free QA results, not application deployment or live-provider acceptance. Coordinator owns every unresolved item below.

## Exact executions

- QA52 tree `21f57d4801720e33035f31b2353ed10d188d2844`, based on `e540be6772f76d906720b79b07947a60893c3b24` plus explicitly named owned changes. Selected Ruff F821/F822/F823 across changed production Python plus all tests passed. Pytest: **83 failed, 3894 passed, 9 errors, 28 subtests passed**,167.25s, exit1.
- QA53 baseline `e540be6772f76d906720b79b07947a60893c3b24`: **42 failed, 3884 passed, 1 deselected, 9 errors, 28 subtests passed**,183.43s, exit1. Historical unsafe dotenv/live-provider case was explicitly deselected; it was never executed. Current QA52 used its inspected synthetic replacement.
- Both: established Python3.14.4 image `sha256:a81175b66e37c3aabcb2d6f92e087af49974126e87e60064bbfd890695383792`, explicit UID1005 service/socket/engine, network-none, no private mounts/credentials, read-only root, tmpfs suite/tmp/state, capped resources. No host application imports/collection/tests.
- Both exclude `tests/test_streaming.py` and `tests/test_streaming_primary.py`: inspected manual live-provider programs with no collectible pytest test functions. No automated failure was skipped to obtain a green result.
- QA52 selection: `python -B -m pytest -o addopts=-ra -q --tb=short --durations=15 --ignore=tests/test_streaming.py --ignore=tests/test_streaming_primary.py tests`.
- QA53 selection: `python -B -m pytest -o addopts=-ra -q --tb=short --show-capture=no --ignore=tests/test_streaming.py --ignore=tests/test_streaming_primary.py --deselect=tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas tests`.
- Complete QA52 synthetic output retained as `qa52-synthetic-stdout.log.gz`; original readable tool output `/tmp/dsh-subprocess-Klrmz2/dsh-subprocess-3339121-5-f3158dd51866-stdout.log`. QA53 complete output is in its tool receipt. Very large prompt parameter IDs inflated QA52 output; the existing export case now has two short descriptive IDs, without changing its cases/assertions.

## Preflight correction

The coordinator first tested the service-owned socket as codexy and got a false `test -S` result; a scalar stat then reported ordinary OS traversal permission denial. No Docker call ran in those two failed checks. Running the authorized scalar check **as dame-curie**, without changing permissions or selecting another socket, verified UID1005 ownership, socket group427784, rootless security options and engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`; exact QA image identity matched. No policy escalation was requested or used.

## Integration failures newly exposed in QA52

All pending corrected-tree execution; these are not83 proven production bugs.

| Family | Observed cause | Owner / disposition |
|---|---|---|
| Foreground matrix/image paths and final-delivery round | Existing shared stub lacks real `_turn_tool_names`; `_preserve_input_actor` is also missing, producing a swallowed media warning. Generation/delivery paths were not reached, so new C01 assertions do not yet establish behavior. | Luna core: bind faithful production methods/fields; retain actual delivery/metrics/memory assertions. |
| Solo and command-formatting cases | Fake bot lacks configured `command_prefix`. | DeepSeek fixture lane source-written; parent independent review/QA pending. |
| Longprompt roundtrip/file cleanup | Shared readback branch now inlines short `longprompt` output, violating existing explicit export contract. Overflow notice129 chars exceeds the existing120-char brief-notice assertion. | Luna production: preserve explicit longprompt file export; shorten notice. Parent owns existing longprompt cases and their IDs. |
| Large operator incident report | New256KiB persisted diagnostic cap means formerly2M-character record fits one attachment; test still expects three. | Luna adapts existing case to bounded stored report plus complete delivery/closed buffers/mention suppression, not a larger persistence cap. |
| Prompt-store tool integration | Positive tool test actor100 has no admin policy in fake bot. | Parent added a bounded actor100 admin mapping; no real authorization relaxation. |
| Progress observer return | Both edit and fallback send fail; source now correctly returnsFalse, existing assertion still demandsTrue. | Parent changed existing assertion to actual settlement result; callback/confirmed-ID checks remain. |
| Native nonterminal failure | Expected exception-type prefix differs from existing executor error string. | Luna: preserve meaningful failure/replay assertion and verify real flow. |
| Prompt-budget fixture | Expected unprotected block was not trimmed as asserted. | Luna: recheck input budget and real protected/unprotected roles; no weakened blanket success. |

## Baseline failures and environment debt

These are recorded, not waived. QA52 retains41 of the42 baseline failed cases; the prior private-URL incident case is already adapted in the current tool-error suite. Other current failures are integration changes/fixtures. Both runs have the same nine setup errors.

| Family | Baseline observation | Ownership / next action |
|---|---|---|
| Checkout snapshot | Nine setup errors plus unborn-head failure: `/usr/bin/git` absent from frozen QA image. | Coordinator QA-environment issue. Do not skip/mock the provenance behavior or run it on the host; establish a compatible isolated Git-equipped envelope before claiming this coverage. No environment installation/image alteration performed. |
| Background thread failure | Test expects one message; real source emits the bounded thread-failure notice plus final result. | Parent: adapt existing assertion to both meaningful notices after checking retained private incident behavior. |
| Mention admission |16 variants lack `_channel_allowed` in fake bot. | DeepSeek bound real method; parent review/QA pending. |
| DeepSeek aliases | Two negative rows are now recognized transports. | DeepSeek separates real supported aliases from actual unknown-model/host negatives; verify expectation changes independently. |
| RAG/web memory | Six assertions run with globally disabled RAG, never invoking fake embedding path. | Parent: verify and explicitly enable only synthetic fixture paths, without real backend/model side effects. |
| Fetch URL | Three old private-address refusal expectations conflict with current validator's explicit HTTP(S)+hostname policy allowing private networks. | Parent policy/test reconciliation still pending. Do not silently restore network restrictions or claim SSRF isolation. |
| Instance fixture/identity | Two fakes lack staging property; one expected instance is syntactically invalid before identity comparison. | DeepSeek binds actual property and uses valid-but-different synthetic identity; independent review/QA pending. |
| Retry-default docs | README row no longer exists; subsequent assertions also target absent retired CONFIGURATION/HTML documents. | Parent kept provider/config/template default5 assertions and removed coupling to retired docs; no files restored, no absence-asserting replacement. |
| Unsupported reasoning commands | Four cases expect rejection, but the production rejection branch is commented out and commands can misleadingly report DeepSeek fields for an unknown transport. | OPEN coordinator production/policy disposition. Original negative assertions retained. DeepSeek's ineffective extra parameterization was rejected/reverted; only real provider-constructor binding remains. No false green or source behavior change yet. |
| Reasoning provider constructor | Fake lacks `_create_main_provider`. | Real method binding added, callback assertions retained; QA pending. |
| Native platform | Instance compatibility overrides bypassed by explicit class-method call. | Baseline defect too; Luna restore bound policy seam without weakening denial assertion. |
| TTS | Existing Fish-selected fixtures expect native Fish URL/body, whereas committed helper builds PPQ OpenAI-shaped speech request. | Source transport is preserved. DeepSeek changed expectations only; no new Fish selection, live compatibility or historical human endorsement claimed. Parent review/QA pending. |

## Independent frozen-source blockers beyond currently failing cases

Luna has explicit ownership to correct and extend **existing** cases only:

1. C06 malformed raw primary alternate cap escapes entry validation when fallback/vision is selected first; validate recognized present aliases before reservation/POST, retain per-attempt clamping.
2. C16 actual custom tool-system prefix `## Available tools\n` is not protected under prompt pressure.
3. C17 eligible undiscovered exact `tool_bash` plugin is resolved through discovery-visible names and can alias to builtin shell.
4. C02 native JSON accepts NaN/Infinity/nonfinite decoded values; reject whole batch before effects.
5. C20 raw tool-result embedded media still reaches persisted metadata as base64 fragments; parameter redaction is not result redaction.

See `review-provider-budget.md`, `review-core-tool-contracts.md`, `implementation-core.md`. Source was frozen for QA52; Luna is now explicitly unfrozen for these corrections. No final core acceptance, artifact, deployment or temporary-channel probe has occurred.

## Reviewer/author attribution

DeepSeek fixture handoff is source-only and partially retracted in `implementation-fixture-debt.md`. Its47/44 resolution-count assertions are **not accepted**; parent relies on actual QA receipts and case-level review. The unsupported-command expansion was not a valid fix and was reverted. Do not count retractions or source-written changes as executed success. All other author diffs remain pending independent parent review and isolated rerun.
