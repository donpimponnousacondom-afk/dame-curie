#!/usr/bin/env python3
"""Operate the durable Dirac V2 debug bot on the dame-curie rootless engine.

Dirac is the debug instance: one uniquely named container with its own private
state root, derived configuration and image selector. It never reads canonical
credentials and never touches the canonical Compose project. Mutations serialize
on the canonical operations lock, so a Dirac start cannot interleave with
`scripts/instance.py`. The container joins the canonical outbound bridge because
the shared RAG relay listens on that bridge's gateway inside the V2 daemon's
network namespace. Layout and acceptance steps: `phase-II_v2/DIRAC_RUNTIME_OPS.md`.
"""

import argparse
import fcntl
import ipaddress
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

if __package__:
    from scripts.instance import Instance, require_private, service_account
    from scripts.log_filter import follow_logs
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I/-P drop the script directory
    from instance import Instance, require_private, service_account
    from log_filter import follow_logs

ACCOUNT, NAME = "dame-curie", "dirac-v2"
INSTANCE_ID, LABEL_KEY, STATE_SUBDIR, IMAGE_SELECTOR = "dame-curie-dirac", "dame-curie.dirac", "dirac", "image"
CONTAINER_LABEL = f"{LABEL_KEY}={NAME}"
EMBED_PORT = 11434
CHECK_PROGRAM = "/opt/dame-curie/check_embeddings.py"
ENTRY_SCRIPT = 'python /opt/dame-curie/check_embeddings.py && exec "$@"'
COMMAND = ("python", "bot.py")
READY_TIMEOUT, READY_INTERVAL, STOP_TIMEOUT = 300.0, 5.0, "45"
LOCALTIME_MOUNT = "type=bind,src=/etc/localtime,dst=/etc/dame-curie-localtime,readonly"
BINDS = (
    ("config", "/config", True),
    ("config/prompts", "/config/prompts", False),
    ("data", "/state/data", False),
    ("sites", "/state/sites", False),
    ("shell", "/state/shell", False),
)
ENVIRONMENT = (
    ("TZ", ":/etc/dame-curie-localtime"),
    ("HOME", "/home/dame-curie"),
    ("DAME_CURIE_ENV_FILE", "/config/bot.env"),
    ("DAME_CURIE_CONTAINER_MODE", "true"),
    ("DAME_CURIE_INSTANCE_ID", INSTANCE_ID),
    ("DAME_CURIE_EMBED_MODE", "external"),
)
SMOKE_MOUNTS = {
    "smoke_root": ("/smoke", "DAME_CURIE_DIRAC_SMOKE_CONFIG", "/smoke/config.json"),
    "smoke_status": ("/smoke-status", None, None),
}
SMOKE_READ_ONLY = frozenset({"smoke_root"})
REQUIRED_ROOTS = {
    "DATA_DIR": "/state/data",
    "DAME_CURIE_SITE_DIR": "/state/sites",
    "DAME_CURIE_PROMPTS_DIR": "/config/prompts",
}
PINNED_VALUES = {"DAME_CURIE_CONTAINER_MODE": "true", "DAME_CURIE_INSTANCE_ID": INSTANCE_ID}
DISABLED = {"0", "false", "no", "off"}
STATE_FIELDS = ("status", "exit_code", "oom_killed", "finished_at", "image_id", "image_ref")
STATE_FORMAT = "{{.State.Status}}|{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.State.FinishedAt}}|{{.Image}}|{{.Config.Image}}"


