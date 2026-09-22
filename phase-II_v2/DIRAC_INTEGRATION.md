# Dirac end-to-end integration — 2026-09-22

## Authority and goal

Root granted autonomous implementation/review/integration, worktree-based Flash agents, small local commits and appropriately isolated retesting while AFK. The goal is a usable temporary Dirac V2 runtime, not canonical Dame credential cutover. The latest grant explicitly permits publisher/syncer work and SSH setup of a separate Dirac folder, useful real inference/tool requests, Discord test noise in guild `1504753066396618815` / channel `1550960386939817984` and its test threads, and labelled operator smoke injection. Do not impersonate a real human gateway message or fake success. Root will review Discord outputs.

Reusing the existing V1 Ollama embedding API is intentional. Do not copy V1 history/databases or start a duplicate V2 embedding model. Existing V1 publishing roots and unrelated remote services remain protected. Verify PHP/Perl/CGI capability at the intended destination; this is not an instruction to silently reinstate removed local site servers or alter shared global server configuration.

## Baseline and corrected history

- Source baseline: `7b4398c`, branch `dev/phaseII_v2`; frozen previously installed application source/image `734c050`.
- Prior selected Discord, command, file/game/message and offline memory/shell checks passed as documented in `RUNTIME_VALIDATION.md`. Preserve partial/failed probe history.
- After that evidence commit, a temporary long-running Dirac instance and Screen append-only logger ran. Root directly confirmed using both. Feature flags were subsequently enabled and RAG enabled, but the embedding request never passed after the shared upstream container disappeared.
- The later public launcher still restricted callbacks/history and forwarded only a limited provider key set. Enabled flags did not establish full feature configuration or coverage.
- Temporary data/config/sites/shell used tmpfs. Container recreation lost that state; the supervisor removed stopped containers. The namespace relay was also a separate transient process. These are test-runtime limitations, not demonstrated product regressions.
- Root now explains deliberately killing many processes while troubleshooting connectivity. The exit-137 observation is not evidence of OOM or a V2 defect. Do not infer current runtime state from the old IDs.
- The external handoff assumed canonical auth, local V2 Ollama/pull and CLI profiles that do not exist. Current assignment retains Dirac auth and shared embeddings; the runbook must match actual code.
- The five-minute LTM summarizer uses the main generation provider only after at least three eligible stored guild messages; fewer return zero silently. Absence of a count/warning is not failure. This does not certify sustained execution.

## Lane ownership

| Lane | Worktree / branch | Agent | Owned source |
| --- | --- | --- | --- |
| Shared RAG deployment/readiness | `dirac-shared-rag` / `work/dirac-shared-rag` | `1e0a90a6-33e0-4059-82a7-a54bdbf3e89a` | Compose, staging override, embedding readiness, instance wrapper, narrow related files/tests |
| Discord jobs/subagents/threads | `dirac-discord-jobs` / `work/dirac-discord-jobs` | `25cb5ae5-0d54-490d-9c3a-157a40fb6b27` | Bot/jobs/routing/tool schemas/prompts, narrow related tests |
| Rejected smoke prototype — not integrated | `dirac-smoke-runtime` / `work/dirac-smoke-runtime` | `cf3cdd0c-9c82-426f-8dc5-9fdb68c751d7` | Frozen at `4aae612`; retained failure evidence, not a deployment candidate |
| Replacement smoke protocol | `dirac-smoke-lean` / `work/dirac-smoke-lean` | `0cf5db20-769d-4a28-af05-8489c7bad404` | Protocol/runtime/operator modules, exact-input queue cancellation and focused tests |
| Separate publishing workflow | `dirac-publisher` / `work/dirac-publisher` | `ee9f9258-ea67-4461-b3f0-a4e2594ce32c` | Publisher source/config examples, narrow related tests/operator guidance |
| Durable operator lifecycle/relay | `dirac-runtime-ops` / `work/dirac-runtime-ops` | `27bc89e8-0192-4ff3-92d8-54b198e19b31` | New compact host CLI/relay and focused tests, no private access |
| Integration/runtime/SSH/evidence | main checkout | Coordinator | Packaging, private runtime operations, isolated checks, live smoke execution and shared ledgers |

