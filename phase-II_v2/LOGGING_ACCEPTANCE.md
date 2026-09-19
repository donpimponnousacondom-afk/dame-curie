# Disposable logging acceptance ledger

Status: **bounded synthetic acceptance completed, including pressure, foreground loss and fresh GNU Screen; not exhaustive terminal/application acceptance**. The structured-redaction correction and recorded reruns passed. Remaining coverage limits are explicit below; no default-mode switch.

## Scope and isolation

Initial coordinator observations used main source `2e34000`, including logging through `f023176`; the corrected reruns include `c2f148b`. Final exercises use the same logging code present in selected release `734c050` and documentation-only checkout `5ef235a`. These are one-off synthetic viewer exercises, not new repository tests or test-suite execution.

- Explicit existing Python3.14.4 venv, `-I -S -B`, a cleared/minimal environment, `HOME=/nonexistent` or a fresh owned temporary HOME, and generated finite producer programs.
- Entry: `scripts.log_filter.follow_logs(..., output_format="screen")`; never `scripts/instance.py`, app bootstrap or a deployment wrapper.
- Audited import closure: logging modules, standard library and `error_reporting.redact_sensitive_text`. Observed `_store` remains unbound; `bot`, `config`, `providers` and `rag_memory` are absent from `sys.modules`.
- Only disposable PTYs/output files and fresh mode0700 Screen/HOME namespaces with synthetic window logs. No existing Screen session, private application log/config/state, credentials, network, Docker, V2 service, Discord or model operation in these logging exercises.
- All producer text and secret-like values are synthetic. Viewer output is not proof of producer-before-persistence secrecy.

## Observed: keyless pipe and regular-file paths

Both finite runs exited zero. Captured outputs contained no raw ESC bytes, omitted the fake API-key value, and escaped injected erase/title/BEL/CR/bidi controls. Descriptor flags, exit-signal handlers and signal mask matched their saved values after return. The regular-file path emitted its explicit filesystem-blocking warning; no filesystem-latency guarantee was measured.

## Observed: ordinary PTY, controls and terminal variants

The disposable child owned its PTY foreground group. In `TERM=screen-256color`, output contained SGR styling only: no non-SGR ESC and no carriage return other than normal PTY-generated CRLF. `TERM=dumb`, an unknown terminal name and `NO_COLOR=1` emitted no SGR.

Keys exercised: help, local counters, folding/detail toggles, recent/unfiltered error replay, older/newer navigation, pinned-page boundaries, pause/resume, reset and quit. Output showed labelled out-of-band replay/pages and clamped boundaries rather than repaint. These small runs do not establish pressure/eviction/resize behavior.

All five PTY runs restored exact termios, input/output descriptor flags, exit-signal handlers and signal mask. Four keyboard-enabled runs ended on requested `q` with status zero. The keyless run ignored typed `q`, waited for source EOF and exited nonzero for the evidence omission below; restoration still completed. Its ordinary terminal echo is not viewer key dispatch.

## Defect found: valid typed JSON corrupted before recognition

A valid synthetic image-start record containing a `request_id` and an `api_key` was converted to `image.request.unparsed`; the request ID disappeared. The Screen prepass applied text redaction before JSON recognition, replacing a quoted value with bare `[REDACTED]`. At EOF the viewer correctly reported incomplete evidence, but the original input should have remained a typed, field-redacted event. The earlier `q` statuses do not certify lossless ingestion.

Luna independently confirmed this is a Screen-local regression, not a legacy parsing defect. The original logging worker owns a narrow fix: retain multiline/private/config suppression, then use the existing structured redaction path before retention. Global redaction and legacy modes must not change. Current-line config/header/env-dump and private-key markers intentionally retain conservative whole-record suppression, which can hide an image ID; no broad sanitizer redesign is authorized.

Fix `702366b` changes only the Screen prepass keyword/docstring and its implementation report. Luna passed its complete inherited redaction/source-line flow; global/legacy behavior and quotas are unchanged. It landed as `c2f148b`; the post-fix observations below use integrated source `9d1abc8`. No image-ID correlation acceptance is inferred from the failing pre-fix exercise.

### Post-fix rerun

