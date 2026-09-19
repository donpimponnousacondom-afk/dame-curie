# Discord-only deployment: source contract and handoff

Baseline: `43ce047`, branch `work/discord-only-deploy-20260919`. This is deployment-lane source work, not a runtime reconciliation. No private settings, mounts, account metadata, engine, service or network were accessed. Nothing was built, started, stopped, published or migrated.

## Deployment contract

- Compose defines exactly `bot`, `ollama`, and `ollama-pull`. No inbound ports, API/web service, Caddy, local site server, nested shell service or replacement server is defined.
- The app remains `python:3.14.4-slim-trixie`, target `app`. `docker/requirements.lock`, its exact pins and `--no-deps` installation are unchanged. Bot games/plugins, Chromium, Stockfish, media, TTS, ASR, tokenizers, image helpers and compatibility patches are retained. The removed FastAPI/uvicorn/Flask runtime was a separate site-runtime image, not the bot interpreter. No PHP, Perl or CGI installation was added.
- Shell executes in the bot's outer container (shell-tool implementation is a separate lane). The bot root filesystem is writable; `HOME=/home/dame-curie`, with an image symlink `/home/dame-curie -> /state/shell` preserving the shell worker's home/cwd contract and the original single persistent bind. Writes outside persistent mounts survive container restart but not recreation. No Docker CLI is copied into the app, and no engine socket, host-root mount, host networking, host PID namespace or V1 path is supplied to it. `user: 0:0` is root **inside the private rootless engine's container**, not host root. `cap_drop: ALL`, `no-new-privileges`, init, PID/memory/CPU limits and stop grace remain.
- Bot outbound traffic uses a project-scoped bridge `outbound`; Ollama is on the internal `embeddings` network. The one-shot pull job retains its separate `model-download` bridge. No host network or host port is granted. Existing Ollama image digest, embedding model, resource limits, health dependencies and readiness gate remain unchanged; preserving those definitions does not authorize running them.
- Host lifecycle still belongs to `scripts/instance.py`, run under the exact approved service account and its private rootless engine. `ENGINE_SOCKET` remains required even though it is no longer interpolated into container mounts. The wrapper supplies a clean environment, explicit UID-derived `DOCKER_HOST`, rejects identity/root/socket mismatches and non-rootless engines, and never falls back to another Docker context/engine.

### Mounts and authoring

| Host source | Container destination | Mode |
| --- | --- | --- |
| `/etc/localtime` | `/etc/dame-curie-localtime` | read-only |
| `/srv/<instance>/config` | `/config` | read-only |
| `/srv/<instance>/config/prompts` | `/config/prompts` | writable |
| `/srv/<instance>/data` | `/state/data` | writable |
| `/srv/<instance>/sites` | `/state/sites` | writable |
| `/srv/<instance>/shell` | `/state/shell` | writable |

All binds retain `create_host_path: false`. `/tmp` and `/app/temp` retain bounded writable tmpfs mounts. The bot example keeps `DATA_DIR=/state/data`, `DAME_CURIE_SITE_DIR=/state/sites`, `DAME_CURIE_SHELL_DIR=/state/shell`, and `DAME_CURIE_PROMPTS_DIR=/config/prompts`.

The entire existing authoring tree, including shared `_images`, stays under the same sites mount. No publisher path, sync configuration/template/code, remote URL selection or file replication behavior was changed. `scripts/publisher/**` is untouched. The public `DAME_CURIE_PUBLIC_BASE_URL` template now uses the existing reserved synthetic origin `https://dame-curie.example.invalid`, labeled as a remote asset origin, rather than advertising the deleted localhost server. The key/path contract and all private configured values are preserved; this is not selection of a real publication destination or permission to point at V1.

The initial `ac5f196` slice retained the startup snapshot bridge, but independent review identified its unprovisioned host-directory/listener dependency as a startup blocker. The separate follow-up removes the Compose socket export and `/srv/dame-curie-checkout/<instance>` bind, plus the socket-activation templates. No replacement host service, checkout mount or metadata bridge is introduced.

