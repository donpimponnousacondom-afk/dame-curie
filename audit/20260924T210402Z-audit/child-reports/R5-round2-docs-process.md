# Round-two child report R5 — documentation, process and ledger consistency (Sonnet, read-only)

Coordinator note: verbatim child output (HTML entities normalised). Dispositions in `../08-ROUND2-REPORT.md`.
Coordinator independently re-ran: the net-zero test-definition count (32/32, no new or deleted test files), the
three standalone commit tree hashes, the QA60/QA61 tree comparison against the committed `d198c37` tree (QA61
identical in every Python/build input; QA60 differs from the commit by one comment-only `bot.py` hunk and two
test files later rechecked in QA61), and the presence of the verbatim root quotes in `SESSION_LOG.md`.

---

# Round-Two Re-Verification Report — dame-curie phase-II_v2 audit remediation

Scope: read-only comparison of round-two implementer claims (`05-IMPLEMENTER-RESPONSE.md`, `07-PROCESS-DISPOSITIONS.md`, `validation.md`, `TODO.md`, `docs/STATUS.md`, `phase-II_v2/SESSION_LOG.md`, `AGENTS.md`) against the actual tree at HEAD `0e9519e` and git history back to round-one baseline `c603cf2`. No code executed, no tests run, no Docker/Screen touched, no `.env`/private paths read.

## 1. Process findings P-01…P-09

