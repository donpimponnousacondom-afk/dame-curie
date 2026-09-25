# Round-two child report R3 — shell/rewrite authorization, image configuration, prompt commands, prefixes (Opus, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../08-ROUND2-REPORT.md`.
Coordinator re-verified before accepting: the dispatcher result-line format versus the `_tool_results_need_followup`
error-prefix check (N-3), the `"autonomy"` actor string and direct `tool.execute` calls in `autonomy.py` (N-1),
the minimal shell environment (`bot_tools.py:5224-5231`), and the `tool_authorized` call sites.

---

# Round-two re-verification: shell/rewrite authorization, image configuration, prompt commands, prefixes

Target: `dev/phaseII_v2` @ `0e9519e`, compared with `c603cf2`. I stayed read-only: I used `git diff`/`git show`, grep and sed. I imported nothing, executed nothing, opened no private paths and wrote no files. All line numbers refer to the current tree.

**Summary:** 13 of the 17 blocks are closed; D-04 is partially closed. I reject the C-28 push-back as argued. The fixes for the core scenarios (C-23 shell, C-24 rewrites, C-04 startup) hold. There are four new residuals, all low or low-medium:

- **N-1:** autonomy silently loses shell and prompt rewrites, but its planner still lists them.
- **N-2:** a shell-allowlisted user can make themselves an admin.
- **N-3:** a call to the stale `hd_image` name ends the turn with no reply.
- **N-4:** reading back an oversized stored prompt gives no sign that it is being left out of the model's context.

---

## C-23 — Shell authorization and environment
**Verdict: CLOSED for the round-one scenario (was high). New residuals N-1 and N-2 (low-medium), plus docs overclaims.**

**What the diff does**
- **Shared policy:** `tool_policy.py:16-25` allows admins, or string IDs on `_shell_whitelist` for `shell` only. It fails closed when there is no actor.
- **The allowlist is now read on every path:**
  - Dispatcher: `bot.py:13850-13851`. This check runs *after* alias resolution (`:13821-13831`), so `bash`/`exec`/`command`/`tool_shell` all hit it as `shell`.
  - Plugin eligibility: `:14061-14067`.
  - Catalog: `_turn_tool_names` `:14759`. This is the final filter, applied after `more_tools` expansion, so discovery cannot re-add shell.
  - In the tool itself: `ShellTool.execute` `bot_tools.py:5464-5465`.
  - Background jobs dispatch with `orig_message` (`jobs.py:786`), so the requester is the actor.
