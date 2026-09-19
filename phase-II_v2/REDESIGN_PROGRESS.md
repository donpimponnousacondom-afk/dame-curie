# Discord-only redesign: integration ledger

## Current checkpoint

Main integration base: `43ce047` (the new approved contract), following the staged foundation `ac38b84` / deployed code `b2f5380`. Worker commits below are **not yet integrated or deployed** at this checkpoint. Logging is integrated first; source implementation proceeds concurrently. No runtime/private configuration/Screen/Discord/model operation has been performed in this redesign round.

| Lane / owner | Worktree branch | Source checkpoint | Independent review |
| --- | --- | --- | --- |
| Screen logging — `831ab4cd-cb0c-4ab5-84a8-ca5f30e29fb9` | `work/screen-logging-20260919` | Implementation/self-review; compile-only complete; final commit pending | Pending Flash/Luna and disposable viewer acceptance |
| Direct shell/site tools — `655f422f-40fa-4b88-a70b-8153a61da08f` | `work/direct-shell-tools-20260919` | Subprocess implementation and six site-tool/exclusive-helper removals; final review pending | Pending |
| Inbound web — `27184be3-e0b3-4046-a486-36729cae5785` | `work/remove-web-api-20260919` | `d63f23c` plus bot lifecycle/control follow-up `4338499` | Flash passed both source slices |
| Deployment — `66d42e88-281a-4321-8302-dab357723bec` | `work/discord-only-deploy-20260919` | `ac5f196` | Luna review in progress (`53e1ddf9-cf6c-4106-9ab2-8b9c9b257d94`) |
| X/Telegram — `a13417fd-0aa5-4b1d-9d5c-4d4e69306ecf` | `work/remove-social-transports-20260919` | `cbea8a5` | Luna review in progress (`99ce642f-6e56-4b5d-b80a-597fa33d3824`) |
| Companion — `766b321b-a0c5-49da-a5e3-48bb726f07c5` | `work/remove-companion-20260919` | `2c3914f`, report `9e81774` | Luna source pass |
| Job routing — `9cbd56f2-80b7-41f4-ae95-681b2e29058b` | `work/job-routing-20260919` | Explicit contract selected; implementation underway | Pending |
| Command prefix / shared prompt extraction | Coordinator after integrated cuts | Read-only inventory only | Pending |

All worktrees are under `/home/codexy/deepseek/dame-curie-worktrees/`. Each worker uses absolute file paths, source-only access and its own commits. No tests are created, collected or executed. Existing fixture alignment is not a passing test result. The checked compiler is the existing isolated Python3.14.4 interpreter.

## Protected publication contract

A three-agent workflow independently mapped publication, prefixes and job/prompt consumers at `43ce047`. Publisher code has no bot import/hook: its contract is filesystem/configuration, not API serving.

- The bot's `/state/sites` maps to the same host `${INSTANCE_DIR}/sites` root. A top-level directory is a site; top-level regular files are not published.
- The `_images` archive is flat: image suffixes plus exactly stem-matched `.txt` prompt sidecars. Image/archive mirroring uses **no deletion**, unlike owned site-tree mirroring.
- Preserve `_public_image_target` / `_persist_public_image`, including redacted atomic prompt sidecars and `DAME_CURIE_PUBLIC_BASE_URL + /bot/_images` URL semantics. Retire serving tools, not these helpers.
- `scripts/publisher/` has 15 tracked files at `43ce047`; its complete Git tree is the immutable baseline for final byte-for-byte comparison. Its code, examples, systemd unit, SSH transport, guard, templates/configuration and actual remote destinations remain untouched.
- V2's remote publisher activation/destination was not established by the prior handoff. A reserved public URL example is not a working destination. Do not repoint to V1 or claim mirror acceptance.

## Cross-lane integration gates

