# Implementation report — existing-test fixture contract drift (QA52 tree `21f57d4…`)

Temporary review evidence. **Retire after round two is accepted.** Authored by the `deepseek-flash` bounded source lane. Source-only: no interpreter/Python/application imports, no test collection/execution, no lint/compile/AST/scanner runs, no runtime/Docker/private-env/state/raw-log/network/install access, no commits, no subagents. Baseline `e540be6`; task-granted tree `21f57d4…` (`git cat-file` object inspection only). Failures read from the synthetic credential-free QA52 stdout `/tmp/dsh-subprocess-Klrmz2/dsh-subprocess-3339121-5-f3158dd51866-stdout.log` (lines 213–1675; targeted reads to avoid the multi-kilobyte parameter-id lines). Baseline counts are the parent's, not a run of mine.

## 0. Retractions (parent review, first round)

The parent did **not** fully accept this handoff. Retracted here, and these points override anything to the contrary below.

1. **The `test_reasoning_commands.py::test_other_models_are_explicitly_unsupported` change is withdrawn and is not a fix.** A tree-wide `grep -rn "verified only" --include=*.py` returns exactly one hit, and it is the **comment** at `bot.py:7273`; the only other mentions are in the tests that assert it. The message is emitted nowhere in source. My version kept `assert "verified only for DeepSeek V4.1 Flash" in text` for Gemini / `deepseek-v4-pro`, which the source cannot satisfy, so it cannot fix the four baseline failures; it also expanded the parameter set with variants that were never baseline-reproduced. The parent restores the original four negative cases and retains only the real `_create_main_provider` binding, and owns that file from here. I make no claim about it.
2. **No resolution count.** My "47" was wrong and is retracted. My nine files carry **44** `FAILED` lines in the QA52 summary (`tests/test_bot_mentions.py` 16, `tests/test_solo_channel.py` 11, `tests/test_deepseek_reasoning.py` 2, `tests/test_instance_ops.py` 2, `tests/test_reasoning_commands.py` 5, `tests/test_instance_backup_compat.py` 1, `tests/test_command_formatting.py` 1, `tests/test_tts_config.py` 1, `tests/test_tts_tempfiles.py` 1 = 44). That is line arithmetic on the synthetic report, not a verified outcome, and the five `tests/test_reasoning_commands.py` entries are not mine to resolve. No count of resolved, unresolved or verified cases is asserted.
3. **Unsupported-command behaviour is OPEN.** Whether admin `!reasoning` / `!effort` should refuse non-DeepSeek models is a contract question that now needs a coordinator disposition (and Luna, for production). It is not a fixture drift, not resolved here, and my earlier implicit treatment of the commented guard as an accepted decision does not stand.
4. **No TTS "selection" claim.** The existing fixtures already selected Fish (`FISH_API_KEY` is set before `TtsTool.execute`, and the helper is reached directly). My TTS diff only **changes recorded expectations** — the endpoint URL and body — to the gateway request the committed helper actually builds. I did not add explicit Fish selection, and the committed gateway body differing from a Fish-native body is recorded, not explained or endorsed.
5. **Status of every change: awaiting independent review and isolated QA.** Nothing in this report is verified, accepted or green. The strongest support available to me is a read of the committed source path; that is not execution evidence.

## 1. Scope

Nine exclusively-owned existing test files, fixture/intent drift only — of which one file's relevant change (item 1 above) is withdrawn. No production file was touched. No new test file, function, class or helper; no `xfail`/`skip`; no assertion relaxed to obtain green; no production validation changed. Everything else in the shared worktree (including Luna's `bot.py`/`providers.py`/`bot_tools.py` and the parent's other tests) is preserved.

