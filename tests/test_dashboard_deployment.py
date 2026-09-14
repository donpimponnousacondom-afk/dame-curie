import base64
from contextlib import closing, contextmanager
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import time
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
USER = "synthetic-admin"
PASSWORD = "synthetic-dashboard-password"
AUTH = {
    "Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
}


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def request(origin, method, path, body=None, headers=None):
    target = urlsplit(origin)
    with closing(
        http.client.HTTPConnection(target.hostname, target.port, timeout=10)
    ) as connection:
        connection.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()


@contextmanager
def local_service(command, origin, env, log_path):
    with log_path.open("w+") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _attempt in range(100):
                assert process.poll() is None, log_path.read_text()
                try:
                    if request(origin, "GET", "/api/health")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("local service did not become ready")
            yield
        finally:
            process.terminate()
            process.wait(timeout=10)


@pytest.fixture
def api_runtime(tmp_path):
    for name in ("data", "sites", "prompts", "home"):
        (tmp_path / name).mkdir()
    (tmp_path / "prompts/personality.txt").write_text("Synthetic initial personality")
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "MAXWELL_ENV_FILE": "/dev/null",
        "PYTHON_DOTENV_DISABLED": "1",
        "DATA_DIR": str(tmp_path / "data"),
        "MAXWELL_SITE_DIR": str(tmp_path / "sites"),
        "MAXWELL_PROMPTS_DIR": str(tmp_path / "prompts"),
        "MAXWELL_CONTAINER_MODE": "true",
        "MAXWELL_INSTANCE_ID": "synthetic",
        "MAXWELL_ADMIN_USER": USER,
        "MAXWELL_ADMIN_PASSWORD": PASSWORD,
        "MAXWELL_API_HOST": "127.0.0.1",
        "MAXWELL_API_PORT": str(port),
        "MAXWELL_PUBLIC_BASE_URL": origin,
        "MAXWELL_CORS_ORIGIN": origin,
        "ENABLE_RAG": "false",
        "MAXWELL_EMBED_BASE_URL": "http://ollama:11434",
        "MAXWELL_EMBED_MODEL": "qwen3-embedding:0.6b",
        "MAXWELL_EMBED_DIM": "1024",
        "DISCORD_CLIENT_ID": "",
        "DISCORD_CLIENT_SECRET": "",
    }
    with local_service(
        [sys.executable, "-m", "api.api_server"], origin, env, tmp_path / "api.log"
    ):
        yield origin, tmp_path, env


@pytest.fixture
def dashboard_runtime(api_runtime):
    api_origin, state, env = api_runtime
    caddy = os.getenv("MAXWELL_TEST_CADDY") or shutil.which("caddy")
    if not caddy:
        pytest.skip("Caddy binary unavailable; set MAXWELL_TEST_CADDY")
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    config = (ROOT / "docker/Caddyfile").read_text()
    config = config.replace(":8080 {", f"{origin} {{\n\tbind 127.0.0.1")
    config = config.replace("api:8765", api_origin.removeprefix("http://"))
    config = config.replace("/srv/web", str(ROOT / "web")).replace(
        "/srv/sites", str(state / "sites")
    )
    config_path = state / "Caddyfile"
    config_path.write_text(config)
    env = {
        **env,
        "XDG_CONFIG_HOME": str(state / "caddy-config"),
        "XDG_DATA_HOME": str(state / "caddy-data"),
    }
    with local_service(
        [caddy, "run", "--config", str(config_path), "--adapter", "caddyfile"],
        origin,
        env,
        state / "caddy.log",
    ):
        yield origin, state, env


