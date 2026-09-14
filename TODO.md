# v1.0 FREEZE — ACCEPTED BASELINE, ARCHITECTURE REWRITE IS SEPARATE

**Root explicitly accepted this state and authorized committing everything, opening and merging its PR, and tagging the merged commit `v1.0` (2026-09-14). The release is an as-is checkpoint, not a claim that the site architecture or deferred coverage is complete.**

- This freeze includes the already-applied Ollama resource setting (12 CPUs / 6GiB), all local hotfixes, this backlog, and the report at [`reports/curie-workflow-wording-2026-09-13.html`](reports/curie-workflow-wording-2026-09-13.html).
- Root will redesign site creation/tool architecture with another agent. Do not start that rewrite here, repair known wording as part of tagging, or hold this freeze for the deferred tests/docs below.
- Keep new reports inside their project workspace. The previous `.dsh/reports/` placement was an agent choice, not a harness requirement; `AGENTS.md` now makes project ownership explicit.
- Preserve the published HTML report as dated evidence. Its original local-only/PR-pending statements describe the audit moment, not release status. The remote copy remains at https://redroom.zombiedawn.net/dame/workflow-audit/ .
- After merging, use current `origin/main` for subsequent work. The one-off permission to merge this freeze does not authorize future automatic merges.

## Historical pre-freeze handoff

The instructions below are retained as context. This freeze authorization supersedes their earlier local-only/no-merge direction; remaining checkboxes are backlog, not release gates.

## Resume here (root's handoff, 2026-09-13)

