# Round-two child report R4 — viewer, preview producer, Dirac CLI, smoke lifecycle, final delivery (Opus, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../08-ROUND2-REPORT.md`.
Coordinator re-verified before accepting: the new `MSG from user_id=… chars=%d` producer line (`bot.py:5818-5824`),
the single `turn.settle` site and `transition_to_final` return path, and the `autonomy.py` raw-output WARNING log.

---

# Round-two re-verification: viewer, preview producer, Dirac CLI, smoke lifecycle, final delivery

I checked the diffs of `7286aa2`, `551060d`, `e540be6` and the relevant hunks of `d198c37` (`bot.py` MSG producer and delivery caller, `tool_progress.py`) against the current tree at HEAD `0e9519e`. I only read source and git output. I ran nothing, read no private paths and wrote no files.

**Summary:**
- **Closed:** C-31 (in source only), C-32, C-34, C-35, C-36, D-06 and I-01.
- **C-33 is only partly closed.** The oversize-frame part of the auditor's fix was not done, and the permanent latch now also applies to the interactive console viewer.
- **C-37 is closed, but the change adds one small new defect:** in one error path the smoke poller stops silently while its health file still says "running".
- **None of the viewer fixes are live.** The running Dirac instance still has the old image and the old viewer, so the round-one attack still works there.

---

## C-31 — any user could permanently latch the viewer
**Verdict: CLOSED in source. NOT deployed; the running instance is still exposed. Residual: low.**

1. **What the diff does:**
   - **Producer:** `bot.py:5818-5824` now logs `MSG from user_id=%s channel_id=%s guild_id=%s chars=%d`. That is integers only, with no message text, display name or channel name. It removes the content rather than escaping it, which is stronger than the auditor asked for.
   - **Nothing breaks:** no viewer recognizer and no test matches `MSG` (the only `MSG` in `scripts/` or `tests/` is `socket.MSG_PEEK`).
   - **Viewer, structure check:** the bracket-depth check now runs only on lines that will be parsed as JSON (`append_events.py:60-62`, `110-111`). A failure gives a one-record `OMITTED_STRUCTURE` (`:129-130`).
   - **Viewer, service name:** an over-long service prefix gives a one-record `ServicePrefixOmitted` (`:149-150`).
   - Neither of these sets `continuity_lost` any more.
2. **Does it close the scenario?** Yes, in source. 33 `[` in a user message is no longer logged. Even a bracket-leading line now costs one record, not the stream.
3. **Triggers that still latch permanently:**
   - A dropped oversize frame: `AppendLines.take` is unchanged (`:37-57`). Any frame over 64 KiB becomes `None`, which sets the latch at `:139-142`.
   - More than 500 open PEM/config redaction spans across service keys (`:121-124`).
   - **New:** the interactive console viewer now uses `AppendParser` (`console.py:20,28-35`). An input record over 2 MiB now latches it permanently; before, it was a single local omission.
   - Things that can blank the stream without latching:
     - `autonomy.py:3150` logs up to 500 characters of raw model output at WARNING, newlines included. That can still forge log records, or open a PEM/config span that hides lines until a closing marker or a `--fresh` restart.
     - The oversize-capable producers the auditor listed are unchanged: the image-prompt log (`bot_tools.py:1099`, `ensure_ascii=False`) and the unknown-tool-name log (`bot.py:13848`).
4. **Overclaim:** "fixed" is true only for source. The block does say the prior image was restored and the host viewer was not installed. So the exact round-one attack still works on the running temporary Dirac (old image logs content, old viewer latches).

## C-32 — omitted records were invisible
**Verdict: CLOSED.**

1. **What the diff does:**
   - Omitted records get the new scope `viewer` (`scopes.py:8-9`). It is deliberately left out of the scope keys, so no key can hide it.
   - `omitted_event` (`append_events.py:87-98`) builds these records with service/logger cleared and a fixed message.
   - Both viewers always show that scope (`append_state.py:22-23`, `controls.py:28-30`). Scope replay includes it (`append_state.py:84`).
   - It is excluded from the error-view history filter and from health coalescing (`history.py:79,125`, `console.py:40`).
   - Rendering ignores the hidden/notes overrides for it (`render.py:63,111-113`).
   - Append-mode repeat suppression only matches health-pattern lines, so omission rows are never folded away (`append_repeats.py:30-33`).
2. **Does it close the scenario?** Yes.
3. **New defects:** none. One cost: after a latch, every incoming line produces a visible omission row, so the pane floods. It is visible, not frozen.

## C-33 — durable redaction continuity
**Verdict: PARTIALLY CLOSED (low–medium). The oversize part of the auditor's durable fix was not implemented and was not explicitly declined.**

