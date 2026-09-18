from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def deployment():
    return yaml.safe_load((ROOT / "compose.yaml").read_text())


def test_one_bot_and_api_share_whole_private_state():
    services = deployment()["services"]
    for name in ("bot", "api"):
        service = services[name]
        mounts = {item["target"]: item for item in service["volumes"]}
        assert mounts["/state/data"]["source"] == "${INSTANCE_DIR}/data"
        assert mounts["/config"]["read_only"] is True
        assert "read_only" not in mounts["/config/prompts"]
        assert all(not item["bind"]["create_host_path"] for item in mounts.values())
        assert service["environment"]["MAXWELL_ENV_FILE"] == "/config/bot.env"
        assert "env_file" not in service
        assert "ports" not in service
        assert "container_name" not in service
        assert "replicas" not in service.get("deploy", {})


def test_core_services_use_the_host_timezone_file_without_a_fixed_offset():
    services = deployment()["services"]
    assert set(services) == {"bot", "api", "ollama", "ollama-pull", "web"}
    for service in services.values():
        mounts = {item["target"]: item for item in service["volumes"]}
        assert mounts["/etc/maxwell-localtime"] == {
            "type": "bind", "source": "/etc/localtime",
            "target": "/etc/maxwell-localtime", "read_only": True,
            "bind": {"create_host_path": False},
        }
        assert service["environment"]["TZ"] == ":/etc/maxwell-localtime"
        assert "/etc/localtime" not in mounts
        assert all(not path.startswith("/usr/share/zoneinfo/") for path in mounts)


def test_private_socket_and_no_host_privilege():
    for service in deployment()["services"].values():
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert not service.get("privileged")
        assert service.get("network_mode") != "host"
        for mount in service.get("volumes", []):
            assert mount["source"] != "/"
            assert mount["source"] != "/var/run/docker.sock"
    socket_mount = deployment()["services"]["bot"]["volumes"][-1]
    assert socket_mount["source"].startswith("${ENGINE_SOCKET:?")


def test_only_bot_receives_private_live_git_socket_directory():
    services = deployment()["services"]
    mounts = {item["target"]: item for item in services["bot"]["volumes"]}
    assert mounts["/run/maxwell-checkout"] == {
        "type": "bind", "source": "/srv/maxwell-checkout/${INSTANCE_ID}",
        "target": "/run/maxwell-checkout", "read_only": True,
        "bind": {"create_host_path": False},
    }
    assert services["bot"]["environment"]["MAXWELL_STARTUP_GIT_SOCKET"] == "/run/maxwell-checkout/snapshot.sock"
    for name, service in services.items():
        assert all("/home/" not in item["source"] and ".git" not in item["source"] for item in service.get("volumes", []))
        if name != "bot":
            assert "MAXWELL_STARTUP_GIT_SOCKET" not in service.get("environment", {})
            assert all(item["target"] != "/run/maxwell-checkout" for item in service.get("volumes", []))
    assert set(services["api"]["environment"]).issubset(services["bot"]["environment"])


def test_web_only_mounts_public_sites_and_host_timezone_and_binds_loopback():
    web = deployment()["services"]["web"]
    mounts = {item["target"]: item for item in web["volumes"]}
    assert set(mounts) == {"/srv/sites", "/etc/maxwell-localtime"}
    assert mounts["/srv/sites"]["source"] == "${INSTANCE_DIR}/sites"
    assert mounts["/srv/sites"]["read_only"] is True
    assert web["ports"][0].startswith("127.0.0.1:")
    caddy = (ROOT / "docker/Caddyfile").read_text()
    assert "reverse_proxy api:8765" in caddy
    assert "/bot/*/api /bot/*/api/*" in caddy
    assert "/state/data" not in caddy


