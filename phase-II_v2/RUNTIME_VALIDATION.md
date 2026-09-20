# V2 runtime validation — temporary identity, isolated state

Status: **bounded nonvoice validation completed and passed** (2026-09-20). Actual text/command/native file/checkers/message paths and the documented offline memory/export paths passed within their limits. Earlier incomplete probes remain recorded. This supersedes earlier no-Discord-execution milestones only for the explicitly authorized isolated work below; it does not activate canonical Dame or establish whole-application/voice/RAG/replica acceptance.

## Authority and isolation

Root saved a temporary Discord credential directly in `/srv/dame-curie/config/bot.env`, then authorized bounded test traffic in guild `1504753066396618815`, channel `1550960386939817984`. Authentication established that it belongs to a different account than canonical Dame `1545541390392369165`. The first probe stopped before fetching the channel or sending. Root explicitly confirmed use of the different temporary account **in isolation**, with disposable state and no canonical identity change.

Coordinator-only operations re-resolve `dame-curie` UID/GID1005 and its private socket through the reviewed canonical operator. Engine ID remains `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`; selected source/image remains `734c050`, image ID `sha256:2e7887c30d10d2b1d491b16a4754f06386a13a440e874fb85f12d33f962d9dc0`. No V1, publisher/mirroring, remote publication, existing Screen or private database/history migration is authorized. RAG/Ollama/model-pull stay held pending separate scope.

The private preflight emitted only allowlisted facts: token present, regular private configuration owned by1005/mode0600, canonical identity/root owner declarations intact, RAG/autonomy/REM explicitly false, primary endpoint/model/auth present, staging=true and the same three created/never-started services. No credential value, prefix, length, fingerprint or private configuration dump was emitted.

All exercised helpers used the selected image, rootless V2 engine, read-only root filesystem, dropped capabilities, no-new-privileges, resource caps and no private mounts. Offline helpers used `--network none` and temporary scratch filesystems. Live helpers used the ownership-checked V2 outbound network and received the temporary credential—and, for scoped model turns, whitelisted provider configuration—through stdin, not Docker environment/arguments. Offline batches `bash-3`/`bash-4`/`bash-5` used synthetic placeholders only. Each ended helper was removed by its exact owned container ID. No repository tests were created, collected or run.

## Observed results

For `bash-8`/`bash-9`, UTC timestamps on live receipts are host collection times, not provider-server timestamps. Approximate durations come from the helper's monotonic counters. The separately identified Docker lifecycle timestamps come from the engine event metadata.

### Image imports — collected bash-545, exit0

- Python3.14.4; `discord.py-self==2.1.0`, `discord-ext-voice-recv==0.5.2a179`, PyNaCl1.5.0 and davey0.1.6.
- Actual Discord, voice extension, `voice_live`, PyNaCl and davey imports passed. `SpeakingState`, DM gateway hook, reader lookup patch and native Opus library were present.
- Actual `bot` import passed with voice enabled; `LiveSpeechSink` and the decoder patch were loaded. No bot entrypoint/login/provider request was invoked.
- This is stronger than package discovery, but not live voice transport acceptance.

### Discord transport — collected bash-546 and bash-547

-546 authenticated successfully, detected the canonical identity mismatch and stopped with no channel fetch/message. Its normal process exit was not a successful transport acceptance.

After root's explicit temporary-account confirmation,547 completed exit0. It verified both exact channel and guild, sent one synthetic message, fetched only that newly created message, verified its content/author, edited it and deleted it. All corresponding receipts and client closure were true; the owned helper was removed. No gateway, main bot, provider turn, private state or canonical service was started by this transport check.

### Local constructor, shell and audio — collected bash-548/549/551

`pip check` returned1 with exactly the known distribution complaint: voice-recv requires `discord-py`, which is not installed. The intentional self-fork supplies the `discord` namespace. No competing distribution, pin change or dependency installation was used to silence this. Actual compatibility observations are recorded separately; the packaging contract is not described as a clean pip check.

