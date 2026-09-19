# Grounding reconnaissance — 2026-09-19

Source baseline: `c460324`, Project Dame-Curie. This is a bounded static inventory, not an exhaustive audit, a feature-removal decision or runtime acceptance. References below are checkout-relative source locations. Nothing referenced outside the checkout was opened or followed.

## Documentation: what exists

| Classification | Local documents | Meaning in this phase |
| --- | --- | --- |
| Inherited operating authority | `AGENTS.md`; `docs/STATUS.md` | Existing text, not current authorization. Deployment, identity, backup and test-pass claims are unverified here. |
| Mixed setup/operating references | `README.md`; `docs/INSTALL.md`; `docs/DOCKER.md`; `docs/SCREEN_WORKFLOW.md` | Describe installation and runtime procedures that must not be executed now. Names, versions and external entry points need later reconciliation. |
| Feature/configuration references | `docs/OVERVIEW.md`; `docs/CONFIGURATION.md`; `docs/MAXWELL_PERSONA.md`; `docs/SVG_EMBEDDING_HOTFIX.md`; `scripts/publisher/README.md`; `assets/tokenizers/README.md`; `email_integration/README.md`; `SECURITY.md` | Present; neither complete nor fully reconciled against current implementation in this review. Presence is not correctness. |
| Explicitly historical/reference | `CONTEXT_MEMORY_ANALYSIS.md`; `RELIABILITY_RESEARCH.md`; `docs/instance-tour.html`; `docs/audits/2026-09-13-upstream-review.html`; `email_integration/LEGACY_MAILGUN.md` | Root `AGENTS.md:94` labels the analyses historical and portable HTML as reference. The upstream comparison was catalogued, not researched or followed. |
| Repository skills | `.agents/skills/implement-tyranny/SKILL.md`; `.agents/skills/curie-readonly-debug/SKILL.md` | Tyranny loaded for future standards; runtime-debug skill not activated. |
| Missing referenced artifacts | `TODO.md`; `reports/curie-workflow-wording-2026-09-13.html` | Referenced by `docs/STATUS.md:37`, not found in this checkout. Do not recover them from other projects, old history or online copies. |

## Material findings retained after challenge

1. **Inherited authority conflicts with this assignment.** `AGENTS.md:22-26` authorizes old rollout/restarts, including documentation-only synchronization; `:46-50` describes suite/live acceptance; `:54-58` describes publication/fetch workflows. None authorizes this session's actions. `docs/STATUS.md:3-19` records historical deployed images and acceptance, not observations of the fresh V2 checkout. Highest-priority containment is the explicit current boundary in every child handoff, not executing these instructions.
2. **Local references are missing.** The two paths above occur at `docs/STATUS.md:37`. `AGENTS.md:15` names a `reports/` convention, but no report files were found there. Root expressly chose `phase-II_v2/` for current temporary notes. This does not require creating a permanent reports hierarchy or rewriting dated history now. The review does not claim these are the only broken links in every document format.
3. **The architecture map has an unsupported path.** `AGENTS.md:69` lists `web/`; the top-level checkout listing has no such directory. This is a source-map discrepancy, not proof that the dashboard is missing or broken. Its actual architecture was not fully audited here.
4. **Python prose does not match the current requirement.** `README.md:445` says Python 3.12 for site runtime; `docs/INSTALL.md:38,45` says 3.11+. Root requires 3.14; `pyproject.toml:10,72` already targets it. These are later documentation corrections, not reasons to downgrade code or run installation commands.
5. **Identity/setup wording is inherited.** README and install references still use Maxwell and external source/install entry points; root's current name is Project Dame-Curie. Those references were not followed. Naming and route changes need an explicit later scope, not a global replacement.
6. **Historical language must remain historical.** Older status entries calling files untracked, reporting a Screen session or recording test counts need provenance labels, not retrospective rewriting as though they were current observations. No current V1 image, Screen session, test result or ownership model has been verified.

## Quality enforcement: declared versus demonstrated

- `pyproject.toml:5-46` declares Ruff, line length 88, Python `py314` and a curated rule set. `:71-80` declares mypy `3.14`, but untyped-body checking and unused-ignore warnings are disabled. This is not strict tyranny enforcement.
- `requirements-dev.txt:1-3` lists pytest and PyYAML, not Ruff/mypy. No CI or pre-commit configuration was found in the inspected conventional paths. The coordinator found standard sample Git hooks and no relevant configured hook/monitor/signing overrides. Tool availability and actual gate execution remain unverified; absence from those files does not prove no external tooling exists.
- The tyranny skill's setup recipe includes broad auto-fix/format instructions, Python 3.12 templates and an unfinished specific-ban list. Loading it is not permission to run that recipe. Preserve Python 3.14, apply standards to future authorized new code, and agree scoped enforcement rather than generating legacy-wide churn.

## Why no test execution or collection yet

The coordinator reread these source paths without importing them:

- `config.py:31-39` imports `load_dotenv`, selects `MAXWELL_ENV_FILE` or the checkout `.env`, and calls `load_dotenv(..., override=True)` at module import. Depending on available files and library behavior, imports can ingest real settings and override existing environment values. Collection can import modules; it is not inherently read-only metadata inspection.
- `tests/test_tool_progress.py:753-842`, `test_streaming_tick_inserts_space_between_glued_deltas`, independently reads the checkout `.env` at `:771-778`, takes provider configuration from the environment, constructs a real provider at `:792-801`, initializes it at `:813` and requests a completion at `:841`. A nonempty base URL controls its skip. This path does not honor `MAXWELL_ENV_FILE` for its direct file read.
- `AGENTS.md:47` expressly excludes that node; `pytest.ini:1-6` does not encode that exclusion. No test was collected or executed to confirm behavior.
- The external library's handling of `PYTHON_DOTENV_DISABLED`, a safe runner's availability and any claimed historical isolation were not verified. A flag alone is not evidence of isolation. No runner, guard, tests or fixes were added.

Future verification needs a separately agreed source-only, synthetic, disposable environment, with no private mounts/credentials and no live side effects. Selecting a synthetic dotenv path alone would not neutralize the direct `.env` reader above. The current phase does not authorize building or running that environment.

## Still unknown / decisions reserved for root

- Backup/snapshot completion and rollback readiness: another agent's assignment, not checked here.
- Which features to remove first; whether and when to rename source/API/environment/route names.
- When to repair inherited agent instructions and separate historical status from current V2 evidence.
- Whether to retire or replace missing document references; never recover them elsewhere without a changed instruction.
- Exact new-code bans and staged enforcement beyond the existing tyranny skill. No broad legacy reformat.
- Test case count, pass/failure baseline and actual V2 correctness. Root's roughly 4,000 tests and old reported totals are not newly verified results.

Inspection intentionally did not establish comprehensive link validity, implementation completeness, runtime health, deployment topology or provider behavior. No feature absence was inferred from a narrow search.
