# Remediation validation receipts — temporary

Retire this file after accepted auditor round two, after consolidating final commit/QA/acceptance references into the implementer response and compact release receipt. This is ongoing work, not final acceptance. No candidate was deployed by these runs.

## Isolation and provenance

Coordinator re-resolved `dame-curie` to UID **1005** and verified its socket `/run/user/1005/docker.sock` as owned by that UID, mode **1660**. The initial unprivileged `stat` failed with ordinary Unix permission denial; the approved service-account run-as succeeded. No alternate engine was used. Engine ID **12fb714d-4e16-45ad-bb31-a86fb1a5ee8d**, security options include `rootless`.

All runs below use frozen image **`sha256:a81175b66e37c3aabcb2d6f92e087af49974126e87e60064bbfd890695383792`**. Observed versions: **Python 3.14.4, pytest 9.0.2, Ruff 0.15.7**. Source is a Git archive, never a host application import or a bind-mounted live checkout. Candidate snapshots use an independent temporary Git index; the normal index is not changed.

Runtime envelope: `--rm`, `--network none`, read-only root, all capabilities dropped, `no-new-privileges`, 256 PIDs, 3 GiB memory, 2 CPUs. Writable disposable tmpfs mounts only: `/suite` 768 MiB, `/tmp` 1 GiB, `/state` 256 MiB; `/suite` and `/tmp` permit synthetic executable fixtures. Explicit Bash entrypoint, never normal application startup. No private mounts, real dotenv, Docker socket mount, real Discord credential or real provider credential. Explicit `DAME_CURIE_ENV_FILE=/tmp/synthetic.env` points at an empty disposable file. Provider URLs use `.invalid`, the key is `synthetic-no-network`, model is `synthetic-model`; RAG/images are disabled, with a valid synthetic native image profile supplied for legacy validation. Loopback inside this isolated namespace is permitted; no outbound route exists.

## Baseline — `bash-34`

- Source: untouched **`ab64853`**.
- Selection: `tests/test_log_console_render.py`, `test_log_console_robustness.py`, `test_log_console_events.py`, `test_log_console_history.py`, `test_log_console_integration.py`, `test_log_console_tty.py`, `test_tool_gates.py`, `test_self_modify_tools.py`, `test_tools_not_admin.py`, `test_shell_runtime.py`.
- Exit **1**. Four viewer failures reproduced: timestamp case assumed default-visible Ollama; 79-column header clipped the origin legend; health-coalescing case assumed default-visible Ollama; escape-key case expected the implemented Up navigation mapping to disappear. The doubly quiet invocation did not print an aggregate count; no aggregate count is claimed.
- Resolution: explicitly enable Ollama in the two tests whose purpose is timestamp/coalescing behavior; move the local-clock label into the title and shorten the scope-line legend; preserve/assert Up navigation and ignored unrelated escape sequences. No default Ollama visibility or keyboard behavior was changed to manufacture a pass.

## First viewer candidate — `bash-35`

- Frozen tree **`62ec1445f63f539a9d1eeaf776635c38e38dbd63`**, based on `ab64853` plus viewer-only source/test changes.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Same six log-console test files above: **172 passed, 8 failed**, 33.01 s, exit **1**.
- All eight failures exposed the coordinator's invalid `dataclasses.replace(live_collapsed=False)` argument. `LogEvent.live_collapsed` is a computed property, not a dataclass field. Removed the invalid argument; the new viewer scope already computes the required false value. Existing subagent-history assertions were adapted to retain folded real payloads while marking omitted payloads as viewer-owned. This failed run is not relabeled as success.

## Corrected viewer candidate — `bash-36`

- Frozen tree **`5ba5b5b5fe53692e24da18445ebe50da6517381a`**, same baseline plus corrected viewer-only changes.
- Source files: `scripts/log_console/{append_events,append_state,append_render,scopes,console,controls,history,render}.py`.
- Existing test files adapted: `tests/test_log_console_{events,render,robustness,history}.py`. No new test file or test function was added; existing cases were extended/renamed where their contract changed.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: the six log-console files listed above. Command uses `python -B -m pytest -o addopts=-ra -q` so the aggregate result is printed.
- **180 passed**, 32.51 s, exit **0**.
- Covers scanned depth/malformed/service rejection versus true framing loss, multibyte service limits, preserved per-service PEM/config state, generic/image-envelope bounds, append/static omission visibility, static history-budget markers, and separation of ordinary unframed successors from viewer omissions.

## Provider, image and actor-gate candidate — `bash-37`