- Working branch: `fix/console-navigation-noise-time`, based on merged main `84935df` (PR#11). PR#10 and PR#11 are already merged; do not reopen their work.
- Local hotfix commits: `abd895f` (console arrows, Ollama toggle/default hiding, local clock display), then `1b96027` (nested API routing, source re-reads, non-silent site-task ending, backend-aware URLs). Preserve this order. A notes-only handoff commit may follow.
- Deployment at the original handoff, before the follow-up below: `maxwell-app:1b96027` and `maxwell-web:1b96027`; fresh Discord login, zero startup errors, healthy API/web/Ollama, publisher active. Generated site code/images were not rewritten. The console-only patch is also live.
- Root is taking a break and manually testing. Collect that feedback before expanding scope. No new runtime work or Netlify integration during the handoff.
- Next round: finish the agreed fixes and deferred validation/documentation below, inspect the complete accumulated diff, push the feature branch and open its PR. Root merges manually. No force-push, rebase, squash, reset or direct main writes. Fetch and inspect current main/PR state before deciding how to integrate newer upstream work; preserve the local commits.
- `docs/STATUS.md` is behind these explicitly deferred hotfixes. Do not mistake its previous image/behavior descriptions for current runtime proof.

## HOSTING SCOPE — STATIC DREAMHOST IS INTENTIONAL, NOT AN UNFINISHED FASTAPI DEPLOYMENT

- Root already understood DreamHost shared-hosting limitations and accepts static-only mirroring. Do not turn the next round into a remote FastAPI hosting/proxy project.
- Curie may build and test FastAPI/Python locally. A copied remote page may lack its backend; root accepts this and can ask Curie to package the project for Discord/download and deploy it elsewhere himself.
- Preserve local Python tooling: the automatic image cutter is useful behavior, not a mistake to prohibit or rewrite.
- Netlify MCP/API deployment is a possible FUTURE integration, not work authorized now. React/static frontends plus Netlify-compatible JavaScript/TypeScript functions are a practical target; an unchanged persistent Python/FastAPI server is not the same deployment model. References: https://docs.netlify.com/build/functions/overview/ and https://docs.netlify.com/build/build-with-ai/netlify-mcp-server/ .
- Root may explicitly ask for another target-compatible framework/runtime later. The current DreamHost mirror's `static.htaccess` deliberately serves source files statically, including PHP; enabling PHP/CGI execution would require an explicit serving-policy change, not merely copying a different extension.
- Revisit the last hotfix's backend-aware URL wording with root's clarified intent; do not impose new restrictions on creating, mirroring, or packaging local backend projects.

## Immediate manual-feedback follow-up (2026-09-13, after 4a803e9)

- Raise the RAG query deadline from 1.5s to 30s (override ceiling 180s). The live identity had no explicit override; keep the 15s failure cooldown and embedding model/state unchanged. This gives CPU contention more time, not more CPU capacity.
- `create_site` incorrectly treated shell-container `/home/maxwell/...` image paths as bot-container host files. Both reported slab images existed. Import through the existing verified, confined shell-export path used by `send_file`, preserving size/ownership/symlink boundaries, then write under the site's public `images/` for normal mirroring. Include import failures in tool feedback; do not require third-party image hosts.
- REVERSE the backend-aware localhost delivery change from 1b96027: create/edit/list should advertise the configured REMOTE URL even with a local backend. Root explicitly wants that. Say HTML/CSS/JS/IMAGES are mirrored; only Python/FastAPI/KV execution is local. Do not describe the mirror as vaguely serving "files only".
- The configured tool budget is 50 iterations / 3600s. The loop could spend its last follow-up generating another tool call, then discard that unexecuted call and emit the fixed incomplete-status fallback. On the last site iteration or repeated-site-test breaker, give Curie a no-tools final response with retained created-site URLs, distinguishing local test results from remote limitations. Do not raise the iteration budget or claim the recent incident's exact exit branch was captured: the bounded log projection did not show a read-loop/time-budget marker.
- [ ] Deferred regressions: slow query success after 1.5s; configurable deadline and cooldown preservation; import nested shell PNGs and mirror identical bytes; retain traversal/symlink/ownership/size refusals and ordinary host/URL image paths; report actual export errors; remote URLs regardless of backend flags; end-of-budget model response with tools disabled, retained links after trimming, and no extra generation for normal completion/no_response/already-delivered replies.
- [ ] Prompt inconsistency to discuss, NOT changed in this slice: create_site's description and bot.py's site instructions explicitly mandate backend=true + Python and forbid client-only sites. That contradicts a free choice of static designs; do not describe the default Python choice as completely unconstrained or expand this hotfix into an unrequested prompt-policy rewrite.

## Deferred validation and polish

Deferred at root's request: ship the hotfixes for manual verification first. No suite runs or broad documentation rewrite in the hotfix round.

- [ ] Add real Caddy → API → generated-backend coverage for nested tile/download routes, query strings, uploads and unchanged static/dashboard routing; inspect adapted route order.
- [ ] Cover repeated site reads and different slices after tool-history trimming/compaction. Remove obsolete read-cache/limit machinery and outdated refusal instructions afterward.
- [ ] Cover empty-text site-loop termination: exhausted iterations/time, repeated site-test stop, a visible incomplete-status reply, and an unverified site link when available. Preserve explicit no_response and already-delivered message/media behavior.
- [ ] Verify create/edit/list backend-aware advertised URLs and server activation after static-site creation, respecting root's accepted static-mirror/local-backend/package workflow. Remote backend hosting is NOT required to finish this iteration.
- [ ] Confirm Curie's emote task manually: gallery, eight tile images, downloads, previews, re-cut/upload/reset, and a final Discord reply. Existing generated code/state was not rewritten by this hotfix.
- [ ] Add console coverage for split CSI/SS3 arrow sequences, chronological scrolling, Ollama hidden by default, o toggle, retained errors and local-time rendering. Full dates/colours remain phase two.
- [ ] Update obsolete private-network rejection tests and cover local/private HTTP fetches and redirects; retain HTTP(S), transfer-size and redirect limits.
- [ ] Reconcile STATUS/SCREEN/DOCKER/tool guidance with the accepted runtime behavior, then run focused regressions and the approved isolated full suite (keep the mandatory unsafe-test exclusion).
- [ ] Review and publish the local hotfix commits after root's manual verification; no automatic merge.
