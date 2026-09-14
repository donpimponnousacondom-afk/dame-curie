# dame_curie — agent operating contract

This is `dame_curie`, a Maxwell side project. Preserve Maxwell code, path, API and environment-variable names unless root explicitly requests a rename. This file applies to the whole checkout.

## Read first

- [Current implementation and deployment status](docs/STATUS.md) is the single current-state ledger. Update it after every material implementation or acceptance milestone.
- [Rootless per-identity deployment](docs/DOCKER.md) is the target architecture and operating reference, not proof of deployment.
- [Shared Screen workflow](docs/SCREEN_WORKFLOW.md) documents current rootless lifecycle/log-following and rollback controls. Ctrl-c in Screen stops the log follower, not the containerized bot.
- For a read-only incident investigation, load the repository skill `curie-readonly-debug` from `.agents/skills/curie-readonly-debug/SKILL.md`. It maps private raw logs, normalized evidence, request/incident IDs and source entry points, and requires a sanitized evidence handoff without repairs, restarts, provider probes or state changes. It is guidance, not a privilege sandbox; separate diagnostic and implementation assignments.
- Historical audit/changelog content is preserved in Git at `96b4803:AGENTS.md`. It is evidence of past observations, not current authority. In particular arbitrary shell `docker cp` exports were removed in `6fa80e8`; do not report them as an outstanding current defect.

## Project-owned reports

- Reports are durable project deliverables, not harness scratch files. Keep their canonical copies inside the active project workspace; this repository uses `reports/` (existing `docs/audits/` reports remain valid).
- Never use `.dsh/`, harness installation/cache directories, `/tmp`, or another tool's internal storage as the sole or canonical home of a project report. Temporary copies and remote publication copies do not replace the project-owned original.
- Include requested reports in the project's commits/releases. Preserve dated reports as historical evidence; keep later corrections and current runtime status clearly dated. Never commit private raw logs, credentials or unsanitized incident data.
- Root established this preference for project reports regardless of the agent or harness creating them (2026-09-14). The earlier `.dsh/reports/` placement was the agent's own decision, not a required harness convention.

## Active authorization

Root explicitly authorized and completed the isolated Docker/Ollama/dashboard rollout on 2026-09-09. The real identity now runs once in Compose; the original host-native bot remains stopped. Current image/test/runtime evidence is in `docs/STATUS.md`. Never launch a second bot with the same identity or another application's writer against its state. Root additionally authorizes routine development synchronization after commits or explicitly requested pushes (2026-09-12): rebuild and select the new image when application code changes, then restart the existing Curie bot; for documentation-only changes, restart the existing image so checkout-at-boot reflects the latest commit. Root prefers frequent restarts over uncertainty about whether changes are live. Verify the running image/startup after synchronization, preserve private settings/state and the log console, and never launch a second identity. Root subsequently confirmed the routine publication workflow (2026-09-12): publish requested, validated changes on feature branches and open/update their PRs without waiting for a separate push request, unless root asks to keep the work local. This never authorizes direct main writes, force-pushes, automatic merges or weakening repository protection.

The approved target is **one Linux service user, private rootless Docker engine and Compose project per bot identity**. Each identity has private credentials, prompts, memory, generated sites, shell workspace and Ollama model storage/service. Shared source/images do not imply shared memories. Do not substitute a shared rootful Docker daemon or PM2 for this boundary.

Keep the existing `dame_curie` Screen session available; do not detach root, destroy unrelated sessions, or silently restart the legacy bot after cutover. No cutover until a backup and tested rollback exist. Synthetic acceptance comes before real identity startup. Production startup is authorized only as the final validated rollout, not as a test fixture.

## Safety and collaboration