With `DAME_CURIE_STARTUP_GIT_SOCKET` unset, the existing `capture_running_build` checks for local Git and otherwise honestly reports unknown checkout commit/branch/date/subject/dirty state. Archive-built images contain no `.git`, so **`!build` checkout metadata remains unknown**; process start time and Python version remain observable. The image's OCI revision/build fields are separate operator evidence, not a live checkout snapshot, and are not substituted into that command. `response_observability.py`, the optional outbound socket client and pure CLI `scripts/checkout_snapshot.py` remain unchanged. The coordinator must remove any stale private `DAME_CURIE_STARTUP_GIT_SOCKET` value: a nonblank configured socket still selects the explicit socket path and does not fall back after a connection failure.

## Staging and lifecycle semantics

`DAME_CURIE_STAGING` is optional in `deploy.env`; omitted means `true`. Staging always applies the base file plus `docker/compose.staging.yaml`. Bot retains profile `discord-activation`; both embedding services retain `rag-activation`; staged long-running services have `restart: "no"`.

| Action | Staging true or omitted | Explicit future non-staging |
| --- | --- | --- |
| `up` / `start` | Validate account/settings/engine and inventory ownership; invoke **no Compose startup** | `compose up -d --wait --wait-timeout 300 bot`, retaining declared dependencies |
| `restart` | Validate/inventory; invoke **no Compose restart** | Restart `bot` only, never all services |
| `logs` | Existing log-format forwarding remains unchanged | Same |
| `stop` | Existing ownership-checked two-pass quiesce, including retired resources | Same |
| `down` | Quiesce; remove labeled legacy shell/site children; `compose --profile '*' down --remove-orphans --timeout 45` | Same |

There is no empty selected-service list handed to `up`/`restart`, hence no fallback to all services. The wrapper accepts no profile activation parameter and does not inherit `COMPOSE_PROFILES`. If the coordinator is separately authorized to **create stopped containers**, profiles may be selected only for that create operation; do not use a profile-enabled `up`, `start`, `restart`, `run`, or model pull during staging. No create action was added to the wrapper.

A staging flag does not stop existing containers, and a new Compose definition does not erase old resources. Returning an existing instance to staging still requires a separately authorized ownership-checked stop/down. Base-only Compose remains the intentionally active future topology; do not use it to bypass the staging gate.

`select_owned` intentionally still recognizes historical `api`/`web` Compose service labels and instance-labeled `shell`/`site` children, with the same exact checkout label validation. Removing those labels from recognition would make cleanup of the previous release fail. Orphan removal is reached only after that inventory/quiesce validation; unknown services, foreign checkouts or conflicting ownership refuse cleanup. This is not a broad prune operation.

Backup still resumes the previously running set after its snapshot, including recognized legacy containers; that pre-existing caller contract was not changed. It must **not** be used as an activation-safe cleanup/migration shortcut. Restore still requires empty roots/no owned containers and does not start services. No backup/restore was run.

## Strict deploy schema and private migration recipe

Current required literal keys:

```dotenv
INSTANCE_ID=dame-curie
INSTANCE_DIR=/srv/dame-curie
ENGINE_SOCKET=/run/user/<freshly-resolved-service-uid>/docker.sock
APP_IMAGE=dame-curie-app:<reviewed-version>
DAME_CURIE_STAGING=true
```

Angle-bracket values are documentation placeholders, not usable configuration. Future instance slugs retain the existing `dame-curie[-<identity>]` syntax, maximum 30 characters, their own same-name service account and `/srv/<instance>` root. This is not replica acceptance.

Compatibility is deliberately narrow:

