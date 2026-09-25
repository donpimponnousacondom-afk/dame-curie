# dame-curie: historical dependency map for surgical cuts

**Retained evidence, not current authority.** The integration queue and audit below describe earlier source/runtime states. Their confirmation/taint, staged-resource, publisher-readiness and grant assertions must not be read as current guarantees or fresh human instructions. Current boundaries are `../AGENTS.md`, `../SECURITY.md`, `../docs/STATUS.md` and `../TODO.md`. Preserve this map through accepted round two; consolidate unique surviving facts before retirement.

## Historical integration queue — earlier recorded decisions

- The earlier V2 foundation was provisioned under the separate grant in `PROVISIONING.md`. Its last handoff reported API/web running and bot/Ollama/pull/shell created but never started; **runtime was not re-observed in this documentation round**. The coordinator must reconcile after reviewed source integration. Keep bot credentials blank, bot entrypoint never started, RAG false, Ollama/pull stopped and model storage empty; V1 remains protected.
- **Email: source removal reviewed and integrated** as `9b01074`/`70b8ceb`, from isolated branch `work/prune-email-20260919`; shared inbox, confirmation/taint, JSON/tasks, media and provider infrastructure remain. Main-only UI follow-up landed in `df6c97e`; the earlier staged images included the cut. See `EMAIL_REMOVAL.md` and the separate staged acceptance in `PROVISIONING.md`.
- **Remote inference naming: reviewed and integrated** as `b2f5380`, from isolated branch `work/openai-inference-names-20260919`. `OPENAI_*` means the compatible remote protocol, not OpenAI's service. Eighteen configured private V2 keys were atomically migrated from the 22-key map without changing values; local Ollama embeddings remain separate. See `INFERENCE_NAMING.md`.
- **Discord-only redesign is now explicitly approved and underway.** The authoritative cut/protection contract is `REDESIGN_PLAN.md`; lane commits, reviews and integration state are in `REDESIGN_PROGRESS.md`.
- **Logging integrated first**, per the coordinator's source handoff, using `LOGGING_PLAN.md`: opt-in `logs --format screen [--no-keys]`, append-only normal screen with no repaint; legacy/default modes, redaction and functional memory stay. Source integration is not terminal acceptance; detailed review state belongs in `REDESIGN_PROGRESS.md`.
- **Approved removals:** X/Twitter, Telegram, companion/GF second account, dashboard/API/OAuth/Caddy/web image, local website/KV/FastAPI/uvicorn servers and six `site_*` tools, human CAPTCHA HTTP fallback and separate nested shell infrastructure. No replacement server; outbound CapSolver/TwoCaptcha remain. Historical `tg:%` privacy filtering is not active Telegram.
- **Direct shell:** Bash inside the outer V2 bot container, `/home/dame-curie` → `/state/shell`, explicit cwd/HOME, DEVNULL stdin and process-group cleanup. Same-UID shell can read bot-readable secrets; it is not an inner security boundary. No host-root/network, nested Docker or engine socket access.
- **Deployment:** bot/Ollama/pull only, no published ports or PM2. Staged omitted/true `up`/`start`/`restart` validates but starts nothing. All-profile orphan cleanup goes only through the ownership-checked V2 wrapper. No checkout listener/socket bridge; an archive image without `.git` gives unknown checkout metadata through the existing build-capture fallback, not proof from OCI labels.
- **Protected:** publisher/syncer and `scripts/publisher/**`, `/state/sites` authoring, `_images` files/sidecars and external mirroring, outbound providers/media/YouTube, Discord administration/autonomy/games/plugins, shared inbox, independent authorization/redaction and functional RAG/REM/graph memory. The model writes locally, never administers the remote. No PHP/Perl/CGI installation. V2 publisher activation/destination is unestablished; reserved `.invalid` examples are not a V1 destination.
- **Prefix/jobs:** canonical `!command` throughout active help/prompts/docs/docstrings. `!bg GOAL` remains free prose; optional `--provider main|autonomy|aux` / `--model MODEL` header requires `-- GOAL`. `spawn_background` accepts profile/model, not URL/key/header. Same-role configuration is required for explicit routing, default main remains unchanged, overrides affect primary only and configured fallback may answer. Jobs use canonical personality/origin server prompt, with goal/context in user role. No real provider/Discord acceptance; authoring/personality tuning is deferred.