def test_web_starts_without_file_capabilities_and_reports_health():
    web = deployment()["services"]["web"]
    dockerfile = (ROOT / "docker/app.Dockerfile").read_text()
    web_stage = dockerfile.split("FROM caddy:2.10.2-alpine AS web", 1)[1]
    assert "RUN setcap -r /usr/bin/caddy" in web_stage
    assert web["cap_drop"] == ["ALL"]
    assert "cap_add" not in web
    assert web["security_opt"] == ["no-new-privileges:true"]
    assert web["healthcheck"]["test"] == [
        "CMD",
        "wget",
        "--spider",
        "-q",
        "http://127.0.0.1:8080/admin/",
    ]
    assert web["healthcheck"]["interval"] == "10s"
    assert web["healthcheck"]["timeout"] == "5s"
    assert web["healthcheck"]["retries"] == 3


def test_image_uses_allowlisted_source_and_locked_dependencies():
    dockerfile = (ROOT / "docker/app.Dockerfile").read_text()
    assert "python:3.14.4-slim-trixie" in dockerfile
    assert (
        "docker:26.1.4-cli@sha256:f13cbf1ea352bdbdc825a9233fc56716bdf818e4f608f63280a1aa0b3dc1f2f7"
        in dockerfile
    )
    assert "docker:26.1.5-cli" not in dockerfile
    assert "COPY . " not in dockerfile
    assert "COPY *.py" not in dockerfile
    assert "--no-deps -r /opt/maxwell/requirements.lock" in dockerfile
    lines = (ROOT / "docker/app.Dockerfile.dockerignore").read_text().splitlines()
    assert lines[0] == "**"
    allowed = [line[1:] for line in lines if line.startswith("!")]
    assert not any("*" in path for path in allowed)
    assert not any(
        path.startswith(("data/", ".venv/", "shelldocker/")) for path in allowed
    )
    assert not any(path.endswith((".env", ".db", ".key", ".pem")) for path in allowed)
    dependencies = (ROOT / "docker/requirements.lock").read_text().splitlines()
    assert all("==" in line and ">" not in line for line in dependencies)
    assert "discord.py-self==2.1.0" in dependencies
    assert not any(line.startswith("discord.py==") for line in dependencies)
    assert "error_reporting.py" in dockerfile.split()
    assert "error_reporting.py" in allowed
    assert "operator_commands.py" in dockerfile.split()
    assert "operator_commands.py" in allowed
    assert "provider_telemetry.py" in dockerfile.split()
    assert "provider_telemetry.py" in allowed
    assert "response_observability.py" in dockerfile.split()
    assert "response_observability.py" in allowed
    assert "rag_maintenance.py" in dockerfile.split()
    assert "rag_maintenance.py" in allowed
    assert "COPY assets/tokenizers/ ./assets/tokenizers/" in dockerfile
    assert {
        "assets/tokenizers/cl100k_base.tiktoken",
        "assets/tokenizers/LICENSE",
        "assets/tokenizers/README.md",
    } <= set(allowed)