- Inspect `pwd`, Git status/branch and recent commits before work. Preserve others' changes.
- Never print, commit, paste, or expose credentials/private message content. For the authorized migration, tools may copy/transform local configuration and state directly without returning values/content to chat. Inspect only necessary non-secret settings, schema/counts, health and sanitized outcomes. Do not dump `.env`, `data/`, container environment arrays, process environments or raw logs.
- Keep credentials in private host files; never in image layers, command arguments, build contexts, test artifacts or public dashboard origins.
- Do not alter the primary chat model/persona/credentials as part of infrastructure work. Do not invent a second Discord identity. Second-instance acceptance uses synthetic state and no live Discord login.
- Use scoped changes, regression tests and explicit staged file lists. Avoid unrelated tool-budget/persona/generated-artifact refactors.
- Coordinate file ownership with parallel agents. One coordinating agent owns infrastructure, runtime lifecycle and final commits.
- Do not open public ports or weaken authentication to make the dashboard appear healthy. Bind the dashboard to loopback unless an existing approved authenticated reverse proxy is configured.

## Legacy integrations

Telegram and Twitter/X are retained only as legacy/proposed integrations. Root does not use them; they are unsupported and must not be extended or included in new feature work. Leave their existing code and stored data alone unless root explicitly requests removal or renewed support. Current delivery work targets Discord only.

## Python and tests

New deployment images and development validation use Python 3.14.4. The pre-cutover host `.venv` was Python 3.13.5; old Ruff/mypy targets are historical tooling settings, not a reason to downgrade valid 3.14 code.

- Run focused tests, then the complete offline suite from a source-only temporary checkout with isolated home/data/site roots, disabled dotenv and a network/private-read barrier.
- Always exclude `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas`: it directly reads deployment credentials and can contact a live provider.
- Never run the application suite against production state. Previous successful full-suite reports do not prove the current HEAD passed.
- Live acceptance uses disposable identities, synthetic facts, authenticated local dashboard requests and explicit Ollama requests. Do not send test Discord/email/X/CAPTCHA side effects.
- Distinguish static checks, mocks, actual image builds, live service acceptance and production rollout. A Python import test is not a Docker build; synthetic UI screenshots are not backend acceptance.

## Commit often

Commit every coherent verified slice. Use a specific subsystem/intent subject and a detailed body recording changes, tests/results, deployment effects and remaining work. Update `docs/STATUS.md` when current state changes. Inspect the complete staged diff and secret-sensitive paths before committing. Never include unrelated generated HTML or runtime data.

Do not amend/rebase/squash root's or another agent's commits without explicit approval. Root's standing workflow authorizes routine feature-branch pushes and PR creation/updates for requested, validated work; honor explicit local-only instructions and leave PR merging to root unless separately requested. Keep rollback-friendly milestones rather than one giant mixed commit.

`main` is protected: deliver changes through a PR, never a direct push. This repository uses squash merges. After a PR merges, fetch `origin` and start the next branch from current `origin/main`; do not continue committing on the merged branch. If work was added there already, replay only the genuinely unmerged commits onto a fresh branch, preserving the old branch and avoiding force-pushes. Verify the PR diff excludes already-merged changes and GitHub reports no merge conflicts.

## Architecture map

- `bot.py`, `providers.py`: transports, live conversation/tool orchestration and OpenAI-compatible chat.
- `provider_telemetry.py`, `response_observability.py`: response-owned timing, tokens, footers, debug and startup-frozen build provenance. Preserve these recent changes.
- `rag_memory.py`: SQLite raw memory plus optional semantic embeddings; chat and embedding endpoints are independent.
- `prompt_storage.py`, `control_defaults.py`: shared prompt persistence and runtime controls.
- `bot_tools.py`, `tool_schemas.py`, `tool_registry.py`: tools, export boundary and schemas.
- `message_pipeline.py`, `concurrency_safety.py`: queues, deduplication, fairness and resource concurrency.
- `autonomy.py`, `autonomy_social.py`, `rem.py`, `jobs.py`: background agency, consolidation and long-running jobs.
- `api/`, `web/`, `docker/Caddyfile`: authenticated API and dashboard.
- `docker_runtime.py`, `site_server.py`, `scripts/instance.py`, `scripts/migrate_instance.py`, `compose.yaml`: instance ownership, generated backends, operations and migration.