1. Exactly the four current required keys, plus optional `DAME_CURIE_STAGING`, are required. Unknown/duplicate keys, shell expansion, quoting, whitespace-bearing or empty values remain errors.
2. A complete old `WEB_IMAGE` **and** `WEB_PORT` pair remains accepted to permit safe operator cleanup before private migration. The image must satisfy the old image-reference syntax; the decimal port must be 1024–65535. Only one retired key, malformed values or unrelated keys are refused.
3. Accepted retired keys are removed from `parse_settings()`'s returned mapping, so they cannot influence Compose interpolation or engine selection. They are no longer required by Compose or the public deploy example. Consumers that previously inspected returned `WEB_*` entries must stop doing so; this is an intentional schema change.
4. All account/private-root/socket/type/owner/rootless checks are still enforced by `Instance`. Legacy compatibility never chooses, substitutes or guesses an engine. Staging defaults are unchanged.

**Coordinator-only, after a separate private/runtime grant:**

1. Re-resolve the approved `dame-curie` account and its own canonical local rootless socket. Confirm exact V2 ownership and the service-readable checkout identity; do not consult or select V1 to fill gaps.
2. Keep Discord credentials blank, RAG false, model storage unwarmed and staging true. Reconcile owned obsolete resources before any future bot activation. Use the existing safe old manifest during that cleanup if needed; the new parser accepts its complete valid web pair.
3. Prepare an atomic same-owner/private-mode replacement of V2 `deploy.env`: preserve exact `INSTANCE_ID`, `INSTANCE_DIR`, `ENGINE_SOCKET`, reviewed app reference and staging value; remove `WEB_IMAGE` and `WEB_PORT` **together**. Do not print the private file or rewrite it through generic dotenv/shell expansion. The source task supplied no migration executable and touched no private file.
4. Deploy the integrated checkout/app artifact only after all shared replacement modules are included. No web image is built or selected. Do not infer that a successful staged no-op proves an image can start or that credentials/models may be enabled.
5. Runtime API/admin/CORS and nested-shell host/engine fields no longer have a consumer in the completed redesign. Their removal from private `bot.env` belongs to the coordinator's exact integrated consumer map, separate from deploy schema migration. Do not alter provider, publisher/sync or public authoring/image URL selections under this cleanup.

## Source-deleted resource inventory

These are source definitions, **not claims of runtime deletion**:

- Compose `api` service, its command and socket healthcheck; Compose `web` service, its loopback port, healthcheck and public site bind.
- Caddy/web image stage, `docker/Caddyfile` and active `examples/Caddyfile.example` inbound API/admin/site-routing example; bot copies/allowlist entries for dashboard assets and deleted API/site/X modules. `docker_runtime.py` remains in the app for shared non-orchestration path helpers. Publisher templates, including `scripts/publisher/static.htaccess`, remain untouched.
- Startup checkout bridge Compose socket export/bind and `docker/systemd/dame-curie-checkout.socket.in` / `dame-curie-checkout-worker.service.in`. Full source reads confirmed that the socket's `ListenStream`/`Accept=yes` and worker's `StandardInput=socket` exist solely to activate that bridge reader. No host listener is provisioned or replaced.
- Docker CLI image stage/copy; bot engine socket bind, `DOCKER_HOST`, daemon-host path and backend-network environment selectors.
- Nested shell image scaffold `docker/Dockerfile`.
- Local per-site Python/FastAPI/uvicorn/Flask image scaffold `docker/site-runtime/Dockerfile` and its bot build-context copy.
- Compose `frontend` and explicit `<instance>-backends` network definitions; replaced only by the bot's outbound bridge, not by another deployment service.
- Active web deployment selectors from the public deploy example; API/admin/CORS and full-host-shell fields from the bot example.
- `ecosystem.config.js`: host PM2 bot/API/Ollama/companion launch definitions retired because direct shell execution must stay inside the outer bot container.
- Installer nested/rootful Docker installation/fallback, dashboard credential wizard, local Ollama install/pull, host `run.sh`/systemd launcher generation, PM2/API startup recipes and automatic provider probes. Existing dependency installation and the discord.py-self reinstall compatibility step remain.
- Build helper automatic checkout extraction, private `APP_IMAGE` mutation, startup and running-bot inspection. `scripts/build_for_human.sh` now builds the committed app revision only, on the freshly resolved canonical private rootless engine, with fail-fast pipeline behavior; it does not deploy or activate it.

