# Background job routing and prompt boundary

Lane: `work/job-routing-20260919`, based on `43ce047d9d5985a78a9cf3899e0302acc36383d6`. Source-only implementation; parent integrates after removal/logging lanes. No deployment effects.

## Reviewed contract

The coordinator confirmed the following against the actual provider source before implementation:

- `spawn_background` accepts `provider`: `main | autonomy | aux` (default `main`) and optional `model`. No URL, API-key or header arguments are exposed. Existing `goal` and `context` remain.
- Job metadata adds only the requested selector and optional model. No provider objects, resolved endpoints, credentials, headers or configuration snapshots are persisted. Old records load as `main`/unset. Restart still cancels queued/running records; it never resumes them.
- Default `main` with no override continues through `bot._generate_response`, with the existing background budgets, `disable_reasoning=False`, main provider state and nightly fallback policy. It does not construct or close another provider.
- Any model override, or either nonmain profile, gets a job-owned `OpenAICompatibleProvider`. No mutation of `bot.ai_provider`, cached autonomy/aux providers, shared endpoints or learned transport limits.
- Explicit profiles require their own configured endpoint **and configured model**, even when a model override is supplied. Nonblank same-role control values precede the same-role `Config` environment values. Missing configuration is rejected at launch with a nonsecret explanation, and checked again at actual provider construction. There is no aux-to-autonomy-to-main cascade in this job path. Existing REM/autonomy getter cascades are unchanged.
- Main overrides preserve main temperature/top-p/top-k, extra headers/body, live reasoning control, configured reasoning defaults, fallback, retries, empty-response retries, audio and vision settings. Explicit clones use configured reasoning behavior rather than forcing the legacy default job's `disable_reasoning=False`.
- Autonomy jobs preserve that role's endpoint/key/model/reasoning configuration and main-configured sampling defaults; aux jobs retain the existing aux temperature of `0.2`. Both retain configured fallback/retry/audio behavior and use background job token budgets, not the short-plan getter's 8192-token cap. Neither inherits main custom headers, extra body, reasoning control, vision routing or nightly preference. These roles have no existing independent vision/extra configuration to copy.
- Existing configured fallback endpoints and credentials remain real fallback routes; an explicit profile is not a promise that fallback cannot answer. Existing `Config` handling of `OPENAI_COMPAT_API_KEY`, including explicitly blank role environment keys, is untouched. Main vision blank-base/key inheritance remains the existing transport contract, not a newly invented role cascade.
- Providers are constructed inside the actual job's first acquired generation slot. Normal `generate_response` lazy initialization is used; there is no new discovery, model-list parsing or special probe. The runner's `finally` awaits the owned provider's `close()` on success, failure, cancellation and early returns after construction, then removes runtime handles. Shared default-main providers are never closed by a job.

## Transport precedence verified, not guessed

Reviewed `providers.py`:

- `generate_response` forwards request options to `generate_chat_completion` and returns `ProviderResult`, including per-call native tools, usage, assistant message and metrics.
- `_request_payload` applies a per-call `model` **only to primary**. Fallback and vision use their own configured model. The job override is passed through this existing argument; endpoint models are not rewritten.
- Primary `extra_body` is copied first, but explicit transport fields overwrite its model/messages/sampling/stream/max-token choices. Tool fields are rebuilt by the transport. Nonprimary requests do not copy primary extras.
- `_headers` applies custom headers only to primary; configured API keys supply Authorization with existing precedence. Nonmain job construction does not supply main extras at all.
- `generate_chat_completion` attaches actual request `endpoint` and `model` to per-call metrics. Requested labels never claim these are the eventual effective values. Progress threads emit `profile/primary|fallback|vision` plus the measured model when the effective response route changes; no endpoint URL/host is displayed or added to job metadata.
- Initialization may succeed through a configured fallback. A missing explicit profile is still rejected before transport creation; an unavailable configured profile can use its real configured fallback rather than borrowing a cached main provider.

No `providers.py` transport changes.

## Discord and tool surface

```text
!bg GOAL
!bg --provider aux -- GOAL
!bg --model MODEL -- GOAL
!bg --provider autonomy --model MODEL -- GOAL
!bg -- --provider is literal goal text here
!job JOB_ID
!jobs
!job cancel JOB_ID
```

`MODEL` is a placeholder, not an invented model default. Flags are optional, recognized only in an initial `--provider`, `--model` or `--` header. An explicit header requires a standalone `--` separator. Header tokens use `shlex`; **the goal never does**. Apostrophes, unmatched quotes, newlines and ordinary prose inside the goal stay valid. Ordinary `!bg GOAL` preserves the existing leading/trailing trim and manager's 2000-character goal cap. Header flags are limited to one occurrence each; unknown/duplicate header flags and empty overrides fail. No whole-goal shell parsing.

Acknowledgements, `!job`, `!jobs`, thread startup and final delivery label the **requested** profile/model (`configured` when unset). Model display is bounded and neutralizes backticks/mentions. Requested models remain fully stored and sent through the model parameter. `!jobs` uses the existing Discord response splitter because added labels can exceed a single message.