| Case | Failing evidence | Source contract read (not execution evidence) | Change |
| --- | --- | --- | --- |
| `test_bot_mentions.py` 16 variants | `bot.py:5857 AttributeError: 'SimpleNamespace' object has no attribute '_channel_allowed'` | admission calls `self._channel_allowed(message.channel, allowed)` (`bot.py:5857`); method reads `self._control["blocked_channels"]` and `discord.Thread` (`bot.py:5374`) | bind the real method in the existing fixture loop alongside `_solo_blocks` |
| `test_solo_channel.py` 11 cases | `bot.py:7410/7428 AttributeError: command_prefix` | `_handle_solo_command` renders every usage line from `self.command_prefix` (`bot.py:7410,7428,7436`) | add `command_prefix="!"` to the existing synthetic bot |
| `test_command_formatting.py::test_link_and_command_help_keeps_inline_markdown` | `bot.py:7476 AttributeError: command_prefix` | VC help text is built from `self.command_prefix` (`bot.py:7476`) | add `command_prefix="!"` to the existing report fixture; expectation `` `!vc join` `` unchanged |
| `test_reasoning_commands.py::test_other_models_are_explicitly_unsupported` ×4 | `text` never contains `verified only for DeepSeek V4.1 Flash` | the only occurrence of that string in the tree is the commented-out branch at `bot.py:7273` | **WITHDRAWN (item 1).** Parent restores the original four negatives; the failure is open, not fixed |
| `test_reasoning_commands.py::test_main_constructor_wires_live_control_callback` | `bot.py:2877 AttributeError: '_create_main_provider'` | `_setup_ai` delegates to `self._create_main_provider(self.config)` (`bot.py:2876`), which is what builds `reasoning_control=lambda: self._control.get(...)` (`bot.py:2880`) | bind the real `_create_main_provider`; the monkeypatched provider constructor and both live-callback assertions are untouched |
| `test_deepseek_reasoning.py::test_other_models_and_hosts_are_untouched` 2 cases | `assert 'openrouter' == ''`, `assert 'deepseek' == ''` | `deepseek_reasoning_transport` recognizes any model matching `deepseek.*flash` on the two hosts (`providers.py:1811-1824`) | drop the two now-recognized rows from the untouched list and assert their real transport/wire shape in the same test; all genuine unknowns (gemini, `deepseek-v4-pro`, both `.evil.test` hosts, plain gateway) stay negative |
| `test_instance_ops.py::test_start_alias_cli_uses_same_operation_lock_and_health_wait[False-up/start]` | `scripts/instance.py:290 AttributeError: 'staging_enabled'` | `lifecycle` gates `up/start/restart` on `instance.staging_enabled`, an `env`-derived property (`scripts/instance.py:190-192,290`) | bind the real `Instance.staging_enabled` property to the fake instance (env `DAME_CURIE_STAGING=false` → `False`); lock/health assertions unchanged |
| `test_instance_backup_compat.py::test_reconstruction_checks_helper_identity` | `ValueError: invalid expected instance` before the identity comparison | `validate_record` requires `INSTANCE.fullmatch(arg)` first (`scripts/instance_backup_compat.py:103-109`) | use a valid-but-different instance name `dame-curie-prod` so the `record["instance"] != expected_instance` check is the one exercised; production validation untouched |
| `test_tts_config.py::test_fish_tts_writes_audio_on_success` | `'https://api.ppq.ai/v1/audio/speech' != 'https://api.fish.audio/v1/tts'` | `_synthesize_fish_tts` posts the OpenAI-shaped speech request to the configured PPQ endpoint and writes the response bytes (`bot_tools.py:288-345`); the Fish-native URL/body is commented out in source | record the real request: URL, `model`/`input`/`voice`/`language` body, bearer header; write-path assertions unchanged |
| `test_tts_tempfiles.py::test_execute_fish_uses_real_helper_and_preserves_voice` | body mismatch (`input`/`voice`/`language`/`model` vs `text`/`format`/`reference_id`) | same helper reached through the real `TtsTool` provider chain with `FISH_API_KEY` set (`bot_tools.py:7085-7100`) | assert the real URL and body, plus the bearer header; add nothing and mock nothing new |

## 2. Deliberate non-changes

- **No production edit.** Every remaining item above is a test-side record of a contract already committed in `21f57d4`, not a defect claim. That reading is source inspection only; it is not execution evidence and does not establish that the tested behaviour is correct.
- **`bot.py:7273` non-DeepSeek rejection is OPEN, not settled.** The only occurrence of `verified only for DeepSeek V4.1 Flash` in the tree is the commented-out branch, so the control currently reports for every model. Whether that is intended is a contract question requiring coordinator disposition (and Luna, for production). This lane neither fixes nor endorses it, and the withdrawn test change (item 1) is not evidence either way.
- **`api.ppq.ai` TTS endpoint.** Inherited from the initial commit (`git log -S "api.ppq.ai/v1/audio/speech" -- bot_tools.py` → `c460324`), with the Fish-native request commented out beside it. My change records the gateway request the helper actually builds; it does not explain why the gateway body differs from a Fish-native body, and it does not add Fish selection. If PPQ is a stale host rather than a chosen Fish-compatible gateway, that is Luna's call; no production behaviour was altered.
- **`test_instance_ops` binding a production property.** Chosen over `staging_enabled=False` because the property is `env`-derived; the fixture's `DAME_CURIE_STAGING=false` therefore still drives the decision the assertion depends on, and the operation-lock/compose ordering assertions are untouched.
- **`test_deepseek_reasoning` extra coverage** is an inline loop inside the existing test (no new test function). It is unproven until QA; if the parent prefers the untouched-only form, that is a valid disposition.

## 3. Verification status

No execution by me. Each surviving selector was cross-checked against the committed source path (control flow read end to end, not just the raising frame). That is the full extent of my evidence and it is **not** a result set. Selected QA selectors for the parent's independent run:

```
tests/test_bot_mentions.py
tests/test_solo_channel.py
tests/test_command_formatting.py
tests/test_reasoning_commands.py
tests/test_deepseek_reasoning.py
tests/test_instance_ops.py
tests/test_instance_backup_compat.py
tests/test_tts_config.py
tests/test_tts_tempfiles.py
```

**No resolution claim.** The nine files carry 44 `FAILED` lines in the QA52 summary; that is line arithmetic on the synthetic report, not a verified outcome, and the five `test_reasoning_commands.py` entries include the withdrawn case. Whether the remaining changes are correct awaits independent review and isolated QA. All other agents' changes are preserved; `git status` for the nine files shows only my hunks.
