# Independent adversarial review — image configuration and local-input boundaries

**RETIRE AFTER ACCEPTED ROUND TWO.** Temporary round-two review evidence, inherited from the `implementation-*.md`
lifetime rule in `TODO.md:60` and `AGENTS.md`'s document-retirement schedule. Summarize the surviving contract into
the final response, then remove with the rest of this bundle. Do not rewrite the auditor originals.

**Corrections after coordinator challenge — round-one draft withdrawn on two points.**

1. *"No case reaches the `IMAGE_GEN_CONFIG_ERROR` refusal; the new branches are unproven."* **False, retracted.**
   `tests/test_hd_image_config.py:128-150` loads a real forced-on `Config` with malformed `IMAGE_GEN_MODELS`
   (`runpy.run_path`, `ENABLE_IMAGE_GEN=true`), assigns it to `tool.bot.config` at `:146`, executes at `:147` and
   asserts the config-error refusal plus `get_session.assert_not_awaited()` / `session.post.assert_not_called()` at
   `:148-150`. The valid-profile `ENABLE_IMAGE_GEN=false` branch is covered at `:153-174` (`switch="false"` →
   `"ENABLE_IMAGE_GEN=false"` at `:172`, with a validated nonempty profile at `:163-167`), and the missing-endpoint
   refusal at `:205-218`. All three refusal branches at `bot_tools.py:1439-1442` are therefore exercised by
   existing adapted cases. There is no coverage hole there; the remaining gap is narrower and is stated in B-1.
2. *"The schema text is the execution opposite of the new contract / a blocker."* **Overstated, downgraded.**
   `tool_schemas.py:107` ("Omit to use message attachments") is **true for the omitted/`None` case**, and an
   explicit `""` is not an omission, so that sentence misdescribes nothing it claims. What is missing is an
   empty-value clarification in the static property description. That is a text gap, not a blocker, and the
   coordinator is handling it. B-1 below is rewritten accordingly, and no part of this review is a blocker inside
   Sol's hunks.

**Static-only / non-execution limit.** This review is source-only: `read`, `glob`, `grep` and source `git diff`
against the shared `/home/codexy/deepseek/dame-curie` working tree at `ab64853` **plus uncommitted edits**. No
application import, no test collection or execution, no Docker/runtime, no private configuration, dotenv, mount or
log read, no dependency/network access, no subagents, no writes except this file. No claim here is an execution or
integration result. Every "verified" below means *traced in source*, not *observed running*. The parent's frozen
pre-core run (`282f21933244cf70d8ab4e30e6d88f9245ac4f8e`, 522 passed / 2 failed, neither failure in the selected
image cases) is treated as the parent's statement, not as my evidence. `tool_schemas.py`, `tool_prompts.py`,
`tool_policy.py`, `control_defaults.py` and `bot.py` are under **active concurrent edit by core Luna**; the image
and config hunks reviewed here are the stable ones named by the assignment. `bot.py` moved under me during the
review (alias map `13381-13407` → `13417-13421`); I re-read each `bot.py` anchor in its current state and none of
the reviewed behavior depends on the lines Luna is moving.

## Checked paths

Owned scope, full diff read: `config.py`, image portions of `bot_tools.py`, `.env.example`,
`docker/bot.env.example`, `docs/IMAGE_GENERATION.md`, `tests/test_hd_image_config.py`,
`tests/test_image_generator.py`, `tests/test_cpa_images.py`.

Callers/consumers traced rather than trusted: `config.py:108-128,164-202,265-295,486-496,498-557`;
`bot.py:3233-3234` (registration), `13381-13421` (alias map), `13440` + `2306-2321`
(`_prepare_tool_params`), `14153-14225` (`_compatible_tool_names` / `_turn_tool_names`), `13666`
(artifact field), `2097-2110` (`image_or_caption_delivered`); `tool_policy.py:16-25`;
`tool_schemas.py:15-34,50-56,99-120,808-836`; `turn_budget.py:32-47,120-123`;
`bot_tools.py:435-462,1027-1053,1140-1185,1227-1244,1247-1472`; `doctor.py` (no `IMAGE_GEN*` reference;
feature status comes only from `Config.feature_report()`); `control_defaults.py:354` (`image_generator` in
`KNOWN_TOOLS`, `disabled_tools` default `[]`); `docker/app.Dockerfile:14` (`WORKDIR /app`) and
`scripts/dirac.py:64-65` (`DAME_CURIE_SITE_DIR=/state/sites`) for the allowed-root question.