549 recorded successful actual `MaxwellBot()` construction with disposable data and a nonvoice baseline, an actual `ShellTool.execute()` write, local espeak→ffmpeg WAV synthesis, a3840-byte `FFmpegPCMAudio` frame, and synthetic stereo PCM→`LiveSpeechSink`→mono WAV delivery. TTS was stereo/16-bit/48kHz with82,027 frames; sink output was mono/16-bit/48kHz with20,160 frames, duration0.42s. The sink stopped and no other asyncio tasks remained after cleanup. No remote TTS, ASR, Discord or provider operation was performed.

Two controller mistakes prevented treating548/549 as clean whole-controller passes:548 tried to close an intentionally absent optional provider;549 expected Bash PWD to retain the HOME symlink spelling. The latter actually reported HOME `/home/dame-curie`, physical PWD `/state/shell` and successful writes—correct behavior, not an image defect. These are probe errors, not product fixes.

551 then completed exit0 with the corrected semantic shell check: HOME and physical PWD refer to the same directory, and the actual shell tool's write landed in the scratch shell root. It additionally exercised native Opus encode/decode (96-byte packet,3,840 decoded PCM bytes). Both PrivateCall and GroupCall expose `connect(*args, **kwargs)`; signature presence does not establish DM voice acceptance.

### Actual scoped bot startup — collected bash-554, incomplete interactive gate

The independently reviewed validation-local driver used the real `MaxwellBot` constructor, inherited `setup_hook`, Discord gateway and inherited `on_ready` (with inbox seeding skipped). Authentication was required to be noncanonical; the bot's gateway identity also had to match the identity verified immediately beforehand. The temporary identity override affected only that helper's environment/default prompt, not canonical files. Exact whitelisted provider settings, including configured headers/body/fallback/vision/retry behavior and unset/blank semantics, were supplied through stdin. Setup ran the normal provider initialization path; its return is not a separate claim that every `/models` request succeeded.

Receipts established construction, setup completion, gateway READY and one approved-channel ready notice. Root-only input was limited to exact `!help`, followed by one nonce-bearing plain mention after help completed. No qualifying help or directed input was accepted before the 125-second input window expired. Consequently no command response or logical model completion was exercised: both provider counters remained zero. This is **not a completed conversational smoke or evidence of a bot defect**; the observations do not distinguish absent input from input that failed the gate.

The process returned1 with the expected window `TimeoutError`, emitted `closed=true`, and its exact owned helper was removed. Off-scope sends, message-history GET attempts and application event-error counters were all zero. The235-second process hard limit was not reached. Canonical services were verified held before the probe and were not operated on by it.

Root later explained that no input arrived because root was AFK; the missing input is accounted for and is not treated as a bot defect. This historical timeout is retained and is not reclassified as a pass.

### Actual scoped text conversational acceptance - collected bash-2, exit0

Dating: the parent coordinator verified host UTC `2026-09-20T05:42:43Z` by `date` only. `bash-2` is Sept20 evidence; the historical `bash-545` through `bash-554` observations above are Sept19.

After a harness restart, root answered "Ready now", kept RAG held, authorized a bounded voice channel `1551103280422064201` in guild `1504753066396618815` but has **no microphone**; the text target `1550960386939817984` is unchanged. The reviewed, unchanged disposable text driver was rerun as the **new runtime job `bash-2`** - `bash-2` is a post-restart runtime job identifier and is distinct from the historical helper numbering above (`bash-545` through `bash-554`), which belongs to the pre-restart harness session. The frozen image, the canonical `734c050` source/image and the three held services were rechecked immediately before the run.

`bash-2` completed `exit0` with `passed=true`, `closed=true` and `probe_removed=true`. Receipts established: actual constructor, setup and READY all true; root `1482143139828596916`'s `!help` received, sent and handler completed; exactly one plain direct mention marker `CURIE_V2_TEXT_1` received; exactly one logical `generate_chat_completion` start **and** completion; `PROBE_OK` delivered; and handler completed before close. Three bot message creations total were observed (ready notice, help response, model reply). Counters for off-scope send attempts, message-history HTTP attempts and event errors were all zero, and no raw model, profile, provider or credential data was output. Root also supplied a screenshot and explicitly confirmed the test succeeded.