- Frozen tree **`282f21933244cf70d8ab4e30e6d88f9245ac4f8e`**, before the concurrent core integration.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: `tests/test_providers.py tests/test_provider_error_reporting.py tests/test_error_reporting.py tests/test_hd_image_config.py tests/test_image_generator.py tests/test_cpa_images.py tests/test_image_delivery_modes.py tests/test_image_media.py tests/test_see_image.py tests/test_self_modify_tools.py tests/test_shell_runtime.py tests/test_tool_error_reporting.py tests/test_image_request_logging.py tests/test_tool_gates.py tests/test_tools_not_admin.py tests/test_send_file_tool.py`.
- **522 passed, 2 failed**, 7.52 s, exit **1**. Provider usage-drain case patched a nonexistent `_SSE_LENGTH_DRAIN_TIMEOUT_SECONDS`; the production constant is `_SSE_LENGTH_DRAIN_SECONDS`. Core author owns that fixture correction. The other failure was a stale private-URL refusal expectation, not the current fetch policy; coordinator changed the existing case to assert permitted mocked private HTTP and rejected non-HTTP/missing-host inputs. Neither failure was suppressed.

## Viewer and lifecycle candidate — `bash-38`

- Frozen tree **`907bb269ab22b8f011d5e5542b434dbfba67fcc8`**; independent-review viewer corrections plus initial lifecycle implementation.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: `tests/test_log_console_render.py tests/test_log_console_robustness.py tests/test_log_console_events.py tests/test_log_console_history.py tests/test_log_console_integration.py tests/test_log_console_tty.py tests/test_dirac.py tests/test_dirac_operator.py tests/test_dirac_smoke.py tests/test_message_pipeline.py`.
- **296 passed, 2 failed**, 116.04 s, exit **1**. Both failures were existing `test_a_stuck_owned_task_holds_back_the_next_request` variants (`deadline`, `after_partial`): unconditional fail-stop prevented resumption after the exact known task settled. All six viewer suites passed. Author repaired known-task admission and retained the task/turn/receipt association before interruptible cleanup; taskless unresolved injection still fail-stops.

## Synthetic progress and fetch-policy correction — `bash-39`

- Frozen tree **`aaa5ae9b8633ccf408698ceb69021971241db9a4`**, built from `282f21933244cf70d8ab4e30e6d88f9245ac4f8e` plus current `tool_progress.py`, `tests/test_tool_progress.py`, `tests/test_tool_error_reporting.py`. This deliberately excludes half-written core integration.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: `tests/test_tool_progress.py tests/test_tool_error_reporting.py`.
- **116 passed**, 27.14 s, exit **0**.
- Includes the inspected, fully synthetic replacement for the historically live-provider streaming case. It uses synthetic SSE bytes and fake progress channels; the unsafe historical case was not executed. New local test helpers were removed in favor of existing mocks before this run. Corrected private-HTTP/non-HTTP policy variants passed without real network access.

## Corrected known-task recovery and final viewer marker ordering — `bash-40`

- Frozen tree **`2cd14b1248d7abbe85e0c5c887df073f78f42ca7`**, built from `907bb269ab22b8f011d5e5542b434dbfba67fcc8` plus `scripts/log_console/safety.py`, `tests/test_log_console_events.py`, `dirac_runtime.py`, `tests/test_dirac_smoke.py`.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: the same ten files listed under `bash-38`.
- **298 passed**, 56.72 s, exit **0**.
- Viewer coverage includes record-local structured redaction, persistent outer-span protection in both EventParser/JSONL and AppendParser, static error-view notices, scoped append replay, and an END-then-BEGIN sequence that must leave the next private-key span open.
- Lifecycle coverage now includes eventual next-request admission after exact task settlement, refreshed returned/delivery evidence, observer removal, and cancellation during cleanup. Independent review subsequently found a separate status-layout/bridge exception gap; its follow-up and further delivery-uncertainty wording are **not included in this passing snapshot**.

## Reviewed lifecycle follow-ups and sensitive-field span scanning — `bash-41`

- Frozen tree **`9b53c52dec958112315f747d59807fa31c2ac613`**, based on `2cd14b1248d7abbe85e0c5c887df073f78f42ca7` plus `scripts/log_console/safety.py`, `tests/test_log_console_events.py`, `scripts/dirac.py`, `tests/test_dirac_operator.py`, `dirac_runtime.py`, `tests/test_dirac_smoke.py`.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: the ten viewer/lifecycle/queue files under `bash-38`.
- **302 passed**, 57.24 s, exit **0**.
- Covers metadata-preserving status for expected bridge/private-layout validation failures without weakening owned-container/inspect failures; terminal receipts distinguish acknowledged message IDs from possibly accepted sends whose responses were lost, including partial known IDs. Existing smoke case parameters simulate both swallowed and propagated response loss.
- Structured redaction now scans values even when the sensitive field is masked wholesale, preventing a BEGIN marker in `api_key` from being skipped before a following opaque secret field. Existing generic/image parameters cover it.

## Viewer health-coalescing boundary — `bash-42`

