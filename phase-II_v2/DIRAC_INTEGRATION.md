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

Still pending: install the reviewed operator source; pin/start the private namespace relay; select the new image only for Dirac; run the ordinary bot with durable binds and the optional protocol; start the separate publisher watcher; exercise real model/tool/thread/site/RAG scenarios; verify HTTP script execution and restart persistence; leave a real Screen/logger handoff. Canonical bot/Ollama/pull remain held and the canonical image selector is unchanged.

Source-traced publisher availability caveat: watch reconciliation reuses stored remote site identities; an out-of-band remote site deletion can therefore leave repeated sync failures. The separate `--once` reclaim path has not yet been exercised for that failure. Normal initial root pinning is not evidence for this recovery case.

The relay is raw TCP, not an HTTP allowlist. Its Docker queries are read-only and mapped to the two service accounts, but forwarded traffic exposes the Ollama API on the private V2 bridge. No claim of explicit user acceptance of destructive model-management endpoints is made. Exercises must use the existing embedding model only and must not mutate V1 models, data, ports or containers. A V2 daemon network-namespace replacement requires relay restart; per-connection V1 container PID lookup follows ordinary V1 container recreation.
