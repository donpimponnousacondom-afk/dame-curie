# C16 micro-review — custom tool prompt budget

**Verdict:** current source contains the narrow fix; retain it. Static review only; no imports or tests run. No deployment effect.

- `tool_prompts.py:189-202,221`: non-native `tool_system_prompt` builds one contiguous string beginning `## Available tools\n`, containing catalog and `## How to call` XML protocol, then appends `TOOL_PROTOCOL`. This is the actual prefix that needs protection.
- `bot.py:15295-15317`: `_apply_prompt_budget` copies messages, recognizes that exact prefix only on `role == "system"`, and records the whole dedicated message as protected; `bot.py:15339-15354` skips it during middle-clipping and raises `PromptBudgetExceeded` if the remaining protected input exceeds the budget. The protection does not match `role == "user"` or a RAG system block merely **mentioning** the prefix later in its text. It is prefix-based, not provenance-based: a system RAG block *beginning* with that exact prefix would also be protected; do not claim otherwise.
- `bot.py:15413` / `bot.py:13083-13099`: the composed tool prompt and separate custom-protocol block are dedicated system messages before budgeting. `bot.py:13226-13254` applies the budget again after catalog refresh. The separate `Custom tool protocol:` prefix is already protected.
- `tests/test_tts_silent.py:706-748`: existing fixture has 50,000 RAG chars and 20,000 filler chars versus 10,000 budget; trimming from the end shortens filler but does **not remove it**. The assertion at lines 728-731 expects removal and fails for the right reason. `too_large` already exercises visible failure for a protected 12,000-char available-tools block.

**Tiny existing-case edits only** (`test_prompt_budget_trims_large_background_blocks`):

1. After `contract` definition add `catalog = {"role": "system", "content": "## Available tools\n" + "t" * 300}`; insert `catalog,` immediately after `contract,` in `messages`. Change RAG text to `"RAG summary mentions ## Available tools\\n and Custom tool protocol: " + "x" * 50000` (literal source should use `\n`, not an actual source-line break). Change previous-conversation content to `"<previous_conversation>\n## Available tools\nCustom tool protocol:\n" + "p" * 1000` and update its current startswith-removal assertion unchanged.
2. Replace the failed `assert not any(...startswith("Unprotected system filler")...)` block at lines 728-731 with:

```python
    filler = next(
        item for item in trimmed
        if str(item.get("content") or "").startswith("Unprotected system filler")
    )
    assert "prompt budget trimmed" in filler["content"]
    assert len(filler["content"]) < len(messages[6]["content"])
```

3. Beside `assert contract in trimmed`, add `assert catalog in trimmed` and `assert catalog["content"] == "## Available tools\n" + "t" * 300`. The existing RAG trim assertion and removed previous-conversation assertion test unprotected **lookalikes**; the added dedicated catalog tests the whole block, and existing `too_large` tests visible failure. After inserting `catalog`, filler is `messages[6]`.

No bot/tool prompt/source changes recommended. Parent should apply the fixture edit and run its isolated QA; this pass did not run it.