All implementation children use `deepseek-official/deepseek-flash` at high effort. They have no runtime/private/SSH access. Parent reviews actual diffs and checks claims before integration; reports do not substitute for receipts.

## Planned acceptance

1. Source/compile/selected isolated synthetic checks, with empty synthetic config/state and no network or real credentials.
2. Verify complete effective Dirac configuration, durable isolated roots, supported startup and truthful protocol metadata.
3. Reach the configured shared embedding API from the actual runtime; one real embedding, then storage/retrieval/REM scenarios where feasible. No duplicate model pull.
4. Real model/tool smoke requests explicitly marked as operator harness tests: shell/file work, Discord thread/job delegation/status/results, and useful authoring tasks.
5. Mirror only Dirac-owned site/archive outputs into the separate remote destination; independently check URLs/content and executable capability without treating model claims as proof.
6. Record each failure, correction and rerun. Keep successful subsets distinct from unexercised features and infrastructure blockers.
7. Verify final bot/Screen/publisher/relay lifecycle and provide exact handoff. No promise of whole-application perfection.

## Progress

### Initial discovery — historical checkpoint

- 06:13 UTC: baseline and four new worktrees established; existing worktrees, reports and report skill left untouched.
- Source lanes launched. The initial smoke implementation was rejected for unnecessary protocol scaffolding and unreliable delivery correlation. The revised contract uses a real bot-written, explicitly labelled notice, a distinct configured operator permission actor, and a ContextVar-backed observer of actual turn deliveries; independent scenario verification remains necessary.
- Fresh coordinator inventory: both engine IDs/account mappings match the baseline; V2's canonical bot/Ollama/pull remain created, never started. Compose is 2.39.4. V1 shared Ollama is now `35f75347e35636c2b7af8feed021f562821771775264b7b42d0b1486d74c29bb`, healthy, with no published port. The former IDs/relay are not current. Plan: private V2 bridge gateway relay into the current V1 Ollama namespace, without recreating V1 or opening a host/LAN port.
- Existing publisher configuration and matching strict-known-host SSH access were verified coordinator-only. The proposed Dirac remote sibling was absent; no remote write has occurred yet. Remote `python3`, `rsync`, `php`, `perl`, and `apache2ctl` binaries exist; that does not establish HTTP script execution. Dirac's site root and image archive will both be beneath its own new subtree, outside both existing V1 destinations.
- Jobs agent disclosed reading unapproved SDK copies, retracted the resulting false `Message`-has-no-slots claim, and rechecked the load-bearing facts against the approved frozen SDK source. Shared-RAG agent also used an unapproved temporary dependency environment for a YAML parse; that is not an accepted project-interpreter check. Coordinator acceptance will use actual pinned image/source and isolated tests.
- Shared-RAG and job diffs have independent Flash source reviewers. Deployment-mode process-environment ownership is intentional, not a bot.env precedence bug; missing networking/image rebuild are integration prerequisites, not five new code defects. Actual Compose merging and runtime probes were pending at this checkpoint.

### Integrated source and pre-activation acceptance

Reviewed production/test source is `1984a26`. All accepted lanes are integrated; the rejected `4aae612` prototype is not. New image packaging explicitly includes `dirac_runtime.py` and `smoke_protocol.py` in both the COPY list and Dockerfile-specific context allowlist.

- Jobs: exact SDK thread creation verified; task-local recursion guard replaces an invalid message marker. Parent-channel allowance covers real threads without introducing category inheritance. A blocked parent cannot grant a *new inherited* allowance; an existing explicit thread allowance retains its old meaning.
- Smoke: one immutable request and one combined record; real labelled notice, configured operator permission actor, exact-input queue cancellation, correlated target-channel delivery IDs, bounded deadline/cleanup/readback. Terminal outcomes are written before optional readback; unreadable/deleted replies do not erase real delivery evidence. Detached jobs are not attributed to the spawning turn. Other-channel output needs separate scenario verification. The ledger must be retained alongside requests; deleting it can re-arm old requests.
- The replacement was independently audited by Flash agent `125a5c09-4887-4af9-b60f-4241f7a80e0c`. Parent review also caught a false claim that the terminal outcome had already been persisted before readback. The corrected implementation is larger than the original target (1,105 production lines across three files); that is recorded, not disguised as a lean 500-line implementation.
- The held image's actual `discord.py-self==2.1.0` SDK was copied read-only for source verification. Its client wires the same HTTP object into connection state and implements `wait_until_ready`. An isolated actual Client construction independently confirmed both facts without login/network. Text and multipart `send_message` return dictionaries, not Message objects.
- Readiness diagnostics now cover HTTP protocol errors as well as URL/config/transport failures without echoing their possibly credential-bearing messages. Unexpected programming errors remain visible.

