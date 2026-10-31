import errno
import inspect
import json
import shlex
import subprocess
from pathlib import Path

from . import guard
from .common import RemoteFailure
from .config import Config
from .state import Site


class Transport:
    def __init__(self, config: Config):
        self.config = config
        self.program = inspect.getsource(guard)

    def ssh(self) -> list[str]:
        known_hosts = str(self.config.known_hosts).replace("\\", "\\\\").replace('"', '\\"')
        control_path = (str(self.config.state).replace("%", "%%") + "/ssh-%C").replace("\\", "\\\\").replace('"', '\\"')
        return [
            "ssh", "-F", "/dev/null", "-i", str(self.config.key),
            "-p", str(self.config.port), "-o", "IdentityAgent=none",
            "-o", "IdentityFile=none", "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f'UserKnownHostsFile="{known_hosts}"',
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes",
            "-o", "ForwardAgent=no", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
            "-o", "ControlMaster=auto", "-o", "ControlPersist=60",
            "-o", f'ControlPath="{control_path}"',
        ]

    def request(self, action: str, roots: list[list[int]], name: str, site: Site):
        return {
            "action": action, "site_root": self.config.site_root,
            "image_root": self.config.image_root, "roots": roots,
            "name": name, "token": site.token, "site_identity": site.identity,
            "marker_namespace": self.config.marker_namespace,
        }

    def command(self, request: dict | None = None) -> str:
        payload = "-" if request is None else json.dumps(request, ensure_ascii=True)
        return shlex.join(["python3", "-I", "-S", "-c", self.program, payload])

    def control(self, request: dict) -> dict:
        argv = [*self.ssh(), f"{self.config.user}@{self.config.host}", self.command()]
        result = self.execute(argv, capture=True, operation=f"{request['action']} {request['name']!r}",
                              input_data=json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode())
        try:
            data = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise RemoteFailure("remote response refused") from None
        if not isinstance(data, dict):
            raise RemoteFailure("remote response refused")
        return data

    def sync(self, source: Path, request: dict, delete: bool) -> None:
        argv = [
            "rsync", "--recursive", "--times", "--omit-dir-times", "--checksum",
            "--perms", "--chmod=D755,F755", "--no-links", "--no-devices", "--no-specials",
            "--protect-args", f"--timeout={self.config.timeout_seconds}",
            "-e", shlex.join(self.ssh()), "--rsync-path", self.command(request),
        ]
        if delete:
            if request["action"] != "site" or not request["name"] or not request["token"]:
                raise RemoteFailure("non-site deletion refused")
            marker_name = f".{request['marker_namespace']}-publisher-owner"
            # Root, 1 November 2026: top-level hidden folders of a site belong to
            # the remote (for example .data written by a server script); a sync
            # never deletes them. Everything else follows the local tree.
            argv.extend([
                "--delete-delay", "--filter", f"P /{marker_name}", "--filter", f"H /{marker_name}",
                "--filter", "P /.*/",
            ])
        argv.extend(["--", str(source) + "/", f"{self.config.user}@{self.config.host}:./"])
        self.execute(argv, capture=False, operation=f"{request['action']} {request['name']!r}")

    def execute(
        self, argv: list[str], capture: bool, operation: str = "remote", input_data: bytes | None = None,
    ) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                argv, stdin=subprocess.DEVNULL if input_data is None else None, input=input_data,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=self.config.timeout_seconds, check=False,
            )
        except OSError as error:
            raise RemoteFailure(f"{operation}: cannot start {argv[0]}: {errno.errorcode.get(error.errno, 'UNKNOWN')}") from None
        except subprocess.TimeoutExpired:
            raise RemoteFailure(f"{operation}: {argv[0]} timed out after {self.config.timeout_seconds}s") from None
        if result.returncode:
            lines = result.stderr.decode("utf-8", errors="replace").splitlines()
            detail = next((line for line in lines if line.startswith("publisher-guard: ")), "")
            if not detail:
                reasons = (
                    "Host key verification failed", "REMOTE HOST IDENTIFICATION HAS CHANGED",
                    "Permission denied", "Connection refused", "Connection timed out",
                    "No route to host", "Could not resolve hostname", "No space left on device",
                    "Disk quota exceeded", "Read-only file system", "Connection reset by peer",
                )
                detail = next((reason for reason in reasons if any(reason in line for line in lines)), "")
            if not detail:
                detail = "no guard diagnostic received"
            raise RemoteFailure(f"{operation}: {argv[0]} exit={result.returncode}: {detail}")
        return result