- Frozen tree **`dd5ca3b71163a8e24923d5659290e8522cfb6437`**, based on `9b53c52dec958112315f747d59807fa31c2ac613` plus `scripts/log_console/console.py`, `scripts/log_console/render.py`, `tests/test_log_console_render.py`.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: `tests/test_log_console_render.py tests/test_log_console_robustness.py tests/test_log_console_events.py tests/test_log_console_history.py tests/test_log_console_integration.py tests/test_log_console_tty.py`.
- **185 passed**, 32.26 s, exit **0**.
- A final coordinator control-flow review found that raw post-gap GIN lines could enter health coalescing and hide or replace a viewer omission. Viewer-owned retained entries now bypass health ingestion; rendering ignores health hidden/summary overrides for that scope. The existing health case covers both actual post-gap ingestion and explicit stale hidden/summary inputs. An unrelated fixture change from maximum to lower severity was reverted.

## Exact standalone viewer commit — `bash-43`

- Tested and committed tree **`bdd636d05898bcc41aafc4f3d75371c3991fbc5f`**: untouched `ab64853` plus only the 14 viewer source/existing-test paths. Unlike preceding mixed snapshots, it contains no concurrent provider/image/lifecycle edits.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: the six viewer files listed under `bash-42`.
- **185 passed**, 32.30 s, exit **0**.
- Local commit **`7286aa2fcdbfc5b87533b8ff81db93d6c52587ad`**, tree identity checked before and after commit. Complete staged diff reviewed; independent Luna viewer report and narrow lifecycle-review appendix cover the final changes. No new test functions/files. Git hooks disabled for this commit to prevent unapproved host execution; isolated QA was run explicitly, not replaced by hook suppression.
- Source milestone only: no application artifact built or temporary runtime replaced.

## Exact standalone lifecycle commit — `bash-44`

- Tested and committed tree **`c13f3d5a492069da1594ee3e61ebe0e82e0ba119`**: `7286aa2` plus only `scripts/dirac.py`, `dirac_runtime.py`, `message_pipeline.py` and their three adapted operator/smoke/queue test files. No concurrent core/provider/image changes are included.
- Ruff `F821,F822,F823`, target `py314`: passed.
- Exact pytest selection: `tests/test_dirac.py tests/test_dirac_operator.py tests/test_dirac_smoke.py tests/test_message_pipeline.py`.
- **117 passed**, 24.77 s, exit **0**.
- Local commit **`551060dbb7d223e1f365c069fbff2db377406f17`**, tree identity checked before and after commit. Independent Luna reviewed the final expected-failure and receipt changes. Coordinator consolidated the final status-result branches to keep three returns without changing validation/skip precedence, then tested this exact tree. Complete source/test diff reviewed; no new test functions/files.
- Hooks disabled to avoid unapproved host execution; no live lifecycle operation, build, deployment or remote Git operation.

## Provider seam integration — `bash-45`, `bash-47`, `bash-49`

- `bash-45`: tree **`e99dd979831264cec1761f151722de352a3b24b7`**, based on `551060d` plus `providers.py`, `error_reporting.py`, `turn_budget.py`, `config.py`, `control_defaults.py`, their existing provider/error tests, and the smoke CLI/protocol case. Ruff stopped with **F821 `_safe_int` undefined in `providers.py:2552`**, exit **1**; pytest did not run. The author replaced the invented helper with the already typed final payload cap.
- `bash-47`: tree **`d057e775b34786daedd887d1b99083cea8706cb0`**, previous tree plus corrected `providers.py`. Ruff passed. Exact pytest selection: `tests/test_provider_error_reporting.py tests/test_providers.py tests/test_error_reporting.py tests/test_smoke_protocol.py`. **198 passed / 1 failed**, 4.46 s, exit **1**. The incomplete Gemini SSE case lost explicitly reported total40 while retaining input17; the JSON counterpart passed. The assertion was not weakened.
- `bash-49`: tree **`9b3ec91e304d0bacaa2515f14fe9904710eee50a`**, previous tree plus `provider_telemetry.py` and the adapted provider-error case. `merge_usage` now retains explicit `totalTokenCount`; no total-minus-input refund inference was reintroduced. A newly introduced nested drain-fixture class/method was removed to comply with the no-new-helper constraint; the existing response iterator now supports a blocking `None` sentinel. Ruff passed; the identical four-file pytest selection **199 passed**, 4.23 s, exit **0**.
- These snapshots exercise provider/budget/error metadata seams, not the concurrent `bot.py` integration, discovery, commands, media or complete suite. Decoded diagnostic capture is bounded payload plus fixed omission-marker overhead; raw capture is byte-bounded. Neither is a network-ingress or successful-body allocation guarantee.

## Withdrawn pending-request listing — `bash-46`, `bash-48`