#### Isolated validation receipts — failures retained

QA image `dame-curie-dirac-qa:20260922`, ID `sha256:a81175b66e37c3aabcb2d6f92e087af49974126e87e60064bbfd890695383792`, derives from the frozen app image. It adds only isolated QA tools: pytest 9.0.2, PyYAML 6.0.3, Ruff 0.15.7 and rsync/SSH client. Python is 3.14.4. Tests receive a Git archive, synthetic dotenv/state and network=none; no real configuration, database, credential, Docker socket or host workspace mount. Loopback fixture servers are permitted inside that network namespace. The unsafe live-config tool-progress test is excluded.

| Run | Observation | Correction / separate rerun |
| --- | --- | --- |
| `bash-15` | QA build failed: Buildx tried to create `/nonexistent` client metadata | Empty private writable client directory; `bash-16` built successfully |
| `bash-17` | 51 passed, three shell-fixture failures | QA `/tmp` was verified noexec; only synthetic fixture storage was made executable |
| `bash-18` | 54 shared-RAG/deployment checks passed | No product change was needed for the noexec fixture issue |
| `bash-19` | 208 jobs/observability/queue/publisher checks and 28 subtests passed | Scope only, not live Discord acceptance |
| `bash-20` | 309 passed, seven failed, 28 subtests passed | Fixed the operator's computed-RAG return contract and six faulty fixtures; production F checks passed |
| `bash-21` | 315 passed, one faulty fixture remained, 28 subtests passed | Fixture called `start()` but expected `main()`'s final print; parent corrected return/stderr assertions |
| `bash-22` | **316 passed, 28 subtests passed**, 35.13s, exit0 | New production modules and Dirac tests also passed Ruff F checks; not a whole-repository lint/test claim |

The real Compose 2.39.4 renderer passed both external variants. Standard mode defaults to bot only; staged mode defaults to no active service and activates only bot with `discord-activation`. Dependencies are removed, the injected local URL is null/unset, and local embedding services require the explicit `local-embeddings` profile. Earlier probe mistakes (missing synthetic INSTANCE_DIR, then assuming staged bot was active by default) failed honestly and were corrected without product edits. No Compose service was started.

#### Private preparation and publication pinning

Coordinator-only preparation verified the saved token's temporary Dirac identity through `/users/@me` (no Gateway session). `/srv/dame-curie/dirac` now contains isolated private config/prompts, data, shell, sites, smoke request/result roots and publisher staging/state/config. Derived `bot.env` copies the complete original file and appends only temporary identity/path/feature overrides; every declared OPENAI field was compared unchanged. Canonical config bytes and canonical identity declaration remain unchanged. No old tmpfs personality is claimed recovered.

The new remote `dirac` subtree was created only after confirming absence. Its site root has identity `2314:10737508354`; the independent nested image archive has identity `2314:15032761234`. Existing V1 roots retained identities `2314:17179884426` and `2314:40802602595`. SSH key/known-host files are private regular copies owned by dame-curie, not shared links. The existing unchanged publisher's `--once` succeeded against this configuration and persisted exactly the two new root pins with zero sites. This proves setup/SSH/pinning, not HTML publication or PHP/CGI execution.

#### Build and remaining activation gate

`bash-23` built `dame-curie-app:1984a26`, ID `sha256:c5d049e2dc9dd70aeed2ad6f39fbb876c12db7d278c22b861a8edced41ac9bea`, from the committed archive. Dependencies reused the existing pinned layers. Build succeeded; it did not install source, change selectors, start a bot or activate a service.

