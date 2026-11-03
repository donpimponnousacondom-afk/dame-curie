# Provider settings: idle-boundary reload

The bot reloads provider settings from its `bot.env` without a restart. The running process keeps the `bot.env` path it started with (`/srv/dame-curie/config/bot.env` on the host, `/config/bot.env` in the container). Editing another file does nothing.

## What to edit

Edit `bot.env` with an atomic save. The reload allowlist covers:

- Main `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY` and shared `OPENAI_COMPAT_API_KEY`.
- `OPENAI_FALLBACK_*` and `OPENAI_VISION_*` endpoint, model, key and reasoning profiles.
- `AUTONOMY_*` and `AUX_*` endpoint, model, key and reasoning profiles, plus `OPENAI_REM_MODEL`.
- `OPENAI_MAX_TOKENS`, `OPENAI_TEMPERATURE`, `OPENAI_TOP_P`, `OPENAI_TOP_K`, `OPENAI_DISABLE_REASONING`.
- JSON objects `OPENAI_EXTRA_HEADERS` and `OPENAI_EXTRA_BODY`.
- `OPENAI_RETRY_ATTEMPTS`, `OPENAI_EMPTY_RESPONSE_RETRIES`, `OPENAI_ENDPOINT_COOLDOWN_SECONDS`.

The exact 31 resolved fields are in `provider_settings.PROVIDER_FIELDS`. Role and reasoning overrides in `bot_control.json` still take precedence. Removing a key resolves it from the original inherited environment and defaults, not from the previously loaded file. An explicitly blank credential keeps its startup semantics.

## When it takes effect

The bot checks at message entry and on its five-second control tick. A valid edit stays pending until foreground replies, queued work, jobs (including cancellation cleanup and final delivery), REM, autonomy, context and voice work, maintenance summaries and outstanding provider operations are idle. Gaps between tools are not idle boundaries, so continuous work delays an edit.

At idle, a complete replacement is built and swapped. No active request is cancelled to apply an edit.

`!debug` reports the provider generation and reload state:

- `pending idle`: a validated edit waits for the boundary.
- `applied`: the new generation is installed.
- `unchanged`: the file matches the active generation.
- `editing`: the file changed while it was read; it is retried.
- `rejected`: an invalid edit was discarded; active providers stay in place.

Malformed dotenv or JSON, wrong header types, non-finite numbers, invalid HTTP URL hosts or ports and a missing main endpoint or model are rejected. A rejection logs the exception type, not file values. A valid file with a wrong credential, model or server fails later in the ordinary provider path.

## What does not reload

This is not a process-wide dotenv reload. It does not rewrite `os.environ`, restart the bot or reload code. The Discord token, command prefix, storage paths, embedding backend, feature switches, image generation and TTS need a restart.

`!version` is separate: it reports the frozen `/app/build_provenance.json` of the running image. Environment edits cannot change it.

The reload was implemented in `d43e4bf`; `dfc6141` fixed foreground final-delivery ownership. Its acceptance evidence is in the September audit records; see [HISTORY.md](HISTORY.md).
