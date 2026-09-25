# Child report D — Dirac viewer latch, `scripts/dirac.py`, smoke runtime, R2/R3, working tree (Opus, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../03-DISPOSITIONS.md`.
Coordinator spot-verified: the unescaped `MSG from …: {message.content[:100]}` INFO line at `bot.py:5761-5771`;
`bounded_structure` returning False past `MAX_DEPTH`/`MAX_STRUCTURES` (`append_events.py:52-71`); the
permanent `continuity_lost = True` on that failure (`append_events.py:88-90`); the service-name length latch
(`append_events.py:103-104`). The child corrected two assumptions in the brief: Dirac uses the `local` log
driver, and R3 (`dfc6141`) lives in `tool_progress.py`, not `bot.py`.

---

# Read-only review: Dirac viewer latch, `dirac.py`, smoke runtime, R2/R3 and working tree

All anchors are relative to `/home/codexy/deepseek/dame-curie/`. I ran no code, tests, Docker or scripts, read no private paths or `legacy/`, and edited no files.

The biggest finding: `6859025` removed the one routine oversized line, but any Discord user the account can see can still latch the viewer with a 33-bracket message. After a latch, the live pane shows nothing, which is what looks like a freeze.

## Corrections to the brief

- **Log driver:** Dirac uses the `local` log driver (`scripts/dirac.py:238`), not json-file.
- **R3 location:** `dfc6141` doesn't touch `bot.py` (`git show dfc6141 -- bot.py` is empty). R3 lives in `tool_progress.py:590-643`; its caller is `bot.py:13131-13158`.
- **Shell and fetch tools:** `ShellTool` and `FetchUrlTool` (`bot_tools.py:5043-5700`) have no `logger.exception` or other INFO-and-above log calls. Failures go to `capture_incident`, which writes the incident store, not the log. The only DEBUG call there is at 6073. Shell output is not logged anywhere else.

## 1. Log console latch

**F1 — high — CONFIRMED (by reading, not run). Any Discord user can latch the viewer.**
- **Cause:** `bot.py:5761-5771` logs `MSG from … : {message.content[:100]}` for every message whose author isn't flagged as a bot. That happens before the blacklist, blocked-channel and allowlist checks (`bot.py:5778`, `5802`).
- **Also covers the bot's own posts:** the account is a user account, so its own messages have `author.bot=False` and get logged too.
- **Trigger 1:** a preview with 33 unbalanced `[` or `{` outside double quotes makes `bounded_structure` fail (`append_events.py:52-71`, depth > 32). `AppendParser.content` then sets `continuity_lost` for good (`append_events.py:83-90`).
- **Trigger 2:** a preview with a newline followed by one "word" over 256 bytes and ` |` looks like a Compose service name. That latches at `append_events.py:103-104`. Four-byte word characters get there within 100 characters.
- **Same line, related effects:**
  - The newline lets a user forge log records with any level (log injection).
  - A preview containing `-----BEGIN PRIVATE KEY-----` or `env: {` hides every following line as `[REDACTED]` (`safety.py:263-283`). With plain `docker logs` the service is always `None`, so this blanks the whole stream, and no notice says why.
- **Recovery doesn't hold:** the documented relaunch uses the default `--tail 100`, so it re-latches while the trigger is within the last 100 lines, and the sender can simply post again.
- **Smallest fix:** see F3. Also neutralise newlines in the `MSG` preview.

**F2 — medium — CONFIRMED. Why it "froze".**
- After a latch, `content()` returns no recognition, so `EventParser.parse` gives the record scope `"service"` (`events.py:98`).
- `"service"` isn't in `SCOPE_KEYS` (`scopes.py:373`), so `Filters.visible` hides it (`append_state.py:237-242`), and no key can show it.
- The only visible sign is one out-of-band notice (`append.py:133-134`). The `e` error view does list the omitted records.
- **Fix:** give `viewer.omitted` events a visible scope such as `system`, or skip filtering for them.

