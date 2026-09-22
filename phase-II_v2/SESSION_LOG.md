# Phase II session ledger

## 2026-09-22 — autonomous Dirac integration grant

Root requested a few hours of independent work: proper review, Flash implementation agents in worktrees, incremental local commits, real useful model/tool tests, Discord subagent/thread functionality, and a separate Dirac remote publishing folder using the available SSH arrangement. Tests must identify themselves as harness smoke tests authorized by root, not human Discord messages; model self-diagnosis is evidence to check, not acceptance by itself. Useful billing against the existing configured endpoint is authorized; endpoint/vendor changes and wasteful token burning are not goals.

Temporary Dirac auth stays. Shared V1 Ollama is intentional, but V1 memory/publishing destinations are not to be reused. Root explained deliberately killing processes during connectivity trouble; the earlier exit137 does not establish OOM or product failure. No automatic restart followed those events.

No `TODO.md` exists in the current checkout. A new root checklist continues the existing redesign/session ledgers, without recovering unrelated history. Baseline `7b4398c`; new worktrees `dirac-shared-rag`, `dirac-discord-jobs`, `dirac-smoke-runtime`, `dirac-publisher` were created at 06:13 UTC. Existing worktrees and untracked report/skill deliverables were left alone. Detailed lane ownership, boundaries and receipts belong in `DIRAC_INTEGRATION.md`.

Publisher scout verified that `static.htaccess` is an unreferenced source artifact, not a deployed restriction: the publisher copies authored files (including per-site `.htaccess`) and executable bits; it neither proves nor configures remote PHP/Perl/CGI support. The coordinator rejected an unsolicited generic `refused_roots` policy; actual destination isolation will be verified during the explicitly authorized Dirac setup.

## 2026-09-19 — grounding only

Starting point: clean `dev/phaseII_v2`, one reachable commit `c460324` (`Initial commit`). Root requested reconnaissance, temporary organized notes and frequent local checkpoints while another agent finishes the backup. No implementation, removal, runtime validation or production work is authorized in this slice.

### Coordinator observations and actions

1. Loaded `choom`, `implement-tyranny` and `subagent-model-routing`. Did not load the runtime-debug skill.
2. Verified the working directory, clean Git status, branch and one-commit history; listed only this checkout's top level and `.agents` contents.
3. Read root `AGENTS.md`, the opening portion of `docs/STATUS.md`, `pyproject.toml` and `.gitignore`; inventoried documentation paths. Did not follow historical commit IDs, external URLs or operational paths.
4. Checked local commit-hook readiness: `.git/hooks` contained only sample files; the targeted configuration query returned no hooksPath, fsmonitor or signing overrides. No hooks or repository programs were run.
5. Discovered the two requested model routes and their reasoning options. Assigned three independent, read-only reviews with the complete production and cross-contamination prohibitions in every prompt.
6. Created `phase-II_v2/` and `phase-II_v2/adversarial-review/`. All requested note content stays here. Existing files, root instructions and tooling configuration remain untouched.
7. Reread the specific dotenv import, live-provider test, pytest/development-dependency configuration and Python-version documentation passages before retaining their findings. Rejected unsubstantiated child claims; see `REVIEW.md`.
8. The skill catalog subsequently added `implement-sanity`; loaded it for the agent-output review, with Python-code checks inapplicable to a notes-only diff. Git now shows concurrent untracked `.agents/skills/implement-sanity/`, not created by this coordinator or assigned children; leave it untouched and outside this checkpoint.

### Child assignments

| Child | Route / effort | Scope | Write ownership |
| --- | --- | --- | --- |
| `efc2d70c-d18f-4051-98ad-28c964251d92` | `deepseek-official/deepseek-flash`, high | Classify local documentation, missing links and mixed inherited claims | None |
| `c784fc11-191a-4e9a-977a-2b6b0afa1c65` | `deepseek-official/deepseek-flash`, high | Inspect quality configuration and test-execution risks as text | None |
| `58d14fe9-67d9-450f-9740-f49677368c5c` | `openai-codex/gpt-5.6-luna`, max | Challenge inherited authority, then independently review the notes | None |