def verify_authenticated_controls(origin, state):
    assert request(origin, "GET", "/api/control")[0] == 401
    assert request(origin, "GET", "/data/bot_control.json")[0] == 401
    assert (
        request(origin, "POST", "/api/login", {"user": USER, "pass": "wrong"})[0] == 401
    )
    status, _, text = request(
        origin, "POST", "/api/login", {"user": USER, "pass": PASSWORD}
    )
    assert status == 200 and json.loads(text)["ok"]
    status, _, text = request(origin, "GET", "/api/control", headers=AUTH)
    assert status == 200
    assert (
        json.loads(text)["control"]["base_personality"]
        == "Synthetic initial personality"
    )
    status, _, _ = request(
        origin,
        "PUT",
        "/api/control",
        {"base_personality": "Synthetic saved personality"},
        AUTH,
    )
    assert status == 200
    assert (
        state / "prompts/personality.txt"
    ).read_text() == "Synthetic saved personality"
    status, _, text = request(origin, "GET", "/data/bot_control.json", headers=AUTH)
    assert status == 200
    assert json.loads(text)["base_personality"] == "Synthetic saved personality"
    assert request(origin, "GET", "/data/maxwell_rag.db", headers=AUTH)[0] == 403
    assert request(origin, "GET", "/data/admins.json", headers=AUTH)[0] == 403
    assert request(origin, "POST", "/api/pm2/restart", {}, AUTH)[0] == 501


def test_real_api_authentication_and_persisted_dashboard_controls(api_runtime):
    origin, state, _ = api_runtime
    verify_authenticated_controls(origin, state)


def test_dashboard_counts_only_current_valid_embeddings(api_runtime):
    from rag_memory import embedding_backend_id

    origin, state, _ = api_runtime
    backend = embedding_backend_id("http://ollama:11434", "qwen3-embedding:0.6b", 1024)
    vector = struct.pack("<1024f", *([0.25] * 1024))
    with closing(sqlite3.connect(state / "data/maxwell_rag.db")) as connection:
        connection.execute(
            "CREATE TABLE vectors (id TEXT, channel_id TEXT, kind TEXT, content TEXT, "
            "timestamp TEXT, embedding BLOB, embedding_backend TEXT)"
        )
        for index, (blob, identity) in enumerate(
            [
                (vector, backend),
                (vector, ""),
                (vector, "foreign"),
                (b"invalid", backend),
                (None, ""),
            ]
        ):
            connection.execute(
                "INSERT INTO vectors VALUES (?, 'synthetic', 'message', 'synthetic', '', ?, ?)",
                (str(index), blob, identity),
            )
        connection.execute(
            "INSERT INTO vectors VALUES ('noise', 'synthetic', 'message', 'ok', '', NULL, '')"
        )
        connection.commit()
    for path in ("/api/rag/memory", "/api/status"):
        status, _, text = request(origin, "GET", path, headers=AUTH)
        assert status == 200
        stats = json.loads(text)
        if path == "/api/status":
            stats = stats["stats"]
        assert stats["total_vectors"] == 6
        assert stats["embedded"] == 1
        assert stats["pending_embeddings"] == 5
        assert stats["eligible_pending"] == 4
        assert stats["excluded_pending"] == 1


def test_caddy_serves_admin_and_preserves_real_api_auth(dashboard_runtime):
    origin, state, _ = dashboard_runtime
    status, headers, _ = request(origin, "GET", "/admin")
    assert status == 308 and headers["Location"] == "/admin/"
    status, headers, text = request(origin, "GET", "/admin/")
    assert status == 200 and "text/html" in headers["Content-Type"]
    assert 'id="loginForm"' in text
    assert headers["X-Frame-Options"] == "DENY"
    assert request(origin, "GET", "/config/bot.env")[0] == 404
    verify_authenticated_controls(origin, state)


def test_browser_login_and_personality_save_use_real_api(dashboard_runtime):
    origin, state, env = dashboard_runtime
    node = shutil.which("node")
    playwright = os.getenv("MAXWELL_TEST_PLAYWRIGHT")
    chromium = os.getenv("MAXWELL_TEST_CHROMIUM")
    if not node or not playwright or not chromium:
        pytest.skip(
            "Set MAXWELL_TEST_PLAYWRIGHT and MAXWELL_TEST_CHROMIUM for browser acceptance"
        )
    result = subprocess.run(
        [node, str(ROOT / "tests/dashboard_smoke.cjs"), origin],
        env={
            **env,
            "MAXWELL_TEST_PLAYWRIGHT": playwright,
            "MAXWELL_TEST_CHROMIUM": chromium,
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        state / "prompts/personality.txt"
    ).read_text() == "Synthetic browser personality"