def test_bot_template_keeps_operational_paths_consistent():
    settings = dict(
        line.split("=", 1)
        for line in (ROOT / "docker/bot.env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )
    assert settings["DATA_DIR"] == "/state/data"
    assert settings["MAXWELL_SITE_DIR"] == "/state/sites"
    assert settings["MAXWELL_PROMPTS_DIR"] == "/config/prompts"
    assert settings["MAXWELL_SHELL_FULL_HOST"] == "false"
    assert settings["MAXWELL_API_PORT"] == "8765"
    assert settings["DISCORD_TOKEN"] == ""
    assert settings["OLLAMA_API_KEY"] == ""
    assert settings["MAXWELL_ADMIN_PASSWORD"] == ""
    assert settings["ENABLE_RAG"] == "true"
    assert settings["MAXWELL_EMBED_BASE_URL"] == "http://ollama:11434"
    assert settings["MAXWELL_EMBED_MODEL"] == "qwen3-embedding:0.6b"
    assert settings["MAXWELL_EMBED_DIM"] == "1024"
    assert settings["MAXWELL_EMBED_API_KEY"] == ""


def test_ollama_is_private_and_has_persistent_per_project_models():
    config = deployment()
    services = config["services"]
    assert config["networks"]["embeddings"]["internal"] is True
    assert services["ollama"]["networks"] == ["embeddings"]
    assert services["ollama-pull"]["networks"] == ["model-download"]
    assert "model-download" not in services["ollama"]["networks"]
    assert "embeddings" not in services["web"]["networks"]
    assert config["volumes"]["ollama-models"] is None
    for name in ("ollama", "ollama-pull"):
        service = services[name]
        assert service["image"] == (
            "ollama/ollama:0.33.3@sha256:"
            "32931b46719f673c05fdbaa81ccb26da18ea4a1c57590a754874ab28ba269eb2"
        )
        assert "ports" not in service
        assert "env_file" not in service
        assert all(
            "KEY" not in key and "TOKEN" not in key for key in service["environment"]
        )
        assert service["volumes"] == [
            deployment()["x-host-timezone"],
            {"type": "volume", "source": "ollama-models", "target": "/root/.ollama"}
        ]


def test_pull_is_one_shot_and_runtime_waits_for_download_and_embedding():
    services = deployment()["services"]
    pull = services["ollama-pull"]
    assert pull["restart"] == "no"
    assert pull["environment"]["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert "ollama pull qwen3-embedding:0.6b" in pull["command"][0]
    assert services["ollama"]["depends_on"] == {
        "ollama-pull": {"condition": "service_completed_successfully"}
    }
    assert services["ollama"]["healthcheck"]["test"] == [
        "CMD",
        "ollama",
        "show",
        "qwen3-embedding:0.6b",
    ]
    for name in ("bot", "api"):
        service = services[name]
        assert service["depends_on"] == {"ollama": {"condition": "service_healthy"}}
        assert service["entrypoint"] == [
            "/bin/sh",
            "-ec",
            'python /opt/maxwell/check_embeddings.py && exec "$$@"',
            "--",
        ]
        assert "embeddings" in service["networks"]


def test_image_contains_readiness_gate_and_explicit_build_provenance():
    dockerfile = (ROOT / "docker/app.Dockerfile").read_text()
    assert (
        "COPY docker/check_embeddings.py /opt/maxwell/check_embeddings.py" in dockerfile
    )
    assert (
        "!docker/check_embeddings.py"
        in (ROOT / "docker/app.Dockerfile.dockerignore").read_text().splitlines()
    )
    for field in ("COMMIT", "BRANCH", "DATE", "SUBJECT", "DIRTY"):
        key = f"MAXWELL_BUILD_{field}"
        assert f"ARG {key}=unknown" in dockerfile
        assert f"{key}=${{{key}}}" in dockerfile
    assert "org.opencontainers.image.revision=${MAXWELL_BUILD_COMMIT}" in dockerfile
    assert ".git" not in (ROOT / "docker/app.Dockerfile.dockerignore").read_text()


def test_site_runtime_uses_python314_compatible_pillow_and_contract():
    dockerfile = (ROOT / "docker/site-runtime/Dockerfile").read_text()
    assert "FROM python:3.14.4-slim-trixie" in dockerfile
    assert "pillow==12.3.0" in dockerfile
    assert "pillow==11.1.0" not in dockerfile
    assert "python 3.14 + flask" in (ROOT / "site_server.py").read_text()


def test_caddy_admin_route_is_explicit_and_keeps_authenticated_api_boundary():
    caddy = (ROOT / "docker/Caddyfile").read_text()
    assert "redir /admin /admin/ 308" in caddy
    assert "@backend path /api/* /data/* /bot/*/api /bot/*/api/*" in caddy
    assert "root * /srv/web" in caddy
    assert "root * /srv/sites" in caddy
    assert "/config" not in caddy
