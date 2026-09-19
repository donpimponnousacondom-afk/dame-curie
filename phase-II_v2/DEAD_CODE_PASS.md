# First soft dead-code pass

## Result

| Measure | Observed |
| --- | --- |
| Application source | Unchanged from `a9c0fba`; mapping docs checkpoint `8d9cb8f` |
| Tool | Vulture **2.16**, isolated Python **3.14.4** |
| Scope | **87 tracked Python files**, **70,746 physical lines** including comments/blank lines |
| Findings | **163**: 150 at 60%, 2 at 90%, 11 at 100% |
| Unreachable blocks reported | **0** |
| Tool exit | **3**, expected findings outcome; no input/syntax diagnostics emitted |
| Application/test execution | None; source parsed, never imported |
| Deletions / application edits | **None** |

This is a manageable candidate inventory, not evidence the rest is live or that 163 things can be removed. Vulture's global name matching misses some dead paths and reports some real framework consumers. Size-sorted reports can put the most important live callbacks at the bottom: `setup_hook` is the largest reported item here, not the best pruning target.

- Exact inputs: `VULTURE_INPUTS.txt`.
- Complete unfiltered findings: `VULTURE_BASELINE.txt`.
- Repeatable installation, source selection and interpretation: `../docs/DEAD_CODE.md`.

## Useful first candidates — not removal approvals

| Candidate | Source evidence / boundary |
| --- | --- |
| `providers.py:1627-1636`, `_deepseek_reasoning_transport` | Ordinary private helper explicitly marked deprecated. The executable request path at `2000` calls the different, current `deepseek_reasoning_transport` defined at `1610`. Strong small cleanup lead; do not rewrite the working provider adapter |
| `bot.py:15975-15982`, `_lean_chat_turn` | Says gated catalogs are gone and always returns False. Also inspect the separately reported `LEAN_TOOL_PROTOCOL` at `2544` and `CHAT_CORE_TOOL_NAMES` import. Keep actual tool registration/protocol and current catalog; do not resurrect or redesign lean mode |
| `bot_tools.py:616-621`, `_heredoc_delimiter` | Small wrapper with no use identified by this scan. The underlying heredoc scanner has other callers and must not be removed with this wrapper |
| `bot_tools.py:8495-8498`, `_shorten` | Ordinary formatting helper with no use identified by this scan. Its docstring's claim of shared use is not caller evidence |

These examples received bounded source inspection, not an exhaustive reverse-call or test-reference audit. Dynamic/external callers remain unknown. The remaining 159 findings were not all individually investigated.

## Known traps to retain

- Ten of the eleven 100% findings are unused context-manager/asyncio/signal callback parameters. Their bodies do not use those values, but their calling protocols still pass them: `bot.py:1871,18445-18459`; `bot_tools.py:128`; `utils.py:1127`; `scripts/log_console/terminal.py:57-66`; `scripts/log_filter.py:92-109`. Do not drop those arguments to chase the score.
- The remaining 100% finding is `rem.py:31`'s `turns_remaining`. Its current prompt is single-pass (`33-42`). This is a signature/caller cleanup candidate, not permission to remove functional REM memory processing.
- Discord `on_*` hooks / `setup_hook` are framework entrypoints; SQLite `row_factory` is a library-consumed setting. Plugin APIs and serialized job fields such as `thread_id` need extension/serialization consumer tracing. These interfaces are not dead merely because the scan reports no ordinary read/call.
- Configuration findings such as `ASR_RIVA_FUNCTION_ID` or `NVIDIA_IMAGE_URL` need per-consumer review. A flagged config-class attribute is not the same thing as an unused environment variable or an unused provider dependency.

## Authorization and integration

After the read-only mapping phase, root explicitly requested a first static, report-only dead-code pass plus reusable tooling ergonomics. That authorized this separate tooling installation/AST scan, not feature removals or application validation. Vulture was selected because it fits that non-executing pass; runtime coverage is deferred. Official release metadata was consulted only to verify the tool's pin, Python support and options.

Created a fresh ignored `.venv` with `/usr/local/bin/python3.14`, installed only `vulture==2.16` (besides venv's bootstrap pip), and verified both versions. Existing package pins were not relaxed; no app/test dependencies or hooks were installed. `requirements-dev.txt`, `pyproject.toml`, both review skills and development guidance now document the soft-audit boundary. The provider/tool/subsystem implementation remains untouched. Production, private configuration, archives and `scratch-mermaid/` stayed outside this scan; no tests, providers, services or deployment scripts were executed.

Next action is a separately selected small candidate review/removal, not automatic pruning of this report or an expanding whole-codebase audit.