1. **What the diff actually implements:**
   - **Done:** visible omission scope; per-record structure and service omissions; structure check only before JSON parsing (`append_events.py:110-111`).
   - **Done: record-local JSON redaction.** Complete JSON lines are parsed with a fresh `EventParser`/`EvidenceRedactor` (`:113-119`, `safety.py:35-42`). They are masked to `[REDACTED]` if an outer span is already open for that service.
   - **Done:** field values are scanned before the sensitive-key mask is applied (`safety.py:71-77`). Begin/end markers are ordered by the last occurrence in a line (`safety.py:103-109`).
   - **Done:** a rejected line is scanned by the stream redactor before it is omitted (`:120`).
   - **Not done:** the auditor asked that oversize drops scan the discarded bytes for key/config markers (with a small overlap) and omit just that record. `AppendLines` is untouched and oversize still latches permanently. "Raise the limit" was correctly not done (`RECORD_BYTES` is unchanged).
2. **Adversarial checks:**
   - **Can a private-key BEGIN marker inside a dropped oversize frame leak the lines up to END?** No, but only because the drop still latches permanently. It fails closed, it is not handled proportionately.
   - **Can the new per-record omission path emit raw text?** Not today. `record()` copies `event.message` into the omission (`:145-148`). Every `content()` branch that returns a parse error returns a fixed constant.
     - This depends on an unstated rule: non-candidate lines never produce a parse error.
     - If a future recognizer set one, `EventParser.content:85-88` would put sanitized source text into an omission row that cannot be filtered.
     - The comment at `:19` ("never re-renders") is enforced by that rule, not by the code.
   - **Narrowing from record-local JSON.** A *valid* JSON line no longer opens or closes the stream's PEM/config span.
     - Opening: a BEGIN marker inside a valid JSON string, with the key body continuing on raw lines, would no longer hide those lines. This is contrived: valid JSON holds its whole string.
     - Closing: an END marker inside valid JSON leaves the span open, which only over-redacts.
     - Net: availability improves (a model-supplied image prompt containing BEGIN no longer blanks the stream). I found no realistic leak.
3. **Overclaims:**
   - "fixed" is too strong; "Genuine framing loss/overflow fails closed" just restates the latch the auditor called disproportionate.
   - The block does not mention that the console viewer now latches on overflow.
   - That console is also what canonical `instance.py logs` uses (`log_filter.py:80-81`, `instance.py:207-210`). So "host viewer source only" hides that the change reaches the canonical viewer too, though it is not deployed.
   - The "sensitive-field state" claim holds (see `safety.py:71-77`).

## C-34 — `transition_to_final` returned True even when delivery failed
**Verdict: CLOSED.**

1. **What the diff does:**
   - `transition_to_final` returns the result of `_deliver_final` (`tool_progress.py:613`).
   - `_deliver_final` returns True only when the edit succeeds (`:617-628`) or the fallback send returns a message (`:636-651`).
   - It returns False when there is no channel, when the send fails, or when the send returns `None`.
   - The caller sets `transitioned` only on True, or when `on_delivered` already recorded a chunk (`bot.py:13522-13540`). Otherwise chunk 0 goes through `_send_with_slowmode` (`:13546-13560`).
   - Memory and REM record only chunks in `delivered_chunks`, with an incomplete-delivery note (`:13578+`).
2. **Does it close the scenario?** Yes.
3. **Double-send risk:** a duplicate needs the edit *and* the fallback send to both land while both lose their acknowledgements. That is narrow and disclosed as uncertainty. The new `sent is None` check and its new error log are minor, unrequested defensive additions.

## C-35 — cancellation could delete a delivered answer
**Verdict: CLOSED.**

1. **What the diff does:**
   - Cancellation during `posted.edit` propagates with no delete. `CancelledError` is not an `Exception`, and `_stopped` and `_posted = None` were set first, so the safety-net `stop()` cannot delete it (`:565-575`).
   - Cancellation during the fallback send deletes only the progress message whose edit failed (`:637-639`).
2. **Does it close the scenario?** Yes.
3. **Residuals:**
   - If a cancelled edit never landed, the stale "working…" progress message stays as an orphan. That is the deliberate trade-off.
   - A failed edit whose acknowledgement was lost, followed by a cancelled fallback, still deletes a message that may hold the answer. Very narrow; it predates this change.

## C-36 — `dirac.py status` and `restart`
**Verdict: CLOSED.**

1. **What the diff does:**
   - **`status` (`scripts/dirac.py:356-397`):**
     - Reads the owned container state first.
     - Catches only `ValueError` (bridge) and `OSError`/`ValueError` (private layout) and reports them.
     - Docker errors (`RuntimeError`, `instance.py:186`) and ownership errors still raise.
     - The docstring now says the embedding check runs through `docker exec`.
   - **`restart` (`:324-341`):** refuses any status other than `running` before private preparation. It reports exit code, finish time, image and OOM flag, and points to `start --replace`.
