import inspect
import json
import shlex
import subprocess
from pathlib import Path

from . import guard
from .common import MARKER, RemoteFailure
from .config import Config
from .state import Site


class Transport:
    def __init__(self, config: Config):
        self.config = config
        self.program = inspect.getsource(guard)

    def ssh(self) -> list[str]:
        known_hosts = str(self.config.known_hosts).replace("\\", "\\\\").replace('"', '\\"')
        return [
            "ssh", "-F", "/dev/null", "-i", str(self.config.key),
            "-p", str(self.config.port), "-o", "IdentityAgent=none",
            "-o", "IdentityFile=none", "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f'UserKnownHostsFile="{known_hosts}"',
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes",
            "-o", "ForwardAgent=no", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
        ]

    def request(self, action: str, roots: list[list[int]], name: str, site: Site):
        return {
            "action": action, "site_root": self.config.site_root,
            "image_root": self.config.image_root, "roots": roots,
            "name": name, "token": site.token, "site_identity": site.identity,
        }

    def command(self, request: dict) -> str:
        return shlex.join(["python3", "-I", "-S", "-c", self.program, json.dumps(request, ensure_ascii=True)])

    def control(self, request: dict) -> dict:
        argv = [*self.ssh(), f"{self.config.user}@{self.config.host}", self.command(request)]
        result = self.execute(argv, capture=True)
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
            "--perms", "--chmod=D755,F644", "--no-links", "--no-devices", "--no-specials",
            "--protect-args", f"--timeout={self.config.timeout_seconds}",
            "-e", shlex.join(self.ssh()), "--rsync-path", self.command(request),
        ]
        if delete:
            if request["action"] != "site" or not request["name"] or not request["token"]:
                raise RemoteFailure("non-site deletion refused")
            argv.extend(["--delete-delay", "--filter", f"P /{MARKER}", "--filter", f"H /{MARKER}"])
        argv.extend(["--", str(source) + "/", f"{self.config.user}@{self.config.host}:./"])
        self.execute(argv, capture=False)

    def execute(self, argv: list[str], capture: bool) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                argv, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=self.config.timeout_seconds, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RemoteFailure("remote transport unavailable") from None
        if result.returncode:
            raise RemoteFailure("remote operation refused or failed")
        return result