def parse_args() -> argparse.Namespace:
    """Parse the operator surface; image, replace and smoke mounts apply to start only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop", "restart", "logs"))
    parser.add_argument("--image", help="start only: local image reference; missing images are never pulled")
    parser.add_argument("--replace", action="store_true",
                        help="start only: remove a stopped owned container after reporting why it stopped")
    parser.add_argument("--no-keys", action="store_true", help="logs only: disable screen keyboard controls")
    parser.add_argument("--fresh", action="store_true",
                        help="logs only: follow new output only, without replaying the retained tail")
    parser.add_argument("--smoke-root", type=Path, metavar="HOST",
                        help="start only: smoke root holding config.json and requests/, mounted read-only")
    parser.add_argument("--smoke-status", type=Path, metavar="HOST",
                        help="start only: writable smoke status directory")
    args = parser.parse_args()
    if args.action != "start" and (args.image or args.replace or args.smoke_root or args.smoke_status):
        parser.error("--image, --replace, --smoke-root and --smoke-status are only available for start")
    if args.action != "logs" and (args.no_keys or args.fresh):
        parser.error("--no-keys and --fresh are only available for logs")
    return args


def smoke_sources(root: Path, uid: int, args: argparse.Namespace) -> dict[str, Path]:
    """Accept only private smoke directories inside the Dirac root; canonical state is never mountable.

    A writable smoke directory may not be the Dirac root itself and may not
    equal, contain or sit inside a read-only mount of this container, because
    either direction of that overlap makes the read-only tree writable through
    the second mount.
    """
    sources: dict[str, Path] = {}
    for option in SMOKE_MOUNTS:
        source = getattr(args, option)
        if source is None:
            continue
        flag = option.replace("_", "-")
        if not source.is_absolute() or not source.resolve().is_relative_to(root):
            raise ValueError(f"--{flag} must live inside {root}")
        if source.is_symlink() or not source.is_dir():
            raise ValueError(f"--{flag} must be a real directory: {source}")
        require_private(source, uid)
        sources[option] = source
    read_only = [*((root / relative).resolve() for relative, _, readonly in BINDS if readonly),
                 *(source.resolve() for option, source in sources.items() if option in SMOKE_READ_ONLY)]
    for option, source in sources.items():
        if option in SMOKE_READ_ONLY:
            continue
        flag = option.replace("_", "-")
        target = source.resolve()
        if root.is_relative_to(target):
            raise ValueError(f"--{flag} must not mount the Dirac root itself: {source}")
        for path in read_only:
            if target.is_relative_to(path) or path.is_relative_to(target):
                raise ValueError(f"--{flag} must not overlap the read-only mount {path}")
    return sources


def state_root(instance: Instance, uid: int) -> Path:
    """Require the parent-created private Dirac root and its five bot roots."""
    root = instance.path / STATE_SUBDIR
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"missing Dirac state root: {root}")
    require_private(root, uid)
    for relative, _, _ in BINDS:
        path = root / relative
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"missing Dirac state directory: {relative}")
        require_private(path, uid)
    return root


def pinned_image(instance: Instance, root: Path, uid: int, requested: str | None) -> str:
    """Resolve one local image to its immutable ID; a missing image fails instead of pulling."""
    reference = requested
    if reference is None:
        selector = root / IMAGE_SELECTOR
        if selector.is_symlink() or not selector.is_file():
            raise ValueError(f"start requires --image or a private {selector} selector")
        require_private(selector, uid, directory=False)
        reference = selector.read_text().strip()
    if not reference or any(char.isspace() for char in reference):
        raise ValueError("image selection must be one literal reference")
    return instance.docker("image", "inspect", reference, "--format", "{{.Id}}").strip()


def outbound_bridge(instance: Instance) -> tuple[str, str]:
    """Require this instance's outbound bridge and read its private gateway."""
    name = f"{instance.name}_outbound"
    if name not in instance.docker("network", "ls", "--format", "{{.Name}}").split():
        raise ValueError(f"missing canonical outbound bridge {name}; the shared RAG relay needs it")
    fields = instance.docker(
        "network", "inspect", name, "--format",
        '{{index .Labels "com.docker.compose.project"}}'
        '|{{index .Labels "com.docker.compose.network"}}'
        "|{{(index .IPAM.Config 0).Gateway}}",
    ).strip().split("|")
    if fields[:2] != [instance.name, "outbound"]:
        raise ValueError(f"{name} is not this instance's outbound bridge")
    address = ipaddress.ip_address(fields[2])
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError(f"refusing to bind non-private gateway {fields[2]}")
    return name, fields[2]


