# Implementation report — log viewer framing, omission visibility, redaction continuity (C-31/C-32/C-33)

Temporary review evidence. **Retire after round two is accepted.** Authored by the `deepseek-flash` source lane; source-only, no application imports, no test collection/execution, no runtime/private/Docker/Screen access, no provider calls, no commits. Baseline `aad36e6`, working tree otherwise unchanged by me (`AGENTS.md`/`TODO.md`/`.agents`/`reports` modifications are not mine).

## 1. Redactor flow proved before any change

Two rejection sites exist in `scripts/log_console/append_events.py` and they are **not** equivalent. Confirmed by reading the complete path:

- **Oversize service prefix — rejected BEFORE redaction.** `COMPOSE.fullmatch` in `record()` is evaluated on the raw framed line; the redactor runs later inside `parse() -> content()` (`:105`, `EventParser` via `super()`), and `parse()` also builds `source_line` from the redacted message. Under baseline, `record()` latched on `line is None or (compose and service > 256 bytes)` and then **replaced the line with a fixed string before calling `parse()`**, so for that path the original body never reached `EvidenceRedactor` and `private_keys`/`config_depth` were never updated. Intake item 2 was correct.
- **Structure-depth failure — after redaction.** `bounded_structure(message)` was evaluated on the value returned by `redactor.text(...)`, i.e. after the whole message had been scanned and the multiline-hiding state committed.
- **`line is None` — no scan at all.** `AppendLines.take()` returns `None` for a record it discarded without decoding (`:43-46`), so those bytes were never examined by anything.

That asymmetry is the whole design constraint: the code latched harder on the case it had already scanned than on the case it had not.

## 2. Changed semantics

### 2.1 `scripts/log_console/append_events.py`

New module constants `OMITTED_CONTINUITY`, `OMITTED_SERVICE`, `OMITTED_STRUCTURE`, `OMITTED_MALFORMED` — fixed assertions. An omitted record is never re-rendered; its retained bytes never reach the terminal.

New `json_candidate(text)`: `text.startswith(("{", "["))`. This is exactly the predicate under which `EventParser.content` calls `json.dumps`/`json.loads` and under which `EvidenceRedactor.message` attempts structured handling, so it is the set that can actually raise `RecursionError`.

New `omitted_event(kind, message, parse_error)`: builds the replacement `LogEvent` directly with `scope=VIEWER_SCOPE`, `level=None`, `service=None`, `logger=None`, `timestamp_origin="observed"`, `details={}`, `source_line=message`.

`AppendParser.content()`:

1. redact first, unchanged (`redactor.text(..., service=service, redacted=True)`);
2. retain the existing `HISTORY_RECORDS` oversize-state clear and latch, unchanged;
3. latch -> `OMITTED_CONTINUITY` with `parse_error="RedactionContinuityLost"`;
4. `message == REDACTED` -> unchanged pass-through of `REDACTED` (checked before the bound so a hidden body is never re-described);
5. `json_candidate(message) and not bounded_structure(message)` -> `OMITTED_STRUCTURE`, **per-record, no latch**, state retained (the scan already happened);
6. otherwise delegate to `EventParser.content`, which keeps its `(ValueError, RecursionError)` handling; a non-`None` parse error now becomes `OMITTED_MALFORMED` **preserving the recognizer and details** (`result[2]`) instead of the previous hard-coded empty dict — same visible text, no data invented.

`AppendParser.record()` — the ordering is the safety property:

1. `line is None` -> lifetime latch `continuity_lost = True`, return `OMITTED_CONTINUITY`. Bytes that were never scanned can still hide a key/config opening marker, so fail-closed is retained indefinitely and `append.py:133-134` still prints its out-of-band notice.
2. otherwise `event = self.parse(line)` runs **unconditionally**, so the full original framed record — including any service prefix and any `-----BEGIN PRIVATE KEY-----` line — goes through `content()` and commits redaction state before any decision is made about it;
3. if that parse raised the latch (oversize redaction state) -> `OMITTED_CONTINUITY`;
4. oversize service prefix (`COMPOSE` service > 256 UTF-8 bytes) -> `OMITTED_SERVICE`, **per-record only**: the record was fully scanned and all intervening boundaries were seen, so this is an attribution/boundary loss, not a continuity loss. Redaction state is provably retained because step 2 scanned those bytes;
5. else return the parsed event unchanged.

