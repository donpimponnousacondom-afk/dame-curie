# Dirac operator smoke protocol

Lane `work/dirac-smoke-lean`, worktree `dirac-smoke-lean`, base `7b4398c`. Source-only: no runtime, container, private
configuration, credential or network access; the parent runs the isolated tests and the live exercise.

## Files

`smoke_protocol.py` (settings, immutable request, the one record, atomic and exclusive writes),
`dirac_runtime.py` (the live poll, observer, injection, deadline, result), `scripts/dirac_smoke.py` (`submit`,
`result <id>`, `pending`), `tests/test_dirac_smoke.py` with `tests/test_message_pipeline.py` (protocol and queue
tests), and — the only edit elsewhere — `message_pipeline.py` (`running_message_id`, `cancel_message`).

## Mounts and config

Host `/srv/dame-curie/dirac/smoke/{config.json,requests/}` read-only at `/smoke`; host `/srv/dame-curie/dirac/smoke-status`
read-write at `/smoke-status`. Both directories resolve against the config file's own directory, so `"requests"` and
`"../smoke-status"` name those mounts on the host and in the container alike.

```json
{"enabled": true, "channel_id": 0, "operator_id": 0, "operator_name": "root", "requests_dir": "requests",
 "status_dir": "../smoke-status", "poll_seconds": 5.0}
```
`enabled` must be stated; a wrong or missing one, a missing request mount or an unwritable status mount raises out of
`start()`, so an opted-in bot does not come up looking tested. `enabled: false` is inert. `bot.setup_hook` imports
`dirac_runtime` only when `DAME_CURIE_DIRAC_SMOKE_CONFIG` is set, calls `SmokeSettings.from_env()`, then
`DiracSmokeRuntime(bot, settings).start()`; shutdown calls `stop()` before the reply queue closes. The runtime sets
`bot._turn_observer` itself.

## One request

`submit --task TEXT|--task-file PATH [--thread ID] [--deadline SECONDS]` writes `requests/<uuid4>.json` exclusively
(`os.link`, so no check-then-create race; 0600), prints the id, and never edits it again. Submit on the host: the
container's request mount is read-only, while `result` and `pending` read both mounts from either side. The runtime
polls every `poll_seconds`, takes the oldest request by file clock, and writes one record `smoke-status/<uuid4>.json`.

1. `accepted` — the request was read.
2. The notice is posted by the bot in the approved channel, or in a bot-owned thread inside it; a DM, a foreign
   thread and a thread the bot does not own are `rejected`, never run. It names the test, says no human typed
   it, states that the permission actor is separate from the author of the text, and mentions the bot — the
   hard ping, in 250 header characters.
3. `running` — the notice message becomes the turn's input through a thin proxy that delegates every attribute
   to the real message and overrides only `author`: the configured operator id, fetched as a real SDK user,
   refused when it is not an integer or is the bot. Injection is `bot._on_message_impl`, so the bot's own
   gates (`bot_enabled`, blacklist, allowlist, sleep) decide as always; `on_message` stays bypassed because
   the notice's own gateway event already consumed its dedup slot.
4. One terminal status: `completed`, `failed`, `rejected`, `timeout` or `interrupted`.

One deadline covers the whole request — resolve, notice, injection, the turn — because each can stall.
Correlation is the notice id in `response_observability.TURN_INPUT`, set by the observer inside the turn's own
task, so the turn's tool children inherit it and an unrelated task is never attributed. Deliveries arrive from
`record_delivery` and from a wrapper around the client's `send_message` (file and plugin posts bypass
`record_delivery`), which reads `payload["id"]` from the returned payload, never an attribute. Only deliveries
into the target channel count: a message the turn posted elsewhere is not part of this receipt, and
cross-channel behaviour is a separate scenario.

`completed` means the turn returned *and* the target channel received a real message — never that the task's goal was
met. `reply_text` is fetched by the exact delivered ids (at most 5) and `reply_verified` stays false; an id the
harness cannot read back is listed in `reply_readback` with its error type, and never turns a delivery into a
failed turn.

## Deadline, queue and restart

At the deadline the runtime cancels that input only — the queued entry if it never started, the task if it did — and
says which of the three happened. Every cancelled task then gets 5s to stop; if it has not, the record says cleanup
is unconfirmed and the runtime starts no further request until that task is really gone. Deliveries found before a
deadline or an interruption are written to the record.

Eligibility to run is "no record exists", so the record directory is the ledger: no finished request can run
again, however many are queued, and a restart rewrites a non-terminal record to `interrupted` rather than
re-running it. Wiping that directory makes the requests still in the request directory runnable again; nothing
here prevents that. A status mount that disappeared is refused rather than read as "nothing is done". A failure
inside the request boundary always lands as a terminal record, and when even that write fails the poll loop
stops with an error instead of retrying.

## Cross-lane and unverified

Requires the jobs lane: `response_observability.TURN_INPUT` and the `bot._turn_observer` bracketing in
`MaxwellBot._run_queued_reply`. Not verified here: real Discord behaviour, the live HTTP client, whether
`bot.http` is the object the SDK's own sends use, `Client.wait_until_ready` (outside the approved extract),
the container mounts, and the parent's isolated test run.
