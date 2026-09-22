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
| Honest smoke protocol/runtime entry | `dirac-smoke-runtime` / `work/dirac-smoke-runtime` | `cf3cdd0c-9c82-426f-8dc5-9fdb68c751d7` | New protocol/runtime/operator modules and focused tests; no competing bot.py edits |
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

- 06:13 UTC: baseline and four new worktrees established; existing worktrees, reports and report skill left untouched.
- Source lanes launched. The initial smoke implementation was rejected for unnecessary protocol scaffolding and unreliable delivery correlation. The revised contract uses a real bot-written, explicitly labelled notice, a distinct configured operator permission actor, and a ContextVar-backed observer of actual turn deliveries; independent scenario verification remains necessary.
- Fresh coordinator inventory: both engine IDs/account mappings match the baseline; V2's canonical bot/Ollama/pull remain created, never started. Compose is 2.39.4. V1 shared Ollama is now `35f75347e35636c2b7af8feed021f562821771775264b7b42d0b1486d74c29bb`, healthy, with no published port. The former IDs/relay are not current. Plan: private V2 bridge gateway relay into the current V1 Ollama namespace, without recreating V1 or opening a host/LAN port.
- Existing publisher configuration and matching strict-known-host SSH access were verified coordinator-only. The proposed Dirac remote sibling was absent; no remote write has occurred yet. Remote `python3`, `rsync`, `php`, `perl`, and `apache2ctl` binaries exist; that does not establish HTTP script execution. Dirac's site root and image archive will both be beneath its own new subtree, outside both existing V1 destinations.
- Jobs agent disclosed reading unapproved SDK copies, retracted the resulting false `Message`-has-no-slots claim, and rechecked the load-bearing facts against the approved frozen SDK source. Shared-RAG agent also used an unapproved temporary dependency environment for a YAML parse; that is not an accepted project-interpreter check. Coordinator acceptance will use actual pinned image/source and isolated tests.
- Shared-RAG and job diffs have independent Flash source reviewers. Deployment-mode process-environment ownership is intentional, not a bot.env precedence bug; missing networking/image rebuild are integration prerequisites, not five new code defects. Actual Compose merging and runtime probes are still pending.