Net structural effect: every message that `bounded_structure` now examines was already examined before, and the non-JSON plain-text records that used to be rejected are no longer examined at all. The change is strictly narrower than baseline; it removes omission paths rather than adding them.

### 2.2 Omission visibility — no toggle

`scripts/log_console/scopes.py` gains `VIEWER_SCOPE = "viewer"`, **deliberately not a member of `SCOPE_KEYS`**. Adding it to the key map would have created a key that can hide omissions, which is the opposite of the requirement.

`scripts/log_console/append_state.py` `Filters.visible()` returns `True` for `event.scope == VIEWER_SCOPE` before the severity-rank, scope-set and Ollama checks. Consequences:

- `viewer.omitted` records survive every `s/b/p/d/t/c/w/a` toggle, `+/-` minimum severity, and the Ollama-vs-local-service predicate. No key and no verbosity level can suppress them.
- They remain ordinary retained records: counted by `AppendHistory.omitted`, shown live by `AppendState.receive`, reachable by `[`/`]` navigation and `Enter` inspection, and reported by the `i` inspector.
- `metadata_scope` cannot produce `"viewer"` (its outputs are `system`/`bot`/`provider`/`discord`/`tool`/`context`/`web`/`subagent`, with `events.py` falling back to `"service"`), so this scope is exclusively viewer-asserted and cannot collide with a producer-derived scope.
- The scope is not a control-surface leak: `append_controls.dispatch` and `filter_key` iterate `SCOPE_KEYS`, so no key reaches it.

`scripts/log_console/append_render.py` adds a `viewer` colour and one help line stating that viewer omission records are not scope-toggleable. `scripts/log_console/render.py` help text is unchanged (back to baseline), because the static console has no viewer scope.

### 2.3 What was deliberately NOT done

- No change to `MAX_DEPTH`, `MAX_STRUCTURES`, `RECORD_BYTES` or the 256-byte service bound. Raising a limit only moves the trigger.
- No clamping, truncating or rewording of the oversized service name, and no attempt to attribute such a record to its service.
- No `try`/`except` anywhere; no new logging; no unrelated refactor.
- No `bot.py` change — the untrusted `MSG` producer is the parent's slice (see §6).
- No change to `scripts/log_console/input.py` or `controls.py` (both reverted to baseline; see §5).
- No new test files or test functions.

## 3. Behaviour under the audit's scenarios

| Scenario | Baseline | Now |
| --- | --- | --- |
| User message whose preview is `"[" * 33` (`bot.py` producer, preview capped at 100 chars) | preview is not a JSON candidate, but `bounded_structure` ran on it anyway -> depth 33 > 32 -> permanent latch -> pane blank until `--fresh` | not a JSON candidate, so no structure check; the preview renders as ordinary text; no latch. Even the fixture shape used before the preview change (`"[" * 33` as a record body) is now parsed rather than latched |
| Record body that *is* a JSON candidate nested past 32 | permanent latch | one `viewer.omitted` record, visible, no latch; next ordinary record renders |
| 257-byte service prefix | permanent latch, body never redacted | body fully redacted first, then one `viewer.omitted` record; no latch |
| Record over `RECORD_BYTES` (for example the retired 100,311-byte tool result) | permanent latch | unchanged: permanent latch, fail-closed, out-of-band notice |
| `-----BEGIN PRIVATE KEY-----` inside the above scenarios | hides that service until the END marker | identical: the marker is scanned in step 2 before any omission |
| Malformed structured record | `OMITTED_MALFORMED`, no latch | identical text, recognizer/details preserved |
| Any omitted record | scope `service`; excluded by every scope key, and by `+/-` in the append viewer | scope `viewer`; visible regardless of all filters, still countable and inspectable |

CPU/memory: unchanged and still bounded by `RECORD_BYTES` (64 KiB) for framing, `ENCODED_BYTES`/`HISTORY_BYTES`/`HISTORY_RECORDS` for retention, and `QUEUE_BYTES`/`QUEUE_BLOCKS` for output. The structure scan is over one already-framed record; the `HISTORY_RECORDS` cap on redactor state is untouched.

## 4. Existing fixtures adapted

Exactly one line, `tests/test_log_console_render.py:92`: `ConsoleState(enabled_scopes=set(), verbosity=4, ...)` -> `verbosity=2`.

