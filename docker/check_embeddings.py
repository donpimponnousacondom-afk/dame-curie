"""Fail-closed readiness gate for the configured embedding backend.

Compose runs this before the bot is exec'd so an unusable embedding backend is
not mistaken for working RAG. It resolves the same effective configuration as
config.py -- the selected dotenv file loaded over the process environment --
without importing the application, and it never prints credentials, the
resolved endpoint or response contents.

The effective endpoint, model, dimension and auth resolve the way config.py
resolves them for the bot -- dotenv file over process environment, then the
same defaults -- because probing a different endpoint than the one the bot will
call would preserve the bug this gate exists to catch. Local and external
deployments resolve identically; only the request shape differs.

The endpoint-form and response-shape rules deliberately mirror
rag_memory._embed_endpoint and its Ollama/OpenAI response parsing. They are
duplicated because this gate must stay importable with the stdlib plus dotenv,
and it must not import the application's dependencies.
"""

import json
import math
import os
from urllib.request import Request, urlopen

from dotenv import dotenv_values

# Compose injects this project's own Ollama URL for the local deployment; a
# value in the selected dotenv file still wins, as it does for the application.
# The three defaults below mirror config.py.
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3-embedding:0.6b"
DEFAULT_DIMENSION = 1024
MIN_DIMENSION = 8
MAX_DIMENSION = 16384
DISABLED = {"0", "false", "no", "off"}
BASE_URL_KEYS = ("DAME_CURIE_EMBED_BASE_URL", "EMBED_BASE_URL")
MODEL_KEYS = ("DAME_CURIE_EMBED_MODEL", "EMBED_MODEL")
API_KEY_KEYS = ("DAME_CURIE_EMBED_API_KEY", "EMBED_API_KEY")


def effective_environment(path: str) -> dict[str, str]:
    """Merge the deployment's dotenv file over the process environment.

    config.py loads that file with override=True, so a key declared in the file
    wins even when the container environment defines the same key. Mirroring
    python-dotenv there: a bare ``KEY`` line carries no value and leaves the
    inherited value alone, while an explicitly blank ``KEY=`` wins as a blank,
    which the readers below treat as unset -- the way config._first_env skips
    blank values. A missing file contributes nothing.
    """
    merged = dict(os.environ)
    for name, value in dotenv_values(path).items():
        if value is not None:
            merged[name] = value
    return merged


def first_setting(
    environment: dict[str, str], names: tuple[str, ...], default: str = ""
) -> str:
    """First non-blank value among ``names``, mirroring config._first_env."""
    for name in names:
        value = environment.get(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def rag_enabled(environment: dict[str, str]) -> bool:
    """Resolve ENABLE_RAG the way config._feature_env does.

    Only an explicit false-ish value disables RAG; unset, blank and unrecognized
    values keep the feature enabled, matching its default-on tri-state.
    """
    return environment.get("ENABLE_RAG", "").strip().lower() not in DISABLED


def embedding_dimension(environment: dict[str, str]) -> int:
    """Resolve EMBED_DIM the way config._int_env does: fall back, then clamp."""
    try:
        value = int(environment.get("DAME_CURIE_EMBED_DIM", str(DEFAULT_DIMENSION)))
    except (TypeError, ValueError):
        value = DEFAULT_DIMENSION
    return max(MIN_DIMENSION, min(MAX_DIMENSION, value))


def embedding_endpoint(base_url: str) -> str:
    """Resolve a base URL to its request URL, as rag_memory._embed_endpoint does.

    A full endpoint is used as-is, an OpenAI-style ``/v1`` base becomes
    ``/v1/embeddings``, and anything else is treated as an Ollama host. No
    vendor or model is inferred from the URL.
    """
    base = (base_url or "").strip().rstrip("/")
    if base.endswith(("/api/embed", "/embeddings")):
        return base
    if base.endswith("/v1") or "/v1/" in base:
        return f"{base}/embeddings"
    return f"{base}/api/embed"


def extract_vectors(payload: object) -> list:
    """Pull vectors out of an Ollama or OpenAI-compatible embeddings response.

    Ollama answers ``{"embeddings": [[...]]}`` (or ``{"embedding": [...]}``),
    OpenAI-compatible services answer ``{"data": [{"embedding": [...]}]}``.
    Batch index ordering is not checked because the probe sends one input.
    """
    if not isinstance(payload, dict):
        return []
    vectors = payload.get("embeddings")
    if isinstance(vectors, list) and vectors:
        return vectors
    single = payload.get("embedding")
    if isinstance(single, list) and single:
        return [single]
    items = payload.get("data")
    if (
        isinstance(items, list)
        and items
        and all(
            isinstance(item, dict) and isinstance(item.get("embedding"), list)
            for item in items
        )
    ):
        return [item["embedding"] for item in items]
    return []


def check_embeddings(
    base_url: str, model: str, dimension: int, api_key: str = "", *, warm: bool = False
) -> None:
    """Require one finite, nonzero numeric vector of exactly ``dimension`` length.

    ``warm`` is the local deployment's unchanged probe: against this project's
    own Ollama it also asks for the just-pulled model to stay resident. Ollama's
    native fields are only ever added to the ``/api/embed`` form, so a
    compatible ``/v1/embeddings`` service receives exactly what rag_memory
    sends it.
    """
    url = embedding_endpoint(base_url)
    payload: dict[str, object] = {"model": model, "input": "readiness"}
    if url.endswith("/api/embed"):
        if warm:
            payload["keep_alive"] = -1
        else:
            payload["truncate"] = False
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urlopen(request, timeout=180) as response:
        vectors = extract_vectors(json.load(response))
    if len(vectors) != 1:
        raise ValueError(f"readiness requires exactly one {dimension}-dimensional vector")
    vector = vectors[0]
    if (
        not isinstance(vector, list)
        or len(vector) != dimension
        or not all(
            type(value) in (int, float) and math.isfinite(value) for value in vector
        )
        or not any(vector)
    ):
        raise ValueError(
            f"readiness requires one finite nonzero {dimension}-dimensional vector"
        )


def main() -> None:
    """Probe the endpoint this deployment actually uses, or skip when RAG is off."""
    environment = effective_environment(
        os.getenv("DAME_CURIE_ENV_FILE", "/config/bot.env")
    )
    if not rag_enabled(environment):
        return
    model = first_setting(environment, MODEL_KEYS, DEFAULT_MODEL)
    dimension = embedding_dimension(environment)
    api_key = first_setting(environment, API_KEY_KEYS)
    external = os.getenv("DAME_CURIE_EMBED_MODE", "local").strip().lower() == "external"
    base_url = first_setting(environment, BASE_URL_KEYS)
    if external and not base_url:
        raise ValueError("external embedding mode requires DAME_CURIE_EMBED_BASE_URL")
    check_embeddings(
        base_url or DEFAULT_BASE_URL, model, dimension, api_key, warm=not external
    )


if __name__ == "__main__":
    main()
