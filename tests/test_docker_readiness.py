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
EMBEDDING_SETTINGS = (
    "ENABLE_RAG",
    "DAME_CURIE_EMBED_MODE",
    "DAME_CURIE_EMBED_BASE_URL",
    "EMBED_BASE_URL",
    "DAME_CURIE_EMBED_MODEL",
    "EMBED_MODEL",
    "DAME_CURIE_EMBED_DIM",
    "DAME_CURIE_EMBED_API_KEY",
    "EMBED_API_KEY",
)


@pytest.fixture
def embeddings_server():
    state = {
        "vectors": [[0.25] * 1024],
        "status": 200,
        "requests": [],
        "headers": [],
        "shape": "ollama",
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(
                (
                    self.path,
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            state["headers"].append(dict(self.headers))
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = (
                {
                    "data": [
                        {"embedding": vector, "index": index}
                        for index, vector in enumerate(state["vectors"])
                    ]
                }
                if state["shape"] == "openai"
                else {"embeddings": state["vectors"]}
            )
            self.wfile.write(json.dumps(body).encode())

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


def isolate_readiness(monkeypatch, tmp_path, settings):
    """Point the gate at a synthetic dotenv file with no ambient embedding settings."""
    for name in EMBEDDING_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / "bot.env"
    env_file.write_text("".join(f"{key}={value}\n" for key, value in settings.items()))
    monkeypatch.setenv("DAME_CURIE_ENV_FILE", str(env_file))


def run_readiness():
    """Execute the gate the way the Compose entrypoint does."""
    runpy.run_path(str(CHECKER), run_name="__main__")


def test_readiness_requires_real_embedding_without_api_credentials(embeddings_server):
    url, state = embeddings_server
    runpy.run_path(str(CHECKER))["check_embeddings"](
        url, "qwen3-embedding:0.6b", 1024
    )
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]
    assert "Authorization" not in state["headers"][0]


def test_readiness_external_ollama_form_matches_the_embedding_request(embeddings_server):
    url, state = embeddings_server
    runpy.run_path(str(CHECKER))["check_embeddings"](url, "shared-model", 1024)
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "shared-model", "input": "readiness"},
        )
    ]


@pytest.mark.parametrize("suffix", ["", "?region=private&route=one"])
def test_readiness_external_openai_form_uses_v1_with_bearer_auth(embeddings_server, suffix):
    url, state = embeddings_server
    state["shape"] = "openai"
    runpy.run_path(str(CHECKER))["check_embeddings"](
        f"{url}/v1{suffix}", "shared-model", 1024, "test-key"
    )
    assert state["requests"] == [
        (f"/v1/embeddings{suffix}", {"model": "shared-model", "input": "readiness"})
    ]
    assert state["headers"][0]["Authorization"] == "Bearer test-key"


def test_readiness_omits_ollama_fields_on_a_v1_endpoint(embeddings_server):
    url, state = embeddings_server
    state["shape"] = "openai"
    runpy.run_path(str(CHECKER))["check_embeddings"](
        f"{url}/v1", "shared-model", 1024
    )
    assert state["requests"] == [
        ("/v1/embeddings", {"model": "shared-model", "input": "readiness"})
    ]


def test_readiness_requires_the_configured_dimension(embeddings_server):
    url, state = embeddings_server
    state["vectors"] = [[0.5] * 768]
    check_embeddings = runpy.run_path(str(CHECKER))["check_embeddings"]
    check_embeddings(url, "shared-model", 768)
    with pytest.raises(ValueError, match="1024-dimensional"):
        check_embeddings(url, "shared-model", 1024)


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
        runpy.run_path(str(CHECKER))["check_embeddings"](
            url, "qwen3-embedding:0.6b", 1024
        )


def test_readiness_fails_closed_on_endpoint_error(embeddings_server):
    url, state = embeddings_server
    state["status"] = 500
    with pytest.raises(HTTPError):
        runpy.run_path(str(CHECKER))["check_embeddings"](
            url, "qwen3-embedding:0.6b", 1024
        )