This is not a security or assertion weakening. `ConsoleState.verbosity` is a real pre-existing field and is used as an **index into `LEVELS`** (`render.py:169`, `render.py:157`, `visible()`); index 4 is out of range and would raise `IndexError` on the first paint, while `2` is `WARNING` and preserves the fixture's intent (suppress INFO while proving exact-prompt/source forensic paging remains filter-independent). All the fixture's other assertions are untouched, including the `state.key("0")` reset comparison. The other three render baselines named in the audit (timestamp span, eighty-column, health coalescing, escape-key) needed no edit: each was already satisfiable by the current control/render API, and the four recorded failures were all caused by the same single stale constructor call.

No constructor field was added to satisfy a test. `tests/test_log_console_render.py` is the only test file that imports `ConsoleState`, `LineBuffer`, `KeyBuffer` or `SCOPE_KEYS`.

## 4a. Append-path regression cases (added after review)

**Correction and disclosure.** An earlier revision of this section added three new test functions plus a module-level helper and constants. That violated the stated boundary: *no new test functions, extend existing bodies or parameterizations only*. The parent caught it and it has been corrected. Nothing from that revision survives; the current tree contains **no added test functions, no added helpers, no added test file**. Every append-path case below lives inside an existing test body, which is named.

**Two further defects were then found by parent review of this source, and both were real:**

- **D2 — parser rejections were filtered out.** `AppendParser.content` returned a placeholder tuple `(None, OMITTED_STRUCTURE, {}, "Omitted")`. `EventParser.parse` then labelled it `kind="text"`, `scope="service"`, and `record()` returned it unchanged — so the structure and malformed omissions were *still* invisible to every scope key except the `"service"` fallback. My §2.1 claim to have made omissions visible held only for the framing-gap path. **Cause of the mistake: I verified the omission *event* constructor and never traced the returned tuple back through `parse()`.** Fixed by raising `ViewerOmission(message, parse_error)` from `content()` and converting it in `record()` via `omitted_event(...)`, which also keeps the Docker timestamp when the record carries one. The base `EventParser.parse` path is unchanged; only `AppendParser.record` interprets the signal.
- **D3 — the `json_candidate` claim was false.** I wrote "only brace/bracket prefixes reach `json.loads`". `recognizers.py:75-86` parses an `IMAGE_LOG` payload with `json.loads` whatever its first character is, so a deep image-envelope payload bypassed the nesting bound entirely. The predicate now also accepts `IMAGE_LOG.fullmatch(text)` and a `CONFIG_DUMP.search(text)` match — the two other shapes that reach a recursive JSON operation. `CONFIG_DUMP` bodies normally return early as `REDACTED`, so that arm is conservative coverage rather than a live path; the image arm is a live path and is what D3 was about. A deep image-envelope input was added to the existing parametrization as `id="deep-image-envelope"`.
- **Also converted:** the `AppendHistory` `SerializedBudget` replacement now emits a viewer-owned omission too. It previously kept the record's original scope and kind, so an over-budget record could still be hidden by that scope's key.

`scripts/log_console/append_events.py` had **no** test coverage before this change — nothing under `tests/` imported `AppendParser` — so these claims would otherwise have been unfalsifiable. The cases are carried by four existing tests, in files whose subject already covers the same contract.

| Scenario | Existing test extended | How |
| --- | --- | --- |
| (a) 33 brackets then a good record | `tests/test_log_console_robustness.py::test_failed_json_ingestion_retains_safe_fallback_and_next_event` | new parameterization inputs `id="bracket-depth"` and `id="deep-image-envelope"`, plus an inlined loop over the test's own two `lines` through `AppendParser().record()` |
| (b) JSON depth rejection then a good record | same test | the inlined loop runs for every input; all four deep/malformed payloads assert `parse_error == "Omitted"`, the omitted record is `viewer.omitted` in `VIEWER_SCOPE`, record 1 parses, `continuity_lost is False` |
| (c) private key + config + brackets + good records | `tests/test_log_console_events.py::test_multiline_private_key_and_config_blocks_are_redacted_per_service` | one line pair added to the test's existing `lines` list, then the whole list inlined through one `AppendParser` and asserted per index |
| (d) `line=None` permanently suppresses later secret lines | `tests/test_log_console_events.py::test_jsonl_does_not_coalesce_health_or_drop_interleaved_traceback_lines` | inlined `parser.record(None)` followed by a secret line and the test's own last health line |
| (e) omission visible under all scopes off / highest severity | `test_multiline_private_key_and_config_blocks_are_redacted_per_service` and `tests/test_log_console_render.py::test_all_scope_toggles_depth_controls_verbosity_and_reset_are_local` and `test_input_overflow_is_a_local_omission_notice_not_a_fake_producer_record` | `Filters(scopes=set(), minimum=4, ollama=False)` compared against a plain INFO record in the same expression, plus the static-console equivalent |
| (f) redaction state retained | `test_multiline_private_key_and_config_blocks_are_redacted_per_service` | the same list drives both the JSONL contract and the append parser; index 1 asserts `[REDACTED]` and no latch |

