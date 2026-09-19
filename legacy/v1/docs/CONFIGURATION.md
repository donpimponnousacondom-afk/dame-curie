# Maxwell configuration quick reference

The installer writes `.env` from `.env.example` and updates only the keys it asks about. Keep `.env` private; it is ignored by git.

## Values set by the wizard

| Variable | Required? | Purpose |
|---|---:|---|
| `DISCORD_TOKEN` | Yes | Discord **user** token for the self-bot account. Treat it like a password. |
| `OLLAMA_BASE_URL` | Yes | OpenAI-compatible base URL. A bare host such as `http://localhost:11434` gets `/v1` appended by the provider code. |
| `OLLAMA_MODEL` | Yes | Chat model name served by that endpoint. |
| `OLLAMA_API_KEY` | Sometimes | ****** for hosted providers such as OpenRouter or OpenAI; blank is normal for local Ollama/LM Studio. |
| `MAXWELL_OWNER_IDS` | Strongly recommended | Comma-separated Discord user IDs allowed to run admin commands. Blank means admin commands are denied to everyone. |
| `MAXWELL_ADMIN_USER` | Optional | Admin username for dashboard/API auth (defaults to `admin`). |
| `MAXWELL_ADMIN_PASSWORD` | Strongly recommended | Password for the admin API/dashboard. Blank makes the API return 503. |
| `ENABLE_AUTONOMY` | Optional | Timed self-directed background actions; off by default to avoid surprise token spend. |
| `ENABLE_REM` | Optional | Timed memory consolidation (also accepted as `REM_ENABLED`); off by default to avoid surprise token spend. |
| `ENABLE_SHELL` | Optional | Shell tool. Requires Docker; the installer disables it when Docker is unavailable. |

See [`.env.example`](../.env.example) for the full set of advanced knobs, including embeddings, dashboard host/port, TTS, X/Twitter, email, captcha solving, and tool-specific limits.

## Compartmentalized deployment and RAG

The host-native installer above is not the rootless deployment manager. See [DOCKER.md](DOCKER.md) for private per-identity bot/API/web/Ollama services and [STATUS.md](STATUS.md) for current acceptance evidence. Container configuration lives in private `/srv/maxwell/<id>/config/bot.env`; environment changes require bot/API restart, whereas supported external prompt edits reload live.

Chat and embedding configuration are independent. Keep the existing chat `OLLAMA_BASE_URL`, model and API key when enabling the private embedder:

```ini
ENABLE_RAG=true
MAXWELL_EMBED_BASE_URL=http://ollama:11434
MAXWELL_EMBED_MODEL=qwen3-embedding:0.6b
MAXWELL_EMBED_DIM=1024
MAXWELL_EMBED_API_KEY=
```

Those DNS names apply inside the instance, not to host-native Python. Ollama has no published host port; only the instance bot/API network can reach its runtime. The separate initialization container downloads the model, then exits. The persistent model volume survives normal `down`, but is a re-downloadable cache, not a memory backup.

Vectors and the durable embedding cache are tagged by endpoint/model/dimension/input-derivation identity. Legacy untagged vectors, other backends and malformed vectors are excluded from semantic retrieval, **without deleting raw memory**. Changing the model or endpoint requires explicit re-embedding; never label existing vectors as if they came from the new model. Merely renaming a model does not prove its weights are unchanged.

`rag_maintenance.py status --db /state/data/maxwell_rag.db` reports counts only. `backfill --db /state/data/maxwell_rag.db --limit 100 --batch-size 4 --max-seconds 60` performs a bounded resumable pass using the same validated client. Invoke these inside the matching configured application image, not an unrelated host venv. `eligible_pending == 0` means all eligible rows are complete; raw `pending` also includes intentionally excluded empty/low-signal events. `ENABLE_RAG=false` sends no embedding requests. The legacy `MAXWELL_EMBED_PENDING_ON_BOOT=true` hook performs one bounded pass, not an unlimited startup migration.