Repo-wide `grep` sweeps: `IMAGE_GEN*` outside `config.py`/tests (only `bot.py:2370` secret registration and
`bot.py:3233` registration); `ImageGeneratorTool`/`image_generator` outside tests; `hd_image` across the tree;
`_shrink`; `IMAGE_GEN_QUALITY`/`"quality"` expectations in `tests/`; `IMAGE_GEN*` mentions in `docs/` and
`phase-II_v2/`.

## Verdicts on the assigned questions

| # | Question | Verdict |
|---|---|---|
| 1 | Invalid profile disables **only** image capability, even forced-on, without unrelated startup failure | **Source-confirmed for config construction and registration.** No startup path consumes `IMAGE_GEN*`; `validate()` no longer mentions it. |
| 2 | Auto-registration requires native protocol + explicit endpoint + valid nonempty exact-ID/description map + listed model; explicitly blank API key stays valid | **Source-confirmed**, including the keyless case. Contract change vs `ab64853` for `MODELS={}`+`MODEL=` (now off, previously registered): deliberate, matches the assignment, undocumented for the running private profile. |
| 3 | Low quality/default model/quality and `image=None` vs `""`/array consistent in schema **and** execution | **Execution confirmed and covered by cases**: explicit `""`/`[]`/`"[]"` route to `generations`, omitted/`None` routes to attachments (`bot_tools.py:1384`, `:1234`). Defaults agree (schema `tool_schemas.py:834` = `config.py:275`; model fallback `bot_tools.py:1415`). Static `image` property text covers only the omitted half — B-1, text gap, not a blocker. |
| 4 | Local symlinks resolved and checked against actual allowed roots; read/reopen race limitations reported accurately | **Source-confirmed** (`realpath` both sides). Race statement in `docs/IMAGE_GENERATION.md` is accurate; same-UID TOCTOU remains a conditional residual risk. |
| 5 | HTTP/network/empty-result/error cases truthful | **Source-confirmed** for the paths that changed. Redirect refusal, private-host acceptance, 20 MiB cap, no-retry string, "may have been billed" text unchanged. |
| 6 | Clean-cut naming maintained (no `hd_image` alias); canonical activation explicitly held | **Confirmed**: no `hd_image` in any active source or alias map. Hold present in `docs/IMAGE_GENERATION.md:56-59`; C-04's companion hold in `PROVISIONING.md` **is missing** (D-1). |

## Findings

### B-1 — Finding (text only): the static `image` property omits the explicit-empty-value case

`tool_schemas.py:105-108` (unchanged by this lane; `git diff -- tool_schemas.py` touches only tool-group
constants and unrelated sections):

```
"image": _str(
    "Optional image URL, data URI, or local path Dame Curie wrote; for several, pass a "
    "JSON list or comma-separated refs (max 4). Omit to use message attachments."
),
```

This sentence is **correct as written for omission and `None`**: `_prepare_tool_params` (`bot.py:2306-2321`)
copies params verbatim (it removes only `message`/`self`), so an omitted `image` is absent from the call and
`ImageGeneratorTool.execute` (`bot_tools.py:1424-1433`) leaves its default `None`, which is exactly the
attachment path at `bot_tools.py:1384`. Nothing here is the opposite of execution.

What the static property does not say is what an **explicit** empty value does, and the two sources that describe
it now differ in granularity. `get_description()` (`bot_tools.py:1273`) carries the full contract —
`"If image is None, attachments are used; image='' generates from scratch."` — and is appended to the tool
description in the built payload (`tool_schemas.py:853-856`). The static parameter text carries only the
attachment half. Exact flow for the missing half: `image=""` or `image=[]` → `image is None` is False at
`bot_tools.py:1384`; `[]` yields `refs = []`; `_native_image_request` (`bot_tools.py:1234`) selects
`generations` and omits the `images` key (`tests/test_cpa_images.py:277-281` asserts exactly that). The behavior
is correct, documented in the description the model also receives, and tested; only a model or operator reading
the parameter description alone gets the shorter story.

