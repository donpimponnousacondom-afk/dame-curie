# Source cut-off review — dame-curie

2026-09-19. Baseline `47cd6f1`; branch `dev/phaseII_v2`. Verdict: **source naming checkpoint, not runtime/test acceptance**. Working V1 remains protected. Broader pruning is root's next assignment.

## Scope and ownership

| Work | Agent / route |
| --- | --- |
| Application/config namespace | `39b69700-7758-47e2-8547-8a9ab7e8ca92`, DeepSeek V4.1 Flash, high |
| Infrastructure/templates/wrappers | `83a7422a-009c-4fcd-9eb0-09dee2219ae9`, DeepSeek V4.1 Flash, high |
| Publisher namespace | `9551bd5c-bf52-4780-b60f-baba77088200`, DeepSeek V4.1 Flash, high |
| Existing fixture alignment only | `ea51831c-470f-474c-be43-49c78ea61d52`, DeepSeek V4.1 Flash, high |
| Independent adversarial review | `1f3a249b-b4d7-40c7-8903-4ce41e0dd378`, GPT-5.6 Luna, max |
| Mapping, scope decisions, corrections, documentation, final Git operations | Coordinator |

The harness catalog advertises `deepseek-official/deepseek-flash` as **DeepSeek-V41-Flash**. The separate V4 Flash vision-experimental route was not selected. Source writers had non-overlapping ownership; no child had permission to inspect or operate the live engine.

## Reviewed contracts

- Full `dame-curie` / `dame-curie-<identity>` slugs, 30-character cap, direct account lookup and `/srv/<full-instance>` roots.
- Compose project/network, runtime resource names/labels, UID-derived host socket, image socket/home paths and shell/export ownership checks.
- `DAME_CURIE_*` configuration producers/consumers, PM2 selectors and bot/API `dame-curie-rag.db` coupling.
- Snapshot socket template filenames, full-slug socket user/group, checkout-owner worker and checkout `.venv` interpreter.
- Archive pax identity, compatibility format/digest key and emitted reconstruction source.
- Publisher scanner/standalone remote guard/HTTP marker exclusions; local state, service account, interpreter and synthetic separate destinations.
- Explicit unconfigured/synthetic URL/mailbox defaults without a renamed real endpoint or a legacy-state alias.
- Existing test fixtures and import roots, without adding cases, assertions or test functions.

## Corrections applied

| Finding | Disposition |
| --- | --- |
| New full slug combined with the old automatic Compose prefix | Compose/project/backend names now derive directly from the full slug |
| Snapshot socket account also prepended the project name | `SocketUser=@INSTANCE@`, `SocketGroup=@INSTANCE@`; fixture uses the same contract |
| Runtime and CLI instance validators did not initially share the selected namespace | Existing validation now accepts only the selected namespace and existing total length limit |
| Real V1 site/OAuth/mailbox fallbacks survived the first pass | Site fallback is reserved `.invalid`; baked callback/mailbox defaults are empty; existing OAuth/configuration flow retained |
| Publisher patch introduced unnecessary constant/module deduplication | Restored original module structure; coordinated literal changes only |
| Mechanical internal persona renaming | Reverted `MAXWELL_BASE_KNOWLEDGE`, `_maxwell_id`, `mentions_maxwell`; real env/config keys remain renamed |
| Temporary filesystem prefixes were reverted together with internal variables | Coordinator retained the new filesystem prefixes; no persona/content changes |
| Global-Python/pip guidance contradicted the project environment | Active doctor/config/tool guidance uses `.venv/bin/python`; installer/doctor version checks select exactly Python 3.14 |
| New installer venv helper rebased a relative install path after `cd` | Removed the unnecessary helper/guard; existing checkout-relative operations invoke `./.venv/bin/python` directly |
| Test helpers inserted a real old checkout path | Existing inserts now derive their own checkout parent; snapshot fixture uses `/opt/dame-curie` |
| V1-specific DNS provisioners were still active source | Root approved byte-preserving quarantine; bot email tools remain |
| Stale index/snapshot findings | Current worktree was reread; corrected publisher/socket files must be the final committed versions, not their first staged drafts |

The earlier alleged name-only destructive-selector bypass was not real: missing/foreign ownership labels raise before selection. A foreign overlapping-prefix object can still trigger that existing fail-closed check. Separate engines per identity are required; no shared-engine acceptance or selector redesign was claimed.

Historical mail/URL comments, persona names, internal probe/log identifiers and ordinary `max` terms were not treated as executable configuration. Preserving them does not authorize using V1 endpoints or following retired guidance.

## Evidence and limits

- Source/file inspection, current Git diffs and manual producer/consumer review are the acceptance evidence for this checkpoint. Luna found the settled naming families aligned; its remaining interpreter-guidance warning was corrected.
- No new tests/cases/assertions were added. The fixture owner reported equal before/after counts of assertion/test-definition lines (8,747) and 155 `tests/*.py` files; these are static text counts, **not a test count, collection or pass result**. Forty-five existing test files changed.
- No application imports, test collection/execution, linter/type-checker runs, dependency installation, builds, provider calls, real login, runtime lifecycle work or deployment was performed.
- An infrastructure child did run `bash -n`, generic `python3` AST parsing of four helper files and `node --check` on an earlier edit. This deviated from the requested explicit isolated-interpreter discipline. Those were parser-only probes with no application imports; they are not Python 3.14/project-environment validation or checks of every final correction. No repeat was performed.
- Python 3.14.4 and standard-library venv help were separately observed earlier using explicit isolated/no-site/no-bytecode invocation. No `.venv` was created. The shell image's distro Python version remains unverified.
- The DNS scripts were moved unchanged; no DNS/mail API was called. Normal Docker context excludes `legacy/` and phase notes; Ruff/mypy skip archived source. Existing pytest discovery already targets `tests/`.
- The inherited provider-resilience documentation test still references retired `docs/CONFIGURATION.md` and missing `doc/html/maxwell-tool-budgets.html`. Its future purpose belongs to pruning; no absence assertion or substitute documentation was created to satisfy it.
- Root requested the unchanged sanity skill be committed as tyranny's twin. The concurrent Mermaid scratch work is not part of this checkpoint. The ignored pre-existing `run.sh` helper was restored to its original content and is not added to Git.

## Final bookkeeping gate

The coordinator reviewed the staged paths and complete source/fixture deltas; final corrections were independently reread. Git identifies both DNS moves as R100 and the staged whitespace check passed. The index contains the reviewed source/fixture/documentation checkpoint and root's requested unchanged sanity skill; concurrent Mermaid scratch work is excluded. The hook directory contains only sample hooks, and the targeted query found no hook/fsmonitor/signing overrides. The resulting local commit is reported with the handoff, not treated as runtime permission. Remaining acceptance/provisioning/private-root/port/publisher/backup questions are recorded in `../docs/STATUS.md`.
