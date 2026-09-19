# Remote inference naming cut

Source-only work on `work/openai-inference-names-20260919`, based on `8876dc4d10da7046df47f6eebeb64f123847504e`. Private settings, V1 and runtime were not read or changed; parent-owned ledgers remain unchanged.

## Contract

`OPENAI_*` means **OpenAI-compatible chat-completions protocol**, not the official OpenAI vendor, account, credentials, SDK or default endpoint. Root identifies the original remote provider as Ollama Cloud; local Ollama is only the RAG/memory embedding service.

The remote class is now `providers.OpenAICompatibleProvider`, replacing `providers.OllamaProvider` without an alias. Its constructor, request options and routing retain their behavior. No SDK/dependency/pin changes are included.

The coordinator confirmed the one default correction after it was reported: remote inference must have an explicitly configured endpoint. `Config.OPENAI_BASE_URL` now defaults to an empty string and uses the existing required-value check. `OPENAI_MODEL` remains required. The installer no longer chooses a local inference model or any vendor endpoint/model preset. It retains the separate, explicitly labeled optional local Ollama installation and `qwen3-embedding:0.6b` pull; no generative model is pulled. The standalone primary streaming probe requires explicit URL/model environment keys instead of defaulting to localhost. No configured URL or model value was changed.

## Exact runtime-key migration

**22 distinct key renames: 21 Config keys plus the provider's direct cooldown environment lookup.** Matching Config attributes and callers use the same new spellings. Empty-response retries also have a direct provider lookup, but that is the same key, not a 23rd mapping.

| Old key | New key |
| --- | --- |
| `OLLAMA_BASE_URL` | `OPENAI_BASE_URL` |
| `OLLAMA_API_KEY` | `OPENAI_API_KEY` |
| `OLLAMA_MODEL` | `OPENAI_MODEL` |
| `OLLAMA_REM_MODEL` | `OPENAI_REM_MODEL` |
| `OLLAMA_MAX_TOKENS` | `OPENAI_MAX_TOKENS` |
| `OLLAMA_TEMPERATURE` | `OPENAI_TEMPERATURE` |
| `OLLAMA_TOP_P` | `OPENAI_TOP_P` |
| `OLLAMA_TOP_K` | `OPENAI_TOP_K` |
| `OLLAMA_DISABLE_REASONING` | `OPENAI_DISABLE_REASONING` |
| `OLLAMA_EXTRA_HEADERS` | `OPENAI_EXTRA_HEADERS` |
| `OLLAMA_EXTRA_BODY` | `OPENAI_EXTRA_BODY` |
| `OLLAMA_FALLBACK_BASE_URL` | `OPENAI_FALLBACK_BASE_URL` |
| `OLLAMA_FALLBACK_API_KEY` | `OPENAI_FALLBACK_API_KEY` |
| `OLLAMA_FALLBACK_MODEL` | `OPENAI_FALLBACK_MODEL` |
| `OLLAMA_FALLBACK_DISABLE_REASONING` | `OPENAI_FALLBACK_DISABLE_REASONING` |
| `OLLAMA_VISION_BASE_URL` | `OPENAI_VISION_BASE_URL` |
| `OLLAMA_VISION_API_KEY` | `OPENAI_VISION_API_KEY` |
| `OLLAMA_VISION_MODEL` | `OPENAI_VISION_MODEL` |
| `OLLAMA_VISION_DISABLE_REASONING` | `OPENAI_VISION_DISABLE_REASONING` |
| `OLLAMA_RETRY_ATTEMPTS` | `OPENAI_RETRY_ATTEMPTS` |
| `OLLAMA_EMPTY_RESPONSE_RETRIES` | `OPENAI_EMPTY_RESPONSE_RETRIES` |
| `OLLAMA_ENDPOINT_COOLDOWN_SECONDS` | `OPENAI_ENDPOINT_COOLDOWN_SECONDS` |

Parent must migrate private V2 settings atomically with integration. Transfer the existing values, including JSON bodies/headers, unchanged. Preserve unset versus explicitly empty keys, especially auth keys. Do not materialize defaults, substitute hosts/models, borrow another account's key, or leave old remote keys as a fallback. No runtime reader accepts the old remote environment names after this cut. Do not rename unrelated local Ollama server keys by prefix.

## Key collision and fallback audit

