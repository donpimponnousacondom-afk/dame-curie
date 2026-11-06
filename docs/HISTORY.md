# History and recovery references

Dated milestones and the Git references that recover retired material. Historical text is evidence, not operating authority.

## Milestones

| Date | Event |
| --- | --- |
| 25 September 2026 | Round-two audit closure on the temporary test bot Dirac (Discord id `1504398705539944560`): corrections `c2d6b0e` and `89fb851`, documentation retirement `f815857`. Preserved originals and receipts: `audit/20260924T210402Z-audit/` (start at `09-CLOSURE.md`). The loose untracked files next to it in `audit/` are root's; `.gitignore` ignores them. |
| 30 September 2026 | Root removed the publisher's content-based credential filter after an API documentation example blocked publication. The filter stays removed. |
| 2 October 2026 | Root's final transition assignment: V1 to V2 cutover without starting V1. Root clarified container tools: Python 3.14 first, lean defaults, no language ban. The Codex `council-pr-babysitter` skill was imported. |
| 3 October 2026 | Canonical Dame Curie (`1545541390392369165`) logged in on source `306b413`. Root removed 12 unsupported live settings and confirmed that removed V1 features and gates stay removed. Publisher repair (19:14 UTC) and remote inventory update (19:44 UTC); backups `/var/backups/dame-curie-v2-recovery/publisher-repair-20261003T191411Z` and `publisher-inventory-20261003T194453Z`. Root's rule "configuration is sacred". [PR3](https://github.com/donpimponnousacondom-afk/dame-curie/pull/3) held the source then; PR #4 superseded it. |
| 4 October 2026 | Root's rules "failures stay visible" and ASD-STE100 writing with no dashes. |
| 9 October 2026 | Root's direction on tool-call batching in the Codex and Claude Code style. The throne-v2 commits ran live from this date and merged as #4 on 31 October (119 files). |
| 31 October 2026 | Root made the coordinator (Claude) director of dame-curie. Review by Sonnet and Haiku replaced the Luna and Sol council. Automated smoke tests moved to canonical Dame Curie in test channel `1566164090039304285`; Dirac was not used from this date. |
| 6 November 2026 | Root replaced review by Sonnet and Haiku with a three-provider council and a Haiku babysitter, for now. The old skill is at `git show 7c117cf:.agents/skills/pr-review/SKILL.md`. |
| 1 November 2026 | Root's rules: new tests allowed and wanted; no word triggers; errors visible to the model; container time zone; day-first dates; publisher hidden folders persist. Self-copy dedupe ran (123 rows deleted; backup `round25-dedupe-20261101T172100Z`). |
| 2 November 2026 | Embeddings moved to OpenAI `text-embedding-3-large` at 1536 (#42); pre-cutover database, `bot.env` and `deploy.env` in `/var/backups/dame-curie-v2-recovery/round33-20261102T174836Z`. Memory audits deleted 397 and 141 rows (backups `round35-20261102T190719Z` and storage box `archive/dame-curie/memory-audit-20261102`). First backup offload to the storage box (`archive/dame-curie/recovery-offload-20261102T023007Z`, 14.2 GB freed). Local Ollama unplugged at 19:17 UTC (`DAME_CURIE_EMBED_MODE=external`). Dirac retired: `dirac-relay.service` stopped and removed at 19:27 UTC; `/srv/dame-curie/dirac` (296 MB), `/etc/systemd/system/dirac-publisher.service`, the host copies of `dirac.py` and `dirac_relay.py` and the relay backup were archived as `archive/dame-curie/dirac-retired-20261102T213015Z/dirac-retired.tar.zst` (83 MB, SHA-256 `7e937d32ab2b44bb813ae5e274a1967e3cf13ad9e3df90baf9b074cabe6b2b67`, verified on the box) and deleted locally. The unused network `dame-curie-backends` was removed. PR #46: documentation clean-up, Dirac file removal, smoke rename, ruff gate, scripts moved into the repository, unused test harnesses deleted. |

## Recovery references

All forms use `git show <rev>:<path>`.

| Material | Reference |
| --- | --- |
| Verbatim prior human grant | `eb188ac:phase-II_v2/SESSION_LOG.md` |
| Retired phase files (`REDESIGN_PLAN.md`, `PROVISIONING.md`, `DOCKER_INVENTORY.md`, `DIRAC_PUBLISHING.md`, `DIRAC_ATTACHMENT_LIMITS.md`, `LOGGING_PLAN.md`, Vulture inputs and baseline, `DEAD_CODE_PASS.md`) | `eb188ac:phase-II_v2/<name>` |
| Retired internal audit notes | `git ls-tree -r --name-only 89fb851 -- audit/`, then `89fb851:<path>` |
| Status before the 3 October rewrite | `ab64853:docs/STATUS.md` |
| Dirac operator, relay and service files | `8580b8a:scripts/dirac.py`, `8580b8a:scripts/dirac_relay.py`, `8580b8a:docker/dirac-relay.service`, `8580b8a:scripts/publisher/config.dirac.example.toml`, `8580b8a:scripts/publisher/dirac-publisher.service` |
| Dirac tests | `8580b8a:tests/test_dirac.py`, `test_dirac_operator.py`, `test_dirac_relay.py`, `test_dirac_relay_hardening.py` |
| Smoke harness before the rename | `8580b8a:dirac_runtime.py`, `8580b8a:scripts/dirac_smoke.py`, `8580b8a:tests/test_dirac_smoke.py` |
| Dirac operations runbook and the September status and TODO history | `8580b8a:docs/OPERATIONS.md`, `8580b8a:docs/STATUS.md`, `8580b8a:TODO.md`, `8580b8a:AGENTS.md` |
| Publisher V1 claim-preserving handoff procedure | `8580b8a:docs/PUBLISHING.md` |
| Dead-code audit page before folding into DEVELOPMENT.md | `8580b8a:docs/DEAD_CODE.md` |
| Codex council review skill, its observations and interface file | `8580b8a:.agents/skills/council-pr-babysitter/SKILL.md` and the same prefix for `references/review-observations.md`, `agents/openai.yaml` |
| Unrelated research script | `8580b8a:mimo.py` |
| Unused live-provider test harnesses | `8580b8a:deep_test_harness.py`, `8580b8a:tests/custom_harness.py` |

One-off host scripts of 1 and 2 November 2026 (`deploy-r33-embed.sh`, `deploy-r35-audit.sh`, `deploy-r36-ollama-off.sh`, `dedupe-apply.sh`, `embed-compat.py`) were never in the repository. Their effects and backups are in the milestones above.

## Accepted deferrals and held decisions

- C09: `config.py` loads dotenv at import time with `override=True`. Accepted. No lazy-loading project is pending.
- P08/I05: historical bytecode provenance is permanently unattributable and quarantined. No cache investigation is pending.
- Voice, replicas, sustained load and publisher remote-deletion recovery are unverified.
- Held by root: reasoning-only terminal responses stay terminal; the mandatory tool `explanation` argument; same-UID shell trust; the four filters listed in `TODO.md`.