**Everything below is the preserved historical `a9c0fba` audit.** Source line anchors, comma-prefix examples, API/PM2/site consumers, proposed future choices and no-execution claims describe that earlier assignment; they are not current capability/operating instructions or a request to ask root for already-approved scope. Current contracts are `REDESIGN_PLAN.md`, `../docs/ARCHITECTURE.md` and `../docs/OPERATIONS.md`.

## Historical audit starting point

- **Source baseline:** `a9c0fba` on `dev/phaseII_v2`. All source line references below refer to that unchanged application snapshot. This is a bounded static map, not runtime acceptance or proof that deployed V1 has identical source.
- **Root's destination:** remove DNS provisioners, email and Twitter/X; determine YouTube's actual scope; preserve working TTS/image generation; establish application-subagent routing and logging boundaries. **Tools and the scattered website prompts are the highest-priority design problem.**
- **This assignment changed documentation only.** No removal, refactor, prompt correction, provider change, test creation/execution/collection, application import, runtime query, private-state read, remote request or deployment was authorized/performed. `scratch-mermaid/` is unrelated work and remains untouched.
- **Subsequent explicit assignment:** root authorized a separate report-only Vulture setup/pass, recorded in `DEAD_CODE_PASS.md`. That later AST scan is not part of the read-only mapping claims here and did not remove application code.
- **Next implementation must be one named slice.** If it reaches another subsystem, report the edge before changing that subsystem. Leaving unused code temporarily is preferable to speculative repairs. No batch implementation of this document.
- Three read-only `gpt-6-astra` scouts covered removal candidates, protected media, and application jobs/logging. Coordinator traced tools, prompt assembly and publishing, then reconciled the shared edges. Root explicitly selected same-model scouts for this assignment; earlier Flash/Luna review belongs to the preceding naming checkpoint.

## Decision board

| Surface | Current source finding | Decision boundary |
| --- | --- | --- |
| DNS provisioning | Two standalone scripts already quarantined | Separate archive-only removal candidate; do not alter actual DNS/mail infrastructure |
| Email | Four tools plus an independent notification poller | Candidate feature cut; keep shared inbox, confirmation/taint, JSON and task infrastructure |
| Twitter/X | Tools, admin commands, client, mentions poller and controls | Candidate feature cut; keep inbox and generic Twitter Card media metadata |
| YouTube | Search/catalogs, metadata, captions, thumbnails, requested frames; several hidden callers | Keep while scoped; no dedicated full-video/audio export interface found in this tool |
| TTS | Tool and VC have different fallback chains; Fish-labelled helper calls PPQ | Protect existing behavior and manual workaround; synthesis and delivery are separate seams |
| Image generation | Two provider-profile families plus shared media storage/delivery | Protect `_images`, public serving and attachment/edit-input paths; not the same thing as website authoring |
| Background jobs | Built-in jobs reuse the main provider; no per-job route selection | V2 requirement gap, not fixed here; Discord threads are a separate delivery concern |
| Logging/console | Several distinct observability and memory surfaces | Do not treat all files or classes named log/trace as disposable diagnostics |
| Tools/site prompts | Editable personality/server prompts coexist with code-owned policy, schema prose and result guides | Primary next design slice; no wholesale tool/runtime rewrite |

**Container count is not feature count.** The earlier dated inventory records 19 running containers using five distinct image IDs: bot/API share app, plus web, Ollama, shell and one site runtime used by fourteen site backends. This is not a fresh query, an unused-image inventory or permission to delete those sites. See `DOCKER_INVENTORY.md:15-85`.

## 1. Tools and website prompting — the critical boundary

### Actual contract distribution

