# C17 — exact native plugin precedence (source-only)

**Verdict: one policy-override patch remains; exact-plugin precedence itself is present.** No execution, test collection, imports, or runtime inspection performed.

- `tool_schemas.py:1132-1139,1165-1172` preserves `raw_name` while stripping a leading `tool_` into normalized `name`; `tool_bash` otherwise becomes `bash`.
- `bot.py:14049-14050` now uses the bound `self._message_tool_platform(message)` and `self._compatible_tool_names(platform)`. The existing synthetic-platform rejection at `tests/test_tts_silent.py:392-411` therefore reaches the execution gate with the override's empty compatible set.
- `bot.py:14054-14071` restores exact raw names for real builtins first and available, non-disabled, actor-authorized plugins from `_tools_for_turn`, independent of plugins-group visibility. `bot.py:14739-14750` explicitly hides plugins before group discovery; the dispatch restoration is needed. `bot.py:13792-13827` avoids aliasing an available exact plugin, while `bot.py:13839-13855` retains disabled, platform, actor and builtin-over-plugin execution gates. The pre-discovery plugin collision and raw-name history assertions already exist in `tests/test_tts_silent.py:266-373`.

**Missing patch — `bot.py:14724`**: `_turn_tool_names` still invokes the class compatibility method, bypassing the bound override when selecting the offered catalog and its `eligible_names` dispatch input. Replace this exact line only:

```diff
-        compatible = MaxwellBot._compatible_tool_names(self, platform)
+        compatible = self._compatible_tool_names(platform)
```

**Adapt existing case only — `tests/test_tts_silent.py:392-411`**: extend `test_dispatch_native_rejects_platform_incompatible_tool` to catch catalog leakage under its existing override. Replace:

```python
    bot._compatible_tool_names = lambda _platform: set()
    message = SimpleNamespace(
        guild=None, channel=SimpleNamespace(id=123), tool_platform="synthetic"
    )
    raw = [_native_call("react", {"emoji": "catjam"})]
```

with:

```python
    bot._compatible_tool_names = lambda _platform: set()
    bot._native_tools_enabled = lambda: True
    message = SimpleNamespace(
        guild=None, channel=SimpleNamespace(id=123), tool_platform="synthetic"
    )
    assert MaxwellBot._build_openai_tools(bot, platform="synthetic", message=message) == []
    raw = [_native_call("react", {"emoji": "catjam"})]
```

Do not change the exact-name precedence block or create tests/helpers. Parent owns edits and synthetic QA; this report certifies only inspected source, not execution.