- Exact standalone tree **`56062c02b3027ade1d58bd678ffc9efd1cc5fb48`**: `551060d` plus only `scripts/dirac_smoke.py` and `tests/test_smoke_protocol.py`.
- Independent Sol's P-05 inspection found a real discovery-to-stat withdrawal race. Coordinator catches only `FileNotFoundError` at the second stat; other filesystem failures remain visible. The existing protocol case supplies a frozen discovery list after unlink, with no new helper/test.
- `bash-46`: Ruff passed, but the coordinator mistakenly included nonexistent historical selector `tests/test_dirac_smoke_protocol.py`. **No tests ran**, exit **4**. This was a coordinator command error, not a product defect.
- `bash-48`: same tree, corrected exact selection `tests/test_smoke_protocol.py`; Ruff passed, **5 passed**, 0.08 s, exit **0**.
- Local commit **`e540be6772f76d906720b79b07947a60893c3b24`** matches that exact tested tree. Independent source recheck complete; hooks disabled to prevent host execution. No live smoke CLI/runtime operation occurred.

## Background catalog scope and refresh — `bash-50`

- Frozen tree **`be7a9d146695c0e17a4eae256d508e1f90e1f40d`**, based on `e540be6` plus `jobs.py`, `job_routing.py`, `control_defaults.py`, `turn_budget.py`, `tests/test_background_jobs.py`.
- Selected Ruff `F821,F822,F823`, target `py314`: passed. Exact pytest selection `tests/test_background_jobs.py`: **39 passed**, 1.18 s, exit **0**.
- Each job gets an independent catalog set; tools/protocol and its system prompt refresh on each step without discarding user/history. Foreground-spawned jobs retain the same spend object; independently started jobs do not acquire a foreground budget. Catalog failure terminates visibly rather than silently substituting no tools. Existing success case parameters exercise discovery plus independent/descendant contexts; existing failure case exercises catalog and generation cleanup. No new functions/helpers.
- Independent Sol rechecked the parent source/test diff and found an out-of-scope fixture variable; coordinator moved it into the outer existing case before this snapshot. Static follow-up found no remaining blocker in this bounded seam.
- This is a seam test using existing bot doubles against baseline bot source, not integrated acceptance of current real bot catalog construction or the whole background execution surface. Core source/filtering and full integrated QA remain pending.

## Background native-replay handoff race — `bash-51`

- Coordinator found that `jobs.py` read the shared native-followup slot only after awaiting its progress post; another job/foreground dispatch could replace that slot meanwhile. Current native dispatch publishes the slot synchronously immediately before returning; the foreground caller already snapshots it without yielding. The job now does the same, before any later await. No new global-state abstraction or bot API refactor.
- Existing fake progress send replaces the shared slot with a foreign turn, and the existing parameterized runner case verifies that replacement actually occurred while the next generation retains its own `discover_1` assistant/tool pair and no foreign data. This is deterministic seam coverage, not a live concurrent Discord probe.
- Frozen tree **`869157081116c6968c177e7f1954e0e56e418f37`**, `bash-50` tree plus only `jobs.py` and `tests/test_background_jobs.py`. Ruff passed; exact selection `tests/test_background_jobs.py`: **39 passed**, 1.21 s, exit **0**.
- Independent Sol separately source-rechecked the publication/return/caller-await ordering and the existing-case adaptation; no remaining blocker in this bounded fix. Other moving core findings remain open until final recheck and integrated QA.

## First full-safe integration and baseline — `bash-52` / `bash-53`

- QA52 frozen tree **`21f57d4801720e33035f31b2353ed10d188d2844`**: selected Ruff F821/F822/F823 passed; **83 failed,3894 passed,9 errors,28 subtests passed**,167.25s, exit1. Full safe automated selection, not a green acceptance result.
- QA53 preintegration baseline **`e540be6772f76d906720b79b07947a60893c3b24`**: **42 failed,3884 passed,1 deselected,9 errors,28 subtests passed**,183.43s, exit1. The historical dotenv/live-provider case was explicitly deselected and never executed; QA52 used its inspected synthetic replacement.
- Both excluded the two inspected manual live-provider scripts `tests/test_streaming.py` and `tests/test_streaming_primary.py`, neither of which defines collectible pytest tests. No automated failure was skipped for green.
- Exact selectors, failures, owners and envelope are in **`qa52-53-triage.md`**. Complete synthetic QA52 stdout is preserved as **`qa52-synthetic-stdout.log.gz`**. Missing `/usr/bin/git` in the frozen QA image caused nine setup errors plus one failed provenance case in both runs; no host execution or mock/skip workaround was used.
- The coordinator's initial socket check ran as the wrong Unix principal and stopped on ordinary traversal permissions before Docker access. Correct scalar verification as the explicitly authorized service user confirmed UID1005, the designated rootless engine and exact QA image; no filesystem permission change, policy escalation or engine fallback.

## Existing-fixture reconciliation — `bash-54`