| Surface | Source anchors | Editable through current prompt storage? |
| --- | --- | --- |
| Personality | `prompt_storage.py:19-29,75-105`; `bot.py:4130-4141` | Yes: external `personality.txt`, or `base_personality` in runtime control JSON |
| Per-server instructions | `prompt_storage.py:50-73`; `rag_memory.py:2395-2402`; `api/api_server.py:593-625` | Yes: external `servers.json`, or runtime `prompts.json` |
| Base knowledge and shared tool policy | `bot.py:2268`, `2423-2538`, `16654-16685` | No; source constants are independently assembled with editable text |
| Tool descriptions | `bot_tools.py:5243-5269`, `5708-5726`, `5964-5988`, `6227-6238` | No; `get_description()` recomputes source-owned strings, not operator-editable policy |
| Native argument descriptions | `tool_schemas.py:373-498` | No; separate source-owned parameter prose and schemas |
| Native/text contract assembly | `bot.py:16095-16166`; `tool_schemas.py:997-1116` | No; combines registry, descriptions, parameter schemas and result semantics |
| Tool-returned instructions | `bot_tools.py:5541-5564`, `5848-5852`, `5918-5939`; `site_backend.py:358-375`; `site_server.py:1197-1220` | No; guides re-enter the next model turn through tool results |
| Background-job system text | `jobs.py:514-548` | Separate source-owned assembly; reuses tool policy but not the normal live-personality reader |

**The earlier dynamic-prompt promise is only partly implemented.** Personality and server text can change without editing Python. That does not replace the tool protocol, descriptions, schema explanations or result guides. Calling a description "live" means it is read from a tool instance at request time, not that an operator can edit it outside source.

Registration and dispatch are additional seams, not prompt text: `bot.py:3932-4057` registers gated built-ins and loads plugins; `15984-16055` filters tools and merges user/platform plugin availability. `tool_schemas.py:842-924,984-1006` defines result/turn-ending semantics. `tool_registry.py:129-139` removes reasoning arguments before execution. Retain these mechanics when extracting wording; moving only `bot_tools.py` does not centralize the contract.

Native descriptions are capped at **1024 characters**, with result semantics appended afterward (`tool_schemas.py:1038,1063-1069`). The text/XML path uses full descriptions (`bot.py:16147-16160`). Long hotfixes therefore do not have identical visibility across paths. No payload or model response was executed to measure effects.

### Confirmed contradictions — recorded, not repaired

1. **Remote PHP/Perl prose versus local Python execution.** Commented-out mandatory FastAPI/uvicorn text was replaced by active remote-host instructions in `bot.py:2480-2489`, `bot_tools.py:5251-5267,5966-5987`, and `tool_schemas.py:398-411,455-489`. Yet `SiteServerTool` requires `app.py`, writes code under private data and starts the local Docker backend (`bot_tools.py:6017-6079`; `site_server.py:900-970`). Its image ends with `CMD ["python", "app.py"]` (`docker/site-runtime/Dockerfile:10-45`). Changing its description to `app.php` did not change its executor.
2. **The `backend` boolean means a local JSON KV/collection service**, not "deploy a remote PHP application" or "start a Python server". Creation records this flag and returns the KV guide (`bot_tools.py:5500-5547`); storage is `DATA_DIR/site_data/<slug>.json` (`site_backend.py:14-21,72-75`). `site_server` is a separate mechanism.
3. **Result text reintroduces local instructions.** `site_server.contract()` still specifies Python, FastAPI/uvicorn, `/bot/<slug>/api`, `/data` and local containers. `site_backend.client_guide()` describes the local same-origin `/api/site/<slug>` service. A personality edit cannot replace these tool results.
4. **Local browser checks are not remote acceptance.** In container mode `SiteTestTool` substitutes `http://web:8080/bot` (`bot_tools.py:6253-6262`). Its inherited base URL comes from the general public origin, not the website-specific override (`5648-5656`); full URLs must match that site's origin/path (`site_test.py:154-178`). A successful local probe does not establish the advertised remote site's backend behavior.
5. **Publishing copies files; it does not transport the local runtime.** Create/edit writes public site files; publisher watches its configured source and mirrors site directories, with a separate non-deleting image archive (`scripts/publisher/service.py:43-98`; `mirror.py:36-48,80-97`). Local Python server code/state is under the separate data tree, not automatically deployed as a remote server. Changing a public URL is not route/runtime synchronization.