At that pre-activation checkpoint, still pending: install the reviewed operator source; pin/start the private namespace relay; select the new image only for Dirac; run the ordinary bot with durable binds and the optional protocol; start the separate publisher watcher; exercise real model/tool/thread/site/RAG scenarios; verify HTTP script execution and restart persistence; leave a real Screen/logger handoff. Canonical bot/Ollama/pull remain held and the canonical image selector is unchanged.

Source-traced publisher availability caveat: watch reconciliation reuses stored remote site identities; an out-of-band remote site deletion can therefore leave repeated sync failures. The separate `--once` reclaim path has not yet been exercised for that failure. Normal initial root pinning is not evidence for this recovery case.

The relay is raw TCP, not an HTTP allowlist. Its Docker queries are read-only and mapped to the two service accounts, but forwarded traffic exposes the Ollama API on the private V2 bridge. No claim of explicit user acceptance of destructive model-management endpoints is made. Exercises must use the existing embedding model only and must not mutate V1 models, data, ports or containers. A V2 daemon network-namespace replacement requires relay restart; per-connection V1 container PID lookup follows ordinary V1 container recreation.

### Live activation and first acceptance — 08:15–09:06 UTC

**Temporary Dirac is now running; canonical Dame bot/Ollama/pull are still held.** Fresh inventory verified both engine IDs, only the three Created canonical V2 containers, and the same healthy V1 Ollama before rollout.

#### Rollout failures, corrections and receipts

1. Source archive `1984a26` was staged with a copy of the existing operator venv. The import gate failed because that minimal venv did not contain python-dotenv; the original installation was not exchanged at that point. Installing exactly `python-dotenv==1.2.3` (the existing image lock) into the *staged operator venv* passed under Python3.14.4. The new archive was then installed at `/opt/dame-curie`; `/opt/dame-curie-pre-dirac-734c050` retains the prior source and venv. Host system Python was not modified.
2. Actual root CLI `dirac.py status` failed with exit2: the reused `service_account()` re-exec hardcoded `instance.py`. Patch `7070c01` gives it an explicit entrypoint and passes Dirac's own script; unchanged canonical/logging dispatch and the new path passed **36 isolated checks** at `380ebe8`. The parent also corrected the fake exec fixture to model a non-returning exec. The two corrected operator files and lane doc were installed; bot image remains `1984a26`, since this patch is host-only. Subsequent actual root `status` returned the expected absent-container JSON with exit1, not an argparse error.
3. New `dirac-relay.service` and `dirac-publisher.service` were started (not enabled for boot). Relay override pins both observed engine IDs. A real embedding from the new app image returned one finite, nonzero 1,024-dimensional vector; before/after `/api/tags` matched and contained only `qwen3-embedding:0.6b`. No bot/config/state mount was given to that probe.
4. First bot launch `bash-25`, container `ccb09615d78aa15b07c50dcfddf2f1bc3e12ffcd009a099f6fe612a5d2a189f6`, passed embedding readiness but then exited1, not OOM. Missing external `personality.txt` caused PromptStorageError. This was the coordinator's incomplete initialization, not a demonstrated prompt-store defect. Its bounded startup log was retained privately before replacement. New public seed `DIRAC_TEST_PERSONALITY.txt` explicitly says the previous tmpfs prompt was not recovered; only that new test personality was installed into Dirac's writable prompts root.
5. Explicit `start --replace` (`bash-26`) printed the old exited-state evidence to stderr before removal, then started container **`7fb28aacad9b396f668ea0b90ca3a2afcf19e0e6e62b2162f4a65781e8b1ee34`** at `2026-09-22T08:33:26.873249295Z`. Image is `sha256:c5d049e2dc9dd70aeed2ad6f39fbb876c12db7d278c22b861a8edced41ac9bea`. Independent bounded log inspection confirmed actual setup completion and Gateway-ready identity **1504398705539944560**, with no startup traceback.
6. Actual seven bind mounts matched the private Dirac roots, including config RO / nested prompts RW and smoke requests RO / status RW. Relay network-namespace inode equals the live V2 daemon's and differs from the host's. Host TCP port11434 has no listener. This is an observed namespace boundary, not an Ollama HTTP-method filter.