All prompts prohibit production/private state, other projects, internet/upstream research, external symlinks, runtime/deployment/Screen actions, application imports, tests/collection, new tests and any file writes. Existing operational permissions are explicitly superseded. Parent alone synthesizes notes and owns final Git operations.

Child acquisition deviations were disclosed after challenge: the documentation child used shell find/grep and a transient in-memory Markdown scanner rather than the requested file tools; the quality child used shell searches and inspected a broader set of checkout test text plus a harness docstring than the requested small sample. Those were static inspection commands, not application/test execution. Both reported no external/project-origin lookup, private-path reads or file writes. The documentation child expressly confirmed it did not read Git remote configuration; its unsupported claim that no remotes exist was discarded. No exhaustive link or module-count claims are accepted. Subsequent reviewers must use the dedicated file tools and keep the assigned scope.

### Validation boundary

Only static file/source inspection and local Git/diff checks are in scope. Action-log entries are coordinator/tool observations, with child reports attributed separately; none establish runtime, deployment or provider behavior. No application or test validity is established. No production health claim, snapshot-completion claim or historical test-count verification is made. No existing tests were added, edited or removed.

### Checkpoints

- `c460324`: inherited starting commit; not a V2 acceptance result.
- `aa77fa0`: grounding checkpoint. Child findings received and challenged; Luna performed independent five-file review. Scope/provenance clarifications were applied. The coordinator inspected the complete staged diff and `git diff --cached --check` passed; the five initial `phase-II_v2/` Markdown files were committed, with the concurrent sanity skill excluded. No tests/runtime validation occurred.

## 2026-09-19 — authorized naming/docs cut-off and Docker metadata

### New human decisions

Root requested an operational naming/path/route/storage cut-off, not a global prose replacement; canonical name `dame-curie`, intentional short URL `dame`. Root authorized read-only Docker name/version/commit inventory, identified the existing service account `maxwell-curie` and explicitly requested run-as-user after the default local socket denied access. Root then fixed the planned new service account as exactly `dame-curie`, with a separate private rootless engine. No user/engine creation or startup was requested in this slice.

Root requested active documentation rebuilt from selected local legacy material and a permanent account/engine/discovery/permission/hands-off procedure. Host wording is generic; project Python 3.14 uses isolated venv/uv, never the system package tree.

### Work and evidence

- Dedicated read-only children mapped application namespaces (`e3ad4463-12b9-4158-b938-1e4d66088cee`), infrastructure selectors (`62d64394-1214-4c48-a031-47cd467e77df`), documentation retirement (`4d5cf1d5-a673-4153-8d16-9a7f62a06fb5`) and adversarial boundaries (`366d76b6-3fdf-4959-9ddd-ccea213ed844`). Flash handled the first three; Luna max the last. All children remained without runtime access or file ownership.
- Parent observed only allowlisted Docker metadata as `maxwell-curie` at its UID-derived local socket. Snapshot: 19 running containers, five distinct running image IDs, `01:03:42–01:05:20 UTC`; full retained evidence in `DOCKER_INVENTORY.md`. The default daemon remains uninspected after its permission denial. No raw inspect/env/credentials/logs/mounts, exec, provider probes, mutations or deployment scripts.
- Source spot-checks included full `select_owned` control flow. A child's name-only stop/remove bypass claim was false: missing/foreign labels raise before inclusion. That proposed fix was rejected. Other corrected overclaims and the source mapping are in `CUTOFF_PLAN.md`.
- Verified the already installed Python 3.14.4 interpreter with isolated/no-site/no-bytecode flags and standard-library venv help. Created no environment and installed no packages; no application imports. `uv` was not found on this session PATH, not investigated elsewhere.
- Archived 21 inherited documentation/guide/asset files under `legacy/v1/` using Git moves. Old AGENTS text is `AGENT_CONTRACT.md`, not an active nested contract. Rebuilt root README/AGENTS/SECURITY and active status/architecture/development/operations pages. Kept LICENSE and tokenizer provenance in place; preserved root's untracked sanity skill.
- Updated tyranny's documentation templates to Python 3.14, constrained its application to authorized new/rewritten code, and removed unverified old hook-version examples without selecting replacement pins or changing installed tooling.
- The file-observation backend initially rejected creation of four replacement files because it still remembered the moved originals. Rereading their now-absent paths refreshed that observation, and the write-tool replacements succeeded. No permission escalation or alternate filesystem bypass was used.