Root reports a shared remote web host without the local Python/uvicorn service capability. That statement is the operating constraint, not permission to inspect the host. Two distinctions remain explicit: the publisher's SSH transfer guard itself invokes remote `python3` (`scripts/publisher/transport.py:41-66`), which is not a hosted Python web server; `scripts/publisher/static.htaccess:1-8` is a static-only template, but the inspected publisher Python modules do not reference/install it. Its existence does **not** prove the remote site's effective policy. No host capability or policy was tested.

### Keep these runtime pieces separate

| Piece | Actual responsibility / important dependency |
| --- | --- |
| `create_site` / `edit_site` | Public files and metadata; image import can use `send_file`'s allowlist and shell export (`bot_tools.py:5393-5473`) |
| `site_backend.py` | JSON KV/collection service **and a shared RateLimiter used by the API** (`api/api_server.py:27-39,812-813,1018`) |
| `site_server.py` | Local per-site Python containers and private code/state; API proxy resolves their verified endpoints (`api/api_server.py:1134-1165`) |
| Caddy/API | `/bot/*` public files, `/api/site/*` KV routes, `/bot/<slug>/api/*` local server proxy (`docker/Caddyfile:12-20`; `api/api_server.py:2583-2592`) |
| Publisher | Filesystem watcher plus guarded SSH/rsync mirror; no automatic PHP/ASGI runtime or URL rewrite inferred |
| `site_test` | HTTP/browser observations of its selected target; not a publisher-completion or remote-backend guarantee |
| Shared media artifacts | Image-generation outputs, source for image editing and attachment delivery, public links and optional remote archive |

**Import coupling also matters:** `bot_tools.py:44-46` imports all three site modules unconditionally. Deleting their files while retaining current `bot_tools` breaks module loading even if the website feature gate is off. Disabling website registration is not deleting its imports, public storage or routes.

## 2. Removal candidates

### DNS provisioners

The two archived files are standalone Cloudflare/Mailgun-oriented setup programs, not SMTP/IMAP implementations: `legacy/v1/email_integration/setup_dns.py:160-269,288-289` and `setup_dns_legacy.py:166-275,294-295`. The assigned archaeology was restricted to those files. No active caller was found in the inspected source; external/manual automation remains unknown.

A future archive-only deletion can concern those two files and index references. It must not remove DNS records, domains, mail routing, SPF/DKIM/DMARC, resolver behavior or external services. Removing an uninvoked provisioning script does not remove already-provisioned records. They were already removed from active source paths at the naming checkpoint; deleting their archive is not necessary to disable a bot capability.

### Email

- Four gated tools: `email_send`, `email_read_inbox`, `email_get_message`, `email_search` (`bot.py:4042-4046`; `config.py:315-320,528-538`). Send uses stdlib SMTP/STARTTLS; reads use IMAPS (`bot_tools.py:10675-10712,11206-11427`). No DNS-provisioner call is part of that transport path.
- Separate `EmailInboxPoller` construction/scheduling: `bot.py:3872-3889,5468-5474`; configured check and notice insertion: `email_inbox.py:301-302,336-395`. It also owns `email_poll_state.json` logic (`123-144`). Removing tool registration alone is not removing polling.
- Full feature boundary: mail wrappers and mail-local helpers, `email_inbox.py`, bot import/construction/tasks/control hooks, configuration and schema/catalog references. A poller-only cut is smaller if root wants to retain on-demand mail temporarily.
- **Keep:** shared `InboxStore`, `inbox_list`/`inbox_act`, friend/group/guild notices, taint/confirmation, incident handling, shared JSON/file locks and task infrastructure. Mailbox contents and existing state are not cleanup targets.