- Frozen tree **`f38e3e400fa4c8036f0477a0d25cb1fe7a40a21d`**, based on QA52 plus only15 explicitly staged existing test files. No moving core source was included. Ruff F821/F822/F823 over tests passed; **970 passed,4 failed**,9.71s, exit1.
- Exact selection: `tests/test_bot_mentions.py tests/test_solo_channel.py tests/test_command_formatting.py tests/test_reasoning_commands.py tests/test_deepseek_reasoning.py tests/test_instance_ops.py tests/test_instance_backup_compat.py tests/test_tts_config.py tests/test_tts_tempfiles.py tests/test_background_error_reporting.py tests/test_prompt_storage.py tests/test_response_observability.py tests/test_provider_resilience.py tests/test_embed_and_web_fixes.py tests/test_web_rag_store.py`.
- The four remaining failures are the original `test_other_models_are_explicitly_unsupported` reasoning/effort variants. Production has its rejection commented out. The fixture author's ineffective extra parameterization and resolution-count claim were rejected; original negative assertions remain. This is an explicit unresolved behavior/policy issue, not silently aligned expectations or xfail-for-green.
- RAG was enabled only behind the existing synthetic embedding/session replacements; production defaults and private state remain untouched. Retired-doc retry assertions were removed while provider/config/template default5 checks remain. Progress settlement assertions now distinguish actual failed delivery.

## Bounded core integration — `bash-55` / `bash-56`

- QA55 tree **`1354ca309efa6ffe24cdf7beb2905dfd45cb8760`**, QA54 plus explicit interrupted-core paths and integrated bound-policy seam: selected Ruff passed; **644 passed,13 failed**,35.31s, exit1. The foreground/provider/partial-delivery cases reached and passed their intended synthetic paths. Ten failures were fake objects missing the now-bound compatibility method; one was the prompt fixture incorrectly requiring filler retention; two still invoked `longprompt` while asserting ordinary `prompt` inline behavior.
- Coordinator bound the actual compatibility method in the existing fake cases; allowed unprotected filler to be trimmed **or removed**, retaining the total budget, intact protected catalog/core/server blocks and visible-overflow assertions; changed the existing inline phase to invoke the actual ordinary `prompt` command. No new test definitions, policy relaxation, production fallback for deficient fixtures or xfail.
- QA56 frozen tree **`a58e8932abdc9009bde187060a90806a79ef5416`**, QA55 plus only `tests/test_tts_silent.py tests/test_tool_gates.py tests/test_longprompt_command.py`: selected Ruff passed; **657 passed**,32.18s, exit0.
- Exact selection for both: `tests/test_foreground_observability.py tests/test_final_delivery_round.py tests/test_provider_error_reporting.py tests/test_providers.py tests/test_provider_resilience.py tests/test_tool_calls.py tests/test_tts_silent.py tests/test_token_trim.py tests/test_prompt_behaviour.py tests/test_text_tool_call_recovery.py tests/test_plugin_system.py tests/test_custom_tool_calls.py tests/test_longprompt_command.py tests/test_operator_commands.py tests/test_rem_commands.py tests/test_background_jobs.py tests/test_tool_gates.py tests/test_tools_not_admin.py tests/test_tool_progress.py tests/test_response_observability.py tests/test_prompt_storage.py tests/test_forwarded_messages.py`.
- Same credential-free network-none/read-only rootless QA image/envelope, synthetic env and no mounts. This is the first green bounded core integration, **not** a green full safe suite, artifact or live-Dirac acceptance. Known reasoning/private-URL expectations and Git-less full-suite provenance setup remain outside this selection.

## Human-directed decomposition checkpoint

- Root challenged the oversized Luna assignment and explicitly directed divide-and-conquer rather than reducing parallelism. Coordinator interrupted that run, preserved its work and froze post-interrupt core tree **`e47270b89faa6c0c93d76d1bb74b760baa6b9700`**. This tree has not yet been executed.
- Six fresh bounded lanes now cover provider admission, nonfinite native JSON, exact plugin precedence, persisted-result media, custom prompt protection and explicit longprompt export. Only provider/schema lanes write their disjoint source/test files; shared `bot.py`/native-test changes return as proposals for coordinator-only integration. Each lane ends after one scoped pass; the retired oversized session receives no further assignments.

## Full-safe green run and checkpoint — QA57–61

