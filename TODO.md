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
- [x] Replace the temporary launcher restrictions with the ordinary bot and complete derived configuration; actual temporary identity reached Gateway ready.
- [x] Give Dirac separate persistent configuration, memory, shell, sites and publisher state; actual mounts verified, restart proof still pending.
- [x] Integrate job/thread routing and cancellation fixes; two real jobs and parent/thread-origin routing passed, with scoped foreground timeout cancellation also observed.
- [x] Add the labelled real-model smoke protocol; actual shell/job/Discord receipts observed without fabricated gateway events.
- [x] Configure isolated SSH publication and verify actual static bytes over HTTPS.
- [x] Verify PHP/Perl/CGI exact HTTP response bodies; all three execute at the Dirac destination, without a local server or global remote changes.
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