| ID | Implementer claim | Tree/ledger verification |
| --- | --- | --- |
| P-01 | "fixed" — cadence corrected; one bounded acceptance, rolled back (`05-IMPLEMENTER-RESPONSE.md:325-331`) | `AGENTS.md:14` carries the "Current release freeze — 2026-09-25" section. `phase-II_v2/SESSION_LOG.md:3-23` and `:25-35` quote root verbatim (`>` blocks) authorizing remediation + "bounded temporary-Dirac/test-channel acceptance." I diffed every non-audit file touched between `c603cf2..HEAD` and every doc mentioning container start/stop/replace; the **only** runtime action recorded anywhere is the QA66→67→68→69 sequence in `validation.md:185-202` (stop old → start candidate `sha256:3136ee…` → one 180 s request → stop candidate → restart old `sha256:5e3ed0…`). No other deployment, build-and-run, or private-setting edit is recorded in that range. `phase-II_v2/DIRAC_RUNTIME_OPS.md` diff (`c603cf2..HEAD`) is a **documentation** correction about what `dirac.py status` already does (ties to C-36), not a new runtime action. |
| P-02 | "fixed" via existing-test adaptation only | Confirmed by diff, see §below — net-zero test functions, zero new/deleted test files. |
| P-03 | "fixed" — safe-suite green, failures retained not suppressed | `validation.md:165` QA60 = "3984 passed, 28 subtests passed…exit 0" — matches `05-IMPLEMENTER-RESPONSE.md:341-345` and `docs/STATUS.md:19`/`TODO.md:15` verbatim. The bash-54 (`f38e3e4`) run at `validation.md:143-146` shows 4 unresolved `test_other_models_are_explicitly_unsupported` failures with an explicit refusal to xfail them ("explicit unresolved behavior/policy issue, not… xfail-for-green"); by QA60 these pass because **production** code was restored (`bot.py:7267`, message "These controls require a recognized DeepSeek Flash transport…", landed in commit `d198c37`), not because the test was weakened — I confirmed `tests/test_reasoning_commands.py:168-182` still asserts the original negative behavior. |
| P-04 | "fixed" — `legacy/` deletion committed, docs corrected | `git show --stat aad36e6` deletes `legacy/README.md` + 23 files (matches round-1's "24 files, 3,970 deletions"). `AGENTS.md:12` records the grant. `git grep -n "legacy/" AGENTS.md README.md docs/ phase-II_v2/*.md` returns zero hits in `AGENTS.md`/`README.md`/`docs/`; all remaining hits are inside `phase-II_v2/*.md` narrating **past** states (dated 2026-09-19 lane docs, `PRUNING_MAP.md`), which `AGENTS.md`'s own text scopes as "temporary working evidence," not active instructions to read `legacy/`. |
| P-05 | "fixed"/retained-with-dispositions, table in `07-PROCESS-DISPOSITIONS.md:13-41` | Spot-checked two rows with `git cherry`: `work/dirac-discord-jobs` claimed "10/0" → `git cherry dev/phaseII_v2 work/dirac-discord-jobs` returns exactly 10 lines, all `-` (patch-equivalent) = **matches exactly**. `work/dirac-hardening-smoke` claimed "0/5" → returns exactly 5 lines, all `+` (non-equivalent) = **matches exactly**. No ref/worktree deletion occurred (table still lists 26 rows; "no row authorizes… deletion," `07-PROCESS-DISPOSITIONS.md:61`). |
| P-06 | "fixed — evidence tracked" | `.gitignore:138` has `/audit/`, added by commit `5b6be67`, which **predates** `c603cf2` (`git merge-base --is-ancestor 5b6be67 c603cf2` = true) — so the ignore rule is old, not something round two added and then bypassed silently. `git check-ignore -v` (default, index-aware) on a tracked audit file reports no match, while `--no-index` confirms the pattern would otherwise apply — i.e., the files are genuinely tracked despite the pattern. Commit `3754a8a`'s message states this explicitly: "Preserve the dated audit bundle explicitly despite its normal ignore rule." `git ls-files audit | wc -l` = 45 tracked files. |
| P-07 | "fixed" | `AGENTS.md:63` now reads `deepseek-official/deepseek-flash` / `openai-codex/gpt-6-luna` / `gpt-6-sol`; `grep -n "GPT-5.6"` over `AGENTS.md` returns nothing. Landed at `ab64853`. |
| P-08 | "deferred" (not "fixed") | `05-IMPLEMENTER-RESPONSE.md:381-384` and `07-PROCESS-DISPOSITIONS.md:63-71` both say provenance of the two `__pycache__/*.pyc` files and `.validation-cache/` remains **unattributed** — this is an honest deferral, not a hidden "fixed" claim. `TODO.md:39-47` names coordinator ownership and a "compact final provenance/limitations receipt" gate. |
| P-09 | "fixed" — verbatim quotes recorded | `phase-II_v2/SESSION_LOG.md:5-11` and `:27-30` both contain `>`-quoted verbatim root text for 2026-09-25. Old uncorroborated sentences ("Root chose…") were removed, not just labeled: `grep -n "Root chose\|root subsequently chose"` over current `docs/STATUS.md` and `phase-II_v2/REDESIGN_PLAN.md` returns **zero** hits. `REDESIGN_PLAN.md:1` title itself now reads "Discord-only redesign — **historical source-scope contract**," with an explicit "not independently corroborated" disclaimer at `:3`. `docs/STATUS.md:7` states "Earlier author-written assertions about root's instructions are historical claims, not new or retroactive authority." |

**P-02 detail (net-zero tests):**
```
git diff c603cf2..HEAD -- tests | grep -cE '^\+(async )?def test_'   → 32
git diff c603cf2..HEAD -- tests | grep -cE '^-(async )?def test_'   → 32
git diff --diff-filter=A --name-only c603cf2..HEAD -- tests          → (empty)
git diff --diff-filter=D --name-only c603cf2..HEAD -- tests          → (empty)
```
Net-zero test function count, zero added/removed test files. `tool_policy.py` (25 lines, `git cat-file -e c603cf2:tool_policy.py` fails, new in `d198c37`) implements exactly the actor-authorization fix requested by C-23/C-24 (`bot.py:13850,14066,14759` all call `tool_authorized(self, message, name)`). `turn_budget.py` (148 lines, also new in `d198c37`) implements exactly the whole-turn output/attempt/deadline budget requested by C-06 (and media cap requested by C-19, tool-group state requested by C-17/C-21). Both carry module/class/function docstrings and no blanket exception handling except one narrow, three-exception-type input-coercion helper (`turn_budget.py:108-114`) parsing a config value — judged in-scope as direct implementation of previously-identified, root-approved findings, not unrequested scope creep.

No new `xfail`/`skip`/`skipif` markers were added anywhere in the range; the one line removed was the historical `pytest.skip("OPENAI_BASE_URL not set…")` guard on the now-replaced synthetic streaming test (`git diff c603cf2..HEAD -- tests | grep -n xfail\|skip\|skipif` → only that one `-` line).

## 2. Documentation findings D-01…D-06

| ID | Tree evidence |
| --- | --- |
| D-01 | `SECURITY.md:16-18` now states shell is "restricted to bot admins and the existing shell-user allowlist," calls the environment filtering "defense in depth, **not secret isolation**," and explicitly says "do not claim the removed taint gate exists." Cross-checked against source: `bot_tools.py:5223-5228` spawns the shell with a hardcoded minimal `env={"HOME":…, "PATH":…, "LANG":"C.UTF-8", "PYTHONUNBUFFERED":"1"}` (no `**os.environ`) and `bash --noprofile --norc`, replacing round-one's `env={**os.environ, "HOME": …}`. `tool_authorized()` (`tool_policy.py:16-25`) gates `shell`/`join_server`/`update_base_personality`/`update_server_prompt`. |
| D-02 | `.env.example:46` = `OPENAI_MAX_TOKENS=16384`; `config.py:217-218` default = `16384`. Aligned. |
| D-03 | `docs/LONGPROMPT.md:3` now reads "examples use the repository convention `!`," and all command examples in that file use `!`. |
| D-04 | `grep -n "confirmation" jobs.py` → no matches (the flagged `jobs.py:499` "confirmation rules" text is gone; current wording at `jobs.py:503-505` says "Preserve actor authorization and configured tool/platform restrictions"). `phase-II_v2/PRUNING_MAP.md:3` carries an explicit "Retained evidence, not current authority" banner covering its stale taint/confirmation mentions at lines 8/34/94/103/112/201. `REDESIGN_PLAN.md` is similarly retitled/disclaimed (see P-09 above). Note: several dated *lane* docs (`DIRECT_SHELL_IMPLEMENTATION.md:22`, `JOB_ROUTING_IMPLEMENTATION.md:49,57,65,72`, `EMAIL_REMOVAL.md:22`, `SOURCE_BOUNDARIES_IMPLEMENTATION.md:48,58`, `SOCIAL_TRANSPORT_REMOVAL.md:23,31`) still say "taint/confirmation… remain unchanged" without a per-file historical banner — these are pinned to 2026-09-19 baselines in their own text but rely on `AGENTS.md`'s blanket "`phase-II_v2/` is temporary working evidence" framing rather than an explicit in-file label. This is narrower than "PRUNING_MAP and redesign/handoff assertions are labelled historical" as stated in `05-IMPLEMENTER-RESPONSE.md:424` — that claim holds for `PRUNING_MAP.md` and `REDESIGN_PLAN.md` specifically, not for every phase-II_v2 lane doc. |
| D-05 | `docs/STATUS.md` is now 53 lines / 6 headers, versus 185 lines / 20 headers at `ab64853:docs/STATUS.md` (`git show ab64853:docs/STATUS.md | wc -l`). The three same-day 2026-09-24 sections are collapsed into one "## Historical temporary runtime — 2026-09-24" section plus a 3-row "Consolidated same-day historical receipts" table (`docs/STATUS.md:34-42`), with the old full narrative preserved at `ab64853:docs/STATUS.md`. |
| D-06 | `phase-II_v2/DIRAC_HANDOFF.md:64` states restart-retains-log-history/can-replay, `--fresh`=`--tail 0`, `start --replace` creates a new stream — matched against `scripts/dirac.py:79-92,313,324-334` (`--fresh` flag, `restart()` function, "follow logs, then rerun start --replace" messages). |

## 3. Validation ledger (validation.md) internal consistency

All ~30 run identifiers (bash-34…bash-51, then QA52…QA69) resolve as real git objects — I ran `git cat-file -t <sha>` on every "frozen tree"/commit hash cited in the ledger (24 checked); **all resolved** (tree or commit, none dangling/unresolvable). Selected identity checks:

- `bash-43`/`bash-44`/`bash-46,48` claim "tested and committed tree X" → committing commit's own tree hash **exactly equals** the claimed tested tree (`7286aa2`→`bdd636d…`, `551060d`→`c13f3d5…`, `e540be6`→`56062c0…`): the committed diff is byte-identical to what was tested, not just "close."
- QA62 tested tree `25a027e…` vs the later `be28b85` commit's tree: `git diff 25a027e… <be28b85-tree> --stat` shows only two **documentation** files changed (`micro-artifact-inputs.md`, `validation.md`) — zero application-code drift between tested and committed source, confirming `validation.md:216`'s own claim.
- QA52's raw synthetic stdout (`qa52-synthetic-stdout.log.gz`, decompressed) tails with `83 failed, 3894 passed, 9 errors, 28 subtests passed in 167.25s (0:02:47)` — **matches** `validation.md:135` exactly.
- Cross-ledger consistency: QA60 (3984 passed/28 subtests), QA61 (201), QA62 (4), QA67-69 request/identity/footer facts appear **identically worded** across `validation.md`, `docs/STATUS.md:19-21`, `TODO.md:15-18`, and `05-IMPLEMENTER-RESPONSE.md` P-01/P-03 blocks — no contradicting counts found in any of these four documents.
- Numbering convention shifts from `bash-N` to `QA-N` around N=52 within the same document (e.g., "bash-54" in one heading is cross-referenced as "QA54" two sections later); this is a labeling-style change, not an inconsistency — the tree/commit references disambiguate unambiguously.

Frozen-vs-candidate distinction: `validation.md:5-11` ("Isolation and provenance") states runs use a **Git archive**, "never a host application import or a bind-mounted live checkout," while "Candidate snapshots use an independent temporary Git index." QA63-65 explicitly build and inspect the actual `dame-curie-app:be28b85` **image** (candidate), distinct from the frozen-tree pytest-only runs (bash-34…QA61).

Restoration quote for QA67–69 (`validation.md:200-201`):
> "Candidate stopped cleanly at 12:30:09.679684654Z, exit0. Candidate retained logs/control snapshot were preserved privately, without printing contents. Field comparison found **only allowed_channels changed**. Original control bytes were restored exactly; derived `bot.env` SHA256 remained unchanged. No request or terminal receipt was deleted, avoiding replay."
> "QA69 restored old image `sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f`, new container `495331359e7d6fcc0ad736eecebdd5c8ee27dbde922dd91cb9e5e5b1ff2f8f46`, started 2026-09-25T12:30:41.035310558Z, running/embedding_readiness=ok."

Bundle-content check (P-06 follow-up): `git ls-files audit` lists 45 files. Two non-`.md` files: `qa-git.Dockerfile` (a benign 10-line Dockerfile that copies `/usr/bin/git` into the QA base image — no secrets) and `qa52-synthetic-stdout.log.gz` (a real gzip'd pytest stdout log; decompressed and scanned for `sk-`/`Bearer `/`token=`/`DISCORD_TOKEN=`/`password`/`api_key` patterns — zero hits). A repo-wide `git grep` for the same patterns across tracked `audit/` text found **one** match, in `review-lifecycle.md:27` — a synthetic illustrative string used to describe redaction-test behavior (a fake PEM-style header and a placeholder token used to test that a redactor's private-key span logic hides a following field), not a real credential. A snowflake scan (`[0-9]{17,20}`) across tracked audit files found exactly three IDs, all already present in `AGENTS.md`/`phase-II_v2/DIRAC_HANDOFF.md`: root's ID, the temporary-Dirac Discord login ID, and the approved smoke-channel ID — no new snowflakes introduced.

## 4. Deferrals and spot-checked C-items

- **C-09** (import-time dotenv): `05-IMPLEMENTER-RESPONSE.md:97` explicitly says "Import-time dotenv loading remains a real boundary… Historical bytecode origin remains unresolved (P-08)" — labeled deferred, not fixed. `TODO.md:45` names it under "Retained items for round-two disposition," owner "coordinator," gate = "Round two must explicitly accept this limit or request a separately scoped lazy-loading change."
- **P-08/I-05** (bytecode/reviewer-method provenance): `05-IMPLEMENTER-RESPONSE.md:383,481` both say "deferred." `TODO.md:47` names the same owner/gate ("Compact final provenance/limitations receipt").
- Both deferrals carry an explicit owner (coordinator) and an explicit gate in `TODO.md:41-49`, satisfying "honestly labelled deferred with an owner and a gate."

8 random C-items spot-checked (block claim → cited commit/current-tree grep):

| ID | Claim | Verified in tree |
| --- | --- | --- |
| C-11 | actual reasoning content, not raw truthiness | `provider_telemetry.py:95-100` defines `reasoning_content()`; used at `providers.py:1094,1115,3110` |
| C-16 | 96000-char schema-inclusive budget; `## Available tools\n` protected | `control_defaults.py:175` = 96000; `bot.py:15314` checks that exact prefix |
| C-21 | dead expansion flag replaced by task-local discovery | `bot_tools.py:4808-4825` `MoreToolsTool.execute` now calls `current_tool_groups()` (from `turn_budget.py`) and mutates the real per-turn set; old `_tools_expanded` string is absent from the tree |
| C-25 | image auto-advertisement requires valid config | `config.py:289-295` gates `ENABLE_IMAGE_GEN` on `IMAGE_GEN_CONFIG_ERROR` |
| C-29 | empty model/quality fall back to defaults | `bot_tools.py:1457` `quality=quality or getattr(cfg,"IMAGE_GEN_QUALITY","low") or "low"`; `_select_image_model()` at `bot_tools.py:1401` handles model the same way |
| C-30 | prefix interpolation, incl. `job_routing.py` | `job_routing.py:21,39` `parse_background_request(text, *, prefix="!")`; `bot.py:6530-6531` calls it with `prefix=self.command_prefix` |
| C-34 | caller uses real settlement result | `tool_progress.py:590-613` `transition_to_final` now `return`s the actual `await self._deliver_final(...)` result instead of unconditional `True` |
| C-37 | exact-task settlement/cleanup | `dirac_runtime.py` cited at commit `551060d`; consistent with lifecycle QA (`validation.md:94-101`, 117 passed) |

All 8 checked out — the cited commit/current source contains the described change; none were "fixed" claims without matching code.

## 5. Coordinator self-consistency

`05-IMPLEMENTER-RESPONSE.md:3` claims "All 52 finding blocks and 6 implementer items." Verified:
- `grep -c "^## Finding "` → **52**.
- `grep -oE "^## Finding [CPD]-[0-9]+"` → exactly `C-01`…`C-37` (37), `D-01`…`D-06` (6), `P-01`…`P-09` (9) = 52, **zero gaps**, no duplicates.
- `grep -c "^### I-0"` → **6** (`I-01`…`I-06`).
- Cross-checked round-one's own ID universe: `grep -oE "C-[0-9]+" 01-AUDIT-REPORT.md | sort -u` yields exactly `C-01`…`C-37` with no gap, matching the response's coverage.

No round-one ID is missing a disposition block. The implementer-raised items (`I-01`…`I-06`) do not appear as predefined IDs in `05-IMPLEMENTER-INTAKE.md` (which uses unlabeled prose sections instead) — this is not a discrepancy, since those items were self-identified by the implementer during remediation and only assigned `I-` numbers in the final response document.

## Summary

Everything checked in this pass (P-01 through P-09, D-01 through D-06, the validation ledger's tree/commit resolvability and cross-document counts, the two deferred items' ownership/gates, and 8 spot-checked C-item source anchors) is anchored, resolvable, and consistent between "the ledger says" and "the tree shows." The one nuance worth flagging to the auditor: D-04's "redesign/handoff assertions are labelled historical" claim is accurate for `PRUNING_MAP.md` and `REDESIGN_PLAN.md` specifically, but several individual dated `phase-II_v2/*_IMPLEMENTATION.md`/`*_REMOVAL.md` lane docs still contain present-tense "taint/confirmation… remain unchanged" phrasing without a per-file historical label (they rely on `AGENTS.md`'s blanket phase-II_v2-is-temporary-evidence framing instead).