**F3 — medium — CONFIRMED. The permanent latch is out of proportion for two of its three triggers.**
- **Structure and service-name triggers:** by the time `bounded_structure` or the service-length check fails, the redactor has already processed the whole line (`append_events.py:83`). Nothing was actually missed, so a per-record omission would do.
- **Structure check is too broad:** the recursion risk only exists where JSON is parsed (`safety.py:285-293`, `recognizers.py:187-198`), but the check runs on every line.
- **Oversize drops:** only here is redactor input really lost (`AppendLines.take`, 29-49).
- **Durable fix:**
  1. Handle structure and service-name failures as per-record omissions and apply the structure bound only before JSON parsing.
  2. For oversize frames, scan the discarded bytes for private-key begin/end markers, config-dump openers and bracket balance, carrying a small overlap between chunks. Keep the redactor state correct and omit just that record.
  3. Also bound the producers in F4.
- **Rejected alternative:** raising the 64 KiB limit alone only moves the cliff. It raises per-line redaction cost, and records near 64 KiB of non-ASCII already exceed `ENCODED_BYTES` (256 KiB) and get omitted anyway. Bounding producers alone can't be complete: exception text, third-party loggers and user content remain.

**F4 — low — PLAUSIBLE. Other single lines that could still exceed 64 KiB.**

Only the longest physical line matters. Standard tracebacks don't print locals, so only exception-message lines can be long. All of these are model- or exception-driven and are bounded in practice by the retained 12,345-token output cap.
- **Image prompts:** `bot_tools.py:1096` (called at 1153-1157) logs the full model-supplied image prompt on one line (`json.dumps` escapes newlines). This is the most realistic one. It is likely below 64 KiB at the current cap, borderline at the 16,384 default (`bot.py:12246`), and certain at the retired 115,200 cap.
- **Unknown tool names:** `bot.py:13433` logs `Unknown tool called: %r (original: %r)`, the model-supplied name twice, unbounded.
- **Exception messages logged in full:**
  - `bot.py:13467-13470`, `12561`, `13258`, `7152`, `8000`, `4660`, `15674`
  - `message_pipeline.py:336`, `utils.py:893`, `autonomy.py:1349`, `plugin_manager.py:362`/`434`
  - A model-controlled example: `plugins/checkers/checkers_game.py:36,40`.
- **Untruncated model strings:**
  - `autonomy.py:3206-3208` (`original_kind`; only the raw JSON is cut to 300)
  - `autonomy.py:4009-4101` (`target_cid`)
  - `rag_memory.py:3014` (`query!r`)
- **Third-party loggers:** unverifiable; discord.py-self is not installed in the host `.venv`.
- **Cleared:**
  - `providers.py:3016`: the `reason` is content-free (`ProviderUpstreamError` reports only labels and `message_chars`, `providers.py:1252-1300`). Same for 1109 and 3076.
  - The alias log at `bot.py:13389` only fires for fixed alias keys.
  - `Executing tool` at 13443 only logs registered names.
  - `provider_telemetry.py` and `response_observability.py` don't log content.
  - `_record_llm_trace` writes a file (`bot.py:14082`), not the log.

**F5 — low — PLAUSIBLE. Framing is on the reassembled line.**
- The 64 KiB check runs on newline-delimited bytes from the `docker logs` CLI (`append.py:61-68`, `append_events.py:29-49`). There is no Docker-frame awareness.
- The incident proves Docker's 16 KiB partial chunks are joined upstream: a 100,311-byte line reached the viewer. No `--timestamps` flag is used.
- **Caveat:** the follower merges the CLI's stdout and stderr into one pipe (`append.py:198-201`). The bot sends INFO/WARNING to stdout and ERROR to stderr (`bot.py:419-425`). A stderr record could land between chunks of a >16 KiB stdout line and mis-frame it. This is Docker behaviour I couldn't verify here.

**F6 — info — CONFIRMED. Replay and `--fresh`.**
- `--fresh` is `--tail 0` (`dirac.py:371`).
- `dirac.py restart` restarts the same container (`dirac.py:330`); the `local` driver keeps up to 3×10 MiB of logs (`dirac.py:238`); `docker logs -f` ends when the container stops. Relaunching with the default tail therefore replays pre-restart lines, including any trigger.
- `start --replace` runs `docker rm` (`dirac.py:316`), which clears the logs.
- **Fix:** document this in the handoff, or offer `--since` set to the container's start time.