All five previous PTY variants returned zero and retained `image.request_id=synthetic-image-7`; none reported an unparsed image or exposed either fake secret. Exact terminal/flags/handlers/mask restoration, unbound store, unloaded app modules and escape/color behavior remained unchanged. The first variant exercised eight labelled page outputs and six replay headings; counters showed pause then reset/resume. The keyless variant ignored typed `q` and completed natural EOF in 1.628 s.

Additional finite, keyless pipe observations:

- Generic JSON redacted its secret while preserving valid JSON, but its arbitrary `request_id` did **not** become typed correlation. A valid image-done record retained its own typed ID and redacted its password; plaintext password redaction also passed. Exit zero.
- Config and private-key multiline continuations containing unlabelled fake secrets stayed hidden. Valid image records after each closing marker resumed normal typed IDs. A current-line headers marker intentionally suppressed the whole typed record. Exit zero.
- Malformed image JSON was omitted without exposing its fake secret; a later valid image retained its ID. EOF reported incomplete evidence, status one, without sticky continuity loss.
- A 70,000-character record caused sticky framing/continuity omission: subsequent unlabelled fake secret and typed ID stayed hidden. EOF reported incomplete evidence, status one.

Every additional run restored flags/handlers/mask, kept the store unbound and loaded no checked application modules. No raw ESC or fake-secret value appeared. These observations validate the narrow correction and specified failure behavior, not exhaustive sanitization.

## Observed: held pipe and repeated exit signals

A fresh disposable controller became a Linux child subreaper for its own process tree only. The generated source reported its own leader/child/PGID; the child installed SIGTERM-ignore before signalling readiness. The controller reaped its own orphaned synthetic child, never signalled the follower group, and targeted repeated signals only at its still-unreaped viewer child. A separate, independently session-owned synthetic sleeper survived both runs and was then explicitly terminated/reaped by the controller.

- Leader exited zero while the TERM-ignoring same-group child held stdout open: viewer returned the documented **incomplete drain** error in **0.424 s**, not a false zero or a hang. The child was reaped with SIGKILL status; the owned group signal-0 probe returned ESRCH. Cleanup itself was not reported incomplete.
- Leader and child ignored TERM; controller sent INT, TERM, HUP, QUIT, TSTP, INT during shutdown: viewer completed requested exit with status zero in **5.376 s**. The child was reaped with SIGKILL status and the group probe returned ESRCH. This exercises the five-second TERM grace and ignored repeated signals during cleanup.
- Both runs restored exact termios, input/output fd flags, handlers and mask. These are observed timings under this synthetic setup, not hard real-time limits or proof about arbitrary detached descendants/real Docker CLI topology. No after-reap mutating signal is inferred from timing; source review separately establishes that order.

## Observed: paused eviction, bounded resume and blocked-output quit

Collected `bash-531` completed exit0. Child-local wrappers around the public `AppendState.receive` and `AppendWriter.submit` methods called the originals once, preserved their return values and recorded only synthetic counters. These instrumentation/retention observations are not RSS or whole-process memory bounds.

- **Paused ingestion:** one completed seed plus 1,500 distinct records produced receive#1501, exactly 500 retained records/230,500 serialized bytes, 1,001 total evictions and zero omitted records/live drops. Completed LIVE watermark stayed at1. Resume disclosed 1,000 unavailable records in the paused range and 480 catch-up-limit omissions, then emitted exactly20 replay rows ending at the newest record. Final observed queue peaks were2 blocks/2,678 bytes. Requested quit, exact restoration and follower-group disappearance passed; settlement observed0.063s.
- **Blocked output:** after the seed, the controller stopped draining the PTY until after viewer exit. Another 1,500 records with 4KiB payloads were fully ingested. Final history held243 records/2,094,903 bytes with1,258 evictions, zero input omissions,1,292 LIVE display drops and completed LIVE watermark81. Observed history peaks were244 records/2,095,334 bytes; queue peaks128 blocks/27,262 bytes. This exercised the history byte cap and queue block cap, not saturation of the queue byte cap. Quit still returned normally with exact restoration and group disappearance in0.091s without clearing output pressure first. Exit0 is not a lossless-delivery claim.

## Observed: resize, split controls, exit signals and injected exception

Collected `bash-536` completed exit0 over seven fresh PTYs. At3x3, help reported the minimum4x4 warning. Resizing to80x24 and paging the old pin retained its tiny geometry; requesting fresh help rebuilt a usable page. A child-local `AppendKeys.feed` observer confirmed separate input chunks for a split arrow and split bracketed paste containing `q0ir `; none dispatched commands. A later ordinary `i` worked. An unfinished CSI expired into the explicit sticky-disabled notice; later `q0i` dispatched nothing, while ISIG Ctrl-C still exited.