The previous V2 runtime may still own API/web/shell/site containers, old frontend/backend networks, web/shell/site-runtime/site-specific image tags and stopped app/Ollama containers. Container cleanup remains label/checkout checked. Retired network/image removal needs a separate exact-ownership inventory; the new Compose file does not declare old networks and `down` does not prune old images or delete model/state volumes. No private roots, authored sites, images, databases, model volumes, publisher state or remote resources were deleted here.

## Shared integration seams

- Web/API lane owns source deletion and narrow replacement non-serving modules. `docker_runtime.py` is intentionally retained in both explicit app COPY and allowlist: the coordinator confirmed its `container_mode`, `confined_path` and `STATE_ROOT` consumers in knowledge-graph/asset/export code. Removing an engine socket/CLI does not make those path helpers dead. The coordinator subsequently confirmed no replacement source module is needed from the web lane; its knowledge-graph path logic remains inline. Future `job_routing.py` COPY/allowlist integration belongs to the coordinator after routing lands. No shared asset helper may be dropped merely because its old filename mentioned a site.
- Shell lane owns direct command execution, cancellation, output delivery and preservation of common authorization/taint checks. Its confirmed home/cwd is `/home/dame-curie`; the image provides a symlink to the original `/state/shell` bind, not a duplicate host mount. Container filesystem writability is supplied here; no command/path allowlist was added.
- Coordinator owns final `config.py`, root `.env.example`, `doctor.py` and cross-lane removals. At baseline `doctor.py` still probes default Docker and references admin settings; `scripts/migrate_instance.py` still emits removed site-server registry/container metadata. Those require integration review, not execution. Companion/X/Telegram example fields are outside this lane's deployment-field edit.
- Logging lane owns the `scripts/instance.py` logging-format seam. Signatures, imports, `log_format` forwarding, logs dispatch and TTY/run-as handling were left intact.
- Build/app changes are an integrated-release slice, not a standalone runnable image against baseline API/site imports. The coordinator must reconcile every replacement import and COPY entry before build. Operational ledgers/docs are coordinator-owned and were not edited here.

## Validation and limits

- Read `AGENTS.md`, `REDESIGN_PLAN.md` and the four required active orientation docs fully. Loaded `implement-tyranny` and `implement-sanity`.
- Reviewed the actual owned diff and relevant lifecycle/ownership/parser control flow. Retained strict image pins, media/voice compatibility and publisher boundaries; no new helpers, try/except wrappers, tests or cases were added.
- Updated existing lifecycle/deployment fixtures narrowly: non-staging callers now state that mode explicitly, restart targets bot only, down expects orphan cleanup, and obsolete Caddy/site-runtime tests/assertions were retired. The existing legacy deploy fixture is deliberately retained to exercise old-manifest compatibility in a later authorized test run.
- Passed compile-only checks for changed `scripts/instance.py`, `tests/test_instance_ops.py` and `tests/test_docker_deployment.py` using `/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/discord-only-deploy/.validation-cache -m py_compile` with those explicit absolute files.
- Passed `bash -n` for changed `install.sh` and `scripts/build_for_human.sh`, and `git diff --check`. No JavaScript was added or modified; the PM2 definition was deleted.
- Bridge follow-up: retired only the existing mount-specific deployment test and listener-template rendering test (plus its unused `configparser` import); no replacement cases or absence assertions. Passed compile-only checks for the changed `tests/test_checkout_snapshot.py` and `tests/test_docker_deployment.py` with the same isolated interpreter/cache command, plus full follow-up diff review and `git diff --check`. CLI reader/client tests and application code were not changed or executed.
- No application imports, test collection/execution, YAML library/Compose validation, builds, installs, network calls, Docker/sudo/runtime/Screen operations, private reads or nested agents. Compile and parser checks do not establish image readiness, shell/media correctness, runtime isolation or deployment acceptance.