## Discord command readability

- **Dense command reports belong in fenced code blocks.** Status/configuration dumps, diagnostics, key-value reports and plain-text tables must use opening and closing triple backticks on their own lines. Use a plain fence without a language tag for ordinary reports; never put the first data line on the opening-fence line.
- Reuse `send_command_response(..., code_block=True)` for these reports. It preserves balanced fences when splitting messages, handles embedded backticks and respects Discord's 2,000-character limit including footers. Do not hand-wrap a long report and then split through its fences.
- Use judgement: short acknowledgements/errors stay plain; deliberately rich help, clickable links and headings can remain outside the block. Single backticks are **inline code**, suitable for individual commands/paths, not a replacement for a multiline fenced report. Do not apply command formatting indiscriminately to conversational replies or model-facing tool results.
- Test the **actual emitted Discord content**, not only the values inside it: balanced fences, readable line breaks, safe embedded fences, message-length limits and unchanged short replies. Readability is part of command acceptance, not a second pass left for root to discover in Discord. Apply this rule whenever adding or modifying commands.

## Numeric OpenRouter effort

Root explicitly requires **every integer1–100** for DeepSeek **V4.1 Flash** on OpenRouter, regardless of advertised enum schemas. `!effort N` must persist/send the exact JSON integer, including50/75/100; no rounding, tier conversion or silent substitution after rejection. Keep named reasoning commands and unrelated routes/models unchanged. Capture full received rejections for root's support report; local/mock acceptance does not prove the upstream honors the integer. Do not reinstate the old three-preset restriction.

## Private incidents and Discord cleanup

- Automatic runtime-error notices use the single `PUBLIC_ERROR_TEXT` from `error_reporting.py`, with no TPS/TTFT/footer or exception suffix. Keep normal validation/refusal/cancellation semantics and the `error_replies` switch; do not manufacture failures from arbitrary `Error`-looking model/tool text.
- Retain full useful diagnostics in the identity-global private last-ten incident history. `!error` requires an explicit index 0–9 (0 newest) and current bot-admin authorization. **Diagnostic reports and usage/index/empty-history answers go to the requesting admin's one-to-one DM**, including server invocations; no target override, shared-channel report fallback or new public file/API export. If DM delivery itself fails, only the generic dove notice may be sent at the invocation origin—never diagnostics or files. Long reports may use complete UTF-8 attachments. Known credentials/auth material are redacted without dropping upstream explanations, paths, traces or received error bodies.
- Keep existing bot/model self-diagnostic tools, log access and model-facing tool feedback. Root knowingly accepts possible model-authored diagnostic quotations; automatic public projection must be safe, not a pretext to disable useful tools or filter arbitrary generated answers. Private report messages must not be automatically ingested into shared memory or dispatched to plugins; intentional admin references/log reads remain usable.
- `!forward N` is deterministic, admin-only and silent on success. Delete only this bot's own N latest messages in the invoking Discord channel/DM before the invocation; never other authors, another channel or the invocation. Serialize history selection and deletion; do not use model deletion/purge tools. Protect command-owned deletions from plugin side effects.
- **Discord deletion is not memory deletion.** Never clear, rewrite, re-embed or tombstone existing context, RAG, REM, tool history or bot-owned context caches as part of `!forward`. Preserve the existing model-accessible deletion tools independently.
- Root explicitly excluded legacy **REM/autonomy audit and status displays** from this rollout because they are not currently used. Leave their existing outputs and stored data alone; do not claim mixed legacy audits were made safe or keep redesigning them. Actual runtime-failure notices still follow the generic-error contract.

## Documentation rules

`CONTEXT_MEMORY_ANALYSIS.md` and `RELIABILITY_RESEARCH.md` are historical. The portable HTML guides remain reference copies, not live status reports. Prefer current code/tests plus `docs/STATUS.md`; correct stale operational instructions when their behavior changes. Keep historical evidence dated rather than blending it with current claims.
