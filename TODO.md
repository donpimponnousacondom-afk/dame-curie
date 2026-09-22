# Dirac V2 — integration TODO

## Current assignment — 2026-09-22

Root authorized autonomous implementation, isolated retesting, live labelled smoke scenarios, separate Dirac publishing over the existing SSH arrangement, and small local commits while AFK. Keep temporary Dirac authentication. Reuse the existing V1 embedding service without sharing V1 data or launching a duplicate model. Canonical Dame cutover is not this assignment.

No earlier `TODO.md` is present in the current checkout (both exact-name and case-pattern discovery returned none). This checklist continues the existing `phase-II_v2/REDESIGN_PROGRESS.md` and `phase-II_v2/SESSION_LOG.md`; their historical receipts remain intact.

## Work queue

- [x] Read the handoff and challenge unsupported findings against source and actual receipts.
- [x] Preserve the successful Discord/native-tool checks; root-initiated process killing is not an inferred OOM/product failure.
- [x] Establish baseline `7b4398c` and four separate Flash implementation worktrees.
- [x] Support external/shared embeddings and RAG-off without forcing a second local Ollama/pull chain; real Compose merge checked without activation.
- [x] Make embedding readiness honor the configured endpoint/model/dimensions/authentication; isolated checks passed.
- [ ] Replace the temporary test launcher restrictions with a supported, complete Dirac runtime/configuration path.
- [ ] Give Dirac separate persistent configuration, memory, shell, sites and publisher state.
- [ ] Preserve/reconcile Discord job/subagent/thread routing, ownership, progress, results and cancellation.
- [ ] Add an explicitly labelled operator smoke-test protocol using the real bot/provider/tools; never fabricate human gateway messages or tool receipts.
- [ ] Configure SSH publication into an isolated Dirac remote subtree and verify static authoring/mirroring.
- [ ] Check PHP/Perl/CGI at the intended destination; report unsupported execution honestly, do not silently restore removed local servers.
- [ ] Run isolated checks and real useful model/tool/site/thread/RAG scenarios in the approved Discord channel and its test threads.
- [ ] Record failures and fixes separately; rerun the failing scenario rather than upgrading an old result.
- [ ] Independently review integrated changes, package/build only the reviewed source and commit coherent slices.
- [ ] Leave verified Dirac plus Screen/logger ready for root; give exact access, deployment state and remaining limits.

## Execution boundaries

- Coordinator alone handles runtime, private configuration, credentials, existing SSH material and remote changes. Source agents receive no private values or logs.
- V1 bot/data/publishing destinations are not migration, deletion or testing targets. Shared Ollama is an intentional exception for embedding API use.
- Synthetic tests must be isolated from real dotenv/state/network side effects. Live smoke tests are separately labelled and authorized; existing tests are not run blindly.
- All harness implementation/review agents use DeepSeek Flash. Actual bot inference retains root's configured endpoint/profile and fallback semantics.
- No remote Git publication, unrelated refactor, speculative voice/security repair, global remote-server changes or duplicate model downloads.
- Root's recent Dirac-specific prompt was written in disposable runtime state; do not claim it survived a stopped/removed tmpfs container. Preserve any recoverable Dirac-only prompt; otherwise explicitly recreate the test provenance rather than invent its contents.

## Tracking

- Human-readable progress: `phase-II_v2/REDESIGN_PROGRESS.md`.
- Session decisions/chronology: `phase-II_v2/SESSION_LOG.md`.
- Current runtime and acceptance ledger: `phase-II_v2/DIRAC_INTEGRATION.md`.
- Current repository milestone: `docs/STATUS.md`.