Answered from the unchanged line-by-line trace of that list: indices **0, 4 and 6** are omitted and 1, 2, 3, 5, 7–11 parse. Index 0 and 4 and 6 are all `RedactionContinuityLost` because the large-body classification saturates — the first record raises the latch and every later record is omitted *through the latch*, so the omission set is order-dependent and the assertion is written as an exact index list plus a set of error classes rather than a per-index claim I could not justify.

## 4b. Static-console omission visibility — fixed in source, adapted in existing fixtures

The conservative answer to the review question was: **yes**, it could be hidden. `Console.ingest(None, ...)` built its record with `dataclasses.replace` over a text parse, which left `level=None`, `service=None` and scope `"system"` (via `metadata_scope`). Through `ConsoleState.visible` that meant `LEVEL_VALUE.get(event.level or "INFO", 1) == 1`, so `verbosity > 1` — one press of `-` — hid it, and toggling `s` off hid it *and* dropped it from `state.choices`, making it unreachable by `[`/`]` as well. "The static console has no latch" was not evidence that it needs none: the dropped record is the same unknown-redaction-state event, and a `BEGIN` marker inside it would leave every later secret line unmasked.

Fixed in source, no new control and no new key:

- `console.py` now uses the **same** `AppendParser` as the append viewer instead of `EventParser`. `ingest` calls `parser.record(line)` for ordinary lines and `parser.record(None)` for the dropped record, so the latch, the per-record omissions and the redaction state are all shared rather than reimplemented. The framing limit (`MAX_PENDING_BYTES`), the `omitted_events` counter and the health feed/prune behaviour are unchanged; the static-specific notice text is preserved with one `dataclasses.replace` over the returned event.
- `controls.py` `ConsoleState.visible` returns `True` for `VIEWER_SCOPE` before the scope/severity/Ollama checks, mirroring `Filters.visible`. The scope is **not** added to `SCOPE_KEYS`, so no key reaches it and no toggle can hide it.
- `scopes.py` holds `VIEWER_SCOPE` as a module constant outside `SCOPE_KEYS`.

Why arbitrary log text cannot claim this: a producer record's scope comes only from `metadata_scope`, whose possible outputs are `system`, `bot`, `provider`, `discord`, `tool`, `context`, `web`, `subagent`, or the `events.py` fallback `"service"` — never `"viewer"`. Only the viewer's own omission constructor sets it, reachable only from `AppendParser` and `Console.ingest`. It is not a recognizer target either, so a forged line cannot make itself viewer-owned by content.

Existing fixtures adapted for this, both of which already exercise the relevant control surface:

- `tests/test_log_console_render.py::test_input_overflow_is_a_local_omission_notice_not_a_fake_producer_record` — its `kind` assertion updated from `console.omitted` to the viewer-owned `viewer.omitted`, scope asserted `VIEWER_SCOPE`, and extended: with `verbosity = CRITICAL` and `enabled_scopes` cleared, a following INFO record is asserted absent from `console.frame(...)` while the omission notice is asserted present.
- `tests/test_log_console_render.py::test_all_scope_toggles_depth_controls_verbosity_and_reset_are_local` — extended so that, with the state already at CRITICAL and a separate `ConsoleState(verbosity=CRITICAL, enabled_scopes=set())`, a plain INFO record is not visible, a viewer-owned record is, and `render_frame` shows the viewer row while the INFO row stays out. The test's existing `key("0")` reset and all its prior assertions are unchanged.