The whitelisted, real, existing provider configuration was again supplied through stdin with no private mounts, and the temporary identity override remained a per-process scratch prompt only - no canonical identity configuration changed. No production code fix and no image rebuild occurred. `bash-2`'s exact owned HelperID `68d4204da142e5fe18caa9abefcba6fb4aadbf7e156bfcb39a8228e1079983b0` was removed.

This is **scoped text conversational acceptance**. It is not whole-application, tools, voice, RAG or replica acceptance. No voice connection was made. Root subsequently removed voice testing and security-hardening fixes from this assignment: they are **not pending acceptance gates**, and no pre-existing voice/security behavior is to be patched as part of the surgical removal. Remaining work targets preserved nonvoice Discord capabilities.

### Nonvoice offline memory/file/plugin acceptance — collected bash-3, exit0

On Sept20, after root asked to continue nonvoice checks while away from Discord, a fresh network-none helper exercised actual image code with synthetic inputs only. Python3.14.4 and `MaxwellBot()` construction passed; no setup hook, Discord login/gateway or real provider call was invoked. The helper received no real credentials or private mounts; the coordinator did not read private `bot.env` for this batch.

| Surface | Observed receipt | Boundary |
| --- | --- | --- |
| Functional memory | User and assistant messages stored in order; system fixture skipped; read-back and a separate maintenance-mode connection to the same tmpfs SQLite matched; channel clear returned empty; embeddings disabled and non-NULL embedding count0 | Fresh tmpfs SQLite only; not RAG retrieval, REM or real-history acceptance |
| Registered file tool | Registered `send_file` produced correct5-byte text/base64 `discord.File` payloads, caption marker and URL-result contract | In-memory recording sink, not Discord delivery |
| Checkers plugin | Actual plugin loader/registry and follow-up result contracts; empty → started → active → owner-resigned → empty; start/state produced2 valid PNGs | PNG decode/verification, not visual review or live upload |
| Ownership | A different synthetic user could not resign the fixture game and produced no send; owning user could resign | Plugin ownership path only, not general Discord administration |
| Cleanup/isolation | All explicit shutdown steps returned; `closed=true`; exact helper removed; zero validation-label helpers remained; canonical bot/Ollama/pull still `created`, never started, restart=no | No production source changes, service activation or image rebuild |

HelperID `a36dbad89a21c25e6b81be2b7ee3e154869c979fed0ae19ce864058316e4dc91`; driver SHA-256 `afbd3ef5964848dd2b381e0c7747a88392ec6056c464c025585faf8823c63e23`. The account, socket, rootless engine/root and frozen image were rechecked under the operations lock; socket UID1005/GID427784/mode1660 were observed without repair. Container limit90 seconds, host attach limit110 seconds; no repository tests were created, collected or run. These are **synthetic method-level runtime checks**, not new live Discord acceptance.

The coordinator rejected two review suggestions: creating an unexpectedly missing pre-existing operations lock, and suppressing cleanup exceptions. Both would weaken the chosen acceptance boundary. The unchanged driver passed, including never-logged-in client closure.

### Nonvoice offline command/payload/export acceptance — collected bash-4, exit0

A second fresh network-none helper used the same frozen image and containment. Actual `_handle_command` produced the fenced `!version` response with Python3.14.4 and mention suppression, and `!jobs` produced the empty-manager response. The verified root ID passed the application's owner predicate; a synthetic nonadmin's `!prompt` was rejected with `not authorized`. No real administrator action or gateway author was involved.

`message_has_visible_payload` returned the expected matrix for empty, text, attachment-only, embed-only and forwarded-attachment fixtures. Registered `send_file` also read a synthetic20-byte file from `/state/data/exports/local.txt` and passed its exact bytes/name through the recording sink. This batch exercised the local export-safe file branch, not the shell-workspace export branch or actual upload.

All receipts, shutdown and removal passed. HelperID `99ad8ff5073b8dc0eb36afe2939f50a405fbc192e36b8e8dbbeeea3c9aac88b8`; driver SHA-256 `f3e0c0cfbc2103eded56b81aabc86212c2607d04b0531bb19bbcbcd3e9d17f21`. Zero validation helpers remained and all three canonical services were rechecked held.

