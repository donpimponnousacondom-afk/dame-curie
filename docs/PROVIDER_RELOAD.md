# Provider settings: idle-boundary reload

Provider-file reload was implemented in `d43e4bf`; `dfc6141` subsequently fixed foreground final-delivery ownership. Deployed revision and dated receipts are separate in `STATUS.md`. Dirac uses `?` commands; the repository's default prefix remains `!`.

## What to edit

Edit the instance's selected `bot.env` (Dirac: `/srv/dame-curie/dirac/config/bot.env`). Prefer an atomic save. The running process keeps that startup-selected path; editing a different checkout's `.env` does nothing.

The reload allowlist covers:

- Main `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY` and shared `OPENAI_COMPAT_API_KEY`.
- `OPENAI_FALLBACK_*` and `OPENAI_VISION_*` endpoint/model/key/reasoning profiles.
- `AUTONOMY_*` and `AUX_*` endpoint/model/key/reasoning profiles, plus `OPENAI_REM_MODEL`.
- `OPENAI_MAX_TOKENS`, `OPENAI_TEMPERATURE`, `OPENAI_TOP_P`, `OPENAI_TOP_K`, `OPENAI_DISABLE_REASONING`.
- JSON objects `OPENAI_EXTRA_HEADERS` and `OPENAI_EXTRA_BODY`.
- `OPENAI_RETRY_ATTEMPTS`, `OPENAI_EMPTY_RESPONSE_RETRIES`, `OPENAI_ENDPOINT_COOLDOWN_SECONDS`.

The exact 31 resolved fields are in `provider_settings.PROVIDER_FIELDS`. Existing role/reasoning overrides in `bot_control.json` still take precedence; their existing control mechanisms are not replaced by this loader. Removing an environment key resolves it from the original inherited environment/defaults, not from the previously loaded file. Explicitly blank credentials retain their existing startup semantics.

## When it takes effect

The bot checks at message/queued-turn entry and on its five-second control tick. Valid edits stay pending until foreground replies, queued work, jobs (including cancellation cleanup and final delivery), REM, autonomy, context/voice work, maintenance summaries and outstanding provider operations are idle. Between-tool gaps are not idle boundaries. Continuous work can therefore delay an edit.

At idle, a complete replacement is constructed and swapped synchronously. The existing Config instance receives only the provider fields; role caches are rebuilt as needed. Displaced clients remain tracked until whole-round idle cleanup closes them. No active request is deliberately cancelled to apply a file edit.

`?debug` reports a process-local provider generation and reload state:

- `pending idle`: validated edit waiting for the boundary.
- `applied`: the new generation was installed.
- `unchanged`: file resolution matches the active generation.
- `editing`: the file changed while being read; it will be retried.
- `rejected`: an invalid/unreadable edit was discarded; active providers stay in place.

Malformed dotenv/JSON, wrong header value types, non-finite numbers, invalid HTTP URL hosts/ports and missing main endpoint/model are rejected. Rejection logs expose the exception type, not file values. Syntactically valid but incorrect credentials, nonexistent models or unreachable servers cannot be certified by offline validation; their ordinary provider failures still require correcting the settings.

## What does not reload

This is not process-wide dotenv reload. It does not rewrite `os.environ`, restart the bot or reload code. Discord token/identity, command prefix, storage paths/databases, embedding backend, feature switches, image generation and TTS remain outside this allowlist. Existing independent runtime controls keep their own behavior. In particular, editing `COMMAND_PREFIX` requires a restart.

`?version` is separate: it reports the frozen `/app/build_provenance.json` from the running image. Environment edits, host checkout commits and provider generations cannot change that build identity.

## Evidence and limits

- The exact tree committed as `d43e4bf` passed **825 focused isolated tests**, Python 3.14.4, without network, credentials or private mounts. Expanded Ruff F821/F822/F823 checks passed. One stale README-row assertion in `test_provider_resilience.py` was explicitly deselected after reproducing the same failure on pre-reload `dba8359`; this is not a full-suite-green claim.
- The initial review reported no remaining P0/P1 blocker, but a later scheduling review found a gap: a foreground final progress edit could outlive its turn's idle markers. `dfc6141` makes that edit/fallback settlement awaited by the turn. The issue was delivery/receipt timing, not evidence of interrupted model calls or closure of Discord's separate transport.
- The original `d43e4bf` image separately verified its committed source blobs, baked provenance, module imports, staged edit and rejected invalid port in a credential-free/no-network probe; that probe did not exercise the delayed-final-edit schedule.
- Boot/daily summary loops and tracked job workers are drained before transport teardown. General Gateway-command admission during shutdown remains a preexisting limitation; this change is not a wholesale shutdown redesign.
- Live Dirac receipt `74d4aa30ddc0463c8162207491c46a80` held a temporary cooldown edit through 14.9 seconds of actual tool work, then applied it as generation 2. Removing the owned override restored the original environment bytes exactly and applied generation 3. No endpoint, model or credential was changed. This validates that observed deferral/restoration schedule, not every supported profile combination or the previously detached final-edit tail. The R3 integrated regression instead holds a single final Discord edit and verifies both the observer and `providers_idle` remain busy until delivery settles.
- Deployment and live receipts are recorded in `STATUS.md` and `../phase-II_v2/DIRAC_HANDOFF.md`, separately from isolated acceptance.
