# V2 Discord-only reconciliation — in progress

## Authority and current limit

Coordinator-only work under `REDESIGN_PLAN.md`, after independent source review. This record is not activation permission. No bot entrypoint, Discord/provider/model request, Ollama/model-pull start, model warm/download, V1 operation, publisher invocation or existing Screen access is permitted or performed.

**Current state: two candidate images built; isolated validation rejected the home/workspace alias, and its narrow image fix has source review. Rebuild/rerun and release/lifecycle/private-file mutation remain pending.** Old API/web are still running. Source and image evidence are not whole-bot, voice, media, RAG, provider, multi-instance or terminal acceptance.

## Fresh identity and ownership observations

Observed on 2026-09-19 during this redesign, rather than copied from the foundation ledger:

- Account `dame-curie`: UID/GID `1005`, home `/home/dame-curie`.
- Explicit client `/usr/bin/docker`; socket `/run/user/1005/docker.sock`, socket/non-symlink, owner1005, group427784, mode1660. The group is not assumed to equal the account's primary group.
- Engine ID `12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`; Docker root `/home/dame-curie/.local/share/docker`; rootless/seccomp/cgroupns reported, systemd cgroup driver.
- All daemon calls run as the freshly resolved V2 account against that explicit socket. No default/rootful/V1 fallback.
- Six containers only in the initial all-state inventory. Five Compose containers have project `dame-curie` and exact config-files label `/opt/dame-curie/compose.yaml,/opt/dame-curie/docker/compose.staging.yaml`; the separate shell has `dame-curie.instance=dame-curie`, `dame-curie.kind=shell`. No backup helper was present in that inventory.

| Container | ID prefix | Fresh state / restart | Image content ID |
| --- | --- | --- | --- |
| web | `92bf0988ad18` | running, healthy / unless-stopped | `sha256:7521271f14e8c9e6d587caa6344cb489419de71319a024631a7fa85965fd9935` |
| api | `e28a01b9c512` | running, healthy / unless-stopped | `sha256:e78fd663b29f4c8fbd5a7d98cd11c1a1af4563f3d444cb9165b2aad73cced8c9` |
| bot | `d34272f8223b` | created, zero start time / no | same old app ID above |
| shell | `f8d3f6a83167` | created, zero start time / no | `sha256:f46befbafc842c6ea8f91c9678db694ca0bf308d75c357954f079129d07ac0c3` |
| ollama | `45b214b2ebf1` | created, zero start time / no | `sha256:2a5d0462221131b2313d838e99c30cf4190a5207236f065b246acd11ae718e85` |
| ollama-pull | `23c9f50fc575` | created, zero start time / no | same Ollama ID above |

The old app/web tags are `dame-curie-app:b2f5380` and `dame-curie-web:b2f5380`. The pinned Ollama reference is `ollama/ollama:0.33.3@sha256:32931b46719f673c05fdbaa81ccb26da18ea4a1c57590a754874ab28ba269eb2`. Never-started metadata is not a fresh inspection of model-volume contents; those contents have not been read in this redesign.

## Sanitized private structural audit — read-only

The existing operator venv is Python3.14.4 and has no python-dotenv package. No package was installed. The coordinator used the already approved tool venv/parser, loaded the reviewed pure deployment parser and extracted the public default personality as AST data, then dropped supplementary groups and UID/GID to1005 **before** private-file or engine I/O. No application modules, tests, database/model contents or raw logs were loaded. Only allowlisted booleans and ownership/mode metadata were emitted; no configuration values, prompt text or credential material were emitted or modified.

- `/srv/dame-curie`, `config`, `data`, `sites`, `shell`, `config/prompts`: non-redirected, owner/group1005, mode0700.
- `deploy.env`, `config/bot.env`, `data/bot_control.json`, `config/prompts/personality.txt`, `config/prompts/servers.json`: regular, non-redirected, owner/group1005, mode0600.
- Reviewed `parse_settings()` accepts existing private deployment selectors. Identity/root/socket match current account metadata, staging is true, and the complete valid legacy WEB selector pair is present.
- Main/GF/OAuth Discord fields checked are blank or unset. `ENABLE_RAG` and `ENABLE_AUTONOMY` explicitly false; REM disabled. Bot control is explicitly false. The autonomy control was not literally false in this first check; absence versus an explicit value remains to be distinguished, rather than inferred as enabled.
- Container mode and data/site/shell/prompt roots are canonical. HOME, env-file selector and instance-ID overrides are absent. Startup bridge socket key is absent.
- Known retired keys present: FULL_HOST, admin user/password, API host/port, CORS origin, ENABLE_X and ENABLE_TELEGRAM. Their narrow removal is pending; unconsumed secrets still matter because dotenv and shell inherit the environment.
- `COMMAND_PREFIX` is absent: retain absence and use the new `!` source default.
- Raw personality text does not exactly equal the current source literal; storage framing/prior-default provenance has not yet been resolved. Do not infer customization or rewrite it from that result. Server prompt mapping is empty. Provider values/unset-vs-blank and publisher configuration remain unchanged.

## Candidate image build

Independent Luna source review passed production integration at `9d1abc8` and residual template/dashboard/PM2 cleanup through `a913437`. Frozen public Git archive:

- SHA `a913437e927106d8048caabd3eb1ee41b3f30fec`.
- Tag `dame-curie-app:a913437`.
- Build-reported content ID `sha256:dca68cf71d748bd4ea73c97b4b3c0e290f522024e404e4adb41601871c83aea6` (scalar image reinspection still pending).
- Resolved Python base `python:3.14.4-slim-trixie@sha256:2ca02f32b4d9d893863367ce07ec1972819f476dd38d8612f2a9cb6a41cbb727`.
- `docker/app.Dockerfile`, target `app`, pinned `docker/requirements.lock`, explicit source metadata build arguments; public archive only, no private context/mounts. The uncommitted acceptance report was explicitly excluded. `dirty=false` describes that immutable archive, not an assertion that the working checkout was clean.

