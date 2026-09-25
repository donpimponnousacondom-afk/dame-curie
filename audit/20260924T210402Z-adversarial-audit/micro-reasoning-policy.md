# Unsupported reasoning-command policy — source-only micro-review

**Disposition:** Reject `!reasoning`/`!effort` changes for an unrecognized primary transport, without persistence. Report unsupported on status too. Leave existing persisted controls untouched; do not claim that a configured provider request is disabled or changed. Parent owns the policy decision and source/test edits.

## Evidence and boundary

- QA baseline and fixture recheck were reported to retain four cases under `tests/test_reasoning_commands.py::test_other_models_are_explicitly_unsupported` (lines 167–174). I did not execute them. Their four variants cover status/change for both commands against `google/gemini-3.7-flash` on OpenRouter, require an unsupported response, and require no control file.
- `bot.py:7259–7318`: authorization precedes validation; the historical unsupported-transport branch is commented out at 7267–7268. Unknown transport currently enters the supported branch, can write `deepseek_reasoning` at 7278–7284, then reports invented DeepSeek wire fields at 7285–7309 (`transport == ''` takes the direct-API formatting branch). The comment's author or reason is unknown; do not silently reinstate its old exact-model wording as policy.
- `providers.py:1811–1825` recognizes `deepseek.*flash` aliases on OpenRouter and DeepSeek hosts/subdomains. Preserve this broadened matcher, not the deprecated exact-model matcher at 1828–1837. `tests/test_deepseek_reasoning.py:141–155` explicitly recognizes more Flash aliases while excluding Gemini, non-Flash models, and unrecognized hosts.
- `bot.py:2879–2904` wires live stored control into the primary provider. `providers.py:2121–2164,2194–2259` applies it only on a recognized Flash transport and matching primary model; on unknown routes it leaves configured `extra_body` request options in place except existing independent disable/Kimi handling. Fallback, vision and model-override isolation is covered in `tests/test_deepseek_reasoning.py:158–165`. Command rejection must not rewrite provider request behavior or delete preexisting control (which can apply again after a future switch back to Flash).

## Minimal proposed replacement in `bot.py`

Replace **only** commented lines 7267–7268 with this explicit policy branch, preserving the preceding authorization check and the entire supported branch:

```python
        elif not transport:
            text = (
                "These controls are verified only for DeepSeek V4.1 Flash and "
                "recognized DeepSeek Flash aliases on OpenRouter or the official "
                "DeepSeek API. Current model unchanged; no control saved. "
                "Any previously stored DeepSeek preference is not applied to "
                "this primary model; configured provider request options remain unchanged."
            )
```

This is a deliberate **reject-unknown-without-persistence** choice, not a resurrection of exact model lists: the live broadened transport detector makes the decision. No call to `deepseek_reasoning_level` on unknown routes, so no fabricated effective tier or wire claim. Existing authorization still wins for non-admin changes; status remains available. For unknown commands with previously saved preferences, the response says unapplied to the current primary rather than pretending the preference is erased. The separate alternative—**retain newly requested preferences** for later Flash use but label them unapplied—would require a distinct command contract and tests; it creates a latent change upon switching models and contradicts the existing four no-file assertions. Do not quietly choose it.

## Existing-case expectations / counter-risk

- Four unknown-model command cases return unsupported text and create no file; non-admin changes remain `not authorized`. A preexisting control file is not mutated.
- Supported OpenRouter/direct Flash routes and broadened aliases still enter the original branch: valid admin commands persist, supported status reports remain, OpenRouter integer 1–100 stays exact, direct numeric presets remain limited, invalid settings do not persist. Existing configured `extra_body` and fallback/override behavior remain provider-owned.
- Risk: an unknown model on a recognized host can still send its explicitly configured reasoning options (or existing independent disable policy). The message deliberately says **control not applied**, not **reasoning off**. A previously stored preference can take effect again when the primary returns to a recognized Flash alias; that is existing provider semantics, not a new write.

No source/tests edited; no execution, runtime, private data, network, or Git history accessed. Release/deployment effects: none. Parent should decide policy and validate in its separately authorized isolated QA context.
