# dame-curie — agent contract

Root's current instructions override repository guidance. This is the Discord-only V2 workstream; protected V1 is functional, not an assumed incident to repair.

## Read first

Read `docs/STATUS.md` for source/artifact/runtime facts, `TODO.md` for remaining work, `docs/OPERATIONS.md` for account/engine and recovery boundaries, and `docs/DEVELOPMENT.md` / `docs/ARCHITECTURE.md` for validation and source contracts. README is the small current documentation index. Never inspect another checkout or upstream project to fill gaps.

## Current assignment — final production transition, 2026-10-02

Root delegated completion of the Queen's V1-to-V2 transition, isolated automated testing and bounded real inference, necessary source/worktree integration, production cutover and reviewed repository PRs. This is the final release, not another Phase-II scout. The coordinator makes ordinary engineering decisions and resolves defects; ask root only for genuinely necessary human intervention or a reserved policy decision. This current grant supersedes the earlier temporary-only hold, not the security-policy boundary below.

- **Never start V1, its old shell or its old stack, including for rollback.** Keep the stopped source and recovery state until V2 operation and isolated restore checks pass. Recover/retry V2 without reviving V1.
- Isolate Queen memory/context from Dirac and live test writes. Dirac is disposable and may be used only as an isolated temporary acceptance identity. Do not migrate its persona, memories, credentials or remote destinations to the Queen.
- Prepare and verify V2 without the Queen's Discord auth. Install that auth **only at the final cutover step**, after source, artifact, migration, provider and recovery gates. Preserve the Queen's supported shell tools and authored state, including classified state outside the old HOME mount.
- Coordinator authority includes required private state projection, rootless build/lifecycle, embedding model transfer and publisher handoff, followed by narrowly scoped retirement only after success and verified recovery. It does not authorize secret disclosure, broad permissions, unrelated services, new publication policy or restarting V1.
- Source children receive bounded files/worktrees and no private/runtime access unless separately and explicitly delegated a compliant envelope. Keep Python3.14, existing-test adaptation and isolated QA rules below.
- Root authorized preparing/publishing task-branch PRs to the verified Dame Curie repository. Never force-push, push to main or merge without a separate explicit grant. Preserve unrelated `reports/` and `root-review-reports` work.
- Standing PR protocol: use [.agents/skills/council-pr-babysitter/SKILL.md](.agents/skills/council-pr-babysitter/SKILL.md). The coordinator owns fixes/publication; independent **Luna/max and Sol/high** review each pinned PR head and monitor complete current-head CI. Both review final deltas; neither races edits or treats CI alone as correctness. This project-local skill was imported from root's explicitly authorized Codex skill folder; its Council observations are historical, not runtime authority here.

## Closed assignment and authority — 2026-09-25

Root authorized complete local audit remediation, independent review, coherent local commits, credential-free isolated QA and bounded automated acceptance in the prepared **temporary Dirac** channel. The later assignment narrowed corrections to `audit/20260924T210402Z-audit/08-ROUND2-REPORT.md` section5 and requires actual documentation consolidation/retirement this round. Root renamed the audit directory; preserve original report contents rather than rewriting them to match the new path.

Root: “we defer the decision to you about doing this live or not, yet or not yet.” On documentation: “make sure you do that at the end of this round because it's massive.” The current coordinator therefore decides whether/when this corrected candidate enters temporary normal use **after** required checks/review. Bounded acceptance alone is not that release decision. Before release, reverify identity/rollback readiness and minimum image/disable controls; measure stored server-prompt UTF-8 sizes without exposing text. Preserve low reasoning, output cap12,345 and REMoff unless an expressly documented acceptance case requires a reversible temporary-only override.

This grants no canonical/V1 activation, publisher/shared-service lifecycle change, remote Git operation, general private inspection, general chat injection or unbounded inference. Ordinary configured embedding requests are permitted: shared compute with separate profile stores is not itself an isolation blocker. Reasoning-only terminal/fallback and mandatory tool-reasoning policies remain unchanged pending root.

Source children have **no execution, runtime or private-read authority**. Coordinator-only exceptions above are not inherited by a new source task. Use existing response/validation ledgers; children return scoped chat findings, not a new report each. Preserve originals, failures, retractions, quarantine and unresolved evidence. Local commits and source review never independently authorize rollout.

**Outcome:** correction source`c2d6b0e`/`89fb851`, documentation retirement`f815857` and temporary-only promotion are recorded in`audit/20260924T210402Z-audit/09-CLOSURE.md`. Original controls were restored, the accepted image pinned, and final identity/readiness verified. The assignment is closed; the dated grant above is **not recurring permission** for later runtime/private operations. Future source tasks retain the defaults below.

## Approved design and protected resources

The consolidated design is in `docs/ARCHITECTURE.md`: remove dashboard/API/web hosting, nested shell, X/Telegram and companion/GF; run shell inside the outer bot container; retain Discord administration, autonomy, games/plugins, media/inbox and functional memory. The independent publisher, local authoring/image paths and remote mirroring remain protected. No replacement API/server, PM2 deployment, PHP/Perl installation or model-driven remote administration. Other feature cuts require root's assignment.