#### Real smoke ledger

| Request / scenario | Observed result | Independent verification |
| --- | --- | --- |
| `b943d9f1303f40b6b0ce6b76b00bdd1a` — ordinary shell | Completed; notice `1551874647946043465`, reply `1551874746000347177`; explicitly identified itself as a harness smoke test | `/srv/dame-curie/dirac/shell/dirac-smoke/first.txt` exactly equals `DIRAC-LIVE-20260922-8f29a6` plus newline; actual reply reports Python3.14.4 and no anomaly beyond the expected HOME/cwd distinction |
| `11283ba4001a4445b61b099a1835576b` — site worker from parent | Completed acknowledgement `1551876070381195326`; actual job `c927c30f`, requested main/configured model, done | Actual Discord thread `1551875915644932137`, owner1504398705539944560, parent1550960386939817984, public type11; bot progress/result message IDs fetched independently; local and remote files checked below |
| `bb525036ac044d9fa9d7e516d6a3f570` — status self-diagnosis | **Timeout**, no target-channel delivery, returned=false; notice `1551877164549279746`; only that input cancelled | This did not fail the completed site job. It ran two shell calls and three message searches. One real provider response took101s. The coordinator had imprecisely requested a native job-status tool: source actually exposes spawn_background plus the human `!job` command. No application patch is claimed from this timeout |
| `09e120f6ca614e5eaf8e7c05016e8554` — conversational turn inside first job thread | Completed; notice `1551880035319676990`, reply `1551880074733682699`; actual second job `0df54176`, done | Exact `DIRAC-THREAD-20260922-613f` plus newline in `from-thread.txt`. Second job source is first thread; new standalone sibling `1551880062251442216` was independently fetched and has the approved parent, temporary bot owner and public type11. This exercises inherited channel permission and fixes the thread-origin routing case |
| `58f492c47390487289bc8249671d1455` — separate corrected status rerun | Protocol completed with reply `1551882348617011282`, but **scenario refused by the taint gate**; notice `1551882189229137921` | Dirac explicitly reports no fresh read: automatic web results tainted the turn before its one shell call. The guard stays enabled; no synthetic confirmation or alternate execution is counted as a passing rerun. Source tracing of the automatic search trigger is in progress |

The protocol's `reply_verified=false` deliberately does not certify model claims. Optional `reply_readback` records readback problems; an empty list with returned text is not a readback failure. Scenario verification above is a separate coordinator result.

#### Real publication and execution

The live publisher watched the worker-authored site at `/state/sites/dirac-smoke`. Independent HTTPS GETs returned:

- `https://redroom.zombiedawn.net/dirac/sites/dirac-smoke/index.html`: HTTP200, HTML, **5,434 bytes exactly matching the local file**.
- `probe.php`: HTTP200, exactly `DIRAC-PHP-72cda` plus newline (16 bytes), not PHP source.
- `probe.cgi`: HTTP200 text/plain, exactly `DIRAC-CGI-72cda` plus newline (16 bytes), not Perl source.
- `probe.pl`: HTTP200 text/plain, exactly `DIRAC-PERL-72cda` plus newline (17 bytes), not Perl source.

Both Perl probes were executable locally. **PHP, CGI and Perl execution genuinely passed at this destination.** No per-site `.htaccess`, global server change, interpreter installation or local web server was needed. Publication used the operator-managed SSH service. The page's interactive click behavior has not yet been browser-tested. Later exact source inspection confirmed the three executable probes contain only constant print/echo statements, with no input or environment/filesystem access. That source inspection followed the first HTTP probe; future executable probes must be inspected before fetching them.

#### Memory and viewer observations

Read-only metadata from Dirac's own `dame-curie-rag.db` showed 20 bot_output, 7 ltm, 26 message and 3 shared_context rows; every stored vector length was 4,096 bytes. One independently decoded sample was finite/nonzero and 1,024-dimensional. This establishes actual bot memory/vector writes and LTM activity, beyond the embedding health probe. It does not yet certify restart persistence, semantic recall quality or complete REM coverage.