def derived_config(root: Path, uid: int, gateway: str) -> tuple[bool, str]:
    """Validate Dirac's private derived bot.env; return (rag_enabled, problem) without reporting credentials.

    A missing or unreadable file reports no known value; a mismatch reports the
    RAG switch that was read, so a caller can still tell whether the endpoint
    rule applies.
    """
    path = root / "config" / "bot.env"
    if path.is_symlink() or not path.is_file():
        return False, f"missing private derived config: {path}"
    try:
        require_private(path, uid, directory=False)
        values = dotenv_values(path)
        enabled = str(values.get("ENABLE_RAG") or "auto").strip().lower() not in DISABLED
        endpoint = urlsplit(str(values.get("DAME_CURIE_EMBED_BASE_URL") or ""))
        port = endpoint.port
    except (OSError, ValueError):
        return False, "derived config is unreadable or not private"
    for key, expected in REQUIRED_ROOTS.items():
        if values.get(key) != expected:
            return enabled, f"derived bot.env must set {key}={expected}"
    for key, expected in PINNED_VALUES.items():
        if key in values and values[key] != expected:
            return enabled, f"derived bot.env must not override {key}={expected}"
    if enabled and (
        endpoint.scheme != "http"
        or port != EMBED_PORT
        or endpoint.path not in {"", "/"}
        or endpoint.hostname != gateway
    ):
        return enabled, f"derived DAME_CURIE_EMBED_BASE_URL must be http://{gateway}:{EMBED_PORT} while RAG is enabled"
    return enabled, ""


def owned_container(instance: Instance) -> str | None:
    """Return the Dirac container ID; ownership needs both the reserved label and the reserved name."""
    ids = instance.docker("ps", "-aq", "--filter", f"label={CONTAINER_LABEL}").split()
    if not ids:
        return None
    if len(ids) > 1:
        raise ValueError(f"multiple containers carry {CONTAINER_LABEL}; resolve them before operating")
    name = instance.docker("inspect", ids[0], "--format", "{{.Name}}").strip()
    if name != f"/{NAME}":
        raise ValueError(f"reserved label {CONTAINER_LABEL} is held by {name}; refusing")
    return ids[0]


def container_state(instance: Instance, container: str) -> dict[str, str]:
    """Read the bounded state fields used for reporting; container environment is never printed."""
    values = instance.docker("inspect", container, "--format", STATE_FORMAT).strip().split("|")
    return dict(zip(STATE_FIELDS, values, strict=True))


def create_arguments(root: Path, image: str, bridge: str, smoke: dict[str, Path]) -> list[str]:
    """Build the pinned debug container; no pull, no Docker socket, no added capability."""
    arguments = [
        "create", "--name", NAME, "--label", CONTAINER_LABEL, "--init",
        "--user", "0:0", "--restart", "no", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "256", "--memory", "4g",
        "--cpus", "4", "--stop-timeout", STOP_TIMEOUT, "--pull", "never", "--network", bridge,
        "--log-driver", "local", "--log-opt", "max-size=10m", "--log-opt", "max-file=3",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
        "--tmpfs", "/app/temp:rw,nosuid,nodev,size=256m,mode=1777",
        "--mount", LOCALTIME_MOUNT,
    ]
    for key, value in ENVIRONMENT:
        arguments += ["--env", f"{key}={value}"]
    for relative, target, readonly in BINDS:
        arguments += ["--mount", f"type=bind,src={root / relative},dst={target}{',readonly' if readonly else ''}"]
    for option, (target, variable, value) in SMOKE_MOUNTS.items():
        source = smoke.get(option)
        if source is None:
            continue
        suffix = ",readonly" if option in SMOKE_READ_ONLY else ""
        arguments += ["--mount", f"type=bind,src={source},dst={target}{suffix}"]
        if variable is not None:
            arguments += ["--env", f"{variable}={value}"]
    return [*arguments, "--entrypoint", "/bin/sh", image, "-ec", ENTRY_SCRIPT, "--", *COMMAND]