- Before this cut, the active primary auth lookup was `os.getenv("OLLAMA_API_KEY", os.getenv("OPENAI_COMPAT_API_KEY", ""))`. Only the primary key name changes. The existing shared `OPENAI_COMPAT_API_KEY` remains a **distinct, vendor-neutral** setting and Config attribute.
- `OPENAI_API_KEY` wins whenever present, including when explicitly empty. Only an **absent** primary key uses `OPENAI_COMPAT_API_KEY`. The provider still strips the resolved key before creating its bearer header.
- `AUTONOMY_API_KEY` and `AUX_API_KEY` keep their existing unset-only fallback to `OPENAI_COMPAT_API_KEY`. They do not gain a new direct fallback to `OPENAI_API_KEY`. Control overrides and main-provider reuse continue unchanged. A dedicated base URL with an explicitly blank key remains keyless; do not infer per-field key inheritance from shorthand example comments.
- Before the rename, the only `OPENAI_API_KEY` occurrence found in active Python outside the proposed new consumer was a synthetic source string in `tests/test_publisher_scan.py`, not application auth wiring. No existing application consumer needs rerouting. Private/process configuration and external consumers were not inspected: if parent finds an already populated destination key, it must resolve that collision explicitly rather than overwrite it silently.
- Main `extra_headers` still preserve custom `Authorization` when the resolved API key is empty. A nonempty API key still wins case-insensitively and supplies `Authorization: Bearer ...`. Primary extra headers/body are not newly shared with fallback, vision or dedicated autonomy/AUX clients.
- Fallback key behavior is unchanged. Vision blank base/key still inherit the primary values. No bearer is invented for a keyless endpoint.
- `bot.py`'s incident credential registration now names the new primary/fallback/vision keys and retains the shared compat key. The provider's endpoint-secret registration is unchanged. `error_reporting.py` and console redaction use existing value/header/secret handling, not an Ollama-specific auth selector; no new logger or redactor behavior was added.

## Caller and API/UI trace

- `Config` definitions and validation; `providers.py` class, direct retry/cooldown lookups and trusted-endpoint explanation.
- `bot.py` main client, dedicated autonomy/AUX clients, nightly fallback detection, REM status/model selection, LTM summarizer hook, output budgets and incident-secret registration.
- `jobs.py` output-budget defaults; `doctor.py` required-setting diagnostics and chat probe. Local embedding probe remains separate.
- Installer help/prompts/writers and its existing probe gate, which now also requires the explicit base URL. `.env.example` and `docker/bot.env.example` use new remote names. PM2 comments distinguish remote inference from the unchanged local embedding process.
- Existing provider, bot, background, reasoning, media-isolation, configuration, deployment-template and streaming fixtures/imports were aligned; no cases/tests/assertions were added.
- Dashboard REM copy now references `OPENAI_REM_MODEL`. `autonomy_*`, `aux_*`, `deepseek_reasoning`, nightly-fallback and other control keys remain unchanged. `api/api_server.py`, `api/storage.py` and `control_defaults.py` show no persisted `ollama_*` API/control schema to migrate. No database/control-file rewrite is required by this naming cut. External imports of the old class/Config attributes do require migration; no compatibility alias is supplied.
- The REM UI's older claim that REM always shares Autonomy (rather than resolving AUX first) is pre-existing; this cut changes its env-name references only. Actual `_get_aux_provider` / `_get_aux_model` / REM routing is preserved. Parent may correct that broader UI description separately.

## Preserved wire and logging contracts

`normalize_base_url`, `{base_url}/models`, `{base_url}/chat/completions`, payload fields, sampling/reasoning rules, host/model-sensitive OpenRouter/DeepSeek handling, fallback/vision selection, retries, cooldown values and telemetry adapters are unchanged. Configured private proxies remain allowed through the existing trusted-provider connector; the untrusted-fetch SSRF resolver was not added.

The exact Python log envelope remains `%(asctime)s - %(name)s - %(levelname)s - %(message)s`. The remote logger remains `providers`; provider diagnostics were already generically labeled `Provider ...`, not local-Ollama messages. The misleading remote class/config names are gone. Incident sources, event formats and parser regexes are unchanged. `scripts/log_console/scopes.py` still classifies `providers` / `provider_telemetry` as provider and `rag_memory` as context; its existing local `ollama` service-to-provider scope mapping is deliberately preserved, not repurposed. No logging-plan implementation is included.

## Remaining Ollama references, classified