### Limits and next milestone

This slice changes documentation/skill guidance only. Application Python, deployment configuration and tests remain unchanged. Source namespace alignment, concrete V2 private-root/project conventions, isolated validation and any provisioning/deployment remain pending. A later account/engine layout must honor root's exact `dame-curie` user, not earlier provisional suffixes. No snapshot/backup completion was inferred.

### Documentation checkpoint review

Flash reviewed active navigation/version/account wording; Luna reviewed the written operations procedure, new active contract and quality guidance. The coordinator clarified future narrow metadata grants and intentional immutable V2 artifacts versus protected V1 namespaces, and kept source-renaming/acceptance pending. Historical initial notes now carry explicit pre-cut-off provenance instead of masquerading as current instructions.

Before staging replacements, Git reported all 21 archive moves as 100% identical. After replacement staging, the archived copies of AGENTS/README/SECURITY/STATUS were additionally matched by Git blob IDs against `aa77fa0`; remaining moves retain R100 status. Archived bytes were not rewritten.

The global staged whitespace check reported three pre-existing two-space Markdown line endings in `legacy/v1/README.md:807-809`. Its blob exactly matches the starting README, so those historical bytes were retained deliberately. The check excluding the byte-preserved `legacy/v1/` cluster passed for active docs, guidance and working notes. All staged paths are documentation/skill/archived-asset paths; root's untracked sanity skill remains excluded. Final ledger edits receive the same scoped check before commit.

No tests, application imports, builds or mutation of the observed V1 resources were used as this documentation gate. This became checkpoint `47cd6f1`; the operational source cut-off was its next implementation milestone.

## 2026-09-19 — source naming checkpoint

The full-slug/account/private-root conventions were selected before parallel implementation: `dame-curie` and `dame-curie-<identity>`, direct account/resource prefix and `/srv/<full-instance>`. Root did not authorize provisioning or startup.

Flash high writers separately owned application/configuration, infrastructure/templates and publisher source. A fourth writer aligned existing fixtures only. Luna max independently challenged the actual source diff; parent reviewed coupled contracts, rejected speculative defects and owned final corrections. Exact identities, findings and provenance limits are in `SOURCE_REVIEW.md`.

### Additional human decisions

- Root approved quarantining both V1-specific DNS provisioning scripts unchanged; broader removals/changes await the next informed pruning assignment. Bot email functionality remains.
- Root announced concurrent Mermaid scratch work from another session. `scratch-mermaid/` is preserved and excluded from this checkpoint.
- Root explicitly requested the staged, unchanged `implement-sanity` skill be committed, with a message naming it as the review twin of `implement-tyranny`. This supersedes the earlier exclusion of that user-owned file, not permission to modify it.
- Root checked the Flash version. The current catalog identifies `deepseek-official/deepseek-flash` as DeepSeek-V41-Flash; the separate vision-experimental route was not used.

### Implementation and review