### Twitter/X

- This is more than two tool registrations: unconditional client import (`bot.py:368`), gated construction (`3894-3929`), `x_read`/`x_post` (`4051-4053`), admin command path (`7883-7884,8274-8336`), mentions task (`5475-5485`), live controls (`4747-4762`), autonomy-post gate (`autonomy.py:1303-1311`) and shutdown (`bot.py:18629-18635`). Deleting `x_client.py` alone breaks the import.
- Read backends are cookies, configured gateway, RSS and syndication, with different supported modes (`x_client.py:902-906,946-950,1349-1378,1509-1530`). "No credentials" does not mean every read operation is supported. The client has its own HTTP session (`1414-1420`).
- Feature-owned state includes `x_graphql.json`, `x_post_log.json` and `x_poll_state.json` source paths (`x_client.py:1233-1234,1345-1368,1650`); mentions are written to the shared inbox (`1743`). No live state was read or designated for deletion.
- **No image-generation call was found in the traced X paths.** Cookie posting sends an empty media-entities list (`x_client.py:727-745`). This is a scoped observation, not proof covering unknown runtime plugins.
- **Keep generic Twitter Card metadata.** `twitter:image` / `twitter:player:stream` in `bot.py:12875-12898` are website-media metadata consumed by generic GIF/media handling (`12977-12989`), not the X client. Do not globally delete strings containing Twitter.
- Full candidate boundary includes X wrappers/client and the enumerated wiring/schema/control/config surfaces. Keep shared inbox, HTTP libraries, JSON helpers, redaction, taint/confirmation and generic media. Existing X-specific harness/fixture references need disposition within that future slice, not a new absence-test campaign.

## 3. YouTube scope — keep

`YouTubeTool.execute` implements genuine query search plus channel/handle/playlist/search-URL catalog listing (`bot_tools.py:9627-9700`), video metadata, captions and visual context. It is not merely a link formatter, and the inspected dedicated tool has no full-video/audio download/export interface.

| Capability | Source behavior |
| --- | --- |
| Search / lists | `ytsearch` and flat-playlist/catalog JSON; query is an actual argument (`tool_schemas.py:633-647`; `bot_tools.py:9668-9700`) |
| Transcript | Direct timedtext, then yt-dlp supplied/automatic subtitles (`9305-9399`); **not** speech-to-text over downloaded audio; missing captions reported explicitly (`9741`) |
| Metadata | oEmbed and yt-dlp JSON (`9401-9433`) |
| Frames | Up to six explicitly requested timestamps via stream resolution and ffmpeg (`9435-9489`); no timestamps means no frames (`9235-9238`) |
| Thumbnail | HTTP fallback supplying vision-image markers (`9492-9521,9717-9720`) |

Inbound edges are important: chat automatically invokes it before the model (`bot.py:14054-14095`), autonomy can inspect recent links (`autonomy.py:2466-2518`), and generic media intake plus `see_video` call its URL classifier (`bot.py:13096-13120,13224-13235`; `bot_tools.py:8980-8983`). Downloaded subtitles/frames/temp bytes are different from a user-facing movie download feature. Other general-purpose tools were not exhaustively assessed for arbitrary downloading.

Preserve yt-dlp/yt-dlp-ejs, its JS-runtime support, optional cookie-path handling, shared HTTP/vision handoff and ffmpeg. FFmpeg also supports speech/voice: removing a YouTube dependency by package name can break another subsystem. No YouTube cut is recommended here.

## 4. Protected media

### TTS: provider selection is not delivery

| Entrypoint | Current executable path |
| --- | --- |
| `tts` voice-message tool | Fish-labelled/PPQ helper when keyed → NVIDIA Riva → gTTS; **no espeak branch in this tool** (`bot_tools.py:9970-10091`) |
| VC synthesis | Conditional local-espeak-first → PPQ → keyed Riva → gTTS; a Riva exception can also try espeak (`bot.py:747-924`). Not an unconditional local fallback |
| Manual / automatic voice | Manual VC command and automatic reply playback have different gates (`bot.py:8338-8343,8459-8496,8995-9052`) |