Run `doctor.py --probe` only when live provider requests are intended: it probes chat as well as embeddings. Its embedding check requires a correctly sized finite nonzero vector, not merely HTTP 200. For embedding-only acceptance use the explicit maintenance path or deployment readiness check instead.

## Common provider snippets

```ini
# Local Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_API_KEY=
```

```ini
# OpenRouter
OLLAMA_BASE_URL=https://openrouter.ai/api/v1
OLLAMA_MODEL=moonshotai/kimi-k2.6:free
OLLAMA_API_KEY=your-openrouter-key
```

```ini
# OpenAI
OLLAMA_BASE_URL=https://api.openai.com/v1
OLLAMA_MODEL=gpt-4.1-mini
OLLAMA_API_KEY=your-openai-key
```

```ini
# LM Studio
OLLAMA_BASE_URL=http://localhost:1234/v1
OLLAMA_MODEL=the-loaded-model-name
OLLAMA_API_KEY=
```

## Custom request options and OpenRouter routing

`OLLAMA_EXTRA_BODY` and `OLLAMA_EXTRA_HEADERS` accept JSON objects, defaulting to `{}`. Header values must be strings. Invalid JSON/non-object values stop startup rather than silently dropping routing restrictions. These options require an application image built from the updated source and a bot restart; changing only the production `.env` does not update an older image.

For per-request DeepInfra routing without account/workspace-wide provider changes:

```ini
OLLAMA_BASE_URL=https://openrouter.ai/api/v1
OLLAMA_MODEL=openai/gpt-oss-120b:nitro
OLLAMA_DISABLE_REASONING=false
OLLAMA_EXTRA_BODY='{"provider":{"only":["deepinfra"]}}'
OLLAMA_EXTRA_HEADERS={}
```

Keep the existing OpenRouter key in `OLLAMA_API_KEY`. Provider selection is a **body** field, not a header. Availability and account-level restrictions still apply; `only` does not override them. See [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection). The base slug `deepinfra` allows its variants; use `deepinfra/turbo` to target that endpoint specifically. `:nitro` prioritizes throughput among eligible endpoints; it is not itself a provider pin.

