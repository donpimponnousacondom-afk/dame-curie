# Dirac shared embedding deployment — source evidence

Lane `dirac-shared-rag`, worktree `/home/codexy/deepseek/dame-curie-worktrees/dirac-shared-rag`,
branch `work/dirac-shared-rag`, base `7b4398c`. This is source and synthetic evidence
only. Nothing here is a runtime result: no container was started, no engine was contacted,
no application module was imported and no test was executed in this lane.

## Defect this lane fixes

`compose.yaml` hard-wires one embedding deployment: `bot` depends on a healthy local
`ollama`, which depends on the one-shot `ollama-pull`, and the readiness gate in
`docker/check_embeddings.py` ignores configuration entirely — it always posts to
`http://ollama:11434` for the hardcoded model `qwen3-embedding:0.6b` and requires exactly
1024 dimensions. `config.py` had already made `DAME_CURIE_EMBED_BASE_URL`,
`DAME_CURIE_EMBED_MODEL`, `DAME_CURIE_EMBED_DIM` and `DAME_CURIE_EMBED_API_KEY` tunable,
so the deployment could start a private Ollama, a one-shot model pull and a readiness gate
that all disagreed with the endpoint the bot would actually call.

The intended Dirac deployment reuses the existing V1 Ollama embedding API with isolated V2
data and no duplicate model, which that topology cannot express.

## Interface

`deploy.env` gains one optional literal setting:

| Setting | Values | Default | Meaning |
| --- | --- | --- | --- |
| `DAME_CURIE_EMBED_MODE` | `local`, `external` | `local` | `local` keeps this project's own Ollama; `external` embeds through a configured endpoint and starts no local model service. |

`DAME_CURIE_STAGING` keeps its existing meaning, including that the wrapper still turns
`up`/`start`/`restart` into validated no-ops. An unknown or absent value is rejected /
defaulted exactly as before, and an existing private `deploy.env` without the new key stays
valid.

### File selection

`scripts/instance.py` derives the file list from one helper, `compose_files(staging, mode)`,
and passes those files to `docker compose -f ...` in that order:

| `DAME_CURIE_STAGING` | `DAME_CURIE_EMBED_MODE` | Compose files |
| --- | --- | --- |
| `true` (default) | `local` (default) | `compose.yaml`, `docker/compose.staging.yaml` |
| `false` | `local` | `compose.yaml` |
| `true` | `external` | `compose.yaml`, `docker/compose.staging.yaml`, `docker/compose.embeddings-external.yaml` |
| `false` | `external` | `compose.yaml`, `docker/compose.embeddings-external.yaml` |

Two rows are exactly what the wrapper selected before this change, and `compose.yaml` plus
`docker/compose.staging.yaml` are unchanged by it.

Ownership provenance is derived from the same helper: `owned_config_files()` builds the four
exact `com.docker.compose.project.config_files` strings this checkout can produce, and
`select_owned()` accepts only those. A container whose label names any other checkout, or an
individual overlay without the base file, is still rejected. Keeping the accepted set wider
than one instance's current mode is deliberate: a mode or staging flip must not make
previously created containers look like foreign resources to `stop`/`down`/`backup`.

### External overlay

`docker/compose.embeddings-external.yaml` is additive only:

* `bot.depends_on: !reset []` — Compose refuses a dependency on a service disabled by the
  active profiles, so the local health dependency has to be removed, not merely hidden.
* `ollama`, `ollama-pull` → `profiles: !override [local-embeddings]` — neither service
  starts by default, including on a bare `docker compose up`, and `!override` also replaces
  the staged overlay's `rag-activation` profile so no profile can start a local model
  service in this mode.
* `bot.environment.DAME_CURIE_EMBED_MODE: external` and
  `DAME_CURIE_EMBED_BASE_URL: !reset null` — the base file's local service URL is cleared so
  it cannot be mistaken for a shared endpoint; the endpoint must come from the private
  `bot.env`.

