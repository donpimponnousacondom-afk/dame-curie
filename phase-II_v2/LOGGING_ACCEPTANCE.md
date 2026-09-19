# Disposable logging acceptance ledger

Status: **partial acceptance; Screen structured-redaction correction source-reviewed, integration/rerun pending**.

## Scope and isolation

Coordinator observations use main source `2e34000`, including logging through `f023176`. These are one-off synthetic viewer exercises, not new repository tests or test-suite execution.

- Explicit existing Python3.14.4 venv, `-I -S -B`, a cleared/minimal environment, `HOME=/nonexistent`, and generated finite producer programs.
- Entry: `scripts.log_filter.follow_logs(..., output_format="screen")`; never `scripts/instance.py`, app bootstrap or a deployment wrapper.
- Audited import closure: logging modules, standard library and `error_reporting.redact_sensitive_text`. Observed `_store` remains unbound; `bot`, `config`, `providers` and `rag_memory` are absent from `sys.modules`.
- Only disposable PTYs and unnamed temporary output files. No existing Screen session, private log/config/state, credentials, network, Docker, V2 service, Discord or model operation.
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

Fix `702366b` changes only the Screen prepass keyword/docstring and its implementation report. Luna passed its complete inherited redaction/source-line flow; global/legacy behavior and quotas are unchanged. Integration and post-fix rerun are pending. No image-ID correlation acceptance is claimed from the failing exercise.

## Observed: held pipe and repeated exit signals

A fresh disposable controller became a Linux child subreaper for its own process tree only. The generated source reported its own leader/child/PGID; the child installed SIGTERM-ignore before signalling readiness. The controller reaped its own orphaned synthetic child, never signalled the follower group, and targeted repeated signals only at its still-unreaped viewer child. A separate, independently session-owned synthetic sleeper survived both runs and was then explicitly terminated/reaped by the controller.

- Leader exited zero while the TERM-ignoring same-group child held stdout open: viewer returned the documented **incomplete drain** error in **0.424 s**, not a false zero or a hang. The child was reaped with SIGKILL status; the owned group signal-0 probe returned ESRCH. Cleanup itself was not reported incomplete.
- Leader and child ignored TERM; controller sent INT, TERM, HUP, QUIT, TSTP, INT during shutdown: viewer completed requested exit with status zero in **5.376 s**. The child was reaped with SIGKILL status and the group probe returned ESRCH. This exercises the five-second TERM grace and ignored repeated signals during cleanup.
- Both runs restored exact termios, input/output fd flags, handlers and mask. These are observed timings under this synthetic setup, not hard real-time limits or proof about arbitrary detached descendants/real Docker CLI topology. No after-reap mutating signal is inferred from timing; source review separately establishes that order.

## Still pending

- Integrate the source-reviewed fix and rerun valid typed JSON plus plaintext/malformed/multiline redaction paths.
- Foreground loss, first-signal variants, Ctrl-D and deliberate-exception paths beyond the observed incomplete-drain error.
- Pressure, sustained receive/eviction, rejected-page retry, bounded resume, split/expired control sequences, tiny-terminal and resize behavior.
- Disposable GNU Screen copy mode, remapped prefix and detach/reattach behavior; an ordinary PTY is not Screen acceptance.
- Legacy behavior remains source-preserved, not exhaustively re-exercised. No default switch to Screen mode.

None of these observations authorizes bot/Ollama/model-pull activation, private history access, remote publication or V1 mutation.