To request an explicit reasoning effort, add it to the same object, for example `OLLAMA_EXTRA_BODY='{"provider":{"only":["deepinfra"]},"reasoning":{"effort":"high"}}'`. For other models this is opt-in: `OLLAMA_DISABLE_REASONING=false` alone sends no effort level. DeepSeek V4.1 Flash is explicitly parameterized as described below. Explicit per-call disabling (including auxiliary calls) takes precedence over custom reasoning fields. Supported effort levels depend on the selected model/provider; see [OpenRouter reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

For OpenRouter app attribution, set HTTP **headers**, not body fields:

```ini
OLLAMA_EXTRA_HEADERS='{"HTTP-Referer":"https://council.zombiedawn.net/","X-OpenRouter-Title":"Dame Curie: Always Teasing"}'
```

`HTTP-Referer` is the app's URL/unique identifier; `X-OpenRouter-Title` sets its display name. OpenRouter still accepts `X-Title`, but the title alone does not create an app entry. Attribution opts the app into public rankings/analytics; see [OpenRouter app attribution](https://openrouter.ai/docs/app-attribution). Use your own app URL/title for another identity.

Merge these into any existing `OLLAMA_EXTRA_HEADERS` object; leave `OLLAMA_EXTRA_BODY`, routing, model and credentials unchanged. The configured API key takes precedence over any case variant of `Authorization`. For the current Curie deployment, edit private `/srv/maxwell/curie/config/bot.env`, not the development checkout `.env`, then coordinate a bot/API `restart` through the [instance operator](SCREEN_WORKFLOW.md#stop-start-restart). The deployed image already supports these options; no image rebuild is needed.

Scope and precedence:

- Options apply only to the main client's **primary endpoint**, including background/auxiliary calls that reuse that client and primary model overrides. They are not inherited by fallback, vision, or separately constructed autonomy/auxiliary clients—even on the same host. OpenRouter's `provider.only` does not disable Maxwell's separately configured fallback endpoint.
- Runtime-owned `model`, `messages`, `temperature`, `top_p`, `top_k`, `max_tokens`, `stream`, `stream_options`, `tools` and `tool_choice` take precedence. Use their existing configuration/call arguments rather than extra-body overrides.
- Each request gets its own copy of the extra body, preserving configured routing through retries without sharing mutable nested state. Existing retry/streaming/telemetry behavior remains authoritative.
- Headers can contain credentials: keep them in private instance configuration, never source control or public files. Clear endpoint-specific options when changing the main endpoint.

## DeepSeek V4.1 Flash reasoning controls

Primary Discord commands use the configured prefix (`!` here). Anyone can report; existing bot administrators can change settings:

| Command | Effect |
| --- | --- |
| `!reasoning` | Report requested/effective primary reasoning and exact wire fields |
| `!reasoning low` / `high` / `max` | Persist the chosen hosted tier; apply to subsequent primary requests without restart |
| `!reasoning off` | Explicitly disable reasoning on the verified hosted routes |
| `!effort` | Report the exact integer or named tier currently selected |
| `!effort 1` through `!effort 100` | On OpenRouter, persist and send that exact integer; no rounding or conversion to a named tier |

Root explicitly authorized full numeric passthrough on OpenRouter, even if the advertised API schema rejects it. The V4.1-specific [reference encoder](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md) supports integer 1–100; `low`, `high`, and `max` are aliases for reference values 50, 75, and 100, not an independent second effort axis. `!effort 37` stores JSON integer37 and sends `reasoning: {"enabled": true, "effort": 37}`. `!effort 50/75/100` also sends integers—not strings. Named `!reasoning low/high/max` commands retain their existing string-tier behavior; both commands update the same primary setting. Invalid/out-of-range input is refused without changing settings. A provider rejection is retained with its complete received body and request metadata for `!error`; it never causes silent tier substitution. Do not claim OpenRouter honors the numeric value merely because local tests pass. Direct DeepSeek API numeric-command behavior is unchanged: only reference presets50/75/100 map to named tiers there. Numeric commands are deployed in `maxwell-app:c010a37`; see [STATUS.md](STATUS.md) for acceptance and current runtime evidence.

For OpenRouter's `deepseek/deepseek-v4.1-flash`, every request explicitly includes `reasoning: {"enabled": true, "effort": "high"}` by default; off sends `{"enabled": false, "effort": "none"}`. Official DeepSeek `deepseek-flash` (including the documented transitional Flash aliases) instead receives `thinking: {"type": "enabled"}` and `reasoning_effort: "high"`; off explicitly sends `disabled`/`none`. A persisted `deepseek_reasoning` control overrides the configured primary baseline. Explicit per-call disable/enable overrides retain precedence, including auxiliary calls. Fallback/dedicated clients do not inherit the primary command override; matching DeepSeek calls still receive explicit parameters. Other models are unchanged.

No dashboard UI was added. Commands report actual loaded primary configuration; environment changes still require the normal operator restart. Preserve custom routing and attribution when changing the baseline.

## Independent normal and HD image configuration

The two image profiles never inherit `OLLAMA_*` chat credentials/model/routing or one another's key. Normal `IMAGE_GEN_PROTOCOL=pollinations` retains the keyless legacy generator; `images` explicitly selects native `/images/generations`. HD `GEMINI_IMAGE_PROTOCOL=chat_completions` retains the existing Gemini-compatible adapter; `images` selects native generation and JSON `/images/edits` with `images[].image_url` references. Native responses use `data[0].b64_json`. Existing names are retained for compatibility; a GPT image model belongs on the native protocol, not the chat-completions route.

Curie's intended local-proxy profiles (set both dedicated keys privately, not in source):

```ini
IMAGE_GEN_PROTOCOL=images
IMAGE_GEN_BASE_URL=http://192.168.241.2:8317/v1
IMAGE_GEN_API_KEY=
IMAGE_GEN_MODEL=gpt-image-2.5-flare
IMAGE_GEN_QUALITY=low
IMAGE_GEN_TIMEOUT=300

GEMINI_IMAGE_PROTOCOL=images
GEMINI_IMAGE_BASE_URL=http://192.168.241.2:8317/v1
GEMINI_IMAGE_API_KEY=
GEMINI_IMAGE_MODEL=gpt-image-2.5-sunburst
GEMINI_IMAGE_QUALITY=max
GEMINI_IMAGE_TIMEOUT=600
```

Flare/low expresses the speed-oriented request and Sunburst/max the maximum-quality request supported by [OpenAI's documented model family](https://developers.openai.com/api/docs/guides/image-prompting). **The current local proxy does not demonstrate that distinction:** both live probes returned `quality=low`, roughly 1.57 megapixels and similar latency, and the updated local toolkit's broader measurements report ignored quality/size/format/count settings and no observable difference among 2.5 aliases. No actual slower/higher-quality execution, chosen canvas, or transparent output is promised. These fields are still sent explicitly; changing Curie's labels cannot unlock a capability the gateway ignores.

A blank dedicated base rejects requests before image fetching/generation. A blank key permits deliberately keyless gateways; it does not borrow chat auth. Native generation submits exactly one POST with redirects disabled. Timeout, HTTP failure, unrecognized/empty result or decode failure never triggers another generation or silent provider fallback. Native HD references preserve original bytes; only the legacy chat adapter uses `GEMINI_IMAGE_MAX_INPUT_EDGE` shrinking. Existing Discord delivery, permanent image persistence and same-turn preview suppression remain intact.

The configured proxy address is private, not host loopback inside a container. Host port8317 remains bound only to127.0.0.1. The rootful proxy's extra internal bridge `maxwell-curie-cpa` uses `192.168.241.0/29` and fixed proxy address192.168.241.2, avoiding Curie's independent rootless172.17 routes. It exposes no Docker socket to Curie. After **recreating** `cli-proxy-api` (an ordinary restart retains attachment), reattach the existing private network using `sudo docker network connect --ip 192.168.241.2 maxwell-curie-cpa cli-proxy-api` and verify reachability/authentication before image use. Do not publish the proxy publicly or disable rootless host-loopback isolation.

Both tools remain under `ENABLE_IMAGE_GEN` and independently disableable runtime tool controls. Native support requires the updated image; see [STATUS.md](STATUS.md) for source versus deployed evidence.

### Image request console logs

Both `image_generator` and `hd_image` emit `Image request start` and `Image request done` INFO records as single-line JSON. A shared `request_id` pairs concurrent calls. Start records show the actual requested model ID, sanitized API endpoint, protocol, generation/edit operation, quality, input-image count, delivery flag, timeout, and **the exact outgoing prompt**. JSON escaping preserves newlines/Unicode without paraphrasing or clipping native/chat prompts. Pollinations keeps its existing 1,500-character request limit: `prompt` is what was sent, and `requested_prompt` retains the original when it differs; seed/dimensions are also logged. These fields identify the request sent to the configured gateway, not proof of which upstream model an alias ultimately resolves to.

Done records report elapsed request/decode milliseconds, HTTP status (null when no response arrived), outcome, output byte count/format, exception type and private incident ID. Outcomes distinguish connection failure, HTTP rejection, non-JSON data, image decoding failure, timeout and cancellation; successful generation is not proof of Discord delivery. No request retries or delivery behavior are added.

Root explicitly requested complete prompt visibility in the operator console. Treat these logs as private conversation data. Known raw/URL-encoded credentials and authentication material are redacted; endpoint userinfo/query/fragment, edit-image data and response bodies are not emitted. Existing image-tool result summaries are redacted before their 200-character console limit; model-facing results remain unchanged. Full received failure diagnostics stay in the existing admin-only incident history, correlated by `image_request_id`.

## Provider retries

`OLLAMA_RETRY_ATTEMPTS` defaults to **5 total attempts** (range 1–10), not five retries. Explicit environment values override this default. Transient failures wait **10, 20, 30, 40 seconds** before attempts 2–5; the delay is linear and also applies when switching endpoints. Deterministic request rejection/failover and corrected-payload retries do not use this backoff, but still consume the fixed attempt budget.

With a fallback configured, ordinary routing uses the primary for attempts 1–2 and the fallback for later attempts; endpoint cooldown and caller-requested fast/preferred fallback still apply. Fast fallback retains its shorter two-attempt budget. `OLLAMA_EMPTY_RESPONSE_RETRIES` (default 2) reserves up to that many remaining attempts for non-streaming empty-content recovery; it never increases the total budget. Caller-specific deadlines remain unchanged and may cancel a request before all attempts and the default 100 seconds of backoff finish.

Recognized JSON/+json and SSE response Content-Types determine HTTP 200 decoding; missing or other types retain requested-format parsing for gateway compatibility. Explicit JSON/SSE error envelopes fail even after partial output; diagnostics contain allowlisted error code/type, a message-derived category, and numeric framing information, never raw error bodies or message previews. Unknown error labels are reported as unknown. Unterminated SSE tails fail instead of silently losing output. Malformed JSON frames remain skippable with numeric diagnostics; this is not a full SSE framing rewrite.

## Per-call provider measurements

`!debug` (or the configured command prefix) shows the running client's loaded primary/fallback model and provider hostname before its process-local measured-reply section. No completion or provider probe is needed to inspect the loaded configuration. This is not a reread of edited environment files or a guarantee of the next request's route: fallback and per-call overrides can differ. Measurements still belong to their original response and disappear when the process restarts. The debug report uses fenced code blocks without an unmeasured TTFT/TPS footer; endpoint credentials, paths, query strings and raw request options are not displayed. Requires the updated image; see [STATUS.md](STATUS.md).

Streaming requests send `stream_options: {"include_usage": true}`. An explicit unsupported-option HTTP 400/422 teaches that endpoint to omit the option for this process. A corrected request stays on that endpoint and consumes a remaining attempt; it never adds an attempt or overrides the five-attempt ceiling. Non-streaming requests omit the option.

Measurements travel with the returned response, not a shared provider's last-call record:

- **TPS** is generated output tokens, including reasoning, divided by the **successful HTTP attempt's full elapsed seconds**, consistently for SSE and JSON. This is end-to-end request throughput, not server-side decode speed or a short arrival-burst rate. Failed attempts, backoff, other tool-loop calls and unrelated requests are not accumulated into this sample; the successful attempt number is retained.
- **TTFT** starts when that request is sent and ends at its first observed generated text, reasoning, tool name or arguments. Roles, IDs, usage-only frames and opaque signatures do not start it. JSON/non-streaming cannot reveal first-token arrival: total response time is used as an explicitly estimated proxy. Parsing uses actual recognized response Content-Type rather than assuming the requested stream mode.
- **Reported counts win.** Canonical OpenAI completion/output totals already include their reasoning breakdown; it is not added twice. Known separately reported Gemini candidate/thought counts, Ollama count aliases and consistent reported total-minus-input counts are recognized. Partial SSE usage trailers preserve earlier valid fields; later valid corrections replace rather than accumulate counts. An output count of zero despite observed generated output is treated as an unavailable placeholder, not a fabricated zero-throughput measurement.
- **Missing counts use fixed CL100K estimates**, with pinned `tiktoken` and the verified local vocabulary in `assets/tokenizers/`. No tokenizer network download occurs during inference. Reasoning promoted into an answer and parsed custom-tool JSON are counted only once. If only reasoning is reported, visible output is estimated separately and provenance is marked mixed. Unreported hidden reasoning remains unknown.
- Estimated input uses compact JSON framing for textual messages and tool schemas. It is a comparable local approximation, not the model's exact chat template; structured media payloads and opaque signatures are excluded, so unreported media token costs remain unknown. Input counts mean tokens for this request, not context-window capacity.

Required tokenizer dependencies and vocabulary must be installed together. The local tokenizer is initialized before generation, so a missing or corrupt required asset fails before a paid request rather than retrying an otherwise successful completion.

## Reconfigure

From a cloned checkout:

```bash
./install.sh --local --reconfigure
```

Or, for an existing install made by the one-liner:

```bash
cd ~/maxwell
./install.sh --local --reconfigure
```
