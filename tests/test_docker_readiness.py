import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from unittest.mock import Mock

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "docker/check_embeddings.py"


@pytest.fixture
def embeddings_server():
    state = {"vectors": [[0.25] * 1024], "status": 200, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(
                (
                    self.path,
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            assert "Authorization" not in self.headers
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"embeddings": state["vectors"]}).encode())

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", state
        finally:
            server.shutdown()
            thread.join()


def test_readiness_requires_real_embedding_without_api_credentials(embeddings_server):
    url, state = embeddings_server
    runpy.run_path(str(CHECKER))["check_embeddings"](url)
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness", "keep_alive": -1},
        )
    ]


@pytest.mark.parametrize(
    "vectors",
    [
        [],
        [[1] * 768],
        [[1] * 1024] * 2,
        [[float("nan")] * 1024],
        [[0] * 1024],
        [[True] * 1024],
        [[0.25] * 1023 + [True]],
        [["0.25"] * 1024],
    ],
)
def test_readiness_rejects_unusable_embeddings(embeddings_server, vectors):
    url, state = embeddings_server
    state["vectors"] = vectors
    with pytest.raises(ValueError, match="1024-dimensional"):
        runpy.run_path(str(CHECKER))["check_embeddings"](url)


def test_readiness_fails_closed_on_ollama_error(embeddings_server):
    url, state = embeddings_server
    state["status"] = 500
    with pytest.raises(HTTPError):
        runpy.run_path(str(CHECKER))["check_embeddings"](url)


@pytest.mark.parametrize("setting", ["false", "0", "no", "OFF", '"false" # disabled'])
def test_readiness_main_skips_http_for_explicit_disabled_rag(
    tmp_path, monkeypatch, setting
):
    env_file = tmp_path / "bot.env"
    env_file.write_text(f"ENABLE_RAG={setting}\n")
    monkeypatch.setenv("MAXWELL_ENV_FILE", str(env_file))
    monkeypatch.setenv("ENABLE_RAG", "true")
    transport = Mock(side_effect=AssertionError("disabled readiness attempted HTTP"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    runpy.run_path(str(CHECKER), run_name="__main__")
    transport.assert_not_called()


@pytest.mark.parametrize("ready", [False, True])
def test_compose_entrypoint_gates_application_exec(embeddings_server, tmp_path, ready):
    url, state = embeddings_server
    state["vectors"] = [[0.25] * (1024 if ready else 768)]
    checker = tmp_path / "check_embeddings.py"
    checker.write_text(CHECKER.read_text().replace("http://ollama:11434", url))
    env_file = tmp_path / "bot.env"
    env_file.write_text("ENABLE_RAG=true\n")
    entrypoint = yaml.safe_load((ROOT / "compose.yaml").read_text())["x-app"][
        "entrypoint"
    ]
    entrypoint = [
        value.replace("$$", "$").replace(
            "/opt/maxwell/check_embeddings.py", str(checker)
        )
        for value in entrypoint
    ]
    marker = tmp_path / "started"
    result = subprocess.run(
        [
            *entrypoint,
            sys.executable,
            "-c",
            "import pathlib, sys; pathlib.Path(sys.argv[1]).touch()",
            str(marker),
        ],
        env={**os.environ, "MAXWELL_ENV_FILE": str(env_file), "ENABLE_RAG": "false"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (result.returncode == 0) is ready
    assert marker.exists() is ready


@pytest.mark.parametrize("present,pull_exit", [(True, 0), (False, 0), (False, 7)])
def test_one_shot_pull_is_idempotent_and_propagates_failure(
    tmp_path, present, pull_exit
):
    stub = tmp_path / "ollama"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  serve) echo $$ >"$TEST_STATE/server"; exec sleep 30 ;;\n'
        '  list) test -f "$TEST_STATE/server" ;;\n'
        '  show) test "$TEST_PRESENT" = true ;;\n'
        '  pull) printf "%s" "$2" >"$TEST_STATE/pulled"; exit "$TEST_PULL_EXIT" ;;\n'
        "esac\n"
    )
    stub.chmod(0o700)
    service = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"][
        "ollama-pull"
    ]
    command = service["command"][0].replace("$$", "$")
    result = subprocess.run(
        [*service["entrypoint"], command],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:/usr/bin:/bin",
            "TEST_STATE": str(tmp_path),
            "TEST_PRESENT": str(present).lower(),
            "TEST_PULL_EXIT": str(pull_exit),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == pull_exit
    assert (tmp_path / "pulled").exists() is not present
    if not present:
        assert (tmp_path / "pulled").read_text() == "qwen3-embedding:0.6b"
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path / "server").read_text()), 0)
