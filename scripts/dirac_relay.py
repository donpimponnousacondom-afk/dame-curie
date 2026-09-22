#!/usr/bin/env python3
"""Root-run relay from the Dirac V2 container to protected V1 Ollama.

V2 and V1 are separate rootless engines, so the Dirac container can reach neither
the host loopback nor the other engine's bridge. This helper binds one private
address - the V2 instance's outbound bridge gateway, inside the V2 daemon's
network namespace - and forwards each accepted connection into the current
network namespace of the selected protected V1 Ollama container's loopback. The
target PID is resolved read-only per connection, so a V1 recreate is followed.

There is no proxy command, no user-supplied target, no V1 mutation and no
published host port. Run it as host root under its own unit; see
`phase-II_v2/DIRAC_RUNTIME_OPS.md`.
"""

import argparse
import ipaddress
import os
import pwd
import socket
import subprocess
from pathlib import Path

NSENTER, SOCAT = "/usr/bin/nsenter", "/usr/bin/socat"
TARGET_PORT, BACKLOG = 11434, 64
V2_ACCOUNT, V1_ACCOUNT = "dame-curie", "maxwell-curie"
V1_CONTAINER, V1_PROJECT, V1_SERVICE = "maxwell-curie-ollama-1", "maxwell-curie", "ollama"
TARGET_FORMAT = (
    "{{.State.Pid}}|{{.State.Running}}"
    '|{{index .Config.Labels "com.docker.compose.project"}}'
    '|{{index .Config.Labels "com.docker.compose.service"}}'
)


def engine_socket(account_name: str) -> tuple[int, str]:
    """Resolve one service account's own private rootless endpoint; there is no fallback engine."""
    account = pwd.getpwnam(account_name)
    if account.pw_uid == 0:
        raise ValueError("service account cannot be root")
    return account.pw_uid, f"unix:///run/user/{account.pw_uid}/docker.sock"


def docker_query(socket_url: str, *args: str) -> str:
    """Run one read-only query against the named engine and fail loudly instead of substituting another."""
    result = subprocess.run(["docker", "--host", socket_url, *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} failed on the selected engine")
    return result.stdout


def bridge_gateway(socket_url: str, network: str) -> str:
    """Read the private gateway of the V2 instance's outbound bridge."""
    gateway = docker_query(socket_url, "network", "inspect", network, "--format",
                           "{{(index .IPAM.Config 0).Gateway}}").strip()
    address = ipaddress.ip_address(gateway)
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError(f"refusing to bind non-private gateway {gateway}")
    return gateway


def engine_netns(pid_file: Path | None, netns: str | None, expected_uid: int) -> str:
    """Resolve the parent-verified daemon network namespace and refuse the caller's own."""
    if netns is not None:
        path = netns
    else:
        text = pid_file.read_text().strip()
        if not text.isdigit():
            raise ValueError(f"{pid_file} does not contain an engine PID")
        if os.stat(f"/proc/{text}").st_uid != expected_uid:
            raise ValueError("engine PID is not owned by the V2 service account")
        path = f"/proc/{text}/ns/net"
    current = os.stat("/proc/self/ns/net")
    target = os.stat(path)
    if (current.st_dev, current.st_ino) == (target.st_dev, target.st_ino):
        raise ValueError("engine namespace is the caller's own; refusing to bind in it")
    return path


def forward_argv(pid: int) -> list[str]:
    """The one fixed helper: enter the V1 container namespace and speak to its loopback."""
    return [NSENTER, f"--net=/proc/{pid}/ns/net", "--", SOCAT, "-", f"TCP4:127.0.0.1:{TARGET_PORT}"]


def target_pid(socket_url: str, container: str, project: str, service: str) -> int | None:
    """Resolve the running V1 Ollama PID read-only; None when it is absent, stopped or foreign."""
    result = subprocess.run(
        ["docker", "--host", socket_url, "inspect", "--type", "container", "--format", TARGET_FORMAT, container],
        capture_output=True, text=True,
    )
    fields = result.stdout.strip().split("|")
    if result.returncode or len(fields) != 4 or fields[1] != "true":
        return None
    if fields[2] != project or fields[3] != service or not fields[0].isdigit():
        return None
    pid = int(fields[0])
    return pid if pid > 0 else None


def serve(listener: socket.socket, socket_url: str, container: str, project: str, service: str) -> None:
    """Forward connections until stopped; each one re-resolves its target container."""
    while True:
        connection, _ = listener.accept()
        pid = target_pid(socket_url, container, project, service)
        if pid is None:
            connection.close()
            continue
        subprocess.Popen(forward_argv(pid), stdin=connection, stdout=connection, stderr=subprocess.DEVNULL)
        connection.close()


def main() -> None:
    """Enter the V2 daemon namespace, bind the private gateway, then forward fixed targets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-account", default=V2_ACCOUNT, help="V2 service account owning the daemon")
    parser.add_argument("--network", required=True, help="V2 instance outbound bridge name")
    namespace = parser.add_mutually_exclusive_group(required=True)
    namespace.add_argument("--engine-pid-file", type=Path, help="parent-verified rootless engine PID file")
    namespace.add_argument("--engine-netns", help="parent-verified /proc/<pid>/ns/net path")
    parser.add_argument("--v1-account", default=V1_ACCOUNT, help="protected V1 service account")
    parser.add_argument("--v1-container", default=V1_CONTAINER)
    parser.add_argument("--v1-project", default=V1_PROJECT)
    parser.add_argument("--v1-service", default=V1_SERVICE)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("the relay requires host root for setns and nsenter")
    v2_uid, v2_socket = engine_socket(args.v2_account)
    _, v1_socket = engine_socket(args.v1_account)
    gateway = bridge_gateway(v2_socket, args.network)
    fd = os.open(engine_netns(args.engine_pid_file, args.engine_netns, v2_uid), os.O_RDONLY)
    os.setns(fd)
    os.close(fd)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((gateway, TARGET_PORT))
    listener.listen(BACKLOG)
    print(f"dirac relay bound {gateway}:{TARGET_PORT} -> {args.v1_container} loopback", flush=True)
    serve(listener, v1_socket, args.v1_container, args.v1_project, args.v1_service)


if __name__ == "__main__":
    main()
