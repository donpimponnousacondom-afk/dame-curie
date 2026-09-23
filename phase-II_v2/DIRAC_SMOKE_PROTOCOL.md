# Dirac operator smoke protocol

Current source contract. The deployed revision and dated runtime evidence are in `DIRAC_HANDOFF.md`;
older receipts are not retroactively reclassified by this hardening.

## Files

`smoke_protocol.py` (settings, immutable request, the one record, atomic and exclusive writes), `dirac_runtime.py` (the
live poll, observer, injection, deadline, result), `scripts/dirac_smoke.py` (`submit`, `result <id>`, `pending`, `health`),
`tests/test_dirac_smoke.py` with queue/update/observability regressions. `bot.py` supplies turn boundaries and
provenance-preserving refreshes; `response_observability.py` and `tool_progress.py` mark non-answer deliveries.
`message_pipeline.py` supplies `running_message_id` and `cancel_message`.

## Mounts and config

Host `/srv/dame-curie/dirac/smoke/{config.json,requests/}` read-only at `/smoke`; host `/srv/dame-curie/dirac/smoke-status`
read-write at `/smoke-status`. Both directories resolve against the config file's own directory, so `"requests"` and
`"../smoke-status"` name those mounts on the host and in the container alike.

```json
{"enabled": true, "channel_id": 0, "operator_id": 0, "operator_name": "root", "requests_dir": "requests",
 "status_dir": "../smoke-status", "poll_seconds": 5.0}
```
`enabled` must be stated; a wrong or missing one, a missing request or status directory (the runtime never creates
them) or an unwritable status mount raises out of `start()`, so an opted-in bot does not come up looking tested.
`enabled: false` is inert. `bot.setup_hook` imports
`dirac_runtime` only when `DAME_CURIE_DIRAC_SMOKE_CONFIG` is set, calls `SmokeSettings.from_env()`, then
`DiracSmokeRuntime(bot, settings).start()`; shutdown calls `stop()` before the reply queue closes. The runtime sets
`bot._turn_observer` itself; `bot.py` never does.

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
   the notice's own gateway event already consumed its dedup slot. `notice_author` pins the real poster across
   late fetches and partial updates. In-flight prompt rebuilds receive that rebound proxy, not the raw bot-authored update snapshot. Memory attribution uses that poster, including self-account IDs whose
   Discord `bot` flag is false; the operator remains the permission actor. Synthetic instructions are not
   extracted as human facts. No memory purge or broader REM change is part of this fix.
4. One terminal status: `completed`, `failed`, `rejected`, `timeout` or `interrupted`.

One deadline covers the whole request — resolve, notice, injection, the turn — because each can stall. Correlation is
the notice id in `response_observability.TURN_INPUT`, set by the observer inside the turn's own task, so the turn's tool
children inherit it and an unrelated task is never attributed. Deliveries arrive from `record_delivery` and from a
wrapper around the client's `send_message` (file and plugin posts bypass `record_delivery`), which reads
`payload["id"]` from the returned payload, never an attribute. Only deliveries into the target channel count: a message
the turn posted elsewhere is not part of this receipt, and cross-channel behaviour is a separate scenario.

`completed` requires a returned turn, a usable result from its own model call (text or tool calls), and a target-channel
delivery while that successful result stands which is not marked as a notice. The runtime observes the real
`_generate_response` contract and restores any pre-existing instance override on shutdown. Sleep notices, public
errors and transient progress are explicitly marked; their IDs remain evidence, but cannot pass a turn. A real
answer delivered before a later provider failure still counts. None of this proves the requested task's goal was met.

The terminal outcome is written before optional readback. On ordinary turn settlement, records with delivered IDs,
including failed notice-only turns, get readback (at most 5 IDs, 5s total). Deadline/interruption receipts retain known
IDs but do not promise readback. `reply_verified` stays false; unreadable IDs are listed in `reply_readback`.
A stall, failure or shutdown during readback cannot downgrade a completed record. Final progress-to-answer edits and their fallback sends are awaited by the originating turn before its observer closes or its provider-reload busy markers clear. A successful callback—not the transition's boolean alone—is delivery evidence. Other genuinely late deliveries after closure remain excluded; a later readback cannot turn a failed outcome into success.

## Deadline, queue and restart

At the deadline the runtime cancels that input only — the queued entry if it never started, the task if it did — and
says which of the three happened. Every cancelled task then gets 5s to stop; if it has not, the record says cleanup
is unconfirmed and the runtime starts no further request until that task is really gone. Deliveries found before a
deadline or an interruption are written to the record. The timeout context must actually expire to classify a request as `timeout`; an earlier escaping upstream fetch/send timeout is `failed`, with the same owned-input cleanup and known delivery evidence.

Eligibility to run is "no record exists", so the record directory is the ledger: no finished request can run again,
however many are queued, and a restart rewrites a non-terminal record to `interrupted` rather than re-running it.
Wiping that directory makes the requests still in it runnable again; nothing here prevents that. A status mount that
disappeared is refused rather than read as "nothing is done". Ordinary request failures are recorded while status storage remains writable; a terminal record cannot be guaranteed on broken storage. Fatal poll/discovery/write errors fail-stop the worker and initiate bounded cleanup of its owned inputs/hooks instead of retrying. A request
unlinked before reading is withdrawn without a receipt; a vanished/unstatable entry is skipped during listing,
so it does not kill polling. Malformed or unreadable request contents still produce a failed record when storage permits.

## Advisory health, not proof of liveness

`health` reads `smoke-status/runtime-state`, a JSON snapshot without the request-record `.json` suffix. It is excluded from stale-request recovery. Runtime arm, failure and stop update last-observed state when writable; fatal causes are retained through subsequent cleanup. Concurrent stop callers serialize around the same poll task. If its bounded settlement cannot be confirmed, the snapshot says `stop_unconfirmed`, not `stopped`, and the runtime admits no further request. Diagnostics contain an error type or a trusted fixed protocol reason, not raw SDK/request text.

The command always reports `worker_liveness: "unknown"`: an old snapshot cannot prove the current worker is alive. Missing/unreadable health is unavailable evidence, not a healthy default. `result` retains the compatible `status: "pending"` when no receipt exists; it and `pending` rows explicitly qualify acceptance as `no_record` and liveness as unknown. Absence of a record does not prove the request never executed if the ledger was lost or deleted. No heartbeat, automatic replay, second status store or daemon API is introduced.

## Evidence boundary

The SDK routes sends through the wrapped HTTP client. Readiness is awaited by the poll task, never by
`setup_hook`. The isolated hardening run at `65fe79e` passed 341 focused tests with Python 3.14.4 and no network
or private mounts. These tests do not impersonate Discord Gateway events or establish live task success;
use the exact-version runtime receipts in `DIRAC_HANDOFF.md` and `DIRAC_INTEGRATION.md`.