- Renamed operational env/config keys, labels/resource selectors, images, paths, shared RAG basename, PM2 identifiers and publisher markers/templates together. Existing validators now enforce the full new instance namespace without legacy aliases.
- Corrected duplicated Compose and socket-account prefixes, aligned archive generation/reconstruction keys and removed remaining real V1 site/OAuth/mailbox fallback values without choosing real V2 identities.
- Reverted unrequested publisher deduplication and internal persona identifier churn. Retained canonical temporary filesystem prefixes. No new helper, blanket exception handler, logger, type escape or test was introduced.
- Host wrappers select checkout `.venv`; active doctor/config/tool guidance no longer recommends global Python/pip. Existing installer/doctor gates now require exactly the 3.14 minor version, not any future version by accident. Final staged-diff review caught an added venv helper that rebased a relative install directory after `cd`; parent removed that helper/guard and used direct checkout-relative interpreter calls.
- Existing fixtures/import roots were aligned in 45 test files, without adding tests/cases/assertions or executing/collecting them. The stale documentation-reading test remains a reported pruning decision, not a fabricated passing result.
- Both DNS scripts were moved into `legacy/v1/email_integration/`. Archive/build-context/static-tool boundaries were updated without changing dependency pins or running tools. The ignored pre-existing `run.sh` was restored to its original content and is not added to Git.
- Current active docs now distinguish implemented source conventions from absent runtime/replica/deployment acceptance. Names alone do not prove separate state, ports, mounts or remote publishing destinations.

### Execution-provenance correction

The infrastructure writer disclosed generic `python3` AST parsing of four helper files, `bash -n` and `node --check` against an earlier edit. No app or tests were imported/executed, but these are not explicit isolated Python 3.14 checks or final-source validation. The claim was corrected, no repeat was requested, and no suite/linter/type-checker pass is claimed.

No new runtime queries followed the earlier authorized inventory. No private-state/configuration reads, provider/login calls, environment/dependency creation, Docker builds/pulls/lifecycle work, deployment, migration or publication occurred. A local source checkpoint does not authorize the next runtime step.

## Read-only subsystem map — source baseline `a9c0fba`

Root requested a fast parallel map before surgical pruning, explicitly selecting three same-model scouts. Root's desired removal candidates are DNS, email and X; YouTube needs scope clarification, while working TTS/image generation remain protected. Application subagent/provider selection and logging/console need separate boundaries. The highest-priority issue is duplicated, inconsistently editable website/tool prompting and its mismatch with remote hosting. Root explicitly forbids opportunistic cross-subsystem repairs and broad all-at-once runs.

- Scout `4f51a2c5-9309-45bf-b2cc-758f73fe47f1` (`gpt-6-astra`) mapped DNS/email/X/YouTube, including only the two explicitly relevant archived DNS scripts.
- Scout `95423f35-9df4-4945-9aa9-d2fcfedb6f6a` (`gpt-6-astra`) mapped TTS/image provider selection, manual PPQ routing and protected artifact/delivery dependencies.
- Scout `0dfdc711-6145-4d35-9421-e6a562bd728e` (`gpt-6-astra`) mapped application background jobs/provider routing and logging/console versus functional memory events.
- Coordinator mapped tool registration, descriptions/schemas/result feedback, live versus source-owned prompt layers, local site/KV runtimes, remote file publishing and browser-test targets. Scout ownership was read-only; all documentation writes stayed with the coordinator. Existing scouts also checked the synthesized claims without editing code.

Findings and resume instructions are in `PRUNING_MAP.md`, linked from active status. The `mermaid-diagrams-v1` authoring contract was loaded, and root confirmed the renderer is available; chat diagrams summarize source relationships, not observed runtime traffic. No scratch Mermaid work was read or changed.

No application/test/configuration changes, new tests, code imports/execution, syntax-parser runs, test collection, provider probes, Docker/service access, private-state reads, dependency installation, remote access, deployment, migration or feature removal were performed. The source snapshot stays unchanged; any next implementation requires root's single-slice instruction.

## Explicit follow-up — static dead-code tooling and first soft pass

Root then requested the exact second-provider configuration trace and a first, report-only dead-code audit with reusable ergonomics. Source inspection confirmed real `AUTONOMY_*` and `AUX_*` endpoint/model families for different consumers; built-in spawned jobs still do not resolve them. Those details were incorporated in the reviewed mapping checkpoint `8d9cb8f`.