Limits: `!version` response handling is accepted, not its checkout revision display—the driver did not assert a known Git field; frozen image inspection carries provenance. `!jobs` covered only an empty manager, not populated/guild-filtered lists or job execution. Offline drivers never ran `setup_hook`, so their written control files were not loaded; environment flags and the absence of setup/login, not those files, provided isolation. These remain method-level checks, not live gateway, model-selected native tools, media extraction or Discord permission acceptance.

### Direct-container shell → attachment bridge — collected bash-5, exit0

The third fresh network-none helper enabled only the local shell feature additionally. `/home/dame-curie` and the disposable `/state/shell` were verified as the same directory. Actual registered `ShellTool.execute` ran a harmless `printf` command, wrote a16-byte fixture, and delivered it through its `files=` branch. Registered `SendFileTool.execute` then read the same `/home/dame-curie/probe-shell.txt` path through the shell-workspace export branch and delivered identical bytes/name. Both deliveries reached the in-memory sink; the command/result markers and attachment count2 matched.

The normal per-tool taint check evaluated the untainted fixture; no confirmation gate was disabled. Synthetic `guild=None` intentionally selected the no-progress branch—this was not a real DM, permission exercise, native model-tool dispatch or live upload. Shell progress UI, failure/timeout/truncation branches and size limits were not exercised. The command timeout was10 seconds; helper/host deadlines remained90/110 seconds. No nested container, publisher/mirroring operation, real shell workspace or private mount was involved.

`closed=true`, helper removed, zero validation helpers remaining, and canonical bot/Ollama/pull rechecked held. HelperID `df0691f403a0306d80cad64aaccb5fa076291618d93090c04f12741aa6cd6635`; driver SHA-256 `01ee6e0c4096cf55a75dd1ac14c3aec345de29f7c28edcce819402defb8bca9a`. No production change or image rebuild was needed in any of the three new offline batches.

### Installed SDK attachment dispatch — source collected bash-6, exit0

A further network-none helper imported only the installed Discord SDK and copied its public `abc.py`, `http.py` and `message.py` for source inspection. No bot construction/login/provider call or private `bot.env` read occurred. HelperID `6fd2b678b7175b3293f578f06a5bf49981ea23703bdd3d4f50088aed9591ab3e` was removed; zero validation helpers remained and the three canonical services were again held.

The selected image's actual `Messageable.send` passes text and file parameters to `HTTPClient.send_message`; that method handles both JSON and multipart. `Message.reply` delegates to `channel.send`. There is no `HTTPClient.send_files` in this installed source. A review hypothesis claiming the attachment observer would be bypassed was therefore rejected; no speculative SDK wrapper was added. Source hashes: `abc.py`=`c7743a21f8d0cb96942a57f1f5ff5f9dfb451abd98e3a4ae4bef8aba4c380bfc`; `http.py`=`7ea2e3d961ba43781487de0df017e9dca7d6e6dc9a996fe46dcb12a87b966f4f`; `message.py`=`d73045bd467eebfe50f87950c687ab595151bc86b716a1b200b1859b1f4f6885`. This establishes the observation point, not live attachment acceptance.

### Live nonvoice command/tool check — collected bash-7, incomplete (exit1)

A separate disposable driver was used for root's `!version`, `!jobs`, then one directed native-tool turn intended to produce a fixed16-byte text attachment and a checkers start/PNG. It retains the authenticated temporary-identity override, real setup/gateway/dispatch, scratch state and provider configuration through stdin. Process-local observers call the actual class-qualified native-dispatch methods; only the two fixture-constrained tools may execute. Pre-call reservations cap logical provider calls at4 and message-creation calls at12; normal provider retries/fallbacks remain unchanged. Final acceptance follows explicit cleanup and requires both attachment receipts, the completed handler, final marker and zero scope/error counters.