2. **Does it close the scenario?** Yes.
3. **Residual:** a small race window — a container that exits between the state check and `docker restart` is still restarted and its stop evidence is lost. Low.

## C-37 — smoke `_handle` cleanup and stop during timeout handling
**Verdict: CLOSED for both round-one scenarios. NEW defect: low.**

1. **What the diff does:**
   - One handler (`dirac_runtime.py:677`) now covers timeout, generic exceptions and cancellation. For any failure after the turn is opened it cancels the exact input, waits for it to settle, then discards it (`:708-761`).
   - The exact task comes from the new `cancel_message_with_task` (`:869-874`).
   - The record is written terminal, with an "unconfirmed" suffix, *before* the wait (`:734-738`). If `stop()` cancels the poller during that wait, the record is `timeout`/`failed`/`interrupted`, never `running`. The retained receipt (`:737-738`) is then reconciled by `stop()` (`:333-360`) or by the poll loop (`:523-531`).
2. **Does it close the scenario?** Yes, both parts.
3. **New defect:** when the input has no task and settlement is unconfirmed, `_handle` sets `_stop_requested = True` (`:749-751`). This is reachable if the deadline expires or an exception escapes during `_on_message_impl` before the message is queued. The poll loop then returns quietly (`:543-545`). The runtime-state file still says `running`, `_started` stays True, and nothing logs that polling stopped. New requests sit pending with an "advisory" health file that is wrong; `dirac_smoke.py health` does say liveness is unknown. Fail-closed was the intent; the status report is what's wrong.
   - **No `_stop_lock` deadlock.** `_stop_lock` is only taken in `stop()`. `_cleanup_lock` is released when the poller is cancelled.
   - **Slower stop:** with a stuck turn, stop can take about 2 × `CLEANUP_SECONDS` (10 s). The poller's handler and `stop()` each wait 5 s. At the timing boundary it can report `stop_unconfirmed` even though the turn settled.
   - **AGENTS.md check:** `except (Exception, asyncio.CancelledError)` merges four handlers that already existed. Cancellation is re-raised, so nothing new is swallowed. The traceback is still discarded, apparently on purpose for privacy.
4. **Overclaim:** "taskless uncertainty fails closed" leaves out that it fails closed without telling anyone (stale health file).

## `message_pipeline.py` (551060d)
**In scope and behaviour-preserving (info).**

`cancel_message_with_task` (`:376-398`) returns `(cancelled, running_task)`. `cancel_message` (`:364-375`) wraps it with identical results. The queue sets the running task and its message ID together in one step (`:311-314`), so there is no gap. `cancel_message` now has no production caller, only tests.

## I-01 / `e540be6` — request withdrawn during the pending listing
**Verdict: CLOSED.** It catches only `FileNotFoundError` around the second `stat` and skips that request (`scripts/dirac_smoke.py:136-139`). No new catch-all.

## D-06 — restart log replay and `--fresh`
**Verdict: CLOSED.** `phase-II_v2/DIRAC_HANDOFF.md:64-66` states:
- restart keeps the log history;
- default `--tail 100` can replay old lines;
- only `logs --fresh` uses tail 0, and it is not a restart flag;
- replacement starts a new log stream;
- stopped/dead restart is refused.

This matches `dirac.py:89-92,405`. Line 23 is a dated note that still says "the redactor [is] unchanged", which is now stale.

## Side observation (outside the cluster)
`7286aa2` changed an existing keyboard test (`test_escape_sequences_do_not_trigger_scope_or_history_keys` → `test_arrow_keys_navigate_…`). Its expectation went from `["q"]` to `["[", "q"]` while `input.py` did not change, i.e. a failing baseline test was made to match the code. This is disclosed in `validation.md` (bash-34) but not in the commit message ("Existing cases only").

## Not read or not verified
- The rest of `d198c37` beyond the two `bot.py` hunks and `tool_progress.py`.
- The full `05` response beyond my blocks.
- The `review-*.md` files, except `review-viewer-authorization.md:18-19`.
- In the viewer package: `append_terminal`, `append_controls`, `paging`, `jsonl`, `terminal`, and `input.py` beyond `KeyBuffer`.
- `smoke_protocol.py` beyond `request_files`, `instance.py` beyond `docker()`, and `bot.py` `_on_message_impl` (so I don't know how reachable the taskless path is).
- Test bodies beyond spot checks.
- No test counts were reproduced.
- The producer inventory for user- or model-controlled log content was a bounded grep, not exhaustive.