This follow-up separately authorized tool setup and static parsing, not application execution or removal. Neither review skill nor the project had a configured Vulture audit. Coordinator verified the official Vulture 2.16 release metadata/Python 3.14 support, created a fresh ignored `.venv` using `/usr/local/bin/python3.14` (3.14.4), and installed Vulture only, besides bootstrap pip. This narrow tool-release verification was not research of another application checkout/upstream. Existing package pins and Ruff settings were preserved.

- Selected 87 tracked non-test Python source files; excluded archives, deep test harness, generated/private trees and scratch work. The exact manifest is `VULTURE_INPUTS.txt`; physical line count was 70,746.
- Vulture parsed without importing application modules. Default report: 163 findings (150 at 60%, 2 at 90%, 11 at 100%), no unreachable blocks and no emitted input/syntax errors. Exit 3 means findings, not execution failure. A second 100%-only view returned the same eleven findings and expected exit 3.
- Most high-confidence results concern required callback signatures. A bounded source look identified deprecated/retired helper candidates and preserved their active replacements/shared scanners; no reported code was deleted. `DEAD_CODE_PASS.md` records evidence and limits; `VULTURE_BASELINE.txt` preserves the complete first report.
- Added the exact dependency pin, report-only project settings, both skills' dead-code review discipline, and permanent `docs/DEAD_CODE.md` usage. No custom scanner/wrapper, blanket suppression, new tests, hook or automatic clean-tree gate was added. This is deliberately not application readiness or coverage evidence.
- Independent read-only review confirmed the report counts and soft-pass boundaries. It found that the initial documented process-substitution recipe would hide a failed Git selection. The permanent workflow now clears the array, accepts a cached path list only after Git succeeds, and separates path review from invocation. This corrected the future recipe; the recorded successful baseline remained valid.
- Root reported a harness rendering problem and requested the draggable diagram form. Coordinator used flat Mermaid flowcharts without subgraphs; no harness/plugin/server change or restart was attempted, and current rendering success was not claimed.

Application/test code, real configuration and protected V1 remained untouched in that audit assignment. No app/test import or execution, private-state read, Docker/service access, provider call, deployment or pruning occurred there.

## 2026-09-19 — authorized V2 foundation and parallel next slices

Root included provisioning in this round and selected fresh V2 state, secret-safe V1 provider settings transfer and bounded non-Discord provider checks. Root explicitly prohibited Discord credentials/activity and required Ollama/model-pull to remain stopped with RAG disabled. Canonical principal IDs were confirmed. Detailed current evidence lives in `PROVISIONING.md`.

- Coordinator created the `dame-curie` account/private rootless engine and restrictive roots, transferred only allowed provider settings, and began image preparation. V1 lifecycle and personal history remain untouched.
- Flash restored-source web closeout was limited to branding, namespaced browser storage and PM2 selectors; immutable artifact provenance is recorded. Coordinator fixed wrong identity/implicit partner defaults and the missing image-media Docker input.
- Luna caught a canonical-wrapper bypass of the staging overlay. Coordinator added the default-on staging gate, exact ownership-label layouts and appropriate restart/down selection; Luna re-reviewed without a remaining source blocker. Existing fixtures were aligned, no new tests or test execution. Source syntax and Compose service selection were checked.
- Root then authorized removing the email subsystem in worktree `/home/codexy/deepseek/dame-curie-worktrees/prune-email`, branch `work/prune-email-20260919`, based on `3a71cbb`. Its agent owns only that branch; shared inbox/notifications/media are protected and central ledgers stay coordinator-owned. Review/integration is pending.
- Logging is the next priority: an Astra child traced the actual Hortator implementation under root's narrow other-project source grant, with independent Flash/Luna adversarial review. `LOGGING_PLAN.md` is a reviewed proposal, not implementation or terminal acceptance. Existing logging and functional memory remain; no agent touched live Screen.