The active shared Fish-labelled helper posts to **`https://api.ppq.ai/v1/audio/speech`**, with `model`, `input`, `voice` and hard-coded `language="en"`; the Fish endpoint/payload is commented out (`bot_tools.py:292-328`). Its `fmt` argument is not included in that active payload. Preserve this known manual compatibility patch until TTS itself is assigned.

`FISH_API_KEY`, voice/reference settings and NVIDIA credentials influence runtime choices; TTS generally reads environment per call. `TTS_ENGINE` influences VC's local-first condition, not selection of a single remote tool provider. Live VC controls are another layer (`api/state.py:368-379`; `control_defaults.py:272-276`; `bot.py:9025-9040`). NVIDIA/Riva is also used by live ASR (`bot.py:965-979`), so it is not an image-only dependency.

Delivery remains separate: Discord voice-message upload needs format conversion, duration/waveform helpers; Telegram has its own voice/audio adapter; VC plays WAV using Discord audio facilities and receive/reply coordination (`bot_tools.py:10093-10249`; `bot.py:2023-2064,2121-2125,9005-9052`). Do not collapse these into "three TTS providers".

### Image generation: protect artifact infrastructure

- `image_generator`: Pollinations path by default, or explicit OpenAI-style `images` endpoint/profile (`config.py:438-446`; `bot_tools.py:1327-1359,1426-1445,1640-1656`). It does not borrow the chat endpoint when its dedicated endpoint is absent.
- `hd_image`: dedicated `GEMINI_IMAGE_*` profile, choosing `chat_completions` or `images` protocol; generation/edit selection follows reference presence (`config.py:466-482`; `bot_tools.py:1682-1693,1800-1887`). The namespace does not prove the upstream provider is Gemini. No cross-provider failover was established in this path.
- Both default to save-first, `auto_send=False`. They persist under `DAME_CURIE_SITE_DIR/_images`, with best-effort redacted prompt sidecars; default save failure is not repaired by automatic regeneration (`bot_tools.py:1231-1285,1367-1423,1890-1951`). `auto_send=True` has a distinct possible byte-delivery path when persistence fails.
- Public image URLs use the general `DAME_CURIE_PUBLIC_BASE_URL` plus `/bot/_images`, **not** `DAME_CURIE_SITE_PUBLIC_BASE_URL`. Preserve that root, Caddy route/mount, send-file allowlist and HD local-reference allowance (`bot_tools.py:1231-1245,1769-1784,7414-7433`; `docker/Caddyfile:18-20`; `compose.yaml:59-64,218-223`). Memory recording is another consumer.
- Publisher archival of `_images` and matching `.txt` sidecars is downstream, separate from provider generation (`scripts/publisher/mirror.py:45-48,86-88`; `scan.py:156-169`). Turning off website tools is not equivalent to deleting media storage or stopping publication.

Prospective seams, not an implementation order: speech policy/adapters; platform speech delivery; image provider/reference loading; media artifact storage/addressing; website authoring; remote publication. No direct DNS/email/X implementation call was found in the inspected protected-media request paths.

## 5. Application background agents

**Built-in `spawn_background` / `,bg` does not support an independent per-job model/provider selection in the inspected path.** Its schema carries goal/context (`tool_schemas.py:534-544`); execution calls `bot._generate_response` without a route override (`jobs.py:596-602`), which delegates to shared `ai_provider` and the main night/fallback policy (`bot.py:3494-3534`). Changing global main-provider configuration is not per-job routing.

Discord thread creation/progress is optional and failure-tolerant (`jobs.py:465-494`), not what selects the provider. Jobs have their own message list but share bot tools, provider, limits and delivery machinery. Tools execute against the original message/channel; the optional thread receives progress summaries (`jobs.py:496-560,625-684`). Job history in `background_jobs.json` is not restart/resume execution: previously active records are canceled when loaded (`jobs.py:127-206`).

