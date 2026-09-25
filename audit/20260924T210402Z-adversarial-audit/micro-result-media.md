# C20 persisted tool-result media — source review

**Finding: no patch needed.** The current source already closes the described gap.

- `bot.py:13980-14004`: `_remember_tool_call` sanitizes its local `stored_result` first: framed `__IMAGE_B64__`/`__AUDIO_B64__` payloads become encoded UTF-8-byte labels; base64 data URIs become media/format labels with matched-value UTF-8 byte counts. Only then is the result head/tail-bounded to 8,000 chars; the combined memory content is also bounded. Useful surrounding result text remains.
- `bot.py:14259-14274`: dispatch retains the raw result line in `result_by_id` and sends that line to memory recording; `_remember_tool_call` constructs the sanitized copy without mutating that line or the tool arguments.
- `bot.py:14446-14500`: actual result-line media extraction remains later in the dispatch flow, before follow-up stripping/truncation; image/audio payloads are still extracted from the original result text for delivery.
- `tests/test_tts_silent.py:286-293,356-371`: the existing case asserts the raw image payload and data URI do not occur in persisted metadata, and asserts the exact stored result text with truthful length labels and preserved surrounding text. It separately asserts the data URI remains in the returned tool result, while the framed image payload is absent there. No test run performed.

No replacements or test adjustment are missing. This was source inspection only; no QA claim.