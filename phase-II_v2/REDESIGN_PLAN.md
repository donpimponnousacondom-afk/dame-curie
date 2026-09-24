# Discord-only redesign: approved execution contract

Baseline: `ac38b84`, branch `dev/phaseII_v2`. This is root's new implementation assignment, not permission inferred from older audit notes. Root is AFK and requested parallel execution with best bounded decisions, no repeated scope questions.

## Integration order

1. Implement the reviewed Hortator/Screen logging port (`LOGGING_PLAN.md`), preserving legacy modes and functional memory.
2. Integrate independently scoped removals and direct-container shell execution.
3. Normalize the command prefix and remove stale capability references against the integrated source.
4. Separate tool/prompt contracts and implement reviewed per-background-job routing. Authoring/personality policy tuning is deferred.
5. Reconcile the V2 release and record precise evidence/remaining activation holds.

Implementation and source inventories may run concurrently in isolated worktrees; integration follows this order. Children never operate runtime. Source review does not establish runtime correctness.

## Remove

- Dashboard and its HTTP/admin/OAuth API, static dashboard pages, Caddy, web image/service and their deployment selectors. No replacement API server.
- Bot-local website serving and site-management tool machinery: Python/FastAPI/uvicorn site servers, local JSON KV/item APIs, per-site containers and site testing/server tools. File authoring moves to shell; nothing should suggest starting a local website server.
- Separate nested shell container/image and shell Docker orchestration. Commands execute inside the bot's own outer container.
- Twitter/X, Telegram and companion/GF secondary-account machinery. Preserve the single Dame Curie identity and root owner checks.
- Obsolete active references to removed features, including registration, schemas, controls, help, comments/docstrings and prompts. Do not invent replacement features.

## Preserve exactly

- **Publisher/syncer implementation, remote publication semantics and destination selection.** Do not edit `scripts/publisher/`, change its configuration, invoke it, or publish anything. Its independent service mirrors files; the model writes locally and does not administer the remote server. Root says this mechanism already works and must remain untouched.
- Local authoring and image/archive paths, shared image replication, outbound provider configuration, generic fetching, media handling and attachments. Remove HTTP servers without deleting shared asset/storage/URL utilities: relocate necessary non-serving helpers narrowly, preserving their behavior.
- Discord administration, autonomy, games and plugins; TTS/ASR/image/YouTube paths and existing manual compatibility patches; shared inbox/notifications, independent permissions, redaction and RAG/REM/graph/context memory.
- Python3.14 and strict image dependency pins. Removing a server package does not mean removing Python or HTTP client libraries needed by the bot. Do not install PHP, Perl or CGI tooling.

## Shell boundary

Root confirmed direct execution inside the bot container. Remove nested-container command/path restrictions, not the outer account/container isolation. No host-root mount, host Docker socket, host networking, V1 roots or host execution. Keep explicit V2-owned data/site/shell mounts, writable working storage, process cancellation and Discord output/delivery behavior. Preserve independent tool authorization. Root's explicit 2026-09-24 amendment removes the web-read taint/confirmation subsystem in full; it does not remove admin/owner checks or authorize host/V1 access. The model may author files with shell; local serving and remote administration are not the publishing workflow.

## Command prefix

Canonical active Discord prefix: **`!`**. Align runtime defaults, emitted help, schemas, tool prompts, active docs, comments and docstrings. Replace command references, not punctuation or CSV/Python commas. Existing V2 stored source-default prompts may need a coordinator-only mechanical migration after source integration. V1 is untouched. Quarantined archives and publisher sources remain untouched; clearly historical evidence is not an active command recipe.

## Job/prompt contract

Trace current consumers before selecting the minimal contract. Jobs must retain existing behavior by default and gain explicit per-job trusted provider-profile/model routing; no API key/URL arguments exposed to model tools, no invented endpoint/vendor defaults and no silent secret copying. Separate runtime identity/personality from tool/capability instructions so removed tools are not advertised. Root will tune website-authoring prompts later: do not replace that with a speculative prompt rewrite now.

## Swarm ownership

- Logging lane: `scripts/log_*`, the logging-format seam in `scripts/instance.py`, isolated implementation report.
- Shell/site-tools lane: direct shell execution and removal of local site tools in `bot_tools.py`/schemas; preserve shared media/file behavior.
- Web/API lane: remove inbound HTTP/site-serving modules; identify and relocate shared non-serving state/assets consumers narrowly.
- Deployment lane: Compose/images/installer/lifecycle scaffolding; default staging must start **nothing** after API/web removal. Coordinate instance-log seam with logging integration.
- Integration-removal lanes: X/Telegram and companion/GF, with separate worktrees and consumer maps.
- Read-only scouts: publisher/media invariants, command-prefix inventory, job/prompt routing design, independent adversarial review.
- Coordinator: shared ledgers/contract, conflict resolution, final prefix pass, cross-lane integration, private V2 settings and all authorized runtime reconciliation.

Workers do not edit these shared ledgers or another worktree. Use coherent local commits with explicit paths, no push/rebase of another worker. Compile-only changed Python under the existing Python3.14 tool interpreter is allowed; no application/test imports or test collection/execution, no new tests, no installs, no private configuration/state/log reads, no Docker/sudo/Screen/network or nested agents without an explicit assignment. Existing obsolete fixtures may be removed/aligned to the exact cut, not replaced by feature-absence tests.

## Runtime holds and handoff

Only the coordinator may reconcile the newly approved V2 removal/deployment. Re-resolve `dame-curie` UID and its explicit private rootless socket every time. Remove obsolete V2 API/web/shell/site resources only after reviewed source integration and ownership checks. Do not operate protected V1 or its publisher.

**Never start the bot entrypoint, contact Discord, transfer/use Discord credentials, start Ollama/model-pull or download/warm models.** Discord stays blank, RAG false and fresh model storage empty. No existing production Screen session, remote publication or private history migration. Any terminal exercise must be a disposable synthetic viewer-only session; no existing service/session is controlled. Report source/static checks separately from terminal, image and functional acceptance.

The prior staged deployment has API/web running and bot/Ollama/pull/shell unstarted. That is the last handoff, not permission to assume live state now. V2 publisher activation and checkout bridge were not established; do not silently reuse a V1 destination/root to manufacture readiness.