- QA57 resolved signed Debian Git package metadata in a source-free disposable preparation container. QA58 preparation image `sha256:11069a04c5fab56c126679251c7b4d90af293dc5ad74df294e46db5716ba80f4` installed pinned Git/git-man `1:2.47.3-0+deb13u1` plus transitive dependencies, including Perl and a perl-base upgrade despite apt `--no-upgrade`. This intermediate layer is retained as preparation evidence, not used for application QA or production.
- QA59 instead copied only `/usr/bin/git` and its default templates into the original frozen base. Final isolated QA image **`sha256:fdaf6b6f3273d05ae84d3560cef7a8add26128aa098995efd2a725e2ce145b57`**: Git2.47.3, Python3.14.4, pytest9.0.2, Ruff0.15.7; inherited perl-base remains5.40.1-6. No project dependency/pin or application-image change. Preparation used package networking without application source/private mounts; all test executions stayed network-none. Recipe: `qa-git.Dockerfile`; original base tag was checked against immutable `a81175…` before builds. The final recipe's local FROM tag requires the same precheck when reproduced.
- QA60 tree **`e2d639755f90bfb16ff8a834975ae704772cb6ae`**: **3984 passed,28 subtests passed**,155.37s, exit0; selected Ruff passed. Exact full-safe selection: `python -B -m pytest -o addopts=-ra -q --tb=short --show-capture=no --durations=15 --ignore=tests/test_streaming.py --ignore=tests/test_streaming_primary.py tests`. Only the two previously inspected manual live-provider scripts were ignored. No skipped/xfail/deselected automated failure. Real local Git exercised the ten formerly blocked provenance checks inside the container.
- Reasoning CLI policy deliberately rejects unrecognized transports without saving a new preference or inventing DeepSeek wire state. Existing preferences and configured provider options remain unchanged; the broadened recognized Flash matcher is preserved. Existing four cases also verify byte-exact preservation of preexisting controls. Fetch tests preserve existing private/local HTTP(S) access, test surviving scheme/host/redirect validation, and explicitly prove no session acquisition on direct refusal. Neither behavior grants SSRF isolation or live-provider acceptance.
- Definition inventory found two newly introduced fixture constructors. Coordinator removed both; independent Sol rechecked the exact hunks. QA61 tree **`25763dfee4483e4887479b2997ff64b0009d562c`** includes those two fixture changes and removal of a stale no-op comment: selected Ruff passed; **201 passed**,1.59s, exit0, selecting `tests/test_forwarded_messages.py tests/test_plugin_system.py tests/test_reasoning_commands.py tests/test_fetch_url.py`.
- QA61 then measured actual tool registrations and serialized catalogs in the same isolated image using real setup/catalog/schema functions with a synthetic bot/actors and all feature gates enabled:70 built-ins,4 checkers tools. Admin core15 tools:14413 schema characters/14436 UTF-8 bytes; workflow24:21431/21460; all/debug74:54608/54649. Ordinary actor core14:12892/12915; workflow21:18744/18773; all/debug70:51085/51122. These are compact serialized-schema measurements, not token/billing counts, a complete prompt measurement or a live profile. Correction to the initial coordinator prose:36k characters is the bounded history limit, **not** the prompt budget. `control_defaults.py` sets the schema-inclusive prompt budget to **96000 characters**. The measured all-groups schema alone does not exceed that default. No model token/billing inference follows from these character counts.
- Root explicitly challenged the coordinator's four-hour checkpoint gap. Application/source/tests were immediately committed as **`d198c37ee038e57e7cca4183b60eef0eaef6f1fc`** (60 files); staged Python/build paths were byte-compared with QA61 before commit. No deployment, application artifact or final audit acceptance follows from this checkpoint. Subsequent work must checkpoint completed bounded slices before beginning another scope; evidence/docs remain working drafts until reconciled.

## Artifact input isolation — QA62

- Before building, coordinator found `docker/app.Dockerfile.dockerignore` omitted new `tool_policy.py` and `turn_budget.py` even though the Dockerfile COPY list named them. Both exact allowlist entries were added.
- Existing constructor-probe subprocess inherited the parent interpreter's full `sys.path` through PYTHONPATH, permitting original-checkout imports that could mask missing copied modules. Its PYTHONPATH now names only the copied app; standard interpreter/site-packages initialization remains intact. No new test/helper definition.
- Independent Sol reviewed this three-line patch without a source-level blocker (`micro-artifact-inputs.md`). QA62 frozen tree **`25a027ede3ca81cf93dae194ccd61e7c979441dc`**: selected Ruff passed; `tests/test_bot_construction.py`: **4 passed**,7.05s, exit0, in the same network-none Git QA image. Actual candidate-image verification remains a separate gate; this does not retrofit artifact proof onto QA60.

## Candidate artifact and compact measurement recheck — QA63–65

- QA63 used inspected `scripts/build_for_human.sh` against the reverified UID1005/rootless engine `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`. Git archive source **`be28b8598215ff6a0c72d7c3160403f2425a61f0`** produced **`dame-curie-app:be28b85`**, immutable image **`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`**. Python base resolved to `python:3.14.4-slim-trixie@sha256:2ca02f32b4d9d893863367ce07ec1972819f476dd38d8612f2a9cb6a41cbb727`; existing apt/pip layers were cached. No checkout/private settings/container lifecycle change.
- A separate network-none/read-only image check compared **all56 copied source/config/tokenizer/plugin inputs** against Git blob IDs from that commit. All matched. Baked manifest and OCI revision label matched the full commit, branch `dev/phaseII_v2`, dirty=false.
- QA64 executed the **existing** `CONSTRUCTION_PROBE` literal from committed `tests/test_bot_construction.py` inside the actual image, not a checkout-mounted surrogate. The literal was extracted by stdlib AST inside the disposable container; no application import on the host and no new test/helper was authored. `/app` was the only added application import path. Its existing audit hook forbids network/subprocess creation and writes outside synthetic `/state`; constructor, plugin/memory initialization and close passed. No login/provider request, real configuration, private mounts or long-running service. Image generation/TTS/VC/RAG/autonomy were disabled for this construction case; this is not their live acceptance.
- QA65 repeated the QA61 catalog measurement on the **same frozen tree25763d… and same synthetic envelope**, omitting bulky name inventories so all scalar rows were visible. Every table row in `06-TOOL-INVENTORY.md` matched. No paid inference or tool execution. This verifies the recorded fixture measurements, not real Dirac's profile.
- Candidate artifact is built and source/construction-verified; **not deployed**, no temporary channel probe yet. Installed host operator identity/version remains to be reverified separately. Normal release/canonical/V1/publisher remain untouched.