A fresh disposable GNU Screen logger was opened, sent `q`, and verified gone while Dirac remained running with the same container. Persistent viewer **`dirac-v2`** was then launched and its window verified. Attach as codexy with `screen -r dirac-v2`; `q` exits that viewer, not the bot. The earlier attached `dame_curie` and every unrelated Screen session were left untouched.

Still to verify before final acceptance: explain the status rerun's automatic-web/taint refusal without disabling the safeguard; selected media/game handling; memory recall/REM details; graceful restart and persistence/no-replay; final live inventory and Screen handoff. The publisher's out-of-band deletion recovery caveat remains distinct from the passing initial publication scenario.

### Automatic-search correction ready — not deployed yet

Independent Flash source tracing identified the status refusal's trigger: `_needs_up_to_date_info()` combined `model` in the requested JSON field list with `new` in a different sentence saying **no new jobs**. The automatic pre-generation search marks the current message tainted before its search completes. RAG recall is not a taint writer; neither is taint inherited from the earlier timed-out message. The shell gate correctly refused a tainted turn without a real one-shot confirmation.

Patch `c0ea9d8` changes only the broad AI-topic/recency branch to require the two signals in the same punctuation-delimited sentence. Explicit search intent and current-event phrases are unchanged. Neither taint protection, its configuration switch nor confirmation behavior was changed. A single sentence mixing unrelated signals can still produce a false positive; this is a narrow correction, not a semantic intent classifier. Parent follow-up `9a3fa43` tests the actual `compose_notice()` output instead of a copied header.

`bash-27` passed **351 tests plus 28 subtests** in 35.53s on the fully integrated tree, including the web-search regressions, existing taint-gate checks and root/logging re-exec cases. Selected Ruff F checks passed. `bash-28` built **`dame-curie-app:9a3fa43`**, ID **`sha256:077db691648c0e98af7a4d0c54cd3b4c240d11018b140da3666ff04b1ad2147c`**. At this checkpoint, the image had not replaced the running `1984a26` container. The next step was controlled replacement and an identical-task rerun, preserving both unsuccessful receipts.

### Replacement and human test-channel update

The old container stopped cleanly with exit 0, OOM=false, at 09:31:51 UTC; its log and the prior installed source/venv were retained privately. New container `6036186ac04afb39cb7db2a32ef0bea304dbb2c36799ce0a607dbc0244d14f88` runs the tested `9a3fa43` image and independently reached Gateway ready as temporary Dirac. All eight snapshotted files, both completed job records, all 65 prior vector rows and all five terminal smoke records survived; the receipts were byte-equivalent as parsed records and were not replayed. Canonical config and deployment selector hashes stayed unchanged.

The identical status task now passed as new request `7e00c2cfd65d4f0bae0d0a25ff2ce19a`, reply `1551889680293826653`, returning both actual persisted job records without a taint refusal. Both previous unsuccessful scenarios remain recorded. A real checkers sequence also produced three independently retrieved and visually inspected PNG boards; detailed game/REM/recall evidence will follow in the final acceptance checkpoint.

At root's direct request (applied at 10:01 UTC), **group DM `1545158306404892753`** was added alongside existing allowed parent `1550960386939817984`. Because Discord identifies it as type 3, `reply_groups` was also enabled; ordinary private-DM replies remain disabled, and the whitelist remains restricted to these two IDs plus the existing inherited-thread behavior. No block/solo lock conflicts existed. A private pre-change control backup was retained. The same container hot-loaded the final change at **10:02:42.388343301 UTC**, with no restart. This enables root's real testing in that group; the operator smoke receiver remains scoped to its original guild test parent and owned threads.

### Final scoped acceptance — 2026-09-22

**Handoff: `DIRAC_HANDOFF.md`.** This closes the temporary-runtime integration objective, not canonical cutover or exhaustive application/security acceptance.