## 2. `scripts/dirac.py`

- **Info — CONFIRMED. Arguments and engine selection are sound.**
  - The `--fresh`/`--no-keys` rejection is consistent (`dirac.py:89-92`).
  - The ownership check requires both the label and the reserved name (`dirac.py:212-222`).
  - I found no path to the wrong engine: `Instance` pins `DOCKER_HOST` to the account's socket, checks its owner and requires rootless (`scripts/instance.py:155-181`). `deploy.env` keys are whitelisted, so `DOCKER_HOST` can't be overridden (`instance.py:82-99`). The readiness check and log follower reuse the same environment (`dirac.py:262`, `371`). `service_account` refuses other users (`instance.py:111-139`).
- **Info — CONFIRMED.** `restart` and `start --replace` behave as `DIRAC_HANDOFF.md` describes (`dirac.py:305-316`; `--pull never`; image pinned to its ID at 156). `--image` does not update the selector file.
- **Low — CONFIRMED. `status` is misleading in two ways.**
  - With a config problem and a present container, it reports `embedding_readiness: "not running"` and no container state (`dirac.py:354-358`). The exit code of 1 is correct.
  - It runs `docker exec` inside the live container (362 → 262), which contradicts its "without mutating anything" docstring.
  - **Fix:** report "not checked" and fill in the container state first.
- **Low — CONFIRMED. `restart` loses stop evidence.** On a stopped container it silently starts it and drops the previous exit code, OOM flag and finish time (`dirac.py:324-333`), which `start` deliberately preserves. **Fix:** read and report the state first, or refuse and point to `start --replace`.

## 3. Smoke runtime (`162b39c`)

- **Info — CONFIRMED. No health-file collision.** The health file is `runtime-state` with no suffix, and its temp is `.runtime-state.tmp` (`smoke_protocol.py:31`, `370-376`). Request IDs must be alphanumeric (`smoke_protocol.py:174`). So nothing collides with the `*.json` recovery scan (`dirac_runtime.py:364-383`). The health payload holds only status, time and exception class name (`449-459`), with no path.
- **Info — CONFIRMED. The R9 timeout check is correct.** `.expired()` is used correctly for Python 3.11+/3.14 (`dirac_runtime.py:640`). There is one harmless race: an upstream timeout raised as the request deadline expires is attributed to the deadline.
- **Info — CONFIRMED. Stop and start lifecycle.**
  - `stop()` is serialised by `_stop_lock` and the `_started` guard. A stop called from the poll task itself is handled (`315-316`).
  - A stop called from inside a turn task would cancel itself and exit with `_started` still true and no health write. That is unreachable today: the only caller is in the shutdown path (`bot.py:15773-15779`).
  - `start()` has no guard against being called twice, but has one call site (`bot.py:4577-4582`).
  - A partial start removes its hooks again (`287-292`).
  - `_interrupt_stale` rewrites any non-terminal `.json` file in the status directory, including unrelated ones, and a non-object `.json` there aborts bot startup.
- **Low — CONFIRMED. Generic failures leave the turn running.** The generic `except Exception` in `_handle` (`710-726`) runs after the turn has been opened (`583-584`) but neither cancels nor discards it. The turn can keep running, and the next request can overlap it. The traceback is also discarded entirely. **Fix:** do what the upstream-timeout branch does: cancel the input, wait for it to settle, then discard it.
- **Low — PLAUSIBLE. A stop during timeout handling leaves the record `running`.** The timeout handler awaits (`643-655`, `667-668`). If `stop()` cancels the poll during that wait, the cancellation escapes the sibling `except asyncio.CancelledError` at 697. The record stays `running` until the next process start marks it interrupted.

## 4. R3 (`dfc6141`) and R2 (`acf5da9`)