def embedding_readiness(instance: Instance, enabled: bool) -> str:
    """Run the reviewed in-image check and report only its outcome class, never provider text."""
    if not enabled:
        return "skipped: ENABLE_RAG is off in the derived config"
    result = subprocess.run(["docker", "exec", NAME, "python", CHECK_PROGRAM],
                            env=instance.env, capture_output=True, text=True)
    if result.returncode == 0:
        return "ok"
    return f"failed: exit {result.returncode}"


def wait_ready(instance: Instance, container: str, enabled: bool, timeout: float) -> str:
    """Poll the reviewed check until it passes, the container leaves running, or the deadline passes."""
    deadline = time.monotonic() + timeout
    while True:
        readiness = embedding_readiness(instance, enabled)
        if readiness == "ok" or readiness.startswith("skipped"):
            return readiness
        state = container_state(instance, container)["status"]
        if state in {"exited", "dead"}:
            return f"{readiness}; container is {state}"
        if time.monotonic() >= deadline:
            return f"{readiness}; gave up after {timeout:g}s"
        time.sleep(READY_INTERVAL)


def prepared(instance: Instance, uid: int) -> tuple[Path, bool, str, str]:
    """Validate the private layout and derived config against the live bridge gateway."""
    root = state_root(instance, uid)
    bridge, gateway = outbound_bridge(instance)
    enabled, problem = derived_config(root, uid, gateway)
    if problem:
        raise ValueError(problem)
    return root, enabled, bridge, gateway


def endpoint(gateway: str) -> str:
    """The one embedding endpoint the relay serves on the V2 outbound bridge."""
    return f"http://{gateway}:{EMBED_PORT}"


def start(instance: Instance, uid: int, args: argparse.Namespace) -> dict[str, object]:
    """Create and start Dirac, keeping failure evidence instead of deleting the old container."""
    root, enabled, bridge, gateway = prepared(instance, uid)
    smoke = smoke_sources(root, uid, args)
    image = pinned_image(instance, root, uid, args.image)
    existing = owned_container(instance)
    if existing is not None:
        state = container_state(instance, existing)
        if state["status"] == "running":
            raise ValueError(f"{NAME} is already running; use restart, stop or status")
        if not args.replace:
            raise ValueError(
                f"{NAME} exists in state {state['status']} (exit {state['exit_code']}, "
                f"finished {state['finished_at']}, image {state['image_ref']}, oom {state['oom_killed']}); "
                "follow logs, then rerun start --replace"
            )
        print(json.dumps({"replacing": NAME, "previous": state}, sort_keys=True), file=sys.stderr)
        instance.docker("rm", existing)
    container = instance.docker(*create_arguments(root, image, bridge, smoke)).strip()
    instance.docker("start", container)
    return {"action": "start", "container": NAME, "id": container, "image": image, "bridge": bridge,
            "endpoint": endpoint(gateway),
            "embedding_readiness": wait_ready(instance, container, enabled, READY_TIMEOUT)}


def restart(instance: Instance, uid: int) -> dict[str, object]:
    """Restart only a running owned container; preserve stopped failure evidence."""
    container = owned_container(instance)
    if container is None:
        raise ValueError(f"{NAME} does not exist; use start")
    state = container_state(instance, container)
    if state["status"] != "running":
        raise ValueError(
            f"{NAME} exists in state {state['status']} (exit {state['exit_code']}, "
            f"finished {state['finished_at']}, image {state['image_ref']}, "
            f"oom {state['oom_killed']}); follow logs, then use start --replace"
        )
    _, enabled, bridge, gateway = prepared(instance, uid)
    instance.docker("restart", "--time", STOP_TIMEOUT, container)
    return {"action": "restart", "container": NAME, "id": container, "bridge": bridge,
            "endpoint": endpoint(gateway),
            "embedding_readiness": wait_ready(instance, container, enabled, READY_TIMEOUT)}


