# Child report E — Documentation consistency and process ledger (Sonnet, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../03-DISPOSITIONS.md`.
This child found and read the coordinator's in-progress `02-EVIDENCE.md` during its run and cites it; the
child states it re-verified those load-bearing facts independently. Treat its agreement with `02-EVIDENCE.md`
as corroboration, not as an independent second source.

---

# dame-curie consistency and process audit — `dev/phaseII_v2` @ `c603cf2`

Method: read-only inspection via `Read`/`Bash grep`/`git log`/`git blame`/`git show`. No application import/execution, no tests, no Docker/service/Screen access, no `.env`/`bot.env`/data/logs/db/credential reads, no `legacy/` reads. An existing independent adversarial audit was already present on disk at `audit/20260924T210402Z-adversarial-audit/` (mtimes 2026‑09‑24 21:04–23:10 UTC, gitignored, not created by me); I read it as corroborating evidence and independently re-verified its load-bearing claims (tree hashes, `config.py`/`bot.py` line numbers) rather than trusting it blindly.

## 1. Deployment cadence and process pattern

**Ledger says** three source releases plus two private setting edits were pushed to the live temporary Dirac instance on 2026‑09‑24 alone, each following a same-day incident:

| Time (UTC) | Event | Source/evidence |
|---|---|---|
| 09:16 | `085c95b` taint/confirm gate removed (source only) | commit |
| 09:57 | `4e4027a` image-generator unification (source only) | commit |
| 10:04:02 | **Live replacement begins** (bundles `085c95b`+`4e4027a`+`723e7d8`+R3/R2/R9/R4) | `docs/STATUS.md:31` |
| 10:10:54 | `33aae2d` records the rollout | commit |
| 15:18:25 | private edit: `OPENAI_MAX_TOKENS` 115,200→12,345, container restart | `audit/provider-incomplete-validation.md:15` |
| 15:41:32 | `74d827d` stop-incomplete-output fix committed | commit |
| **15:43:18** | Live replacement begins (incomplete-response handling) | `docs/STATUS.md:21`; `phase-II_v2/DIRAC_HANDOFF.md:19` |
| 17:41:32/17:46:41 | `4db86ad` records the rollout | commit |
| 18:34:29.612 | private edit: `deepseek_reasoning`→`low`, hot-reloaded (no restart) | `docs/STATUS.md:11`; `audit/dirac-reasoning-audit-input.md:11` |
| 18:57:49 | `6859025` bounded-tool-log fix committed | commit |
| **19:04:46** | Live replacement begins (console-freeze fix) | `docs/STATUS.md:10`; `phase-II_v2/DIRAC_HANDOFF.md:3` |
| 21:12:53 | `c603cf2` records the rollout | commit |

