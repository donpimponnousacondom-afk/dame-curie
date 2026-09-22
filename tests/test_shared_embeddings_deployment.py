"""Shared/external embedding deployment selection; synthetic source checks only."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "docker/compose.embeddings-external.yaml"
COMPOSE_TAGS = ("!reset", "!override")

SPEC = importlib.util.spec_from_file_location(
    "instance_embed_mode", ROOT / "scripts" / "instance.py"
)
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


class Tagged:
    """A YAML value together with the Compose merge tag it was written with."""

    def __init__(self, tag: str, value):
        self.tag = tag
        self.value = value


def load_compose(path: Path) -> dict:
    """Parse a Compose file, keeping merge tags visible instead of rejecting them."""

    class Loader(yaml.SafeLoader):
        """SafeLoader that records Compose merge tags."""

    def tagged(loader, node):
        if isinstance(node, yaml.SequenceNode):
            return Tagged(node.tag, loader.construct_sequence(node, deep=True))
        if isinstance(node, yaml.MappingNode):
            return Tagged(node.tag, loader.construct_mapping(node, deep=True))
        return Tagged(node.tag, loader.construct_scalar(node))

    for tag in COMPOSE_TAGS:
        Loader.add_constructor(tag, tagged)
    return yaml.load(path.read_text(), Loader=Loader)


def fake_instance(embed_mode: str, staging: str):
    """An instance stub whose selection is read from the deployment environment."""
    app = ops.Instance.__new__(ops.Instance)
    app.name = "dame-curie"
    app.project = "dame-curie"
    app.env = {"DAME_CURIE_STAGING": staging, "DAME_CURIE_EMBED_MODE": embed_mode}
    return app


def deploy_text(*extra: str) -> str:
    """The required private deployment settings plus optional ones."""
    return "\n".join(
        (
            "INSTANCE_ID=dame-curie",
            "INSTANCE_DIR=/srv/dame-curie",
            "ENGINE_SOCKET=/run/user/1005/docker.sock",
            "APP_IMAGE=dame-curie-app:test",
            *extra,
        )
    )


def test_local_deployment_keeps_its_own_ollama_and_static_defaults():
    bot = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]["bot"]
    assert bot["environment"]["DAME_CURIE_EMBED_MODE"] == "local"
    assert bot["environment"]["DAME_CURIE_EMBED_BASE_URL"] == "http://ollama:11434"
    assert bot["depends_on"] == {"ollama": {"condition": "service_healthy"}}


def test_external_overlay_drops_local_embedding_services_without_touching_the_base():
    services = load_compose(OVERLAY)["services"]
    environment = services["bot"]["environment"]
    assert services["bot"]["depends_on"].tag == "!reset"
    assert environment["DAME_CURIE_EMBED_MODE"] == "external"
    assert environment["DAME_CURIE_EMBED_BASE_URL"].tag == "!reset"
    for name in ("ollama", "ollama-pull"):
        profiles = services[name]["profiles"]
        assert profiles.tag == "!override"
        assert profiles.value == ["local-embeddings"]


def test_compose_file_selection_is_derived_from_the_deployment_mode():
    assert [path.name for path in ops.compose_files(False, "local")] == ["compose.yaml"]
    assert [path.name for path in ops.compose_files(True, "local")] == [
        "compose.yaml",
        "compose.staging.yaml",
    ]
    assert [path.name for path in ops.compose_files(False, "external")] == [
        "compose.yaml",
        "compose.embeddings-external.yaml",
    ]
    assert [path.name for path in ops.compose_files(True, "external")] == [
        "compose.yaml",
        "compose.staging.yaml",
        "compose.embeddings-external.yaml",
    ]


def test_external_mode_adds_only_the_overlay_to_the_compose_command(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        ops.subprocess,
        "run",
        lambda command, **kwargs: recorded.append(command)
        or SimpleNamespace(returncode=0),
    )
    fake_instance("external", "false").compose("up", "-d", "bot")
    fake_instance("local", "false").compose("up", "-d", "bot")
    assert [value for value in recorded[0] if value.endswith(".yaml")] == [
        str(ROOT / "compose.yaml"),
        str(OVERLAY),
    ]
    assert [value for value in recorded[1] if value.endswith(".yaml")] == [
        str(ROOT / "compose.yaml")
    ]


def test_deploy_env_accepts_only_the_documented_embed_modes():
    assert "DAME_CURIE_EMBED_MODE" not in ops.parse_settings(deploy_text())
    assert (
        ops.parse_settings(deploy_text("DAME_CURIE_EMBED_MODE=external"))[
            "DAME_CURIE_EMBED_MODE"
        ]
        == "external"
    )
    with pytest.raises(ValueError, match="local or external"):
        ops.parse_settings(deploy_text("DAME_CURIE_EMBED_MODE=shared"))


def test_ownership_still_accepts_the_canonical_file_lists():
    """Both file lists the wrapper produced before this change stay valid."""
    for staging in (False, True):
        labels = {
            "com.docker.compose.project": "dame-curie",
            "com.docker.compose.service": "bot",
            "com.docker.compose.project.config_files": ",".join(
                str(path) for path in ops.compose_files(staging, "local")
            ),
        }
        item = {
            "Id": "bot",
            "Name": "/dame-curie-bot",
            "Config": {"Labels": labels},
            "State": {"Running": False},
        }
        assert ops.select_owned([item], "dame-curie", "dame-curie") == [item]


def test_ownership_accepts_every_selected_file_list_and_rejects_other_checkouts():
    labels = {
        "com.docker.compose.project": "dame-curie",
        "com.docker.compose.service": "bot",
        "com.docker.compose.project.config_files": ",".join(
            str(path) for path in ops.compose_files(True, "external")
        ),
    }
    owned = {
        "Id": "bot",
        "Name": "/dame-curie-bot",
        "Config": {"Labels": labels},
        "State": {"Running": False},
    }
    assert ops.select_owned([owned], "dame-curie", "dame-curie") == [owned]
    foreign = {
        **owned,
        "Config": {
            "Labels": {
                **labels,
                "com.docker.compose.project.config_files": str(
                    ROOT / "docker" / "compose.embeddings-external.yaml"
                ),
            }
        },
    }
    with pytest.raises(ValueError, match="another checkout"):
        ops.select_owned([foreign], "dame-curie", "dame-curie")