## Temporary acceptance preparation — QA66

- Root corrected the coordinator's overbroad interpretation of the shared-embedding boundary: ordinary requests use shared computation while profiles retain separate stores; they are not shared-service mutation. Existing RAG usage is permitted. No new embedding isolation defect was discovered; no RAG-disable workaround or backend change is appropriate.
- Account/socket/engine and old temporary container freshly reverified:UID1005, engine`12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`, container`0b1ba5fd43d75319d4908ba01cf32dce6cf87c5df5b5a145c0540c1175cb4ef6`, old image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`, started2026-09-24T19:04:47.31718802Z, running. Local log retention is10m×3.
- Minimal private control/protocol metadata confirmed smoke channel`1550960386939817984`, operator root`1482143139828596916`, enabled smoke, requests=`requests`, status=`../smoke-status`, polling1s; reasoning=low, output cap12345, REMoff, autonomyoff, RAGon. Smoke channel is allowed, but the current global scope is not smoke-only. No credentials or private message content printed.
- Root-owned interpreter chain resolves to `/opt/python-3.14.4/bin/python3.14`; version3.14.4, service user is not a member of root's group. Installed shared `scripts/instance.py` and `scripts/log_filter.py` matched source and were not changed. Only temporary-specific `scripts/dirac.py`, `scripts/dirac_smoke.py`, and `smoke_protocol.py` were installed and byte-compared with reviewed source. Previous copies are private at `/var/backups/dame-curie-dirac/audit-acceptance-20260925T121644Z/`. Viewer modules and Screen untouched.
- QA66: pending smoke list empty; no accepted/running smoke records. Updated operator `status` returned exit0, config=ok, embedding_readiness=ok for the old image. This is an actual normal embedding probe, not metadata-only or complete RAG acceptance.
- Planned bounded live case: preserve controls/retained logs privately, stop the old temporary instance, scope only the candidate to the approved smoke channel, run one benign constant-response request (deadline180s), then restore original controls and old image. Keep reasoning low/cap12345/REMoff and existing RAG profile unchanged. This is temporary acceptance, not normal release. No candidate start or smoke request had occurred at this checkpoint.

## Bounded temporary acceptance and restoration — QA67–69

- Old instance stopped cleanly, exit0. Original controls and the old container's bounded retained log stream were copied opaquely into the root-only rollback directory above; raw logs were not displayed or inspected. The only candidate control delta was `allowed_channels=["1550960386939817984"]`. Low reasoning,12345 cap,REMoff,autonomyoff and existing RAG remained unchanged. Selected private image metadata: explicit quality=high; neither retired `hd_image` nor `image_generator` was disabled. No disable mapping needed for this observed temporary profile; canonical remains uninspected/held.
- QA67 started candidate image`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`, container`f6e068f1f43c9b108678ec848d2070b1f1f8ccf8354446a57d6ac29f8c16b201`, embedding_readiness=ok. A bounded startup-log selector emitted only timestamp/Discord identity. Its first attempt incorrectly matched logger`bot` (imported-module name), so returned no row/exit1. Source confirmed `getLogger(__name__)`; correcting the entrypoint selector to`__main__` verified identity**1504398705539944560**, log time14:22:50.041 local (+02:00). This was a coordinator observation error, not a failed login. Fresh smoke advisory state was running; advisory state alone does not establish liveness.
- Exactly one request: **`608cc14a42714fd58bafbf8084b09690`**, submitted**2026-09-25T12:25:29Z**, deadline180s, approved parent channel**1550960386939817984**, operator root**1482143139828596916**. Benign task asked for one `DAME_AUDIT_OK_be28b85` reply, no other tools/file access/settings/background work. Durable receipt became completed at**12:25:37Z**: returned=true, one delivered ID, no failure, no readback failures. This is a model-backed delivery observation, not proof of every requested internal tool path or all remediated behavior.
- QA68's first whole-wire equality assertion failed (51 characters instead of21), correctly retained as exit1. Source `response_observability.py::prepare_delivery/strip_footer` established the configured runtime footer contract. A read-only check of the **same request**, no retry/inference, found exact21-character marker body plus one29-character `-# ` footer ending in the reserved U+2063/U+2060/U+2063/U+2060 marker (and the separating newline). Exact body, footer shape/length, completed/returned, one delivery and zero readback failures all passed. Arbitrary extra text was not accepted; the protocol's `reply_verified=false` remains unchanged and is not a semantic-verdict field. The revised checker does not turn the initial failed assertion into a historical pass.
- Candidate stopped cleanly at**12:30:09.679684654Z**, exit0. Candidate retained logs/control snapshot were preserved privately, without printing contents. Field comparison found **only allowed_channels changed**. Original control bytes were restored exactly; derived `bot.env` SHA256 remained unchanged. No request or terminal receipt was deleted, avoiding replay.
- QA69 restored old image**`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`**, new container**`495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`**, started**2026-09-25T12:30:41.035310558Z**, running/embedding_readiness=ok. Whitelisted startup metadata verified the same Discord identity at14:30:45.780 local (+02:00). Original-control byte comparison and profile fingerprint passed after startup; low/12345/REMoff/autonomyoff confirmed; pending smoke list empty.
- **Acceptance result:** one bounded happy-path model/delivery/readback case passed under the actual footer contract; adverse cancellation, budget exhaustion, live image/voice/admin features and all provider transports were not exercised. **Candidate is not the current running image**. Three reviewed temporary-operator files remain installed; host viewer modules/Screen were not changed or reattached. No canonical/V1/publisher deployment, settings, model pull or shared-service lifecycle mutation; ordinary existing embedding API requests occurred as clarified by root.