These tags require Docker Compose **2.28.1** or newer: `!reset`/`!override` exist since 2.24,
and resetting `depends_on` specifically was only fixed in 2.28.1 (docker/compose#11980). The
coordinator reported the V2 engine's Compose as **2.39.4**, which satisfies that. An older
Compose would reject the overlay, affecting the external deployment only.

### Local embedding metadata in the base file

`compose.yaml` now injects two non-secret values into the bot environment:
`DAME_CURIE_EMBED_MODE: local` and `DAME_CURIE_EMBED_BASE_URL: http://ollama:11434`. A value
in `bot.env` still wins over both, because `config.py` loads that file with `override=True`.
This is what lets the readiness gate resolve the endpoint with the same precedence the bot
uses, including for a bare host install where the `config.py` default
(`http://localhost:11434`) is the correct one.

## Readiness

`docker/check_embeddings.py` resolves the effective settings the way `config.py` does,
without importing the application, and probes exactly the backend the bot will call:

| Setting | Resolution |
| --- | --- |
| `ENABLE_RAG` | `config._feature_env` semantics: only `0`/`false`/`no`/`off` (case-insensitive) disable it. Unset, blank and unrecognized values stay enabled, and a disabled value performs no HTTP at all. |
| endpoint | `DAME_CURIE_EMBED_BASE_URL` then `EMBED_BASE_URL`; the selected dotenv file wins over the process environment, blank values fall through, and the fallback default is `config.py`'s `http://localhost:11434`. A bare `KEY` line carries no value and leaves the inherited value in place; `KEY=` is an explicit blank. |
| model | `DAME_CURIE_EMBED_MODEL` then `EMBED_MODEL`, default `qwen3-embedding:0.6b`. |
| dimensions | `DAME_CURIE_EMBED_DIM`, unparsable/blank → `1024`, clamped to `8..16384`. |
| auth | `DAME_CURIE_EMBED_API_KEY` then `EMBED_API_KEY`; sent only as `Authorization: Bearer …` when non-blank. |

Local and external modes resolve the endpoint identically, so a private file that points the
bot somewhere else also moves the probe. The two modes differ only in the request shape:

* local: unchanged pre-existing probe — `{"model", "input", "keep_alive": -1}`, which also
  keeps the just-pulled model resident;
* external: the shape `rag_memory` itself sends — `{"model", "input"}` plus
  `"truncate": false` for an `/api/embed` URL, and no Ollama-only `keep_alive` on someone
  else's service.

Endpoint form mirrors `rag_memory._embed_endpoint`: a full `/api/embed` or `/embeddings` URL
is used as-is, a `/v1` base becomes `/v1/embeddings`, anything else is treated as an Ollama
host. Response parsing accepts `{"embeddings": [[…]]}`, `{"embedding": […]}`, and
`{"data": [{"embedding": […], …}]}`, and then requires exactly one finite, nonzero numeric
vector of the configured length. No vendor or model is inferred from the URL. In `external`
mode without any configured endpoint the gate fails closed with
`external embedding mode requires DAME_CURIE_EMBED_BASE_URL` instead of guessing.

The deployment mode is Compose-injected structural metadata: it is read from the process
environment only, and the private dotenv file cannot flip it, because this gate uses
`dotenv_values()` and never mutates the process environment.

Nothing is printed on success, and no endpoint, model, vector or credential is printed on
failure. The gate still fails closed: a non-zero exit keeps the Compose entrypoint from
`exec`-ing the bot.

## What the coordinator must set for shared V1 embeddings

1. `deploy.env`: `DAME_CURIE_EMBED_MODE=external` (keep `DAME_CURIE_STAGING` as required for
   the current hold).
2. Private `bot.env`: `DAME_CURIE_EMBED_BASE_URL=<the reachable V1 Ollama URL the
   coordinator provides>`, and `DAME_CURIE_EMBED_MODEL`/`DAME_CURIE_EMBED_DIM` matching that
   model, plus `DAME_CURIE_EMBED_API_KEY` only if it needs one. `ENABLE_RAG=true`, or blank
   or unset, enables RAG; `ENABLE_RAG=false` makes the startup probe a no-op.
3. Confirm Compose ≥ 2.28.1 on the V2 engine before the first `external` run.

No local Ollama container, no model pull, no V1 state, database or secret is mounted or
read by this lane. V2 RAG data stays in the instance's own data root. The overlay adds no
network, `extra_hosts` entry or port: reachability of the shared endpoint is a deployment
input, not something this source guesses at. The coordinator reports the V1 shared Ollama as
a separate healthy container and owns its networking, so the only V2-side requirement is a
reachable URL in the private configuration above.

## Checks actually run in this lane

* `ast.parse` of `docker/check_embeddings.py`, `scripts/instance.py`,
  `tests/test_docker_readiness.py`, `tests/test_shared_embeddings_deployment.py` under the
  parent checkout's Python 3.14 venv interpreter. Syntax only; no import.
* A structural YAML parse of `compose.yaml`, `docker/compose.staging.yaml` and
  `docker/compose.embeddings-external.yaml` with a tag-aware reader, confirming the three
  service names and that `!reset`/`!override` appear on exactly `bot.depends_on`,
  `bot.environment.DAME_CURIE_EMBED_BASE_URL` and the two `profiles` keys.
* `git diff` review of the whole change, including a re-read of the final file contents.

Not run: `docker compose config`, any container or engine command, any test collection or
execution, any application import, and any network call. The readiness behaviour below the
syntax level is exercised only by the synthetic tests added here, which the coordinator can
run under an isolated environment.

## Limits and open items

* The `!reset`/`!override` merge result is asserted declaratively (the tags are present on
  the right keys), not by a real Compose merge. Only the coordinator can run
  `docker compose config` and prove the merged model on the actual engine and version.
* `DEFAULT_BASE_URL`, `DEFAULT_MODEL` and `DEFAULT_DIMENSION` deliberately duplicate
  `config.py`'s defaults because the gate must not import the application; a future default
  change in `config.py` has to be mirrored here.
* Local mode's private `bot.env` should keep `DAME_CURIE_EMBED_MODEL`/`DAME_CURIE_EMBED_DIM`
  matching the model `compose.yaml` pulls and health-checks. A divergence now fails the
  readiness gate — which is honest, but it is a new fail-closed path for a previously
  silently degraded configuration.
* The readiness gate verifies one synthetic vector request. It cannot prove RAG storage,
  retrieval, REM or long-run embedding health.
* No claim is made about any deployed Dirac resource, image, private configuration or
  Compose version. Feature flags, private keys and the temporary Dirac identity remain the
  coordinator's runtime lane.
