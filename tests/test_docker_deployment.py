from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def deployment():
    return yaml.safe_load((ROOT / "compose.yaml").read_text())


def test_bot_uses_whole_private_state():
    services = deployment()["services"]
    for name in ("bot",):
        service = services[name]
        mounts = {item["target"]: item for item in service["volumes"]}
        assert mounts["/state/data"]["source"] == "${INSTANCE_DIR}/data"
        assert mounts["/config"]["read_only"] is True
        assert "read_only" not in mounts["/config/prompts"]
        assert all(not item["bind"]["create_host_path"] for item in mounts.values())
        assert service["environment"]["DAME_CURIE_ENV_FILE"] == "/config/bot.env"
        assert "env_file" not in service
        assert "ports" not in service
        assert "container_name" not in service
        assert "replicas" not in service.get("deploy", {})


def test_core_services_use_the_host_timezone_file_without_a_fixed_offset():
    services = deployment()["services"]
    assert set(services) == {"bot", "ollama", "ollama-pull"}
    for service in services.values():
        mounts = {item["target"]: item for item in service["volumes"]}
        assert mounts["/etc/dame-curie-localtime"] == {
            "type": "bind", "source": "/etc/localtime",
            "target": "/etc/dame-curie-localtime", "read_only": True,
            "bind": {"create_host_path": False},
        }
        assert service["environment"]["TZ"] == ":/etc/dame-curie-localtime"
        assert "/etc/localtime" not in mounts
        assert all(not path.startswith("/usr/share/zoneinfo/") for path in mounts)


def test_outer_container_privilege_boundary():
    for name, service in deployment()["services"].items():
        assert service["read_only"] is (name != "bot")
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert not service.get("privileged")
        assert service.get("network_mode") != "host"
        for mount in service.get("volumes", []):
            assert mount["source"] != "/"
            assert mount["source"] != "/var/run/docker.sock"


def test_image_uses_allowlisted_source_and_locked_dependencies():
    dockerfile = (ROOT / "docker/app.Dockerfile").read_text()
    assert "python:3.14.4-slim-trixie" in dockerfile
    assert "COPY . " not in dockerfile
    assert "COPY *.py" not in dockerfile
    assert "--no-deps -r /opt/dame-curie/requirements.lock" in dockerfile
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
    assert settings["DAME_CURIE_SITE_DIR"] == "/state/sites"
    assert settings["DAME_CURIE_PROMPTS_DIR"] == "/config/prompts"
    assert settings["DISCORD_TOKEN"] == ""
    assert settings["OPENAI_API_KEY"] == ""
    assert settings["ENABLE_RAG"] == "false"
    assert settings["DAME_CURIE_EMBED_BASE_URL"] == "http://ollama:11434"
    assert settings["DAME_CURIE_EMBED_MODEL"] == "qwen3-embedding:0.6b"
    assert settings["DAME_CURIE_EMBED_DIM"] == "1024"
    assert settings["DAME_CURIE_EMBED_API_KEY"] == ""


def test_ollama_is_private_and_has_persistent_per_project_models():
    config = deployment()
    services = config["services"]
    assert config["networks"]["embeddings"]["internal"] is True
    assert services["ollama"]["networks"] == ["embeddings"]
    assert services["ollama-pull"]["networks"] == ["model-download"]
    assert "model-download" not in services["ollama"]["networks"]
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
    for name in ("bot",):
        service = services[name]
        assert service["depends_on"] == {"ollama": {"condition": "service_healthy"}}
        assert service["entrypoint"] == [
            "/bin/sh",
            "-ec",
            'python /opt/dame-curie/check_embeddings.py && exec "$$@"',
            "--",
        ]
        assert "embeddings" in service["networks"]


def test_image_contains_readiness_gate_and_explicit_build_provenance():
    dockerfile = (ROOT / "docker/app.Dockerfile").read_text()
    assert (
        "COPY docker/check_embeddings.py /opt/dame-curie/check_embeddings.py" in dockerfile
    )
    assert (
        "!docker/check_embeddings.py"
        in (ROOT / "docker/app.Dockerfile.dockerignore").read_text().splitlines()
    )
    for field in ("COMMIT", "BRANCH", "DATE", "SUBJECT", "DIRTY"):
        assert f"ARG DAME_CURIE_BUILD_{field}=unknown" in dockerfile
    assert 'Path("/app/build_provenance.json").write_text(json.dumps(manifest)' in dockerfile
    assert "Full build commit required" in dockerfile
    assert "ENV DAME_CURIE_BUILD_" not in dockerfile
    assert "org.opencontainers.image.revision=${DAME_CURIE_BUILD_COMMIT}" in dockerfile
    assert ".git" not in (ROOT / "docker/app.Dockerfile.dockerignore").read_text()


def test_builder_pins_archive_and_manifest_to_same_commit():
    script = (ROOT / "scripts/build_for_human.sh").read_text()
    assert 'git archive "$rev"' in script
    assert '--build-arg DAME_CURIE_BUILD_COMMIT="$rev"' in script
    assert 'git show -s --format=%s "$rev"' in script
    assert '--build-arg DAME_CURIE_BUILD_DIRTY=false' in script