- **Plugin precedence:** a plugin that is actually named `bash` wins over the alias. That runs plugin code, not the built-in shell, so it is not a bypass. A plugin named `shell` still uses the built-in and its gate.
- **Unauthorized calls don't trip the breaker:** they return before the breaker branch. `shell` is a result tool, so the model gets a follow-up turn to explain the refusal.
- **Subprocess environment:** `bot_tools.py:5224-5231` runs `bash --noprofile --norc -c` with only HOME, PATH (identical to the image's PATH), `LANG` and `PYTHONUNBUFFERED`.
  - `DISCORD_TOKEN` and `OPENAI_API_KEY` no longer appear in `$ENV`, and `BASH_ENV`/`.profile` persistence is gone.
  - The tool's own caps and `container_mode()` read `os.environ` in the parent process (`:5079-5121`), so they are unaffected.
- **Docs:** `docs/ARCHITECTURE.md:47`, `README.md:12-14`, `SECURITY.md:12-18` and `REDESIGN_PLAN.md:34` now match the foreground code.

**New findings**
- **N-1 (low-medium): autonomy runs as actor `"autonomy"`** (`autonomy.py:4170`) and calls `tool.execute` directly (`:4199-4201`).
  - `shell`, `update_base_personality` and `update_server_prompt` therefore now always return errors for autonomy.
  - Yet `_autonomy_tool_allowed` (`:1291-1305`) and the planner catalog (`:2936-2947`) still advertise them. Their descriptions even say "Admins … only".
  - This silently removes a capability that was used before (see the `AUTONOMY_DISABLED_TOOLS=shell` comment at `:598`). The fail-closed direction is correct, but it is not documented anywhere, and it wastes planner actions.
- **N-2 (low; docs): the shell allowlist is effectively admin-level.**
  - `/state/data` is writable from the shell (`compose.yaml:131-136`), and `admins.json` is reloaded every 5 s (`bot.py:9550-9554`). An allowlisted user, or text injected into their turn, can make them an admin within 5 s.
  - `/config/bot.env` (`compose.yaml:120-125`) stays readable, so the minimal environment only removes the one-step `$DISCORD_TOKEN` read.
- **Residual (low): `send_file` exports any file under `/home/dame-curie` (the shell workspace) for any actor**, provided shell is merely *registered* (`bot_tools.py:4899-4911`). It does not call `tool_authorized`.
- **Residual (low): the minimal environment drops things shell users had before:**
  - `TZ` (`compose.yaml:106`), so shell `date` now reports the image's default time zone.
  - The login-profile PATH additions such as `~/.local/bin`.

**Overclaims**
- 05: "Direct execution and advertised catalog gate privilege." This is false for the autonomy planner's catalog.
- `SECURITY.md:16`: "The same actor policy applies to catalog visibility." Same autonomy exception.
- `SECURITY.md:18`: "can still read bot-readable configuration/state". The shell can also *write* it, which is how N-2 escalates.
- TODO: "gated separately". Not a real separation, because of N-2.
- **Provenance:** 05 does not say who chose this trust model. Root's quoted grant is general ("agree about your implementation"), while the intake said "Root must choose". It should be labelled a coordinator choice, as C-28 is.

## C-24 — Personality and server-prompt rewrite tools
**Verdict: CLOSED.**

- **Gates added:** `bot_tools.py:7701-7702` and `:7761-7762` check `tool_authorized` inside `execute`. They are also filtered from the catalog, and a missing actor fails closed.
- **No collision with `!prompt`:** the command writes through `self.memory.set_server_prompt` directly (`bot.py:6617-6628`), never through the tool class.
- **Size limit:** the tool's 4,000-character cap stays at or under 16,000 bytes, so it fits the new 16 KiB limit.
- **Residuals:**
  - The autonomy planner still advertises both tools (N-1).
  - A whitelisted shell user can rewrite the personality storage directly (N-2).

## C-04 — Image config blast radius and migration hold
**Verdict: CLOSED.**

All image checks moved out of `validate()` and into class-body state (`config.py:265-295`), with the helper at `:108-128`.

| Configuration | Result |
| --- | --- |
| `pollinations` protocol | Sets the config error; image generation off; bot starts |
| Unmatched `IMAGE_GEN_MODEL` | Same |
| Malformed or non-object `IMAGE_GEN_MODELS` | The strict `ValueError` (`:80-96`) is caught at import (`:270-273`); no import crash for `doctor.py` |
| `ENABLE_IMAGE_GEN=false` | Returns false; nothing raises |
| Forced `true` with a bad profile | Still overridden to off (`:293-295`) |

- **Registration** happens only when enabled (`bot.py:3266-3267`).
- **No correctly configured profile is newly disabled.** The only new requirements, a non-empty endpoint and a non-empty model map, already failed at call time before.
- **Hold recorded:** `docs/IMAGE_GENERATION.md` (Migration section) and `phase-II_v2/PROVISIONING.md:5-7`.

## C-05 — Image quality default
**Verdict: CLOSED.** Default is `low` in `config.py:276`, `.env.example:218`, `docker/bot.env.example`, the guide and the schema default (`tool_schemas.py:836`). The explicit private `high` is left alone.

## C-25 — Unconfigured image tool visibility
**Verdict: CLOSED.** In `auto` mode the tool registers only when the profile is usable. The template now contains the `IMAGE_GEN_*` block. If a stale `image_generator` call reaches an unregistered tool, it is a result tool, so the model still gets a follow-up turn.

## C-26 — Path resolution and edits (realpath, no downscaling)
**Verdict: CLOSED.** `realpath` is applied to both the roots and the reference (`bot_tools.py:1330-1331`). The time-of-check/time-of-use gap and the edit latency are both disclosed in the docs.

## C-27 — Attachment fallback only when `image is None`
**Verdict: CLOSED** (`bot_tools.py:1384`). `""`, `[]`, `"[]"` and whitespace all generate from scratch.

- **Residual (low; a design tension, not a defect):** C-29's premise is that some models fill optional arguments with `""`. Such a model would now ignore the user's attachment on an edit request.

## C-28 — No `hd_image` alias (push-back)
**Verdict: PUSH-BACK-REJECTED as argued (low).**

**The rationale is factually wrong.**
- The pre-`4e4027a` `hd_image` also defaulted `auto_send=false` (save-only) and also used attachments when the image was omitted (`git show 4e4027a^:tool_schemas.py:65-90`). An alias would be close to 1:1; only the `""` edge case and the quality default differ.
- The principle "reject stale names rather than silently reinterpret them" contradicts the existing `dalle`/`flux`/`image`/`generate_image`/`gen_image` → `image_generator` aliases (`bot.py:13787-13791`).

**Rejecting the name is not recoverable for the model (N-3).**
- An unknown name returns `Tool hd_image: Error - unknown tool…` (`bot.py:13849`, `:13900`). The breaker is not touched.
- But `_tool_results_need_followup` checks `result.startswith("Error…")` (`bot.py:2153`), and dispatcher result lines always start with `Tool <name>:`, so that check can never match.
- `hd_image` is not a result tool, so the loop breaks (`:13261`). If the model sent no text alongside the call, the user who asked for an image gets **no reply at all**.

**`disabled_tools`:** checked for Dirac (`validation.md:196`); canonical is held. That part is fine.

**Either of these closes it:**
- Add the alias.
- Treat any `Tool X: Error` line as needing a follow-up turn. This is the generic fix, and it also covers any other hallucinated name.

## C-29 — Empty optional arguments
**Verdict: CLOSED.** Empty `model` falls back to the default (`:1415`); empty `quality` falls back to the config value (`:1462`). A whitespace-only quality would still be sent as-is (nit).

## C-03 — `!prompt` above 2,000 characters
**Verdict: CLOSED.** In `bot.py:6591-6629`:

- Viewing a prompt of 1,800 bytes or less sends it inline (at most about 1,840 characters with the wrapper). Larger prompts come back as `prompt.txt`; prompts over 512 KiB are refused explicitly.
- Setting a prompt replies with a short acknowledgement and no echo, capped at 16 KiB.
- Mentions are suppressed, and the prefix is interpolated.
- `send_command_response` is not used. The file attachment is the better choice here.

**New finding N-4 (low):** a stored prompt between 16 KiB and 512 KiB is returned as a file with no hint that it is being left out of the model's context.

## C-22 — Longprompt ceiling and middle-trim of the first system message
**Verdict: CLOSED (low residuals).**

**What changed**
- The server prompt is now its own system message (`bot.py:15907-15913`).
- `_apply_prompt_budget` (`:15290-15358`) now protects:
  - `out[0]` (identity/personality),
  - the tool contract (`## Tools`, `## Available tools`, `Custom tool protocol:`),
  - the server prompt,
  - the omission diagnostic,
  - the live user input.
- If the protected content cannot fit, the user sees a visible `PromptBudgetExceeded` error (`:12868`, `:13640`). The old 24k middle-trim of `out[0]` is gone.
- Oversized prompts are omitted whole in both paths: foreground `:15431-15438` and background `jobs.py:497-503`.

**Residuals**
- The "diagnostic" is only a system message to the model; no admin is told directly.
- The two paths give different advice: the foreground says `prompt <replacement>`, which cannot carry more than about 2,000 characters inline, while background jobs say `longprompt`.
- The 16 KiB number was chosen by the coordinator; the auditor had asked for root's number.
- A guild whose stored prompt is over 16 KiB (possible since `723e7d8`) will lose its lore from context on the next release. Check stored prompt byte sizes (sizes only) before any release.

**Overclaim:** LONGPROMPT.md's "actionable diagnostic". Nothing actionable reaches a human.

## C-30 — Hard-coded `!` in runtime strings
**Verdict: CLOSED.**

- A grep of all non-test `.py` files found no hard-coded `` `! `` or `!word` in any `send`/`raise`/usage string.
- Every line containing `{self.command_prefix}` is an f-string, and none of the converted lines contains other braces.
- `parse_background_request(prefix=…)` is wired (`bot.py:6530`); help was already interpolated.

**What remains (all comments/docstrings, allowed by convention):**
- `bot.py:1942,2554,2576,5827,5857-5858,6481-6522,6746-6748,6861,6909-6913,7361,7402-7403,8514,8550-8555,9024-9025,10327,12132`
- `bot_tools.py:7739-7741`
- `jobs.py:7-9`
- `autonomy.py:1266,3589`
- `control_defaults.py:151,207,211-212`
- `message_pipeline.py:320`
- `plugin_manager.py:859`

## D-01 — SECURITY.md
**Verdict: CLOSED, with the overclaims listed under C-23** (autonomy catalog; "read" understating write access and admin escalation). The taint-gate removal and the not-a-secret-sandbox status are stated honestly.

## D-03 — LONGPROMPT.md prefix
**Verdict: CLOSED.** The examples use `!` and the configured prefix is explained.

## D-04 — Stale "confirmation rules" wording
**Verdict: PARTIALLY CLOSED (low).**

- **Fixed:** `jobs.py:508-509`; banners added to PRUNING_MAP and REDESIGN_PLAN.
- **Not fixed:**
  - Seven dated records still say taint/confirmation "remain", with no per-file banner: `DIRECT_SHELL_IMPLEMENTATION.md:22`, `DISCORD_ONLY_DEPLOYMENT.md:102`, `SOURCE_BOUNDARIES_IMPLEMENTATION.md:48,58`, `COMPANION_REMOVAL.md:30`, `SOCIAL_TRANSPORT_REMOVAL.md:23,31`, `EMAIL_REMOVAL.md:22`, `RUNTIME_VALIDATION.md:94`.
  - `phase-II_v2/README.md:5` still says "`REDESIGN_PLAN.md` is the authority", which contradicts the plan's new "historical, not current grants" header.

## AGENTS.md discipline (cluster code)
Nothing to flag:
- No type escapes.
- The new exception handling is narrow (`ValueError` at `config.py:271`).
- The one new blanket `except Exception` (`jobs.py:691`) consolidates two earlier ones and now fails the job visibly.
- `tool_policy.py` and `_image_config_error` are justified by their fixes; no stray logging was added.

## Out of cluster, flagged for its owner
The dead error-prefix check at `bot.py:2153` (see N-3) also means that an error from any non-result tool, not just unknown names, will not get a follow-up turn. I did not trace concrete consequences for `send_message`.

## Not read
- The test sources and QA logs, beyond grep hits.
- The `review-*`/`micro-*` reports, beyond grep.
- `providers.py`, `turn_budget.py`, plugins.
- `bot.py` diff hunks outside the listed functions.
- Any private configuration or state (out of bounds). I could not verify Dirac's or canonical's stored prompt sizes or image profile validity.