| Role | Deliberately retained references |
| --- | --- |
| Local embedding backend | `rag_memory.py` (including `OLLAMA_EMBED_URL`, `/api/embed`, fallback localhost, vector parsing, queue/breaker prose); the Config `DAME_CURIE_EMBED_*`/`EMBED_*` block; bot's local embedding startup comment; doctor embedding guidance; embedding examples and tests. |
| Local service / model management | `compose.yaml`, `docker/compose.staging.yaml`, `docker/check_embeddings.py`, `scripts/instance.py`, PM2 service and `DAME_CURIE_PM2_OLLAMA`, local installer/pull path. Images, commands, volumes, `OLLAMA_HOST`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_ORIGINS` and service names remain unchanged. |
| Local log parsing / display | `scripts/log_filter.py` health matcher; console `ollama` service scope, visibility controls and labels; GIN/Go/service fixture text in log-console and instance-log tests. These are real local-service consumers, not remote-provider aliases. |
| Vendor / protocol evidence | Ollama Cloud/minimax streaming and prefix-cache comments in providers, bot, config, autonomy and examples; `ollama-native` reasoning comments; native usage fields `prompt_eval_count` / `eval_count` and the `ollama` protocol-family fixtures in telemetry tests. Model IDs and meaningful adapter identifiers are not renamed. |
| Explicit synthetic URLs | Existing localhost/vendor URLs in URL-normalization, env-writer and non-OpenRouter protocol fixtures are explicit test inputs, not runtime inference defaults. They remain unchanged. |
| Test content | `tests/test_web_search_query.py` asks about Ollama Cloud pricing; this is user-content extraction evidence, not configuration. |
| Historical text exception | `tests/test_provider_resilience.py:264` retains `OLLAMA_EMPTY_RESPONSE_RETRIES` inside an assertion about an old audit document. It is not an environment lookup or supported alias. Its missing-doc problem predates this cut. |
| Historical / parent-owned documents | `legacy/`, historical phase audit evidence, Vulture baseline and parent-owned ledgers retain historical names. No such evidence was rewritten to match source. |

There is **no old remote Ollama text-parser compatibility alias**. The deliberate historical assertion and local-service matchers above are the only relevant exceptions, and neither re-enables an old runtime configuration key.

## Integration and validation

Parent owns private V2 migration, provisioning/runtime, combined integration and updates to `AGENTS.md`, `docs/STATUS.md`, `phase-II_v2/README.md`, `SESSION_LOG.md`, `PRUNING_MAP.md`, `PROVISIONING.md` and `LOGGING_PLAN.md`; these files are unchanged here. Their follow-up should record the new 22-key boundary and keep the Discord/Ollama activation holds intact.

Email removal is absent from this branch's base and must not be replayed here. Parent reports it integrated separately as `9b01074` and `70b8ceb`. Shared-file integration needs review, especially `bot.py` credential registration adjacent to the removed email secret, `config.py`, `.env.example`, `docker/bot.env.example` and overlapping fixtures. Preserve both the email cut and this naming cut when resolving conflicts. No email/X/Telegram behavior was modified in this branch.

Pre-existing validation hazards, not repaired here:

- `tests/test_provider_resilience.py::test_retry_defaults_match_config_and_template` expects a removed README table, `docs/CONFIGURATION.md` and `doc/html/maxwell-tool-budgets.html`. Naming its active key references does not make that historical test valid.
- `tests/test_docker_deployment.py:163` expects `ENABLE_RAG=true`, while the staging example already says `false`. Parent identified this as its staging change in base `8876dc4` and is aligning the assertion separately in main; combined integration must retain that correction and this branch's `OPENAI_API_KEY` assertion.
- `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas` still reads `.env` and can call a provider. Streaming probes also make live calls when executed. They were not run or collected.

Validation performed in the assigned worktree:

- Complete source diff/caller review, including redaction, auth fallback, protocol fixtures and parser consumers; narrow implement-sanity review found no new helper, exception wrapper, logger, dependency or unrelated refactor.
- `git diff --check` passed.
- Python **3.14.4** compile-only of all **32 changed Python files**, using parent interpreter `/home/codexy/deepseek/dame-curie/.venv/bin/python` with `-I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/openai-inference-names/.validation-cache -m py_compile` and explicit source paths; no application/test imports or execution.
- Node **v25.9.0** `--check` passed for `ecosystem.config.js`. Dashboard changes are text-only and source-reviewed; no browser/build/runtime claim.

No tests/collection, installs, network/provider/Discord requests, Docker/services/Screen commands, private configuration/state/log reads, V1 changes, merge/rebase/push, or runtime acceptance occurred. Generated compile caches are not deliverables or committed source.