- V2 account: **`dame-curie`**, with its designated private rootless engine. Protected V1 account: **`maxwell-curie`**. Never substitute another account, a default/rootful engine or a guessed socket after failure. Re-resolve account/socket/engine before newly authorized runtime work.
- Canonical Dame: **1545541390392369165**; temporary Dirac: **1504398705539944560**; root/.normal.man: **1482143139828596916**. Do not infer trust from other inherited IDs.
- Separate users/engines do not prove separate mounts, credentials, data, ports or remote destinations. Multi-instance replication remains unaccepted. Same-UID shell access to writable controls is admin-equivalent where ordinary permissions allow it, not a separate sandbox.
- Canonical staging defaults to validated no-op `up`/`start`/`restart`. Final activation requires the current assignment's artifact, profile, data and recovery gates; an old temporary receipt does not clear them.

## Security-policy decisions belong to root

Ask root **before** introducing, expanding, removing or replacing security policy unless the current assignment explicitly authorizes that exact change. This includes content filters, credential-pattern detection, redaction, publication refusals, path exclusions and access restrictions. Explain the concrete behavior and operational impact; do not silently decide what root may publish or execute. Existing code is not proof that root approved its policy: flag inherited restrictions during relevant review and ask rather than automatically preserving, strengthening or removing them. Unapproved security-policy changes are subject to rejection and reversion.

The 2026-09-30 publisher incident is the regression example: harmless API documentation containing `Authorization: Bearer $OPENROUTER_API_KEY` triggered an inherited credential regexp and repeatedly stopped publication. Root explicitly authorized removing publisher content-based credential detection, not weakening SSH verification, destination ownership or filesystem protections. Keep that content filter removed; do not reintroduce it under another name or heuristic without root's explicit approval. Separate path/privacy redaction is not blanket permission for content filtering. V1 is out of scope for further work unless root explicitly reauthorizes it.

## Default boundaries

A source/documentation assignment permits inspection, **not** application imports, test collection/execution, installation, builds/pulls, provisioning, lifecycle changes, migrations, real login or deletion/pruning. Do not execute lifecycle/build scripts even for discovery or `--help`. Do not operate GNU Screen or activate `curie-readonly-debug` for this closure.

Do not read production/backup files, real environment files, databases, raw logs, credentials, process environments or mount contents without a specific compatible grant. Docker metadata permission is not private-content permission. Never dump raw inspect/environment/label collections. The current coordinator's narrowly scoped metadata/count/acceptance exceptions do not open broader access.

Work locally: no automatic fetch/push/PR or remote research. Do not amend others' history, prune refs/worktrees/caches, overwrite unrelated work, or stage root's `reports/` and `.agents/skills/root-review-reports/` material. Accepted history mapping does not prove physical cleanliness or ownership.

## Naming and configuration

Use **dame-curie** externally and `DAME_CURIE_*` for environment identifiers. Root's short URL segment **dame** is intentional. Neutral `.env`, `bot.env`, `.venv` retain their distinct roles; default commands use `!`, while instance-specific help uses its configured prefix.

Remote generation is explicitly configured OpenAI-compatible `OPENAI_*` / `OpenAICompatibleProvider`, not an assumed OpenAI account or local generation. Local Ollama serves embeddings; preserve its distinct service/model-pull names and settings. No old remote `OLLAMA_*` aliases exist. Preserve unset versus explicitly blank configuration, coupled selectors, credentials and storage consumers; no compatibility fallback may reconnect V2 to V1. Do not change persona/model, invent real endpoints or rename ordinary `max()`/`max_tokens` as a naming shortcut.

## Python, QA and review

Python **3.14** is mandatory. Never replace system Python or install project packages into its tree; operator and application interpreters have distinct roles. Preserve strict pins. Load `implement-tyranny` for authorized new Python and `implement-sanity` for actual-diff review, not wholesale legacy conversion. No unrequested helpers, broad exception handling, type escapes, guards or logging; legacy size is not an unrelated refactoring assignment.

**No new test files/functions.** Adapt existing cases/parameterization under this assignment. No host application import/collection or live-environment suite. Coordinator QA uses the recorded frozen credential-free image, synthetic configuration/state, no private mounts and network-none; real-image constructor probes have the same private/network boundary. `DAME_CURIE_ENV_FILE` redirection alone is not isolation: import-time dotenv behavior remains an accepted deferral, not a pending lazy-loading project.

Never run the historical live-provider version of `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas`. Only its reviewed synthetic replacement is admitted to isolated QA. `tests/test_streaming.py` and `tests/test_streaming_primary.py` remain excluded. Historical passing counts do not establish current acceptance or every provider/feature combination.

Use `read`/`glob`/`grep` for inspection. Verify complete control flow, distinguish observed facts from source intent and reports, and challenge the coordinator as well as children. Discover current routes before delegation; give bounded ownership, preserve concurrent edits and rotate author/reviewer roles. Commit reviewed coherent slices promptly with explicit paths and checked diffs.

## Retired documentation and recovery

Root authorized `legacy/` removal and accepted phase/internal-note retirement after surviving contracts were consolidated. Current guidance is the root index plus `docs/`; older notes are evidence, not operating authority. Before any phase deletion, preserve these immutable recovery references: `git show eb188ac:phase-II_v2/SESSION_LOG.md` retains the **verbatim prior human grant**, and the same revision retains `REDESIGN_PLAN.md`, `PROVISIONING.md`, `DOCKER_INVENTORY.md` and the other phase files. Later delegation is quoted above. Do not restore the old tree or follow its obsolete instructions.

C09 dotenv deferral is accepted. P08/I05 historical provenance is permanently unattributable; retain the quarantine, not an open cache-investigation task. Keep external originals and round-two evidence unchanged in the renamed audit bundle. Exact failed/passing QA snapshots and retirement destinations belong in its validation/closure records, not a new forest of agent notes.