I did not add a `v` toggle or any other control for this.

## 5. Claims I could not execute, and one I got wrong

Source-only lane: no `pytest`, no imports. The static traces behind §1, §2 and §4 are complete control-flow reads, not executions.

- **`LineBuffer` — I was wrong, then reverted.** I initially proposed clearing `discarding` when the overflow `None` is yielded, and argued a specific fixture failed. Re-reading the actual feeds against the actual source shows the opposite: `feed(b"\nnext\n")` takes the newline branch at `input.py:27-28`, which clears `pending` and sets `discarding = False`, so a following newline-less record buffers normally and `finish()` yields it. The only safe resumption boundary is a consumed newline, exactly as the parent said. `input.py` is byte-identical to baseline.
- **Static console.** `console.py`/`controls.py` have no latch and no structure bound, and their own omission record (`kind="console.omitted"`, `parse_error="InputRecordTooLarge"`) is produced with scope `system`, which is in `SCOPE_KEYS` and already renders through the `[unparsed: ...]` path. I therefore did not add a viewer bypass there. If review wants the static viewer to treat viewer-scope records as unfilterable too, that is a small follow-up in `ConsoleState.visible`, decided by the parent.
- **Residual risk that needs the parent's execution:** that dropping the latches for the two recovered paths does not leave any *other* record unredacted. Static argument: both recovered paths now scan first, and the only remaining latch trigger (`line is None`) is the only path where bytes are unseen. Any counter-example found by QA invalidates this report's §2.1 and should be sent back to me.

## 6. Unresolved producer requirement (outside my lane)

`bot.py:5761-5771` still writes an unescaped, newline-bearing, user-controlled preview as an INFO record. The viewer repairs in this report make that record *safe to consume* (no latch, no permanent loss, no forgeable omission state) but they cannot make the **preview itself** trustworthy: a newline in the preview still splits one message into several viewer records, and a forged `MSG from …` line is still indistinguishable from a real one at the viewer.

The parent's stated producer decision — numeric actor/channel/guild IDs plus content length only, keeping the recognisable `MSG` prefix — is the correct half. Because the preview becomes digits and separators, the remaining injection surface there is reduced to none of brackets/newlines/PEM markers. Two points to keep in mind while that lands:

1. The parent's change must not be relied upon as the reason the viewer is safe. This repair must hold on its own for every other producer, which is why the latch is retained for any record whose bytes were not scanned.
2. The viewer's `metadata_scope` attributes by logger/service, not by content, so dropping the preview text does not change the message's scope classification.

## 7. QA selection (for the parent to run)

Targeted, in priority order:

- `tests/test_log_console_events.py` — primary. `test_multiline_private_key_and_config_blocks_are_redacted_per_service` now carries the private-key/config sequence and the visibility comparison; `test_jsonl_does_not_coalesce_health_or_drop_interleaved_traceback_lines` carries the framing-gap case. These are the falsifiers for §2.1.
- `tests/test_log_console_robustness.py` — `test_failed_json_ingestion_retains_safe_fallback_and_next_event` now carries the bracket-depth parameterization and the append-viewer loop.
- `tests/test_log_console_render.py` — `test_input_overflow_is_a_local_omission_notice_not_a_fake_producer_record` and `test_all_scope_toggles_depth_controls_verbosity_and_reset_are_local` carry the static omission-visibility assertions; the `verbosity=2` fixture line is the only other change. Any remaining failure means my static pass was wrong; I want the traceback.
- `tests/test_log_console_history.py`, `tests/test_log_console_integration.py`, `tests/test_log_console_tty.py` — no changed symbol imported; must stay green.
- Behaviours most needing independent eyes beyond the cases: the private-key recovery in `test_multiline_private_key_and_config_blocks_are_redacted_per_service` (a PEM opening must still hide the *following* lines while the recovery record itself renders), and the `console.py`/`controls.py` static path, which no case asserted before.

## 8. Scope and deployment effect

Changed source: `scripts/log_console/append_events.py`, `append_state.py`, `append_render.py`, `scopes.py`, `console.py`, `controls.py`. Changed tests (existing bodies only, no new definitions): `tests/test_log_console_robustness.py`, `tests/test_log_console_events.py`, `tests/test_log_console_render.py`. No deployment effect, no runtime action, no commit; nothing outside the two stated ownership lanes was touched.
