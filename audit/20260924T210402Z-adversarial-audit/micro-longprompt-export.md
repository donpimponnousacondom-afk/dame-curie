# Micro-audit: explicit longprompt export

**Coordinator correction — overrides the notice/mismatch conclusions below.** `e47270b89faa6c0c93d76d1bb74b760baa6b9700` is an immutable Git **tree**, not HEAD; HEAD remaining `e540be6` was expected. Before further edits, `git diff --quiet e47270b89faa6c0c93d76d1bb74b760baa6b9700 -- bot.py` exited0. The existing shortened overflow notice with the tested `?` prefix is **105 characters**, verified using literal `printf`/`wc -m`, not over120. The proposed further shortening is unnecessary and was not applied. Export behavior still awaits focused isolated QA. The child's misplaced `temporary audit/…` report was moved intact into this dated audit bundle; original reasoning is retained below, not accepted as a confirmed defect.

## Scope and constraints

- Read `AGENTS.md`, `bot.py` `_handle_command` prompt/longprompt branch, and focused cases in `tests/test_longprompt_command.py`.
- No code changes; no tests, imports, lint, build, or runtime execution.
- Worktree is heavily modified; observed `HEAD` is `e540be6772f76d906720b79b07947a60893c3b24`, not requested frozen `e47270b89faa6c0c93d76d1bb74b760baa6b9700`. Findings describe present worktree only; frozen revision not verified.

## Finding

The explicit `longprompt` no-attachment branch already has the required export behavior at `bot.py:6647-6668`: no prompt is reported; stored content is UTF-8 encoded and rejected only above `TEXT_ATTACHMENT_MAX_BYTES`; otherwise exact bytes are sent as `prompt.txt` under `BytesIO` and `contextlib.closing`. It does not inline short content. This preserves BOM/whitespace because no decode/normalization occurs. Attachment writes retain their separate `SERVER_PROMPT_MAX_BYTES` cap at `bot.py:6673-6678`.

Ordinary `prompt` correctly retains its distinct behavior at `bot.py:6593-6621`: <=1800 UTF-8 bytes inline; larger prompt exports, subject to export cap.

Both over-export notices (`bot.py:6602-6607` and `6653-6658`) interpolate a full replacement suggestion. That copy exceeds the existing <=120 response assertion for the overflow path. Shorten the copy; do not loosen the assertion. E.g. replace each two-line f-string notice with:

```python
f"Prompt exceeds {TEXT_ATTACHMENT_MAX_BYTES // 1024} KiB export limit; unchanged."
```

This retains configured limit information and stays brief. It does not echo prompt text or mentions.

## Existing focused evidence (source only)

- `tests/test_longprompt_command.py:253-294`: `longprompt` exports exact UTF-8 bytes for short and long prompt (BOM, whitespace, CRLF, mentions); file closes; mention suppression; then ordinary short `prompt` is inline.
- `:297-325`: export boundary uses preserved parameter IDs `ascii-at-export-limit` and `unicode-over-export-limit`; exact-at-limit export and >512-KiB overflow are asserted, including <=120 notice. Keep these IDs unchanged.
- `:327-346`: exact-text roundtrip through prompt store and subsequent export.
- `:387-399`: failed export send still closes file buffer.

## Verdict

The core regression fix is already present in the observed branch. The only focused remaining correction is shortening both overflow notices. Source inspection only; no QA claim. Frozen revision mismatch should be resolved by the parent before treating this as verification of `e47270b89faa6c0c93d76d1bb74b760baa6b9700`.
