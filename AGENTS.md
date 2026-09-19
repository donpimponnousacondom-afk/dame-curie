# dame-curie — current agent contract

This checkout is the clean-cut V2 workstream for **dame-curie**. Root's current instructions take precedence over repository guidance. V1 is functional and running; this is deliberate pruning/refactoring, not permission to repair an assumed incident.

## Read first

- `docs/STATUS.md`: what this checkout has and has not completed.
- `docs/OPERATIONS.md`: account/engine mapping, read-only discovery and stop boundaries.
- `docs/DEVELOPMENT.md`: Python 3.14, isolated interpreters, configuration and validation limits.
- `docs/ARCHITECTURE.md`: intended boundaries versus demonstrated behavior.

`legacy/` is quarantined historical material, not active instructions. Exclude it from ordinary orientation/searches. Read a specific archived file only for an explicitly assigned archaeology question; do not follow its external paths, URLs, old commits or operating commands. Never look for another checkout or upstream project to fill gaps. The archive's old agent contract deliberately is not named `AGENTS.md`.

## Current approved redesign

Root approved the Discord-only redesign in `phase-II_v2/REDESIGN_PLAN.md`: logging first; remove dashboard/API/Caddy, bot-local site servers/tools, nested shell infrastructure, X/Telegram and companion/GF; execute shell inside the outer bot container; then tool/prompt boundaries and application-job routing. Active command references become `!command`, including docstrings. The publisher/syncer, local authoring/image paths and remote mirroring are **untouchable**; no replacement API, PHP/Perl installation, local hosting or model-driven remote administration. Preserve Discord administration, autonomy, games, plugins, media and functional memory. This specific human grant supersedes older unselected-feature language, not the runtime/test/privacy holds below. Root is AFK: proceed with bounded best decisions and record concrete uncertainties instead of asking settled-scope questions.

## Protected V1 and isolated V2

- Protected V1 service account: `maxwell-curie`; its local private Docker engine owns the observed V1 resources.
- V2 service account: **`dame-curie`**. Its account and separate private rootless engine were created and verified under root's explicit provisioning grant; current readiness/activation holds are recorded in `phase-II_v2/PROVISIONING.md`. Re-resolve the account/socket before any newly authorized runtime operation. Do not substitute `dame-curie-v2` or concatenate the project name twice.
- A dated, explicitly authorized running-resource inventory is in `phase-II_v2/DOCKER_INVENTORY.md`. It is not current configuration, a backup, host-wide collision proof or source provenance.
- Separate users/engines are the intended isolation boundary. Private configuration/state roots, mounts, ports and remote publisher destinations must also be separated. Multi-instance replication is not yet accepted for V2.

## Authorization boundaries

Default is **hands off runtime**. A source/documentation task grants no Docker or service access. When root explicitly requests a read-only Docker inventory, use the mapped service account and explicit local rootless socket as documented; sudo/run-as requires that specific grant. Never silently fall back to the default/rootful/another account's engine after an error.

No application imports/execution, test collection/execution, dependency installation, builds, pulls, user/engine provisioning, starts/stops/restarts, deletion/pruning, migrations, real login or cutover without a separate compatible assignment. Do not execute deployment/lifecycle scripts even for discovery or `--help`. Source inspection is allowed; execution is not. Do not use the GNU Screen session or activate `curie-readonly-debug` for this cut-off task.

Do not read production/backup paths, real `.env`/`bot.env`, databases, raw logs, credentials, process environments or mount contents. Docker metadata permission does not change that. Never dump raw inspect output or environment/label collections. Keep reports free of credentials and private message content.

A backup, local commit, documentation edit or review pass never authorizes a restart or deployment. No inherited rollout/publishing permissions survive this contract. No automatic fetch/push/PR, history recovery or remote research; current work is local.

## Naming cut-off

Canonical external name: **dame-curie**. Root's intentional short URL segment **dame** remains. Use `DAME_CURIE_*` for shell/Python environment identifiers where hyphens are not valid ordinary identifiers. Neutral filenames such as `bot.env`, `.env` and `.venv` need no cosmetic rename; their roles and containing roots must be explicit.

Root-confirmed identities: **Dame Curie `1545541390392369165`** and **root / .normal.man `1482143139828596916`**. No other snowflake identifies either principal. Do not infer owner/partner trust from inherited third-party IDs.

Remote generative inference uses `OPENAI_*` and `OpenAICompatibleProvider`: **OpenAI-compatible protocol, not OpenAI's service/account or a vendor default**. Require an explicit remote endpoint/model; preserve configured hosts, keys and request behavior. Local Ollama is the separate RAG/embedding backend: keep its service/model-pull names, `OLLAMA_*` server settings and embedding keys distinct. Do not infer local generation from Ollama Cloud or wire-format references. No old remote `OLLAMA_*` aliases exist; private configuration migration must preserve unset versus explicitly blank keys.

Trace coupled image/resource selectors, custom labels, paths, database consumers and routes before changing them. No old-name fallback may silently reconnect V2 to protected V1 resources/state. Do not rename ordinary `max()`/`max_tokens`, rewrite every historical comment, invent real hostnames/mailboxes/Discord identities or change the primary persona/model as a naming shortcut. The operational source cut-off is implemented and statically reviewed; it is not evidence of provisioning, runtime isolation or deployment acceptance. Broader feature pruning still requires root's next assignment.

## Python and review discipline

Python **3.14** is mandatory. Never replace the host's system interpreter or install project dependencies into its package tree. Host project work uses an explicitly selected 3.14 venv or uv-managed environment; containers select their own project interpreter. See development docs for `.venv` versus configuration files.

Load `implement-tyranny` for authorized new Python and `implement-sanity` for review of the actual diff. Stale templates do not authorize Python 3.12, broad auto-fixing, new tooling installation or wholesale legacy conversion. Do not add unrequested helpers, blanket exception handling, type escapes, validation or logging. Legacy file/function size is not an unrelated refactoring assignment.

**No new tests**, especially tests asserting removed features/files are absent. Do not run existing tests or collection in the live environment. Any later validation needs a separately agreed source-only, synthetic/private-read-isolated environment, no real token or production mounts, and no live side effects. Existing `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas` directly reads `.env` and may call a provider; do not run it. Import-time dotenv loading is another risk. Historical suite counts are not current acceptance.

Use `read`, `glob` and `grep` tools for inspection, not shell search or ad-hoc scanners. Keep searches scoped; distinguish current observations, root statements, source intent and unknowns. Verify complete control flow before declaring a defect. Reviews must challenge the coordinator as well as the children.

## Collaboration and checkpoints

Use DeepSeek V4.1 Flash for bounded inventories and GPT-5.6 Luna at max for independent adversarial review. Every child receives the current safety boundary; runtime access remains coordinator-only unless root explicitly assigns otherwise. Give file ownership before parallel writes and preserve root's/other agents' changes.

Inspect working directory and local Git status before work. Commit coherent, source-reviewed slices locally with explicit staged paths and complete diff review. Record what was checked, what was not, deployment effects (normally none), and remaining work. Never amend/rewrite someone else's history or stage unrelated files. `docs/STATUS.md` records milestones; `phase-II_v2/` is temporary working evidence to retire when root closes the phase.
