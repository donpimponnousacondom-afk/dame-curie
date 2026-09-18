import json
import math
import os
from urllib.request import Request, urlopen

from dotenv import dotenv_values


def check_embeddings(base_url: str) -> None:
    request = Request(
        base_url + "/api/embed",
        data=json.dumps(
            {"model": "qwen3-embedding:0.6b", "input": "readiness", "keep_alive": -1}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=180) as response:
        vectors = json.load(response)["embeddings"]
    if (
        len(vectors) != 1
        or len(vectors[0]) != 1024
        or not all(
            type(value) in (int, float) and math.isfinite(value) for value in vectors[0]
        )
        or not any(vectors[0])
    ):
        raise ValueError("Ollama readiness requires one finite 1024-dimensional vector")


if __name__ == "__main__":
    enabled = dotenv_values(os.getenv("MAXWELL_ENV_FILE", "/config/bot.env")).get(
        "ENABLE_RAG"
    )
    if enabled is None:
        enabled = os.getenv("ENABLE_RAG", "auto")
    if enabled.strip().lower() not in {"0", "false", "no", "off"}:
        check_embeddings("http://ollama:11434")