### The second configuration root remembered is real

| Environment family | Corresponding live controls | Traced consumer |
| --- | --- | --- |
| `AUTONOMY_BASE_URL`, `AUTONOMY_API_KEY`, `AUTONOMY_MODEL`, `AUTONOMY_DISABLE_REASONING` | `autonomy_base_url`, `autonomy_api_key`, `autonomy_model`, `autonomy_disable_reasoning` | `AutonomyEngine.plan` → `_get_autonomy_provider` (`autonomy.py:3016-3105`; `bot.py:3536-3668`) |
| `AUX_BASE_URL`, `AUX_API_KEY`, `AUX_MODEL`, `AUX_DISABLE_REASONING` | `aux_base_url`, `aux_api_key`, `aux_model`, `aux_disable_reasoning` | REM/context watcher → `_get_aux_provider` / `_get_aux_model` (`bot.py:3670-3798,10023-10049,10993-11015`) |
| `BG_MAX_TOKENS`, `BG_TIMEOUT_SECONDS`, `BG_MAX_ITERS` | `bg_max_tokens`, `bg_timeout_seconds`, `bg_max_iters` | Job budgets only (`jobs.py:63-103`); capacity uses `DAME_CURIE_BG_JOBS` / `DAME_CURIE_BG_PER_USER` |

Definitions: `config.py:373-392`, `control_defaults.py:281-295`, `.env.example:105-139`. The template calls REM/context helpers "auxiliary background agents"; they are **not** the `spawn_background` worker. `OllamaProvider` here is an OpenAI-compatible HTTP adapter; endpoint/key/model selection is real, but there is no corresponding provider-name enum. A `vendor/model` string does not itself switch the application's endpoint.

Routing details to retain:
- Nonempty live string controls win over corresponding configured environment fields. With a dedicated URL, factories create/cache another client and retain main fallback settings; initialization failure/unavailability can return the main client. No autonomy URL returns main; no AUX URL delegates the entire client to the autonomy factory. A dedicated AUX failure returns main, not autonomy.
- AUX's per-call model independently resolves live AUX → environment AUX → live autonomy → environment autonomy → None (`bot.py:3782-3798`). REM then falls back to `OLLAMA_REM_MODEL`. Autonomy's planner per-call override reads the live model control; setting only environment `AUTONOMY_MODEL` without a separate URL does not select that model through the inspected planner path.
- Dedicated blank AUX API keys do not automatically inherit the autonomy/main key; the config default for both auxiliary families is `OPENAI_COMPAT_API_KEY`. Presence of a live reasoning control wins over the environment boolean, including default control entries. Per-call model overrides affect primary, not configured fallback/vision model choices (`providers.py:1949-1973`). Do not promise every request stays on the chosen endpoint/model.
- Live controls reload separately from startup environment configuration. None of the AUTONOMY/AUX routing fields is resolved or passed by the built-in job worker. No actual endpoint, key, slug or capability was tested. Dynamic external plugins retain their own possible behavior; the checked bundled checkers plugin adds game tools, not a second LLM route.

**Prompt mismatch to preserve in the handoff:** normal chat calls the live PromptStore reader (`bot.py:4130-4141,16670-16685`); jobs read cached `_control.base_personality` at start and append background text/tool policy (`jobs.py:514-548`). When an external prompts directory is selected, the bot explicitly removes that cached key (`bot.py:3200-3202,10577-10579`), so the job's personality prefix is empty by this source path. Jobs also do not use the main base-knowledge/per-server prompt assembly. This is a source-defined difference, not an observed production failure. No routing or prompt fix was made.

## 6. Logging is not one removable subsystem