def stop(instance: Instance) -> dict[str, object]:
    """Stop the owned container and keep it, so exit state and logs survive."""
    container = owned_container(instance)
    if container is None:
        return {"action": "stop", "container": NAME, "present": False, "stopped": False}
    state = container_state(instance, container)
    if state["status"] != "running":
        return {"action": "stop", "container": NAME, "present": True, "stopped": False,
                "state": state["status"], "exit_code": state["exit_code"], "note": "already stopped; evidence kept"}
    instance.docker("stop", "--time", STOP_TIMEOUT, container)
    return {"action": "stop", "container": NAME, "present": True, "stopped": True}


def status(instance: Instance, uid: int) -> tuple[dict[str, object], int]:
    """Inspect Docker metadata and private config; exec the embedding check when eligible.

    Docker inspection and the derived-config read do not change container state;
    the embedding check runs inside a running container via ``docker exec``.
    Container ownership or inspect failures still raise; independent bridge and
    private-layout validation failures retain already verified state metadata.
    """
    container = owned_container(instance)
    report: dict[str, object] = {"action": "status", "container": NAME, "present": container is not None}
    if container is not None:
        report.update(container_state(instance, container))
    if container is None:
        skip = "no owned container"
    elif report["status"] != "running":
        skip = f"container is {report['status']}"
    else:
        skip = ""
    try:
        bridge, gateway = outbound_bridge(instance)
    except ValueError:
        report["config"] = "unavailable: outbound bridge validation failed"
        report["embedding_readiness"] = f"skipped: {skip or 'outbound bridge validation failed'}"
        return report, 1
    report.update(bridge=bridge, endpoint=endpoint(gateway))
    try:
        root = state_root(instance, uid)
    except (OSError, ValueError):
        report["config"] = "unavailable: private Dirac layout validation failed"
        report["embedding_readiness"] = f"skipped: {skip or 'private Dirac layout unavailable'}"
        return report, 1
    enabled, problem = derived_config(root, uid, gateway)
    report["config"] = problem or "ok"
    code = 1
    if skip:
        report["embedding_readiness"] = f"skipped: {skip}"
    elif problem:
        report["embedding_readiness"] = "skipped: derived config failed validation"
    else:
        report["embedding_readiness"] = embedding_readiness(instance, enabled)
        code = 1 if str(report["embedding_readiness"]).startswith("failed") else 0
    return report, code


def logs(instance: Instance, no_keys: bool, *, fresh: bool = False) -> None:
    """Follow the Dirac container through the existing screen log viewer."""
    container = owned_container(instance)
    if container is None:
        raise ValueError(f"{NAME} does not exist; nothing to follow")
    follow_logs(["docker", "logs", "--follow", "--tail", "0" if fresh else "100", container], instance.env,
                output_format="screen", no_keys=no_keys)


def main() -> None:
    """Dispatch one operator action under the canonical operations lock."""
    args = parse_args()
    if args.action == "logs":
        sys.dont_write_bytecode = True
    account = service_account(ACCOUNT, for_logs=args.action == "logs",
                              entrypoint=Path(__file__).resolve())
    instance = Instance(ACCOUNT, account)
    if args.action == "logs":
        logs(instance, args.no_keys, fresh=args.fresh)
        return
    if args.action == "status":
        report, code = status(instance, account.pw_uid)
        print(json.dumps(report, sort_keys=True))
        sys.exit(code)
    fd = os.open(instance.path / ".operations.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "start":
            report = start(instance, account.pw_uid, args)
        elif args.action == "stop":
            report = stop(instance)
        else:
            report = restart(instance, account.pw_uid)
    print(json.dumps(report, sort_keys=True))
    if str(report.get("embedding_readiness", "ok")).startswith("failed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
