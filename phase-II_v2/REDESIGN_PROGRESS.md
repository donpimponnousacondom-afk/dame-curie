# Discord-only redesign: integration ledger

## Current checkpoint

Main integration base: `43ce047` (the new approved contract), following the staged foundation `ac38b84` / deployed code `b2f5380`. Worker commits below are **not yet integrated or deployed** at this checkpoint. Logging is integrated first; source implementation proceeds concurrently. No runtime/private configuration/Screen/Discord/model operation has been performed in this redesign round.

| Lane / owner | Worktree branch | Source checkpoint | Independent review |
| --- | --- | --- | --- |
| Screen logging — `831ab4cd-cb0c-4ab5-84a8-ca5f30e29fb9` | `work/screen-logging-20260919` | `266ef2c`, `a559f09`, signal/pipe-exit fix `bb5184a` | Flash semantics/CLI pass; Luna passed exact fixes through `bb5184a`; no terminal acceptance |
| Direct shell/site tools — `655f422f-40fa-4b88-a70b-8153a61da08f` | `work/direct-shell-tools-20260919` | `700cece`, DEVNULL/comment follow-up `e53aece` | Luna passed mechanics and follow-up; shared imports/routing require integration |
| Inbound web — `27184be3-e0b3-4046-a486-36729cae5785` | `work/remove-web-api-20260919` | `d63f23c`, `4338499`, CAPTCHA cut `a54c5d5`, doctor/migration cut `aa4b65c`, dashboard IPC cut `598bc66` | Flash passed first two; Luna passed all three follow-ups |
| Deployment — `66d42e88-281a-4321-8302-dab357723bec` | `work/discord-only-deploy-20260919` | `ac5f196`, bridge/Caddy-example retirement `afa9eb5` | Luna passed topology and follow-up; cross-lane/private acceptance gates remain |
| X/Telegram — `a13417fd-0aa5-4b1d-9d5c-4d4e69306ecf` | `work/remove-social-transports-20260919` | `cbea8a5` | Luna source pass; no media/memory runtime acceptance |
| Companion — `766b321b-a0c5-49da-a5e3-48bb726f07c5` | `work/remove-companion-20260919` | `2c3914f`, report `9e81774` | Luna source pass |
| Job routing — `9cbd56f2-80b7-41f4-ae95-681b2e29058b` | `work/job-routing-20260919` | `c1ec088`, quote-aware parser/wording fix `2aee86b` | Luna re-review pending (`1b1c5eec-c056-44fe-8662-83c9d7b59c10`) |
| Active documentation/prefix — `b3e4b8c5-6247-40dc-b0e2-2162b55b89a5` | `work/discord-only-docs-20260919` | Reconcile active docs; preserve historical evidence and parent ledgers | Pending |
| Source command prefix / shared prompt extraction | Coordinator after integrated cuts | Read-only inventory only | Pending |

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
6. `afa9eb5` removes the unprovisioned checkout-snapshot mount/export and its listener unit templates; no replacement service. Existing CLI/client remain, with honest unknown checkout metadata in archive images. Coordinator must also remove any nonblank private `DAME_CURIE_STARTUP_GIT_SOCKET`; otherwise the optional client still attempts the missing socket. OCI revision is separate operator evidence, not running-checkout proof.
7. `aa4b65c` removes `doctor.py`'s retired admin-password/Docker-shell checks and the migration's active site-registry retarget/schema/running-app conversion. Opaque registry/authored files and generic safety/prompt/copy checks remain. Compilation is not migration acceptance; never execute a migration for this redesign.
8. Deployment deletes `ecosystem.config.js`, superseding the companion-only edit. Do not run old saved PM2/GF definitions: they could consume primary token/data after persona-switch removal. V2 has never been started through PM2; V1 processes/configuration stay untouched.
9. New `job_routing.py` requires both app COPY and allowlist entries. Logging viewer modules are operator-side, not app producers.
10. Prefix pass happens after cuts: active runtime/default/help/schema/prompt/comment/docstring/documentation examples use `!`; historical evidence and punctuation are not indiscriminately rewritten. Private source-default prompts require a narrowly scoped V2-only reconciliation, not wholesale custom-persona replacement.
11. Coordinator removes `SITE_READ_LOOP_MARKER` from the bot import and its two obsolete routing guards. No shim for deleted site-test repeat machinery. Reconcile remaining active site-result/catalog/prompt references against the shell/web/job cuts, not historical parser data.
12. The additional on-by-default, on-demand `HumanCaptchaServer` listener is retired in `a54c5d5`, without replacement. Outbound CapSolver/TwoCaptcha and normal Discord administration/onboarding remain. This rests on active `TCPSite`/caller evidence and the no-local-server contract, not any supposed external proxy path.
13. `598bc66` removes the dashboard-exclusive `discord_state.json` export and `bot_commands.json` queue after producer/consumer tracing. Control reload, PromptStore, actual Discord reply queue, watermarks, inbox/notifications, incidents/traces, plugins and memory remain. Native presence/activity tools and `clearmem` survive; exact action-name greps alone did not establish capability coverage.
14. Private acceptance also verifies canonical `DAME_CURIE_SHELL_DIR=/state/shell`, required `config/prompts`, exact V2 `APP_IMAGE`/reviewed revision, and independent public-URL/destination isolation. A placeholder is not publication readiness. No PM2/GF cleanup is authorized on V1.