The manager's global/per-user limits, background slot priority/key, tool dispatch, cancellation authorization, progress threads and delivery/measurement handling remain. `spawn_background` is still removed from native job schemas, and the existing original-message recursion flag/taint identity is retained. No taint clearing, new authorization bypass, new memory retrieval or private-context expansion is introduced.

The coordinator separately approved forwarding the selected custom-tool-protocol flag to provider generation instead of discarding it. This is an explicit custom-mode behavior fix, not a claim that every legacy keyword argument is identical; ordinary native mode remains unchanged. ProviderResult/usage/metrics extraction and textual recovery still use the existing bot seams. No new usage accounting scheme.

## Canonical prompt boundary

`jobs.background_messages` reads `bot._get_personality()` (canonical PromptStore identity), and `bot.memory.get_server_prompt` for the **actual originating message's guild ID**, or the existing `DM` scope. It does not read `_control['base_personality']` or invent another personality fallback. It preserves the existing `_tool_system_prompt(platform, message=origin, content=goal)` seam, leaving the parent's broad live tool/capability extraction separate.

Job goal and supplied context are user-role input, not duplicated into system instructions. The focused job instruction keeps execution/confirmation rules, no recursive jobs, thread progress and concise completion. The obsolete instruction to test with `site_test` is removed. The only authoring statement is factual: shell writes local files; an external automatic publisher mirrors them; no local hosting or remote administration. No persona rewrite, hosting tutorial, path/URL change or publisher implementation change.

Canonical prompt/tool-prompt failures now enter the existing first-generation job failure boundary rather than silently falling back to a blank/stale personality. They are not papered over with new broad exception handling.

## Caller and static evidence

Source paths inspected:

- `bot.py`: `_setup_ai`, `_generate_response`, night helpers, unchanged `_get_autonomy_provider` / `_get_aux_provider` / `_get_aux_model`, tool registration, manual background launch/status, `_select_tool_protocol`, `_native_calls_from`, `_usage_from`, live personality/server-prompt assembly and taint dispatch.
- `jobs.py`: create/load/save, tool launch, detached worker, slot/dispatch/termination/delivery paths.
- `tool_schemas.py`: `spawn_background`, shared schema builder's injected reasoning parameter and protocol handling.
- `config.py`: existing main/autonomy/aux/fallback/vision values; source only, no configuration file or environment reads.
- `rag_memory.py` / `bot._get_personality`: existing PromptStore server/personality consumers.
- Existing job/error/measurement/operator fixtures were read and minimally aligned for canonical personality/server prompts or requested-route metadata. No new cases/assertions/tests.

Static scenario review covered default calls; old metadata/restart; role-only and model-only selection; missing role endpoint/model despite override; blank override; invalid/duplicate headers; apostrophes in prose; primary override versus fallback/vision model precedence; per-call effective reporting; failed/cancelled generation and owned-provider cleanup; main-provider nonmutation; per-user/global limits; original-message taint and recursion identity; native-call and metric preservation.

## Validation and limits

- Skills loaded: `implement-tyranny`, `implement-sanity`. Reviewed the actual explicit-path diff, not unrelated legacy style/size.
- **Passed:** compile-only validation using `/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/job-routing/.validation-cache -m py_compile` on `jobs.py`, `job_routing.py`, `bot.py`, `tool_schemas.py`, and the four fixture files listed below. Exit 0, no output. `git diff --check` also passed. No application modules were imported.
- No app/test imports or execution, test collection, new tests, lint/type-checker execution, dependency install, network/provider request, private configuration/state/log read, Docker/sudo/service/Screen operation, nested agent, or another implementation worktree inspection.
- Compilation is syntax evidence only. Route/network success, cancellation under actual I/O, Discord delivery, schema acceptance, tool behavior and role-specific model compatibility are not runtime-validated. A second cancellation interrupting resource cleanup or a transport `close()` failure is not synthetic-tested; cleanup uses normal awaited `finally` ownership, not detached best-effort disposal.
- Existing worker size, per-job end-to-end deadline limitations, legacy pre-generation cancellation bookkeeping, DM listing scope, shared bot followup-state seams and other unrelated orchestration behavior are not refactored here.
- Existing capability text in the base checkout still advertises other lanes' pending removals; parent must integrate those removals and the broad prefix/tool-prompt pass before treating the release as coherent.

## Parent integration seams

- Add **`job_routing.py`** to application Docker COPY and release/source allowlists. This lane does not edit those files.
- Merge only background import/provider-construction/launch/status sections of `bot.py`, and only `spawn_background` in `tool_schemas.py`; neighboring removal/prefix/prompt sections belong to other lanes/parent.
- Fixture edits are limited to `tests/test_background_jobs.py`, `tests/test_background_error_reporting.py`, `tests/test_response_observability.py`, and `tests/test_operator_commands.py`; retain other lanes' fixture removals/alignment.
- Parent owns shared ledgers, broad prefix normalization and broad live tool/capability prompt extraction. Publisher/syncer, config/templates, local authoring/_images disk/URL semantics and retained Discord/autonomy/games/plugins/media/memory features are untouched.