Minimal correction, if the coordinator keeps it (one line, no new case): append the empty-value half to that
`_str(...)`, mirroring `bot_tools.py:1273`. A regression assertion would have to live in a case that already
builds the live tool description — `tests/test_hd_image_config.py:221-249` does (`build_openai_tools(...)` plus
the text-catalog path) — but that case reaches the text through `MaxwellBot._tool_system_prompt`, not through
`get_description()`, so asserting the sentence there is not a direct one-liner. Recorded as gap, not as a demand.

### D-1 — C-04's migration hold was only half-recorded (documentation)

Audit C-04's smallest fix names two files: "record the hold in `PROVISIONING.md` and `IMAGE_GENERATION.md` now".
`docs/IMAGE_GENERATION.md:56` now carries it. `phase-II_v2/PROVISIONING.md` has **zero** `IMAGE_GEN` matches
(`grep -rn 'IMAGE_GEN\|image profile\|image_generation' docs/*.md phase-II_v2/*.md` returns only
`docs/STATUS.md:40`, `phase-II_v2/DIRAC_HANDOFF.md:21,24` and the image guide). `DIRAC_HANDOFF.md:21` states the
profile of the **last observed running container** ("default `astra6.unthawed/gpt-image-2.5-flare`, quality high,
timeout 600") — see D-2 for why that is a record, not a contradiction. Minimal correction: one line in
`PROVISIONING.md` pointing at `docs/IMAGE_GENERATION.md`'s migration section, so the hold is not lost when
`phase-II_v2/` is retired (`TODO.md:63`). Documentation only.

### D-2 — Historical observation vs new source default vs unverified next boot (documentation)

Three distinct things are currently stated in one voice across `docs/STATUS.md:36`, `phase-II_v2/DIRAC_HANDOFF.md:21`
and `docs/IMAGE_GENERATION.md:15`:

- **Historical observation (keep as-is):** the last recorded temporary Dirac container ran image quality `high`
  with timeout `600`. Nothing has been deployed or restarted from this remediation tree, so that record is not
  stale — it is dated evidence of the previous release.
- **New source default (correct, and a real change):** `IMAGE_GEN_QUALITY=low` in code (`config.py:275`),
  `.env.example:218` and the guide's example block. This is the C-05 fix and rests on a deliberate decision.
- **Next-boot effect (unverified here, and worth one sentence):** every image setting is read from the
  environment at import, so a next start inherits whatever `IMAGE_GEN_QUALITY` the private profile holds. If the
  private profile sets `high`, nothing changes; if it omits the key, image edits move `high` → `low` — the same
  `high`-default regression the retired `hd_image` path carried
  (`audit/.../child-reports/C-image-config-taint-longprompt.md:150`). Whether it sets the key is unreadable in this
  session.

I am **not** claiming the running profile regresses. Minimal correction: one sentence in
`docs/IMAGE_GENERATION.md`'s migration section separating the dated running-profile record from the new default and
noting that the new `low` applies only where `IMAGE_GEN_QUALITY` is absent, so canonical reconciliation checks it
explicitly. Documentation only.

### Findings summary

No blocker exists inside Sol's reviewed hunks. Surviving items are B-1 (one schema sentence), D-1 (one
`PROVISIONING.md` pointer) and D-2 (one migration sentence distinguishing a dated record from a new default).

## Push-back / no-change (source evidence)

- **No `hd_image` alias, and none should be added.** `bot.py:13417-13421` maps only
  `generate_image|gen_image|dalle|flux|image`; `grep -rn 'hd_image'` finds it in no active source, config, schema,
  prompt or alias list — only in this bundle, the historical `phase-II_v2/PRUNING_MAP.md:147`, two generic
  synthetic console fixtures, and `docs/IMAGE_GENERATION.md:59`. `05-IMPLEMENTER-INTAKE.md:40` explicitly says the
  alias "needs evidence and a compatibility decision, not an automatic reversal of clean-cut removal", and the
  assignment requires clean-cut naming. The C-28 residual (private `disabled_tools`) stays the coordinator's
  check, now recorded in the guide. No source change.
- **"Explicitly blank API key remains valid" holds at every layer.** `config.py:267` strips to `""`;
  `bot_tools.py:1459` passes `""`; `bot_tools.py:1145-1147` adds `Authorization` only `if api_key`; and
  `tests/test_cpa_images.py:380-415` asserts the image bearer token is present while the chat key is absent. No
  chat endpoint or key fallback exists (`IMAGE_GEN_BASE_URL`/`IMAGE_GEN_API_KEY` are the only sources).
  `docs/IMAGE_GENERATION.md:22` is therefore truthful.