**R3-1 — medium — CONFIRMED. The settlement is awaited but its result is ignored.**
- If both the edit and the fallback send fail, `_deliver_final` just returns (`tool_progress.py:619-643`) and `transition_to_final` still returns True (`617`).
- The caller then treats the reply as delivered (`bot.py:13143-13151`) and skips chunk 0 (`13156`).
- It still sends chunks 1..n, and stores the unsent answer as the bot's reply in memory (`13210-13229`). It also records the REM event and marks the reply as sent (`13232-13235`). The only trace is an ERROR log.
- So the settlement is timing-only; the fire-and-forget version had the same flaw.
- **Fix:** have `_deliver_final` return a success flag and use it as `transition_to_final`'s result, so chunk 0 falls through to `_send_with_slowmode`.

**R3-2 — low — PLAUSIBLE. Cancellation during settlement can delete a delivered answer.**
- On cancellation, `transition_to_final` schedules a delete of the progress message (`tool_progress.py:614-616`), even if the edit already reached Discord.
- This is newly reachable because the turn now stays active during the edit:
  - a same-user interrupt (`bot.py:5905-5927`)
  - `?stop` (`6442-6448`)
  - a smoke deadline
  - shutdown (`15803-15811`)
- **Fix:** let the edit or fallback finish (shield it) before re-raising, or skip the delete once the edit has been issued.

**R3-3 — low — CONFIRMED.**
- **No timeout:** the settlement has no timeout of its own, so the channel's queue slot is held for the edit plus the fallback. This is the same class of wait as the normal send path, not a new unbounded hang.
- **Pre-existing:** the transition path drops stickers, the reply reference and slowmode handling (`tool_progress.py:637`, `bot.py:13143-13165`).

**R2 — no defect — CONFIRMED.**
- The actor is re-wrapped at `bot.py:5479` and the prompt is built from that proxy (`5497-5503`).
- The proxy keeps both the actor and the real poster (`dirac_runtime.py:234-236`), and memory uses the real poster (`bot.py:4978-4988`). The other refresh point, 12254, also re-wraps.
- The raw `latest` object only feeds author-independent media helpers (`bot.py:5485-5493`).
- The raw message written into the in-flight state (`5637`, `5656`) is only read by `_apply_inflight_refresh`, which re-wraps it (sole caller at 12531).
- I found no remaining place that passes the raw bot poster as the actor.

## 5. Working-tree hygiene (process findings)

- **H1 — medium.**
  - **State:** `legacy/` shows 24 files and 3,970 deletions, none staged. The last commit to touch it is `a9c0fba`, "refactor(dame-curie): establish source namespace cut-off" (2026-09-19 04:38:56 +0200).
  - **Why it matters:** `AGENTS.md`, `README.md` and at least 7 `phase-II_v2` docs still reference `legacy/`. Any `git add -A` or `commit -a` would silently commit the removal of the quarantined archive.
- **H2 — medium.**
  - **Evidence:** two host-compiled files sit in the checkout root: `__pycache__/provider_telemetry.cpython-314.pyc` (2026-09-23 15:25) and `response_observability.cpython-314.pyc` (15:27). The first matches the current source's mtime and size.
  - **Pre-commit edit:** the second's header records a source size of 20,818 bytes versus the committed 20,810. It was compiled from an uncommitted edit before `1445f03` (committed 16:00).
  - **What it means:** the files can't tell a compile from an import, but either way it conflicts with the no-imports-on-host rule.
- **H3 — low.**
  - **What:** `.validation-cache/` holds 35 `.pyc` files under a mirror of `/home/codexy/...`, dated 2026-09-19 12:28–15:11. They include test modules (`test_site_public_urls`, `test_prompt_storage`), which points to test compilation or collection on the host tree.
  - **Why `git status` misses it:** only because `.gitignore:5 *.pyc` matches its files. `.git/info/exclude` has no entry, and nothing names the directory itself.

## Key files
- scripts/log_console/append_events.py, events.py, safety.py, append.py
- scripts/dirac.py, scripts/instance.py
- dirac_runtime.py, smoke_protocol.py, tool_progress.py, bot.py, bot_tools.py