(Coordinator note: the child's "commit" times in this table are local +0200 wall-clock values as printed by `git log`; the UTC equivalents are in `02-EVIDENCE.md` E2. The replacement times are UTC as stated by the ledger.)

**Deployments per calendar day:** 2026‑09‑22 = 4 replacements (`901200d`→`65fe79e` sequence, `DIRAC_INTEGRATION.md:20`); 2026‑09‑23 = 2 replacements (`2f159e9`, `d43e4bf`, `docs/STATUS.md:74,62`); **2026‑09‑24 = 3 source replacements + 2 private hot-edits = 5 live changes to the running instance in one day.**

**Incident→hotfix→deploy→record cycles, 2026‑09‑24** — all three match the pattern (bug found → patch committed → temporary-only replacement → doc commit):
- **Image unification (~12:10 record, actual deploy 10:04:02 UTC):** cited root grant is `audit/image-profile-discovery.md:5` ("root selected **Temporary Dirac: configure and deploy**"). A review artifact, `audit/image-unification-review.md` (mtime 09:56:00 UTC, self-described as "Read-only static source/diff review during Luna's concurrent production edits" — i.e. one coordinator/agent reviewing another agent's edit, not root or a separately-instructed reviewer, `audit/image-unification-review.md:1-3`), predates the 10:04 rollout start by ~8 minutes. This is the one 2026‑09‑24 release with a review artifact timestamped **before** the live replacement.
- **Incomplete-response fix (~15:43 record):** `audit/provider-incomplete-validation.md` has mtime 15:46:13 UTC — **3 minutes after** the recorded 15:43:18 UTC rollout start. File-timestamp evidence does not show a pre-deploy review gate; it shows documentation essentially concurrent with/just after the live change.
- **Console fix (~19:04 record):** `audit/dirac-console-freeze.md` (the incident writeup for the very bug being fixed) has mtime 19:12:08 UTC; `audit/dirac-reasoning-luna.md`, `dirac-reasoning-flash.md`, `dirac-reasoning-audit.md` are timestamped 19:06–19:14 UTC — **all after** the 19:04:46 UTC live replacement. No pre-deploy review artifact exists on disk for this release; the review/audit record is retrospective.

**Root grant citation, all three 2026‑09‑24 changes:** in every case the only textual trace of "root explicitly/chose/separately approved" is a sentence the coordinator itself inserted into `docs/STATUS.md` or `phase-II_v2/REDESIGN_PLAN.md` — in the taint-gate case, in the **same commit** (`085c95b`) that performs the removal (`git blame -L47,47 phase-II_v2/REDESIGN_PLAN.md` → `085c95b7`). `phase-II_v2/SESSION_LOG.md` has **no 2026‑09‑24 entry at all** (last entry: "2026‑09‑23 — narrow review-fix implementation," `SESSION_LOG.md:3`), and `TODO.md` was last touched 2026‑09‑23 19:25, before all three changes. Neither of the project's two chronological ledgers independently corroborates any of the three grants; see §4 for detail.

(Note: file mtimes on the gitignored `audit/` tree are not cryptographic proof of authoring order and could postdate an earlier unsaved draft — reported as the best available signal, not certainty.)

## 2. Test-debt normalisation

Chronological "N passed / M failed (baseline-reproduced) / K excluded" receipts, last 3 days (the ledger has no receipts further back with this granularity):

| Date/commit | Passed | Baseline-reproduced failed | Excluded | Named recurring failures | Source |
|---|---|---|---|---|---|
| 2026‑09‑22 `65fe79e` | 341 | 19 (reproduced on `eca42e0`) | — | 3 unnamed files | `docs/STATUS.md:88` |
| 2026‑09‑23 `d43e4bf` | 825 | 0 | 1 (README retry row) | `test_provider_resilience.py::test_retry_defaults_match_config_and_template` | `docs/STATUS.md:63` |
| 2026‑09‑23 `162b39c` | 675 | — | 2 | live-provider test + README retry row | `docs/STATUS.md:53` |
| 2026‑09‑24 `723e7d8` longprompt | 731 | 0 | 2 | `test_provider_resilience.py::test_retry_defaults_match_config_and_template`, `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas` | `audit/longprompt-validation.md:25,54-55` |
| 2026‑09‑24 `085c95b` taint | 864 | 23 (reproduced on `b507a9b`) | 2 | stale private-URL, synthetic-platform, mention fixtures, base-personality persistence (4 files) | `docs/STATUS.md:40` |
| 2026‑09‑24 `4e4027a` image unif. | 1,219 | 24 (23 detailed + 1 stale private-URL) | 2 | same private-URL incident test again | `docs/STATUS.md:30` |
| 2026‑09‑24 `74d827d` | 1,321 | 4 (reproduced on `33aae2d`: 410p/4f) | 2 | 2 stale DeepSeek model-recognition expectations, 1 background notice-count, 1 synthetic-platform | `docs/STATUS.md:20` |
| 2026‑09‑24 `6859025` | 368 | 5 (reproduced on `4db86ad`) | 1 | **exactly** 4× `test_log_console_render.py` + `test_tool_error_reporting.py::test_private_url_refusal_is_not_an_incident` | `docs/STATUS.md:8` |

Selections differ per run (different `--deselect` lists, different test-file subsets), so raw pass counts are **not comparable across rows** — this is stated by the ledger itself ("Counts are selection-specific," `SESSION_LOG.md:7`).

The same handful of failures is carried forward as "baseline-reproduced" across essentially every run in this window: the private-URL-refusal test recurs in the `085c95b`, `4e4027a`, and `6859025` receipts; the four `test_log_console_render.py` cases and the private-URL case are named together verbatim in `6859025`'s receipt; the README retry-row assertion (`test_provider_resilience.py::test_retry_defaults_match_config_and_template`) recurs from `dba8359`→`d43e4bf`→`162b39c`→`723e7d8`; `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas` is excluded in every single run because it "independently reads `.env` and may call a real provider" (`docs/DEVELOPMENT.md:52`) — confirmed live in source, and `pytest.ini` has no marker/deselect for it (verified: `pytest.ini` contains no markers/deselect config).

**Ownership check:** `grep -n -i "test_log_console_render\|test_private_url_refusal_is_not_an_incident\|README retry\|test_streaming_tick_inserts_space_between_glued_deltas\|baseline-reproduced" TODO.md phase-II_v2/REDESIGN_PROGRESS.md` returns **zero hits**. No one is assigned to fix or quarantine any of these; across three days and at least eight QA runs, they are only ever re-detected on the unchanged baseline and re-excluded/re-carried-forward. `docs/DEVELOPMENT.md:52` documents the live-provider test as a known, permanent exclusion rather than a bug to fix — that is the one exception, but it is a documented policy, not a fix or quarantine mechanism (no `pytest.ini` marker exists).

## 3. Naming/identity consistency

**Command prefix.** `config.py`/`bot.py` correctly resolve `self.command_prefix` at runtime (`bot.py:2326`), and the main `!help` listing correctly interpolates it (`bot.py:6949-6975`). But dozens of individual usage/error strings throughout `bot.py` hard-code a literal `!` instead of `self.command_prefix`, e.g.:
- `bot.py:6538` — "No custom prompt set. Use `!prompt <text>` to set one." (the line directly above the `longprompt` branch, which *does* use `self.command_prefix`, `bot.py:6549-6550` — same command family, one dynamic, one not)
- `bot.py:6471` `!bg`, `:6523` `!job`, `:6636` `!downvote`, `:6667/6673/6683` `!neg`, `:6804` `!jailbreak`, `:6872` `!progress`, `:6895` `!admin`, `:7002` `!shell`, `:7047/7066/7095` `!plugin`, `:7122/7135` `!blacklist`/`!unblacklist`, `:7265/7276/7304-7305/7322` `!solo`, `:7370/7455/7478/7482/7521` `!vc`, `:8183/8205` `!context`, `:9018` `!rem`, `:9120/9150-9151/9156/9186-9187` `!autonomy`
- `job_routing.py:39` — `raise ValueError("usage: !bg [--provider PROFILE] [--model MODEL] -- GOAL; each flag once")`

Since temporary Dirac's live prefix is `?` (`phase-II_v2/DIRAC_HANDOFF.md:37`, `docs/PROVIDER_RELOAD.md:3`), a user who mistypes `?bg`/`?admin`/`?vc`/etc. on the actually-running instance is told to use `!bg`/`!admin`/`!vc` — the wrong prefix for that deployment. Comment-only references (e.g. `bot.py:1902,2500,2522,6762,7256` docstrings) are not user-facing and match AGENTS.md's allowance for `!`-labelled docstrings; the ~35 `message.channel.send`/`raise` strings above are live and are the kind of drift AGENTS.md/`REDESIGN_PLAN.md:34-36` intended to normalize.

**Model naming.** `AGENTS.md:57` reads: *"Use DeepSeek V4.1 Flash for bounded inventories and GPT-5.6 Luna at max for independent adversarial review."* This line was last touched by commit `4b98f09` (2026‑09‑19 11:42:49 +0200) and has not changed since. The project's own audit trail shows the routing has moved on:
- `gpt-6-luna` first appears in this repo's history at `36a5c3a` (2026‑09‑23 20:25:42), i.e. **4 days after** `AGENTS.md`'s last edit (`git log -S"gpt-6-luna"`).
- `phase-II_v2/SESSION_LOG.md:5` (2026‑09‑23): "Both advertised `openai-codex/gpt-6-luna` and `gpt-6-sol` routes executed real bounded source tasks."
- `phase-II_v2/SOURCE_REVIEW.md:16`: "The harness catalog advertises `deepseek-official/deepseek-flash` as **DeepSeek-V41-Flash**" — this half is consistent with AGENTS.md modulo formatting.
- `audit/model-routing-research.md` (mtime 2026‑09‑24 09:39) is literally a research memo explaining the drift: "Some central model-selection/pricing documentation search results still feature GPT-5.6 rows; use the exact GPT-6 model cards... Do not substitute GPT-5.6 Sol/Luna figures: they are separate releases" (line 7).
- A third route, `gpt-6-astra`, is used for read-only scouts (`phase-II_v2/PRUNING_MAP.md:25`, `SESSION_LOG.md:154-156`) and does not appear in `AGENTS.md` at all.

Reported plainly, without adjudicating which name is "right": the governing contract (`AGENTS.md`) names a model generation (GPT‑5.6) that the project's own same-repo evidence says was superseded, and has not been updated in the 5 days since.

## 4. Redesign scope compliance

**Tree shows** dashboard/API/Caddy, FastAPI/uvicorn, Telegram, tweepy/Twitter-transport, and companion/GF machinery are genuinely absent from non-legacy source:
- `grep -rn "fastapi|uvicorn|caddy|telegram|tweepy" **/*.py` → zero real hits (`knowledge_graph.py:142` is a docstring analogy only; a "twitter:" hit in `bot.py:11273-11277` is unrelated OpenGraph/`twitter:image` meta-tag scraping for URL previews, not the removed social transport).
- `companion` → one unrelated hit, `scripts/instance_backup_compat.py:180` ("archive and companion record must be distinct" — a backup-metadata string, not the removed companion/GF feature).
- No `Caddyfile`, no `api.py`/`web.py` module (`git ls-files`), `compose.yaml` services are exactly `ollama-pull`, `ollama`, `bot` (matches `REDESIGN_PLAN.md:15-19`, `docs/OPERATIONS.md:27`).
- `shelldocker` and `data_gf` survive only as dead path/exclude-list references (`bot_tools.py:4831` fallback path used only when *not* `container_mode()`; `pyproject.toml:16,19` Ruff excludes) — neither directory exists on disk or in `git ls-files`. This is a harmless naming leftover, not surviving nested-shell-container infrastructure.
- `hd_image`/`POLLINATIONS`/`GEMINI_IMAGE` → zero hits in `bot_tools.py`, `tool_schemas.py`, `control_defaults.py`, `config.py`, `bot.py`; the unification (`4e4027a`) is clean in active source. The only stale mentions are in `phase-II_v2/PRUNING_MAP.md:146-147` (temporary working evidence describing the pre-unification split), and this staleness is **self-flagged** in `audit/image-unification-plan.md:21`: "Its image subsection documents the old two-tool/two-protocol split and should be refreshed... if this audit map remains maintained" — flagged, not fixed.
- `create_site_quota_per_user` appears only inside `control_defaults.py:310` `DEAD_CONTROL_KEYS`, i.e. explicitly-handled legacy-key stripping, not live functionality — not a violation.

**Three 2026‑09‑24 changes the redesign plan did not itself authorize, and their cited grants:**

| Change | Commit | Cited grant | Location | Quoted root instruction, or agent inference? |
|---|---|---|---|---|
| Taint/confirm gate removal | `085c95b` | "Root's explicit 2026‑09‑24 amendment removes the web-read taint/confirmation subsystem in full" | `phase-II_v2/REDESIGN_PLAN.md:32` | **Inserted in the same commit that performs the removal** (`git blame` confirms `085c95b7` authored that exact sentence). No prior, independently-dated record exists. |
| Image-generator unification | `4e4027a` | "root selected **Temporary Dirac: configure and deploy**: read the configured gateway's model catalog... consolidate only relevant settings... rebuild/replace" | `audit/image-profile-discovery.md:5` | Authorizes *configuring and deploying* image settings; the specific design decision to **merge** `image_generator`+`hd_image` into one tool is attributed to *"Parent decision"* in `audit/image-unification-plan.md:37`, i.e. the implementing agent's own call, not a quoted root instruction to unify. |
| `longprompt` addition | `723e7d8` | "Root chose a separate command instead of changing the battle-tested `prompt` handler" | `docs/STATUS.md:44` (inserted by commit `b507a9b`) | Bare assertion by the coordinator, contemporaneous with the acceptance record; no corroborating `SESSION_LOG.md`/`TODO.md` entry exists (see below). |

For all three: `phase-II_v2/SESSION_LOG.md` has zero entries dated 2026‑09‑24 (its last entry is headed "2026‑09‑23"), and `TODO.md` was last modified 2026‑09‑23 19:25, before any of these three commits. Neither of the project's two dedicated decision ledgers records these grants independently of the acting agent's own documentation commit. This does not prove root did *not* say these things — it shows the repository contains no corroboration separate from the implementing agent's own narration.

**`legacy/` deletion:** `git status`/`git diff --stat -- legacy` shows 24 files, 3,970 deletions, unstaged and uncommitted (present at conversation start, not something I touched). `grep -n -i legacy TODO.md docs/STATUS.md phase-II_v2/SESSION_LOG.md phase-II_v2/REDESIGN_PROGRESS.md phase-II_v2/REDESIGN_PLAN.md` returns only references to *moving things into* `legacy/` (archival) — never to deleting it. **No assignment anywhere authorizes this deletion.**

## 5. Documentation drift after today's commits

- **`IMAGE_GEN_QUALITY`:** `config.py:379` defaults to `"low"` when unset. `docs/IMAGE_GENERATION.md:15` and `.env.example:218` both show/set `high`. Not a functional bug (both docs *set* it explicitly), but the documented "default" quality and the code's actual fallback default disagree, and neither doc mentions the code-level `"low"` fallback.
- **`OPENAI_MAX_TOKENS`:** `config.py:194-195` defaults to `16384`; `.env.example:46` sets `8192` and calls it "a sane default" — a second, previously unflagged config/doc mismatch in the same family.
- **`.env.example` vs `docker/bot.env.example` for `IMAGE_GEN_*`:** `.env.example` carries the full seven-key image block (lines 208-219); `docker/bot.env.example` (35 lines total, the container/Dirac-style template) has **none** of `IMAGE_GEN_*` — an operator provisioning a container from that template gets no image-generation defaults at all, and no doc calls this out.
- **`hd_image`/Pollinations/`GEMINI_IMAGE`:** README.md has no image-config references (matches `REDESIGN_PROGRESS.md:21`'s own claim); `docs/IMAGE_GENERATION.md:26` correctly documents the retirement. Only `phase-II_v2/PRUNING_MAP.md:146-147` is stale (see §4), and that staleness is self-acknowledged in-repo.
- **`SECURITY.md`:** last touched by `47cd6f1` (2026‑09‑19), **before** the taint/confirm gate was removed. It contains **zero** mentions of taint/confirm/prompt-injection. On 2026‑09‑24, root (per the ledger) explicitly accepted new risk — "model-directed shell execution after reading external content" with "no per-turn web-read confirmation lock" (`docs/ARCHITECTURE.md:47`, updated same-commit as the removal) — but the one document whose stated purpose is "private-state and disclosure boundaries" (`README.md:26`) was never updated to disclose this. `docs/ARCHITECTURE.md` *was* updated in the same commit (`085c95b`) that removed the gate — so the drift is specifically in `SECURITY.md`, not `ARCHITECTURE.md`.
- **`bot.py:6538`** hard-codes `!prompt <text>` in the empty-prompt hint even though the adjacent `longprompt` branch three lines later correctly uses `self.command_prefix` (see §3) — a live, user-facing instance of the drift documented plainly.
- **`docs/STATUS.md` structure:** 179 lines, 19 `##` sections, newest-first (confirmed by reading top to bottom: "Current temporary Dirac release" is section 1, each subsequent section correctly self-labels "Previous..."/"Historical..." — no stale "Current release" header was left behind by a newer entry). However, three of those 19 sections ("bounded tool logging," "incomplete-output handling," "unified images") are all dated 2026‑09‑24 and each documents a single-day incident/hotfix/redeploy cycle with exact UTC timestamps, container/image hashes and backup paths — this is functioning as an **incident log**, not a milestone ledger, for at least the top third of the file. The remaining ~12 sections (from "Previous runtime — 2026‑09‑22" downward) read as genuine milestones.

## 6. The `?prompt` >2000-character failure

**Ledger says** this was diagnosed read-only on 2026‑09‑23 and never fixed. Exact quotes:
- Diagnosis: *"Current `bot.py:6570–6582` still sends the entire prompt as one `channel.send`... Smallest proposed fix: route both responses through the existing bounded `send_command_response` helper... **No prompt-handler patch, replay, provider call or restart was performed for this diagnosis.**"* (`phase-II_v2/DIRAC_HANDOFF.md:84-85`).
- Decision quoted in `docs/STATUS.md:67`: *"That was read-only diagnosis; root subsequently chose to preserve this handler and add the attachment-based `longprompt` command above."*
- `723e7d8`'s own commit message: *"Add attachment-based longprompt **without changing prompt**"*, and `docs/LONGPROMPT.md:3`: *"the existing `prompt` command, including its message-length limitation, is intentionally unchanged."*

This is presented as a recorded decision to leave `prompt` broken (root allegedly chose `longprompt` over fixing it), not an open unowned defect — but the only textual source for "root subsequently chose to preserve this handler" is, again, the coordinator's own line inserted into `docs/STATUS.md` by commit `b507a9b` (see §4 pattern), with no `SESSION_LOG.md`/`TODO.md` entry corroborating it independently. The defect itself is real and unpatched: `bot.py:6533-6545` still sends the full prompt in one `channel.send` inside a code fence, and the empty-state usage hint at that same location hard-codes `!prompt <text>` rather than `self.command_prefix` (§3, §5) — so on Dirac (`?` prefix) the still-broken command's own error text names the wrong prefix.

## Key file/line references
`AGENTS.md:57`; `docs/STATUS.md` (whole file, 179 lines); `phase-II_v2/REDESIGN_PLAN.md:32`; `phase-II_v2/DIRAC_HANDOFF.md`; `phase-II_v2/SESSION_LOG.md` (no 09‑24 entries); `TODO.md` (unmodified since 09‑23); `bot.py:2326,6538,6549-6550,6471-9187 (usage strings)`; `job_routing.py:39`; `config.py:194-195,379`; `.env.example:46,218`; `docker/bot.env.example`; `SECURITY.md`; `docs/ARCHITECTURE.md:47`; `phase-II_v2/PRUNING_MAP.md:146-147`; `audit/image-profile-discovery.md:5`; `audit/image-unification-plan.md:37`.
