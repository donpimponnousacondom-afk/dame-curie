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
- [x] Give Dirac separate persistent configuration, memory, shell, sites and publisher state; actual mounts and replacement persistence verified.
- [x] Integrate job/thread routing and cancellation fixes; two real jobs and parent/thread-origin routing passed, with scoped foreground timeout cancellation also observed.
- [x] Add the labelled real-model smoke protocol; actual shell/job/Discord receipts observed without fabricated gateway events.
- [x] Configure isolated SSH publication and verify actual static bytes over HTTPS.
- [x] Verify PHP/Perl/CGI exact HTTP response bodies; all three execute at the Dirac destination, without a local server or global remote changes.
- [x] Run scoped isolated and real scenarios: 351 tests plus 28 subtests; native shell, jobs, game/media, real publication, memory/REM and retained recall passed.
- [x] Record failures separately; the identical status task passed only in a new request after the classifier correction, with the guard unchanged.
- [x] Independently review integrated changes, build/deploy reviewed source `9a3fa43` and commit coherent slices locally.
- [x] Leave verified Dirac plus Screen/logger ready for root; exact access, state and limits are in `phase-II_v2/DIRAC_HANDOFF.md`.
- [x] Enable root's additional group DM `1545158306404892753` and verify hot reload without restarting.

## Known follow-up, not covered by this acceptance

- Root's archive report: the image limit is applied to non-text files and unsupported archives are misdirected to `see_image`. Root then explicitly requested 20 MB: the live setting is now 20 MiB (20,971,520 bytes), hot-reload verified without a restart. Archive handling is not repaired by that setting change.
- [ ] Deliver root's requested source-based inventory of enforced attachment limits, distinguishing defaults, live settings, transport, media/prompt budgets and unverified Discord assumptions. Root will compare it with the other bot's limits.
- The private embedding relay forwards the full Ollama API, not an endpoint allowlist; no model-management operations were exercised. Do not treat it as a security boundary.
- See the handoff for boot/restart policy, publisher recovery, job-resumption, classifier/game-label and untested-feature limits. Scoped readiness does not mean every feature or failure mode passed.

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