The whole helper remains bounded to235 seconds, with60-second readiness and125-second interactive waits; the host attach process has a260-second timeout plus5-second kill grace. Root freshly selected **Ready now**; `bash-7` launched driver SHA-256 `9ec3970ba02b6ac2d62d61e1bd76beb5d84f355ed083693248a5181232b1b05e`. HelperID `fc0d6dfd55e8de63bfcbbb402f91e7b8dd1918e7b5bd8b7f8d449bfe7b59bcb3` reached actual setup/READY with the effective catalog exactly two tools. Root's `!version` and `!jobs` were each received, handled and delivered. The directed marker was received and one logical provider invocation started, but none completed before the shared125-second wait expired at the driver's `complete.wait()` gate. Native dispatch/tool executions, attachment receipts and final marker remained0/false; handler completion remainedfalse. Three bot messages were delivered (notice/version/jobs); scope/history/event-error counters remained0. The captured error is this harness-level `TimeoutError`, not an upstream HTTP status or provider error body.

All explicit shutdown steps returned (`closed=true`), the exact helper was removed, zero validation helpers remained and all three canonical services were rechecked held. Child and controller exited1, with one sanitized error; **the live command checks passed, but file/checkers/native-turn acceptance did not**. No removal regression or provider root cause is established by this outcome. Root subsequently clarified that the Gemini change was **V1 only** and V2 was untouched. Root identifies V2's configured model as DeepSeek Flash and supplied a matching OpenRouter request excerpt bearing `CURIE_V2_TOOLS_1` and human-input time `2026-09-20 08:13:37 UTC`; request arrival is corroborated, but no upstream response/status/error is established. No silent model switch, retry, production fix or new login is authorized by that report alone. The saved temporary credential was read for the authorized run, not cleared or rotated; credential lifecycle remains a handoff item.

### Follow-up diagnosis and probe corrections — before bash-8

Root supplied the matching request's input timestamp. A coordinator-only metadata lookup on the re-resolved V2 engine selected **only** the removed `bash-7` helper's container lifecycle events in UTC `08:08:37`–`08:18:37`, collected at `08:29:36 UTC`. It showed start `08:12:39.680180`, die `08:14:49.945193`, destroy `08:14:49.958046`; validation helpers remained0. Thus the `08:13:37` human request had **at most72.945 seconds until process death**, including pre-provider work and shutdown—not125 seconds of generation. Exact provider-entry and wait-expiry times were not captured.

Source `bot.py`/`providers.py`/`provider_telemetry.py` is unchanged between frozen source `734c050` and current HEAD. The helper's60-second AI timeout is per provider attempt; retry/backoff can extend one logical call beyond that. This is a possible explanation, not proof that any retry or specific upstream error occurred. The probe suppressed application logging, so it retained no upstream error body/status. No raw/private log lookup, new request, provider/configuration change or V1 operation was performed for this follow-up.

Root correctly identified contradictory wording in the probe's instruction: it requested file/checkers actions, then said `send_message` and “every other tool” were disabled. The two upload paths do not depend on the registered `send_message` tool, but the instruction was still conflicting. Root now requests `send_message` enabled. At that checkpoint, a **new** three-tool driver was prepared and source-reviewed, not yet executed, with positive instructions, separate60-second human-input/up-to150-second model waits inside the same235-second hard lifetime, and scalar-only per-attempt diagnostics selected inside the helper. The offered catalog is exactly `send_file`, `checkers_start`, `send_message`; limits remain4 logical generation starts/12 message creations, with1 file/1 game/up to2 message-tool executions. Nonempty reply hints and alternate recipients are refused before resolution. Diagnostic wrappers preserve actual provider methods and report status, attempt/time, byte count and exception class only; no raw logs, bodies, headers or endpoints are emitted. A separate finished counter distinguishes raised/returned calls from genuinely pending work. Draft SHA-256: driver `607d873814de5e5106c3bcbe287f6a50a2f86269ca23880c73608ae386e6e567`; controller `01a9d4d58e4b920faa0e50016ceb605ae5d057eb4941575b8b5693229727c642`. Source-only AST/compile and receipt-schema checks passed (43 fact fields/22 provider configuration keys); neither v2 driver nor controller had run at that checkpoint. The original failed driver and its hash remain evidence. No causal claim about the old timeout is made from this prompt correction.