- **`is False` at `bot_tools.py:1441` is safe.** `_feature_env` (`config.py:167-202`) returns only real bools,
  and `IMAGE_GEN_*` eval-time bootstrapping (`config.py:265-295`) reads `os.getenv`, never `cls`. A config object
  lacking `ENABLE_IMAGE_GEN` (as in the test fixture, `tests/test_hd_image_config.py:24-34`) falls through the
  `getattr(..., True)` default, so the new refusal branch is inert there rather than wrong.
- **`_image_config_error` does not leak values.** `config.py:108-128` names only setting names; the reason string
  goes to `FEATURE_REASONS["ENABLE_IMAGE_GEN"]` (`config.py:295`) and surfaces via `feature_report()`
  (`config.py:486-496`) and the startup "Features off" line (`config.py:549-557`). `tests/test_hd_image_config.py:197-198`
  asserts operator descriptions do not appear in the error text.
- **Truthful HTTP/error documentation.** `_is_safe_url` (`bot_tools.py:456-462`) accepts any host with a hostname,
  including private/loopback — matching `docs/IMAGE_GENERATION.md:54` and the unchanged
  `tests/test_cpa_images.py:307-318`, which proves a loopback input is fetched and routed to `/images/edits`.
  `allow_redirects=False` and the explicit 30x refusal are intact (`bot_tools.py:1307,1313-1316`). The 20 MiB
  HTTP/local cap and the "missing byte cap on inline data URIs" caveat (`docs/IMAGE_GENERATION.md:57`) match
  `_read_response_limited(resp, self.MAX_INPUT_BYTES)` / `os.path.getsize` / the unguarded
  `base64.b64decode` at `bot_tools.py:1292`. `docs/IMAGE_GENERATION.md:53` ("Large edits can take longer or cost
  more") is the honest, non-overclaiming form of the C-26 latency note.
- **Allowed roots resolve to real absolute paths in the container.** `_public_image_target` (`bot_tools.py:1027-1039`)
  yields `/state/sites/_images` (`scripts/dirac.py:65`), and the second root `realpath("temp")` is resolved against
  the process CWD (`WORKDIR /app`). No new bug was introduced by `realpath`; both roots and the candidate are
  resolved the same way (`bot_tools.py:1330-1331`), and the prefix check adds `os.sep`, so a sibling directory
  sharing a name prefix cannot pass.
- **`quality or ... or "low"` (`bot_tools.py:1462`) cannot crash** on an unhashable/odd per-call value and cannot
  send an empty quality; only a whitespace-only per-call value (`" "`) is forwarded unstripped, which the
  provider-specific contract already tolerates configured values (`tests/test_cpa_images.py:109-119` covers
  `low`/`high`/`xhigh`/`max`/`auto` and 600 s timeouts).
  Not worth a change.
- **`finally`-block re-read in `_image_generation_request`** (`bot_tools.py:1216-1223`) is pre-existing and out of
  this lane; it uses `sys.exception()` to classify cancellation after the generic handler. Left alone deliberately.

## Adequate existing-case extensions (no new files/functions)

These use changes to existing bodies/parameterizations only and are what I would expect the isolated run to show:

1. `tests/test_hd_image_config.py::test_config_rejects_invalid_image_map_or_default` — forced-on plus each invalid
   field ⇒ `ENABLE_IMAGE_GEN is False`, diagnostic names the setting, values absent from the reason
   (`:177-202`). Also covers `protocol="pollinations"`.
2. `tests/test_hd_image_config.py::test_config_image_model_map_requires_strict_json_object` — malformed and
   non-object JSON via `runpy.run_path` re-import, plus the **full pre-HTTP refusal** on a real forced-on `Config`
   (assign `:146`, execute `:147`, assert `:148-150`). This is the executable proof of the
   `IMAGE_GEN_CONFIG_ERROR` branch at `bot_tools.py:1439-1440`.
3. `tests/test_hd_image_config.py::test_unconfigured_image_profile_can_boot_but_cannot_generate` — `auto` and
   `false` with no endpoint (`:205-218`); covers the `IMAGE_GEN_BASE_URL` refusal at `bot_tools.py:1447-1449`.
4. `tests/test_hd_image_config.py::test_config_accepts_valid_operator_model_map` — blank key, blank quality ⇒
   `low`, and `true`/`false`/`auto` resolution (`:153-174`); with `switch="false"` and a fully valid profile
   (`:163-167`) it reaches and asserts the `ENABLE_IMAGE_GEN is False` branch at `bot_tools.py:1441-1442`
   (`:172-174`).
5. `tests/test_hd_image_config.py::test_chat_settings_cannot_enable_unconfigured_images` — the missing-endpoint
   refusal across `None/""/"   "/"/"` with chat settings re-added, asserting `get_session.assert_not_awaited()`
   and `session.post.assert_not_called()` (`:58-71`), currently absent from the `implementation-images.md` QA
   selection list. Two neighbors carry the same assert-no-HTTP shape: `test_unlisted_model_rejected_before_http`
   (`:87-94`) and `test_missing_or_invalid_image_configuration_errors_before_http` (`:97-109`).
6. `tests/test_cpa_images.py::test_native_auto_attachments_keep_four_reference_limit` — `None` vs `""`/`[]`/`"[]"`
   routing divergence, `/images/edits` vs `/images/generations`, no `images` key when empty (`:263-282`).
7. `tests/test_cpa_images.py::test_native_local_reference_uses_existing_allowed_image_paths` —
   `allowed × linked`; the `linked=True, allowed=True` cell proves an in-root symlink resolves, and
   `linked=True, allowed=False` proves the escape is refused before any session use (`:321-343`).
8. `tests/test_image_generator.py::test_native_generations_and_edits_use_one_configured_endpoint` — empty per-call
   model/quality fall back to configured `synthetic-image-a`/`high` (`:34-49`).

Withdrawn from the round-one draft: the claim that the new refusal branches are unexercised. Items 2-4 do exercise
all three `bot_tools.py:1439-1442` branches against a real re-imported `Config`, which is stronger than tool-shaped
fixtures. Remaining gaps are narrower and are **not** execution claims: (a) no existing case asserts the static
`image` property description text (B-1) — the case that builds the live description
(`tests/test_hd_image_config.py:221-249`) reaches it through `MaxwellBot._tool_system_prompt`, not through
`get_description()`, so an assertion there would not be a one-liner; (b)
`test_real_native_transport_accepts_configured_loopback_endpoint` (`:380-415`) opens a real loopback socket and is
correctly flagged by the author as runnable only under the network-none QA envelope; I did not run it.

## Conditional residual risks (explicitly not findings of defect)

- **Same-UID TOCTOU on local references.** `realpath` → `isfile` → `getsize` → `to_thread(Path(path).read_bytes)`
  (`bot_tools.py:1331-1342`) are separate syscalls over a path the bot's own UID can rewrite. `abspath`→`realpath`
  closes symlink *and* `..` escapes, not a concurrent repoint, and does not stop a hard link placed inside an
  allowed root. `docs/IMAGE_GENERATION.md:55` claims only symlink resolution, and `implementation-images.md:23`
  states the limit accurately; the surviving contract must keep that wording rather than hardening it into a
  sandbox claim. Only demonstrable while a second same-UID writer exists — not a defect in this diff.
- **Unrestricted private HTTP inputs are intentional.** Any `http(s)://` reference is fetched, including loopback
  and RFC1918 (`_is_safe_url`, `bot_tools.py:456-462`); only redirects are refused. Documented at
  `docs/IMAGE_GENERATION.md:54` and asserted by `tests/test_cpa_images.py:307-318`. I raise no SSRF finding: the
  accepted design target is an explicitly configured local Images endpoint, so loopback egress is the feature.
- **Empty `IMAGE_GEN_MODELS` now disables registration.** At `ab64853`, `MODELS={}` with `MODEL=""` passed
  `validate()` and still registered the tool (which then answered with a config error and fed the circuit
  breaker — C-25). The new detector (`config.py:289-292`) returns False, so the tool is absent
  (`bot.py:3233-3234`) and no breaker churn occurs. Intended per the assignment ("requires … valid nonempty map"),
  but it is a visible capability change for such a deployment and belongs in the activation record.

## What I could not check

Private effective image configuration, the canonical instance's real values, its private `disabled_tools`, provider
acceptance, Docker/runtime behavior, test execution and integrated artifacts. Nothing in this report should be read
as acceptance or as evidence that the image path works against a real provider. No source or test file was modified
by this review; this report is the only file written.