## Selected job contract

`spawn_background` and optional `!bg` header flags select `main`, `autonomy` or `aux`, plus an optional primary model override. No endpoint/key/header tool arguments. Ordinary free-form goals remain unchanged. Old metadata defaults to main/unset; restart cancellation remains.

Default main/no-override retains current `_generate_response` night/fallback/reasoning behavior. Explicit same-role autonomy/aux jobs require configured endpoint and model, rather than silently cascading to another role; existing memory/autonomy getters keep their old behavior. Explicit routes/model overrides own their provider lifecycle and do not mutate a shared provider. Main overrides preserve main configured fallback/vision/extra/retry/night settings. Other roles do not inherit main custom authorization headers/body or night preference. Current transport applies overrides only to primary; fallback/vision keep their configured models. Report requested versus actual model honestly.

Jobs use canonical `_get_personality` / PromptStore and the appropriate origin server prompt, not stale control-file personality. Remove `site_test` instructions; broader authoring/personality policy tuning is deferred.

Luna caught a quoted `--` header-separator bug; `2aee86b` consumes only the bounded shlex header and leaves goal prose untouched. Operator wording no longer suggests vision routing in text-only/nonmain jobs. The coordinator initially proposed extending live reasoning control by rewriting a new clone's primary model, then retracted that before any code edits: the existing transport deliberately confines that control to the configured primary model. The main model-specific reasoning boundary and its existing fixture remain unchanged. Owned-provider close-error/repeated-cancellation behavior is an explicit unexecuted edge, not hidden by blanket catches.

## Logging review gates

- Flash passed additive CLI/source selection and the approved keys, semantic rows, folding, history and correlation contract. The 500-record/2 MiB shared ring is the approved plan, not a deviation from the reference's 200/50 counts.
- Parent/Luna found a real owned-process-group leak: waiting for the leader could report success while a same-group child ignored TERM. `a559f09` reserves the PID with `WNOWAIT`, sends group KILL before reaping, then boundedly checks disappearance. No mutating signal follows reap. Actual latency is not measured.
- `bb5184a` implements the two further gates: an outer signal lease spans terminal restoration and group cleanup; exited leaders trigger bounded drain even while a child holds the pipe, with explicit incomplete status. Luna passed the exact follow-up diff with no remaining source blocker; implementation/source review is not terminal acceptance.
- Long OSC/DCS/C1 termination handling is safely fail-closed but needs disposable acceptance. Resume-after-rejected-catch-up differs deliberately from transactional pinned paging and must be exercised under pressure. Legacy modes remain unchanged.
- The duplicate `log_filter` module identity is currently constant-only, not a demonstrated behavioral defect; no unrelated legacy refactor. Raising a cleanup exception during unwinding retains Python's implicit exception context; a claim of no chaining was not accepted.

## Review/acceptance limits

- Flash verified inbound API had no remaining production import consumers and that the knowledge-graph local authored-source path relocation preserves validation/confinement behavior. Luna passed CAPTCHA, doctor/migration, dashboard file-IPC and bridge follow-ups. These seams are source-reviewed, not executed.
- One scout cited an unassigned archived README despite its scope boundary. The citation was withdrawn, no further archive reads were authorized, and the coordinator discarded the external-proxy inference. Active listener/caller evidence independently establishes the CAPTCHA cut; no claim about an external route is accepted.
- Luna verified companion removal preserves primary self/bot gates, mentions/DMs/watch, owner permissions, memory, voice, autonomy and games.
- The social lane retains the legacy `tg:%` memory privacy exclusion; it is not a live Telegram transport and deleting it could expose historical private data. Existing shared taint cases were preserved from a renamed X fixture, not invented anew.
- App voice packaging remains the prior unresolved `discord-ext-voice-recv` versus `discord.py-self` distribution/transport caveat. No competing package installation or voice/Discord acceptance is authorized.
- No source review, compile check, image build or staging reconciliation authorizes bot/Ollama/model-pull activation, remote publication, V1 mutation or a real token transfer.