### Three-tool window — collected bash-8, message tool passed; full fixture incomplete (exit1)

Fresh root readiness authorized driver `607d873…e567` with controller `01a9d4d…c642`; helperID `e07ba18ab16a964c3493bc089b0cfd392c7a44b031d1a6fd82d94acba16dd420`, created/attached around `09:02:33 UTC`. Actual setup/READY and the three-tool catalog passed. Root's screenshot shows the accepted mention contained the marker alone, not the file/checkers instruction; the bot asked what to test. This was a normal response to the supplied input, not a product failure.

The provider generation began `09:03:13.336804 UTC`, its first chat attempt returned HTTP200 headers in770ms, and the logical call completed at `09:03:15.459152` (about2.122s). Actual observed retry maximum5, per-attempt timeout60s; **one chat attempt ran**, with no diagnostic failure event. One native call/batch executed the registered `send_message` successfully and Discord returned its delivered message. Text recovery0; handler completed; provider started/completed/finished all1; pending-before-closefalse. Two total message creations (notice/reply); scope/history/event/fixture/routing/budget violations all0. Native message-tool acceptance therefore **passed**. File/game executions and attachment/final-marker receipts remained0/false because the supplied message did not request them; the complete fixture gate correctly exited1.

Explicit closure returned; exact helper removed at `09:03:18 UTC`, helpers0 and canonical3 rechecked held. No provider error was observed in this run. Successful calls need not invoke `_ProviderDiagnostics.finish_attempt`; absence of that optional diagnostic event is **not** evidence of a pending call. Pending status comes from the logical started/finished counters. This success does not retroactively identify the earlier `bash-7` timeout's cause.

### Full native file/game/message acceptance — collected bash-9, exit0

Root gave fresh readiness again with the **same unchanged** driver/controller and the full copyable three-action instruction. HelperID `5f57b3c7e8039e2be442fee4f58f25013418aadbcb8af51b908abe7ba5e061f2` used the rechecked frozen image, V2 account/engine/network and scratch-only containment. At `2026-09-20 09:07:50.009400 UTC`, the actual gateway accepted root's full directed request.

- Actual constructor/setup/READY and effective three-tool catalog passed.
- Two logical generation invocations completed: about1.021s and0.559s. Each used its first chat attempt and returned HTTP200 (headers395ms and355ms); retry maximum5/attempt timeout60s were observed, with no per-attempt failure event. The separate setup `/models` request also returned200; that metadata response alone is not an authentication claim.
- Three actual native tool calls ran in two batches: `send_file` and `checkers_start`, then `send_message`. Each executed exactly once through the real dispatcher/tool/plugin code. There was no text-recovered call or fixture substitution.
- Discord returned the fixed `curie-v2-probe.txt` attachment with size16 and `checkers_board.png` with positive size; both actual tool result contracts passed. `send_message` then delivered `CURIE_V2_TOOLS_OK`, and its result contract passed.
- Handler completion occurred at `09:07:55.286853 UTC`, about5.277s after the accepted request. The marker was the last message creation. Four creations total: notice, text file, checkers board, final marker.
- Provider started/completed/finished all2; pending-before-closefalse. Text recovery, off-scope/history/event/fixture/routing/duplicate/disallowed/budget violations all0.
- Explicit closure completed, then `closed` and `passed` receipts were emitted with all required flags true. Host exit0 and sanitized errors0. Exact helper removal, helpers0 and all three canonical services still held were verified at **09:07:55.616379 UTC**.

This establishes the selected **live native file delivery, checkers-start/board delivery and message-tool path**, not every plugin operation or canonical Dame's permissions. Earlier offline PNG decoding and shell-to-file checks remain distinct evidence; the live probe did not fetch attachment bytes back from Discord. No production source/configuration change, image rebuild, model switch or voice/security fix was needed. The earlier incomplete outcomes remain recorded; this pass does not retrospectively prove their cause.

## CAPTCHA clarification