1. No deployment before web/site/X source imports and site/shell registrations are reconciled. Individual worktrees are not standalone releases.
2. Keep `docker_runtime.py` in app COPY/allowlist for shared non-serving `container_mode`/`confined_path`/`STATE_ROOT` consumers. No bot Docker CLI/socket/host-path authority remains after the shell cut.
3. Direct shell uses explicit `/home/dame-curie` cwd and HOME, backed by the image symlink to the original `/state/shell` mount. Normalize that known workspace alias for exports while retaining dirfd/no-follow/regular-file/size and shared send-file protections. Commands themselves are not restricted to that path.
4. Mode environment flags alone do not prove a container. The shell lane is adding the requested fail-closed flag plus Docker marker tripwire for accidental host startup; the actual security boundary is the outer rootless container/account and its explicit mounts.
5. `config.py` loads dotenv with `override=True`. Coordinator must audit/remove conflicting deployment-owned values (HOME, mode/identity/socket and retired shell host fields) from private V2 configuration without dumping values or altering provider credentials/options. Compose exports cannot be assumed authoritative over that loader.
6. Existing checkout-snapshot socket was not deployed. Current source topology still mounts it and startup fails when it is missing. Resolve this without silently provisioning another service or claiming bridge readiness; preserve honest build-provenance limits.
7. Remove `doctor.py`'s retired admin-password and Docker-shell checks. Review `scripts/migrate_instance.py`'s obsolete active site-registry conversion, preserving opaque authored files and generic migration safety; do not execute a migration.
8. Deployment deletes `ecosystem.config.js`, superseding the companion-only edit. Do not run old saved PM2/GF definitions: they could consume primary token/data after persona-switch removal. V2 has never been started through PM2; V1 processes/configuration stay untouched.
9. New `job_routing.py` requires both app COPY and allowlist entries. Logging viewer modules are operator-side, not app producers.
10. Prefix pass happens after cuts: active runtime/default/help/schema/prompt/comment/docstring/documentation examples use `!`; historical evidence and punctuation are not indiscriminately rewritten. Private source-default prompts require a narrowly scoped V2-only reconciliation, not wholesale custom-persona replacement.

## Selected job contract

`spawn_background` and optional `!bg` header flags select `main`, `autonomy` or `aux`, plus an optional primary model override. No endpoint/key/header tool arguments. Ordinary free-form goals remain unchanged. Old metadata defaults to main/unset; restart cancellation remains.

Default main/no-override retains current `_generate_response` night/fallback/reasoning behavior. Explicit same-role autonomy/aux jobs require configured endpoint and model, rather than silently cascading to another role; existing memory/autonomy getters keep their old behavior. Explicit routes/model overrides own their provider lifecycle and do not mutate a shared provider. Main overrides preserve main configured fallback/vision/extra/retry/night settings. Other roles do not inherit main custom authorization headers/body or night preference. Current transport applies overrides only to primary; fallback/vision keep their configured models. Report requested versus actual model honestly.

Jobs use canonical `_get_personality` / PromptStore and the appropriate origin server prompt, not stale control-file personality. Remove `site_test` instructions; broader authoring/personality policy tuning is deferred.

## Review/acceptance limits

- Flash verified inbound API had no remaining production import consumers and that the knowledge-graph local authored-source path relocation preserves validation/confinement behavior. That seam is source-reviewed, not executed.
- Luna verified companion removal preserves primary self/bot gates, mentions/DMs/watch, owner permissions, memory, voice, autonomy and games.
- The social lane retains the legacy `tg:%` memory privacy exclusion; it is not a live Telegram transport and deleting it could expose historical private data. Existing shared taint cases were preserved from a renamed X fixture, not invented anew.
- App voice packaging remains the prior unresolved `discord-ext-voice-recv` versus `discord.py-self` distribution/transport caveat. No competing package installation or voice/Discord acceptance is authorized.
- No source review, compile check, image build or staging reconciliation authorizes bot/Ollama/model-pull activation, remote publication, V1 mutation or a real token transfer.