Runtime authority remains coordinator-only. Source commits are not Discord/RAG activation permission.

### Subsequent checkpoints in the same provisioning round

- `f94c291`: reviewed Screen logging proposal; `8876dc4`: naming/static-web/identity/staging closeout.
- Email worker source `1cc0e9c` and report `fd060a2` passed independent Luna review and were cherry-picked cleanly as `9b01074`/`70b8ceb`. Main-only admin polling control removed. Shared inbox/media and X date parsing remain; no history migration/new tests. Source integration and final image acceptance are distinct.
- Root queued Twitter/X as the next pruning cut; implementation has not started. Root then selected the remote inference `OLLAMA_*` to vendor-neutral protocol `OPENAI_*` naming cut in another worktree. Its source commit `85eafb1` is being independently checked by Flash/Luna. Local Ollama embedding/runtime settings remain separate and unchanged. Private V2 key migration is coordinator-owned and pending.
- All required initial images built successfully; shell/site interpreter checks reported Python3.14.4 without networking. Core containers created with both profiles for create only; bot/Ollama/pull each reported never-started timestamps and restart `no`. Source installed under `/opt/dame-curie`; private home permissions stayed unchanged.
- Fresh source-default prompts and empty RAG/graph schema seeded with networking disabled. SQLite integrity passed and six key tables were empty. API/web support startup and final post-integration images/provider checks remain separate acceptance steps.
- The staged example's `ENABLE_RAG=false` change left one existing deployment fixture expecting true; coordinator aligned that assertion after the naming worker flagged it. This was coordinator integration fallout, not a defect attributed to the worker. No fixture was executed.

### Final staged handoff

- `df6c97e` closed email/admin/fixture integration; `b2f5380` cleanly integrated the inference worker's `85eafb1` after independent Flash/Luna actual-diff passes. Both cuts survived their shared hunks. Combined Python3.14 compile-only, Node syntax, Bash parser and whitespace checks passed; no tests or collection.
- Private V2 migration renamed18 present keys from the22-key map atomically, preserving absence, blanks and values, and removing only the obsolete disabled email flag. Shared compat auth and four local embedding settings were unchanged; no private values entered source/reports or V1 configuration changes.
- Final app/web images were built from exact code revision `b2f538017edb3a8aa0b1d800e994a11f5944da07`; active `/opt/dame-curie` source was replaced cleanly, and private deploy refs updated. Documentation-only handoff commits do not change those release identifiers.
- Six V2 containers now exist. API/web are running and healthy; bot/Ollama/model-pull/shell are created with never-started timestamps and restart `no`. Only web binds server loopback18081. Fresh private config/DB ownership is1005:1005 mode0600, SQLite integrity passes, six memory/graph tables and local model volume are empty, and there are no sites. See `PROVISIONING.md` for exact image IDs and the operator entrypoint.
- Local landing/admin/health returned200; unauthenticated controls401; authenticated controls200 with bot disabled. Primary compatible inference returned HTTP200 with visible text on the corrected bounded check. Two capped requests total: coordinator's first reader parsed a partial/keepalive chunk; the second consumed the complete response. This was a smoke-script error, not a production provider defect. No body/credential was printed.
- Site dependency metadata check passed. App check reports the voice extension's unmet `discord-py` distribution requirement while the intentional self-fork is installed. Pins and fork were retained; no full voice acceptance or package-clean claim. Resolve/accept that issue before any future Discord activation.
- One initial coordinator CLI call reversed instance/action and was rejected before Docker access; the correct `instance.py dame-curie up` then passed with staging intact. Protected V1 still reported19 running containers; no V1 exec or lifecycle mutation.
- Bot/Discord/embedding/Telegram activity never ran. No tests, Screen interaction or publishing. Logging proposal remains the next implementation handoff; Twitter/X remains queued; checkout bridge and broader runtime acceptance remain unclaimed.