Source-only re-review of integrated removal `9c09bab` established that the removed `HumanCaptchaServer` was **not Cloudflare Turnstile** and was not merely unused old code. It was a wired, default-enabled, lazily started human **hCaptcha** fallback: serve a challenge page, send a solve link, accept the submitted token and resume the Discord request. The no-local-web cut genuinely removed that manual fallback.

Outbound CapSolver/2captcha wiring remains. Both current adapters actually request hCaptcha; broader module prose does not establish implemented reCAPTCHA or Turnstile support. No challenge was deliberately triggered, no paid solver was exercised and no claim is made about the old listener's real reachability or prior success. No replacement server has been added.

## Startup containment identified before the bot probe

- The known `pip check` distribution complaint remains open: it is a packaging observation about the intentional `discord-py-self` fork, not a functional failure and not a claim that the environment is distribution-clean.
- Existing source review found that constructor/setup is not passive: scratch SQLite/plugin/job state is created; setup probes configured provider `/models`, loads memory/REM and attempts historical REM backfill before loading saved controls.
- Background maintenance also schedules a300-second LTM summary independently of the RAG feature flag. It was **not disabled** - the scoped probes avoided it by bounded runtime only: the historical `bash-554` exited at its125-second window with235-second hard limit, and `bash-2` closed on prompt completion, both inside `bash-554`'s300-second boundary. A bounded window is avoidance, not a disabled task; the unguarded task remains a real startup hazard for longer runs.
- Because constructor/setup is not passive, a real private DATA_DIR is inappropriate for isolated tests.

The initial `bash-554` probe retained the actual constructor/setup/gateway path and prepared, but did not exercise, the real model path; the `bash-2` retry subsequently exercised one logical model completion and its delivered reply. It required a newly created DATA_DIR, disabled history recovery, autonomy, REM, RAG, tools, context extraction and media; suppressed non-target application callbacks without replacing Discord's framework dispatch; skipped global inbox relationship seeding and plugin event dispatch locally; rejected message-history GETs and off-scope sends; and exited before240 seconds. These validation-local exclusions remain explicit limits on acceptance.

## Not yet established

Scoped conversational/command/native file/game/message acceptance is established by the distinct observations above; offline memory, plugin-state/ownership and shell-export checks retain their synthetic method-level boundary. No general administrator/guild-permission, populated job execution, complete gameplay, remote TTS/image generation/media extraction, RAG/REM/Ollama, replica, real-history migration or sustained-operation acceptance is claimed. **Live voice/DAVE/ASR and security-hardening fixes were expressly excluded by root; they are not pending gates for this completed assignment.** Historical local PCM/Opus observations remain local-only evidence, not a live voice pass. The known `pip check` distribution warning is not described as a clean environment.

## Final held state and credential handoff

Final metadata was collected by the successful `bash-9` controller at **2026-09-20 09:07:55.616379 UTC**, after exact helper removal. Validation-label helper count0; the following exact canonical containers each remained `created|0001-01-01T00:00:00Z|no` (never started, restart=no):

- bot: `2638ef3a2b5560062d83098db6a2fb098e69dd258d30b471fbf9473752078c1e`
- Ollama: `94d73cab8bf01b754f0cb46c938c31b75c3cd017d1afa4bffea6dfe77649cd65`
- model-pull: `570eacadb05e7be05aec4de35a6d9bf6637ff3f9a2514f10dd2b0b83037fea73`

Root explicitly selected **Keep for now** for the temporary Discord credential after completion. It remains saved in private `/srv/dame-curie/config/bot.env`; no clearing, rotation or revocation was performed. The declared identity remains canonical Dame while that credential is intentionally temporary/noncanonical. This is a validation arrangement, **not cutover-ready identity configuration**. No further private read was needed for the handoff. Future canonical activation, credential reconciliation, migration or RAG work requires its own assignment; no service start follows from this pass.

No demonstrated removal regression was found in the exercised paths. Earlier failed/incomplete probe outcomes remain failures/incomplete observations, not erased history or retroactive passes. The finished comparison HTML/report/template deliverables were left unchanged by this validation work.