@pytest.mark.parametrize("setting", ["false", "0", "no", "OFF", '"false" # disabled'])
def test_readiness_main_skips_http_for_explicit_disabled_rag(
    tmp_path, monkeypatch, setting
):
    isolate_readiness(monkeypatch, tmp_path, {"ENABLE_RAG": setting})
    monkeypatch.setenv("ENABLE_RAG", "true")
    transport = Mock(side_effect=AssertionError("disabled readiness attempted HTTP"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    run_readiness()
    transport.assert_not_called()


@pytest.mark.parametrize("setting", [None, "", "auto", "true"])
def test_readiness_main_probes_unless_rag_is_explicitly_disabled(
    embeddings_server, tmp_path, monkeypatch, setting
):
    url, state = embeddings_server
    settings = {"DAME_CURIE_EMBED_BASE_URL": url}
    if setting is not None:
        settings["ENABLE_RAG"] = setting
    isolate_readiness(monkeypatch, tmp_path, settings)
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "external")
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


def test_readiness_main_probes_the_configured_external_endpoint(
    embeddings_server, tmp_path, monkeypatch
):
    url, state = embeddings_server
    state["shape"] = "openai"
    isolate_readiness(
        monkeypatch,
        tmp_path,
        {
            "ENABLE_RAG": "true",
            "EMBED_BASE_URL": f"{url}/v1",
            "EMBED_MODEL": "legacy-alias-model",
            "DAME_CURIE_EMBED_DIM": "1024",
            "DAME_CURIE_EMBED_API_KEY": "test-key",
        },
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "external")
    run_readiness()
    assert state["requests"] == [
        ("/v1/embeddings", {"model": "legacy-alias-model", "input": "readiness"})
    ]
    assert state["headers"][0]["Authorization"] == "Bearer test-key"


def test_readiness_main_prefers_the_dotenv_file_over_the_process_environment(
    embeddings_server, tmp_path, monkeypatch
):
    url, state = embeddings_server
    isolate_readiness(
        monkeypatch, tmp_path, {"ENABLE_RAG": "true", "DAME_CURIE_EMBED_BASE_URL": url}
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "external")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", "http://127.0.0.1:1/unreachable")
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


def test_readiness_main_treats_a_bare_dotenv_key_as_no_value(
    embeddings_server, tmp_path, monkeypatch
):
    """A bare KEY line carries no value, so the inherited value still applies, as in config.py."""
    url, state = embeddings_server
    isolate_readiness(monkeypatch, tmp_path, {})
    (tmp_path / "bot.env").write_text(
        "ENABLE_RAG=true\nDAME_CURIE_EMBED_BASE_URL\n"
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", url)
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


@pytest.mark.parametrize("mode", ["local", "external"])
def test_readiness_main_requires_an_explicit_external_endpoint(
    tmp_path, monkeypatch, capsys, mode
):
    isolate_readiness(
        monkeypatch, tmp_path, {"ENABLE_RAG": "true", "DAME_CURIE_EMBED_BASE_URL": ""}
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", mode)
    monkeypatch.setenv("EMBED_BASE_URL", "http://alias.invalid")
    transport = Mock(side_effect=AssertionError("readiness used an inferred endpoint"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    with pytest.raises(SystemExit) as exit_info:
        run_readiness()
    assert exit_info.value.code == 1
    transport.assert_not_called()
    assert capsys.readouterr().err.strip() == "embedding readiness failed: ValueError"


def test_readiness_cli_reports_a_status_without_the_endpoint(
    embeddings_server, tmp_path, monkeypatch, capsys
):
    url, state = embeddings_server
    state["status"] = 401
    isolate_readiness(
        monkeypatch,
        tmp_path,
        {
            "ENABLE_RAG": "true",
            "DAME_CURIE_EMBED_BASE_URL": url,
            "DAME_CURIE_EMBED_API_KEY": "synthetic-secret",
        },
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    with pytest.raises(SystemExit) as exit_info:
        run_readiness()
    assert exit_info.value.code == 1
    stderr = capsys.readouterr().err.strip()
    assert stderr == "embedding readiness failed: HTTPError (HTTP 401)"
    assert url not in stderr and "synthetic-secret" not in stderr


def test_readiness_cli_never_echoes_a_rejected_credential(
    tmp_path, monkeypatch, capsys
):
    """A header value urllib rejects still carries the credential in its own message."""
    isolate_readiness(monkeypatch, tmp_path, {"ENABLE_RAG": "true"})
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", "http://127.0.0.1:1/embed")
    monkeypatch.setenv("DAME_CURIE_EMBED_API_KEY", "synthetic-secret\nX-Forged: 1")
    with pytest.raises(SystemExit) as exit_info:
        run_readiness()
    assert exit_info.value.code == 1
    stderr = capsys.readouterr().err
    assert stderr.startswith("embedding readiness failed: ")
    assert len(stderr.strip().splitlines()) == 1
    assert "synthetic-secret" not in stderr and "X-Forged" not in stderr


@pytest.mark.parametrize("url,error_type", [
    ("http://[::1", "ValueError"),
    ("http://127.0.0.1:1/synthetic-secret path", "InvalidURL"),
])
def test_readiness_cli_never_echoes_an_invalid_endpoint(
    tmp_path, monkeypatch, capsys, url, error_type
):
    isolate_readiness(monkeypatch, tmp_path, {"ENABLE_RAG": "true"})
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", url)
    with pytest.raises(SystemExit) as exit_info:
        run_readiness()
    assert exit_info.value.code == 1
    stderr = capsys.readouterr().err
    assert stderr.strip() == f"embedding readiness failed: {error_type}"
    assert "[::1" not in stderr and "http" not in stderr
    assert "synthetic-secret" not in stderr


def test_readiness_cli_keeps_unexpected_errors_visible(tmp_path, monkeypatch):
    isolate_readiness(monkeypatch, tmp_path, {"ENABLE_RAG": "true"})
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", "http://127.0.0.1:1/embed")
    monkeypatch.setattr(
        "urllib.request.urlopen", Mock(side_effect=RuntimeError("unexpected"))
    )
    with pytest.raises(RuntimeError, match="unexpected"):
        run_readiness()


def test_readiness_main_probes_the_injected_local_endpoint(
    embeddings_server, tmp_path, monkeypatch
):
    url, state = embeddings_server
    isolate_readiness(monkeypatch, tmp_path, {"ENABLE_RAG": "true"})
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", url)
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


def test_readiness_main_local_mode_honours_the_configured_endpoint(
    embeddings_server, tmp_path, monkeypatch
):
    """A configured endpoint wins over the injected local service URL, as it does for the bot."""
    url, state = embeddings_server
    isolate_readiness(
        monkeypatch, tmp_path, {"ENABLE_RAG": "true", "DAME_CURIE_EMBED_BASE_URL": url}
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", "http://127.0.0.1:1/injected-local")
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


def test_readiness_main_keeps_the_deployment_mode_when_bot_env_disagrees(
    embeddings_server, tmp_path, monkeypatch
):
    """Mode is Compose-provided deployment metadata; the private dotenv file cannot flip it."""
    url, state = embeddings_server
    isolate_readiness(
        monkeypatch,
        tmp_path,
        {"ENABLE_RAG": "true", "DAME_CURIE_EMBED_MODE": "external"},
    )
    monkeypatch.setenv("DAME_CURIE_EMBED_MODE", "local")
    monkeypatch.setenv("DAME_CURIE_EMBED_BASE_URL", url)
    run_readiness()
    assert state["requests"] == [
        (
            "/api/embed",
            {"model": "qwen3-embedding:0.6b", "input": "readiness"},
        )
    ]


@pytest.mark.parametrize("ready", [False, True])
def test_compose_entrypoint_gates_application_exec(embeddings_server, tmp_path, ready):
    url, state = embeddings_server
    state["vectors"] = [[0.25] * (1024 if ready else 768)]
    checker = tmp_path / "check_embeddings.py"
    checker.write_text(CHECKER.read_text())
    env_file = tmp_path / "bot.env"
    env_file.write_text(f"ENABLE_RAG=true\nDAME_CURIE_EMBED_BASE_URL={url}\n")
    entrypoint = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]["bot"][
        "entrypoint"
    ]
    entrypoint = [
        value.replace("$$", "$").replace(
            "/opt/dame-curie/check_embeddings.py", str(checker)
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
        env={
            **os.environ,
            "DAME_CURIE_ENV_FILE": str(env_file),
            "ENABLE_RAG": "false",
            "DAME_CURIE_EMBED_MODE": "local",
        },
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