| Layer | Source path / actual consumer | Boundary |
| --- | --- | --- |
| Process output | `bot.py:425-449`; Compose local driver (`compose.yaml:80-84,107-111`) or PM2 files (`ecosystem.config.js:90-94,145-149`) | Runtime output and its collector, not the tool protocol |
| CLI console | `scripts/instance.py:143-152,220-236` → `scripts/log_filter.py:125-149` → `scripts/log_console/` | Parser/rendering with bounded in-memory history; JSONL is stdout unless redirected. View controls do not change application log level |
| LLM/tool traces | `tool_registry.py:78-139` → `bot.py:15910-15937` → `llm_traces.json` → authenticated trace API (`api/api_server.py:1269-1280`) | Sanitized reasoning/parameter summaries, not complete provider replay; result argument is not stored |
| Incidents | `error_reporting.py:282-301,335-397` → `error_history.json` → private operator report (`operator_commands.py:73-106`) | Shared redaction and synchronous persistence; console safety imports the redactor too |
| Discord progress / job thread | `tool_progress.py`; `jobs.py:465-494,704-742` | Delivery surface; thread history is not the worker's context or provider selector |
| Delivery telemetry | `provider_telemetry.py:17-52`; `response_observability.py:205-271` | Shared send metrics/footer, not console parsing |
| RAG / REM events | `rag_memory.py:580-715`; `rem.py:333-425` | **Functional memory input** that changes future model context, not disposable diagnostics |

Console `subagent` scope is a jobs-logger heuristic, not complete per-worker correlation (`scripts/log_console/scopes.py:6-30`). Console image recognition is formatting, not image execution; its sanitization does not retroactively sanitize raw engine logs. PM2-log API returns 501 in container mode and points at host instance logs (`api/api_server.py:1892-1952`). No working browser dashboard/log console was demonstrated; the bounded pass found no `web/**/*` source files. None of these observations authorizes deleting a web/API service.

Tool result handling also contains actual protocol behavior: result/ending groups control follow-up turns; image/audio markers become model context; site results are deliberately not cut by the general result truncator (`tool_schemas.py:842-924`; `bot.py:15690-15755`). Do not remove these as "verbose logging" while changing prompt text.

## 7. Historical next-step contract — superseded by REDESIGN_PLAN.md

| Narrow future assignment | What must stay outside that assignment |
| --- | --- |
| DNS archive cleanup | All actual DNS/mail/host resources; no runtime access |
| Email removal | Shared inbox, notification consumers, taint/confirmation, media, providers and private mailbox/state |
| X removal | Generic Twitter Card/GIF metadata, shared inbox, image generation and generic HTTP/redaction |
| Site-prompt externalization | TTS/image providers, YouTube, site executors, publisher behavior, stored sites and routes unless root explicitly widens scope |
| Background model/provider selection | Discord thread/delivery and unrelated autonomy/media behavior unless the required edge is first disclosed |
| Log-console simplification | REM memory events, tool-result protocol and incident redaction/storage unless individually assigned |

**Recommended next tools step:** agree a site-only editable-prompt boundary using the inventory in section 1, preserving the current hotfix text and mechanical behavior first. Do not combine extraction with deciding remote backend capabilities, rewriting the policy, renaming parameters, replacing the backend or moving every tool class. Operator-editable authoring policy and executable capability facts must become distinguishable; a single editable paragraph cannot change what `site_server` executes. Include native/text exposure and the background-job consumer in that slice's acceptance definition, rather than promising that changing personality edits all tool prompts.

Email and X are separately scorable candidate cuts, not prerequisites for that prompt work and not reasons to refactor protected media. Ask root which single slice to perform next. If a slice needs another feature changed, stop at that boundary and explain before patching.

## Evidence limits

This map does not establish live feature usage, configured credentials/providers, publisher deployment, remote web policy, installed packages, model behavior, private overrides, unused containers, backups or V2 correctness. Dynamic/plugin and external/manual callers prevent a global safe-deletion proof from text search. No syntax parser, test, linter, application import or runtime probe was run in this mapping assignment. Later validation needs the separately agreed isolated/synthetic environment; no new tests are authorized. Mermaid diagrams in the chat summarize this map, not runtime telemetry.