- **Game/media request `1269cb115250482e8d319ef92c8b76bb`:** notice `1551889939170332713`; actual PNG messages `1551889957323415652`, `1551889969243492364`, `1551889977921503342`; fixture resignation `1551890140006326283`; summary `1551890170121560125`. Independently fetched PNGs were 9,300 / 9,816 / 9,816 bytes, all 576×576. Visual inspection confirmed red c3-d4 and black b6-c5; the latter two boards were byte-identical. Native state reported Red to move and two moves played. No gameplay or image-rendering failure was observed. Legacy Maxwell labels and an acknowledgement describing the intermediate Black turn remain; root/normalMan attribution is the deliberate permission actor, not a forged human action. FEN/expanded tool-state expectations from the model were not invented as new requirements.
- **Recall request `f2e2d0bb5fa0412c93db87c90dc57a6f`:** notice `1551895379031756861`, reply `1551895435814244363`. After replacement, in the other job thread, Dirac returned exact `DIRAC-PHP-72cda` without that answer in the request. It attributed this to retained facts, not a fresh endpoint check. Independent bounded logs for09:58:10–09:58:26 show provider tool counts `[0,1]` and only `send_message` dispatched. The initial coordinator assertion of literally zero tools was too strict: delivery itself used a tool, but no file/search/fetch tool ran. This establishes retained-context usability, not isolation of a particular semantic-retrieval algorithm.
- **REM:** eight persisted run records were present at the final bounded observation. The latest timestamp was10:02:58.952063 UTC, with two LTM additions and one shared-context addition. `turns_used=0` is hardcoded even on the real provider/audit path (`rem.py:390–414`); it is not evidence of zero inference. No raw audits or private messages were exposed.
- **Browser publication:** `bash-31` ran isolated Chromium from the frozen app image, without private mounts or a published port. It navigated the actual remote HTML, clicked the actual button three times and observed count0→3, status `3 signals relayed.`, and no horizontal overflow at780×493. The downloaded page source was inspected before browser execution. A real screenshot was inspected; this was independent browser verification, not a fabricated Dirac tool result. No application/site server was started.
- **Final inventory:** mapped engine IDs matched; canonical bot/Ollama/pull remained Created, temporary Dirac remained running on `9a3fa43` with restart=no, and the same V1 Ollama remained healthy. Relay and publisher were active but boot-disabled. Relay namespace matched the live V2 daemon and differed from the host; host11434 remained unbound. Both remote Dirac root device/inode identities still matched their original pins. The recreated `dirac-v2` Screen window was verified.
- **Observer failures retained:** a single-message REST probe returned403; inspection of the actual self-SDK showed its supported readback uses history `around=<id>&limit=1`. That route and an explicit honest HTTP client User-Agent retrieved the actual attachments; default urllib requests had also returned403. No credential/header spoofing or bot-side patch was used. A Go inventory template initially failed on absent `State.Health`; a missing-key-safe formatter fixed the observation, not a service defect.
- **Root's subsequent archive report:** live `max_image_size_mb=10` yields10,485,760 bytes. The media extractor applies this to every non-text attachment, including the reported16,220,247-byte `.7z`; the empty-media fallback then wrongly suggests `see_image`. At diagnosis, no limit adjustment, archive extraction or source repair was silently included in acceptance. Root subsequently explicitly requested a 20 MB allowance. The coordinator atomically set `max_image_size_mb=20` (20,971,520 bytes) and observed live reload at10:24:13.562281263 UTC in the same running container, preserving the whitelist and other controls. The reported archive is below that size guard now; its media/archive classification is still unsupported. Root requested a source-based limits document for comparison with another bot; a separate Flash documentation worktree is auditing active caps. Discord's [current attachment FAQ](https://support.discord.com/hc/en-us/articles/25444343291031-File-Attachments-FAQ) states10 MB for non-Nitro, which is not presented as proof of this account/channel's observed allowance; root's explicit20 MiB setting is retained. No guessed500 MB aggregate limit was added.

Remaining limits are explicit in the handoff: full-API rather than endpoint-filtered embedding relay; no boot/crash recovery claim; source-traced publisher out-of-band deletion recovery caveat; unfinished jobs cancelled rather than resumed; durable smoke records must not be deleted while retaining requests; residual classifier/game-label issues; archive routing; no voice/exhaustive-feature/sustained-load certification. The configured inference routes and safeguards were preserved. No remote Git publication occurred.