Fresh Ctrl-D, first SIGTERM/HUP/QUIT/TSTP runs exited0. A deliberate `RuntimeError("synthetic-viewer-exception")` after the third received record exited1 as expected. Every case restored exact termios, both fd flags, handlers and mask; the store remained unbound, app modules absent and the owned source group gone. Observed settlement intervals ranged0.065–0.224s; these are sampled timings, not hard deadlines. The initial tiny-terminal controller incorrectly waited for text that the viewer intentionally abbreviated; geometry-independent readiness corrected the exercise, not product code.

## Observed: real foreground transfer

Collected `bash-537` completed exit0. A disposable helper had its own process group inside the viewer's PTY session. After the third synthetic record, the probe transferred the actual terminal foreground group to that helper. The loop recorded `terminal foreground ownership lost` and returned normally. Exact terminal/fd/handler/mask restoration was measured **while the helper still owned the foreground**; the viewer did not steal it back. The helper survived follower cleanup. Only afterwards did the controller reclaim its own disposable TTY and terminate/reap its own helper. Both helper and source group were gone; sampled transfer-through-cleanup interval0.051s. The racing SIGTTIN/SIGTTOU exception variant is not established by this quiet transfer.

## Observed: fresh GNU Screen

Installed GNU Screen4.09.01 help and its local manual were checked, including `-D -m` nonforking ownership, `-e`, `-L`/`-Logfile`, system/user rc selection and disabled login accounting. Collected corrected run `bash-530` completed exit0:

- Fresh0700 SCREENDIR/HOME, null system rc, a tiny owned rc, login accounting disabled, exact private session selectors and only the synthetic viewer/source. No existing sessions were listed, attached or controlled.
- Verified the reserved Screen server remained nonforking; viewer/source parent and process-group relationships matched the owned tree, and the window viewer owned its foreground TTY with keys on.
- Ctrl-B was the remapped Screen prefix. Paused viewer output stayed unchanged while `h`/`b` moved within Screen copy mode. Screen's copy-exit `q` was consumed there; subsequent viewer `i` worked. Exact detach/reattach preserved the same running viewer, then local-state/help keys still worked.
- Normal viewer quit returned successfully; server and attachment exited0. Exact termios/fd/handler/mask restoration, unbound store and absent app imports passed. The3,743-byte **window log**, not Screen-rendered attach bytes, contained only viewer-owned SGR and ordinary CRLF. Screen's own redraw/alternate-buffer controls in the attachment stream are expected and were not misattributed to the viewer.
- Viewer/source group disappeared; an independent synthetic sleeper survived and was separately cleaned up. Quit-to-settlement observed0.064s. The owned socket namespace and temporary files were removed.

Earlier Screen controller attempts were rejected rather than counted as passes: `i` is itself a Screen copy-mode exit, so an additional Escape contaminated the next key check; attach readiness and a placeholder-built producer environment also needed correction. Another controller wrongly treated successful `follow_logs() -> None` as a nonzero exit. The final run records normal return separately from child/server status. No product change was needed for these controller corrections; all ended synthetic namespaces were ownership-checked and cleaned.

## Remaining coverage limits

- Rejected-page retry under a saturated priority-only queue, queue byte-cap saturation, very long sustained/RSS behavior and every pinned-evidence/eviction combination were not exercised.
- Split arrows/paste and expired CSI passed; broader UTF-8/SS3/Alt fragmentation, long OSC/DCS bodies (including >64 bytes), C1 ST and all malformed/delayed suffix combinations were not exercised.
- Quiet foreground loss passed; racing job-control signals, forced Screen-server death and every terminal/backend/platform combination are not exhaustively accepted.
- Legacy behavior remains source-preserved, not exhaustively re-exercised. Producer-before-persistence secrecy, native operational event transport and arbitrary detached descendants remain outside this viewer's demonstrated contract.
- No default switch to Screen mode. These are bounded synthetic observations, not application, Discord, voice/media, provider, RAG or replica acceptance.

None of these observations authorizes bot/Ollama/model-pull activation, private history access, remote publication or V1 mutation.