First attempt (`bash-514`) failed before building: `DOCKER_CONFIG=/nonexistent` allowed read-only metadata queries but could not hold builder state (`mkdir /nonexistent: permission denied`). This was an ordinary client-filesystem failure, not an engine fallback or sandbox escalation. Retry (`bash-515`) used a newly created0700 V2-owned temporary Docker client directory, explicit DOCKER_HOST plus `--host`, and the same freshly verified engine. It completed with exit0; the exact temporary directory was cleaned on exit. Both background jobs were collected. No existing Docker client configuration was used for that build.

The image is not deployed and no container from it has started. A final existing-fixture alignment followed the artifact freeze; source release selection must be explicitly finalized rather than silently claiming this image represents later commits. Image ID and resolved base are evidence; a Git SHA plus mutable base tag/apt repositories alone does not prove reproducible image contents. No dependency pins were relaxed, no PHP/Perl/CGI installation was added, and the known voice distribution compatibility caveat remains unresolved.

## Second candidate and a real image defect

The three existing-fixture alignments passed independent Luna source review and explicit Python3.14.4 compilation, without new tests or execution. They and the checkpoint reports landed in `b165c3ead87d12eab454bb42f2bfe0857f3ce947`. A second frozen build (`bash-518`, collected exit0) reused reviewed layers and produced `dame-curie-app:b165c3e`, ID `sha256:38ebb8c2a85352c030230eace44ab474e462e51c4017e62e68251b2aa5ca263d`. Scalar image inspection confirmed that ID/revision, USER0:0, `/app` working directory and normal `python bot.py` command. The pinned Ollama image remains locally available. `/opt/dame-curie` and its venv are ordinary root-owned0755 directories on the same device; neither has been changed.

Three short-lived neutral-name `--rm` containers ran **only explicit Python standard-library/Bash commands**, with entrypoint override, network none, read-only image, all capabilities dropped, no-new-privileges,128MiB/32-PID bounds and no private mounts. The first two supplied a small synthetic `/state/shell` tmpfs. No bot/application import, normal entrypoint, health/provider/Discord probe, model, publisher or private-data operation occurred.

- The first probe exited1 while reading its synthetic output file, before emitting its result. Bash had returned0 because its later diagnostic commands succeeded; that was not shell-write success.
- Follow-up captured the actual cause: `/state/shell` is UID0/mode0700, but `/home/dame-curie` is a separate0755 directory. Bash HOME and physical cwd both remained `/home/dame-curie`, and the write failed with a read-only-filesystem error.
- A third image-only metadata check confirmed `/home/dame-curie/shell` is the symlink to `/state/shell`, while `/home/dame-curie` itself is not a symlink. Thus the build's plain `ln -s` silently nested its link inside a pre-existing HOME directory. This would put ordinary writable-container shell output outside the intended persistent workspace and break the export alias assumption.

**The image is not accepted for cutover.** The source correction removes HOME from the pre-dependency ENV, uses `ln -sT` so an occupied target fails rather than nesting, and sets the same runtime HOME only after alias creation. Luna passed that exact diff; dependency pins, final HOME, outer-container execution and workspace paths are unchanged. The fix must be committed into a new frozen archive, rebuilt and rerun before any source/lifecycle cutover. The failed probes do not demonstrate shell-tool, package or application acceptance. No failed candidate was selected in private deploy.env.

Host coreutils help separately confirmed `mv --exchange --no-copy -T` and `ln -sT` support for the later clean release replacement/construction; no exchange has occurred yet.

## Reviewed next sequence

1. Freeze the final reviewed release SHA; bind archive, source checkout and exact built image to it. Optional validation stays stdlib/Bash-only, network-none, neutral `--rm` container name, no private mounts and no bot entrypoint.
2. Stage a clean root-owned/service-readable archive beside `/opt/dame-curie`, preserve the existing operator venv at its canonical final path, and atomically replace the release. Never overlay-extract or execute install.sh.
3. Re-resolve account/socket/engine; recheck deployment identity/staging, exact Compose config-file labels, private ownership/paths, image availability and unexpected helper/resource gates. Parser/ownership mismatch stops work; do not rewrite around a mismatch or fall back to broad raw deletion.
4. Use the reviewed canonical wrapper `down` with the still-valid legacy deploy file: all-profile remove-orphans, bounded stop, no volume removal/prune. It recognizes old API/web and managed shell/site ownership specifically for this cleanup.
5. Narrow, atomic private migration: remove complete WEB pair and reviewed retired bot-env keys; retain staging and provider/publisher bytes/semantics. Preserve unset prefix and unproven/custom prompt content.
6. Direct stopped creation must reproduce wrapper context because it has no `create` action: exact account/socket, clean environment, `--env-file /dev/null`, canonical project/directory/base+staging files, explicit discord/rag profiles, **only bot/ollama/ollama-pull**, no build/pull/start.
7. Inspect allowlisted state/restart/image/port/mount/ownership gates, then verify staged wrapper `up` starts nothing. Never dump inspect/env/label/mount collections.

Leave old images, model/state volumes and undeclared old networks alone; `down` is not a purge and no broad pruning is authorized. Publisher/syncer and protected V1 remain untouched. Final evidence must distinguish these deployment gates from unperformed application, voice, RAG, provider, publication and terminal acceptance.