## Review and acceptance limits

The Flash viewer implementation report is an author handoff, not a description of the final coordinator-integrated source. Coordinator removed its exception-based omission signaling, corrected fixture/API assumptions, extended static storage/coalescing handling, and retained the actual byte-gap fail-closed latch. Independent Luna reviewed the final viewer paths, including JSONL outer-span behavior and marker ordering, without a remaining viewer blocker; the earlier error-group absorption concern was retracted after tracing real record boundaries. Its separate plugin-name/alias mismatch was subsequently corrected and independently checked in `micro-plugin-precedence.md`, committed in `d198c37` and exercised by QA56/60; it was not mislabeled as an authorization bypass.

The independent image report retracted an incorrect claim that disabled-image refusal lacked executable coverage and downgraded an alleged schema contradiction to a missing empty-input clarification. Coordinator verified the actual existing cases. The process-evidence reviewer violated its explicit no-Python-execution assignment by running bytecode-metadata decoders; it disclosed that after challenge. **Interpreter-derived results from that review are excluded from accepted provenance evidence.** No application import or execution of decoded code was reported, but that does not retroactively authorize the method. Accepted Git inventory/counts were independently recollected and source-mapped as recorded in `07-PROCESS-DISPOSITIONS.md`; historical bytecode/stat provenance remains unknown. The rejected report preserves the deviation and disputed reasoning rather than erasing them.

Current evidence includes the full **safe** QA60 selection, integrated-core/narrowed corrections, candidate artifact/source/construction verification and one bounded live-Dirac happy-path case followed by restoration. It is not an exhaustive live feature/provider/cancellation matrix, proof of zero defects or normal release. Counts from overlapping selections must not be summed as distinct passing tests. The current restored identity/image is recorded in QA69; earlier runtime receipts remain historical. No V1/canonical/publisher or remote Git operation occurred.

## Final document consistency and handoff

- All52 auditor findings plus6 implementer-raised items carry explicit template dispositions, commit/evidence and deployment fields. Independent Luna evidence review and DeepSeek coverage/retirement review found stale current-state wording and missing explicit labels/ownership; source-budget summary anchoring was also clarified. Corrections committed in `ddd2b2a`, then narrowly rechecked with no remaining finding in those scopes. Original reports and reviewer addenda are preserved in `review-final-evidence.md` and `review-final-coverage.md`.
- Coordinator's final tail check also found this ledger's old concluding “no full-suite/artifact/live acceptance yet” paragraph and plugin/inventory pending claims, which no longer described QA60–69. Those current-state conclusions are corrected above; earlier failed/intermediate receipts are not rewritten as passes.
- Local Git comparison confirmed no tracked Python/JSON/tokenizer or application Docker/dependency/example-input change from candidate source`be28b85` through the response review checkpoint, and unchanged original audit00–04/child reports from their first explicit preservation commit`3754a8a`. No new application test/run follows documentation-only edits.
- Explicitly retained: deferred import-time dotenv redesign (C09), unknown historical provenance (P08/I05), disclosed SDK/TOCTOU/same-UID/ingress limits and held viewer/canonical operating gates. C28's no-retired-alias choice is an explicit source-contract push-back, not an alleged specific root instruction. Coordinator ownership, destinations and accepted-round-two retirement gate are in `../../TODO.md`; no evidence/ref/worktree/cache deletion follows this handoff.
