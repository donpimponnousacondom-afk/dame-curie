#!/usr/bin/env python3
"""Operate one private rootless Maxwell deployment without loading bot secrets."""

import argparse
import fcntl
import json
import os
import posixpath
import pwd
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
ROOTS = ("config", "data", "sites", "shell")
SETTINGS = {"INSTANCE_ID", "INSTANCE_DIR", "ENGINE_SOCKET", "APP_IMAGE", "WEB_IMAGE", "WEB_PORT"}
SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?")
IMAGE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._/:@-]*")

ARCHIVE_PROGRAM = '''import sys, tarfile
from pathlib import Path
roots = ("config", "data", "sites", "shell")
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", pax_headers={"maxwell.instance": sys.argv[1]}) as archive:
    for root in roots:
        archive.add(Path("/instance") / root, arcname=root)
'''
RESTORE_PROGRAM = '''import sys, tarfile
from pathlib import Path
maps = {}
for kind in ("uid", "gid"):
    maps[kind] = [tuple(map(int, line.split())) for line in Path("/proc/self/" + kind + "_map").read_text().splitlines()]
def owned_filter(member, destination):
    result = tarfile.data_filter(member, destination)
    for kind in ("uid", "gid"):
        value = getattr(member, kind)
        if not any(start <= value < start + count for start, outside, count in maps[kind]):
            raise ValueError("archive owner is outside the rootless mapping")
        setattr(result, kind, value)
    result.uname = result.gname = None
    return result
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
    archive.extractall("/instance", filter=owned_filter)
'''


def parse_settings(text: str) -> dict[str, str]:
    """Parse literal deployment settings; expansion and shell syntax are forbidden."""
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in SETTINGS or key in values:
            raise ValueError("unknown or duplicate deploy.env setting")
        if not value or any(char.isspace() for char in value) or any(char in value for char in "'\"`$\\;"):
            raise ValueError("deploy.env values must be unquoted literals")
        values[key] = value
    if values.keys() != SETTINGS:
        raise ValueError("deploy.env must contain exactly the documented settings")
    return values


def service_account(instance: str, *, for_logs: bool = False):
    """Select the fixed service identity, dropping host root before any I/O."""
    if not SLUG.fullmatch(instance):
        raise ValueError("instance must be a lowercase slug of 1-30 characters")
    account = pwd.getpwnam(f"maxwell-{instance}")
    if account.pw_uid == 0:
        raise ValueError("service account cannot be root")
    if os.geteuid() == 0:
        terminal_settings = []
        if for_logs:
            if "TERM" in os.environ:
                terminal_settings.append(f"TERM={os.environ['TERM']}")
            if "NO_COLOR" in os.environ:
                terminal_settings.append("NO_COLOR=1")
        os.execv("/usr/sbin/runuser", [
            "runuser", "-u", account.pw_name, "--", "/usr/bin/env", "-i",
            f"HOME={account.pw_dir}", "PATH=/usr/local/bin:/usr/bin:/bin",
            f"XDG_RUNTIME_DIR=/run/user/{account.pw_uid}", *terminal_settings,
            sys.executable, *(("-B",) if for_logs else ()), str(Path(__file__).resolve()), *sys.argv[1:],
        ])
    if os.geteuid() != account.pw_uid:
        raise ValueError("run as host root or the instance's own service user")
    return account


def require_private(path: Path, uid: int, *, directory: bool = True) -> None:
    """Reject redirected or shared instance state before following it."""
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("instance paths cannot contain symlinks")
    info = path.stat()
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    forbidden = 0o067 if directory else 0o077
    if not expected_type(info.st_mode) or info.st_uid != uid or info.st_mode & forbidden:
        raise ValueError(f"{path.name} must be private and owned by the service user")


class Instance:
    """A validated service account, deployment file, and private Docker endpoint."""

    def __init__(self, name: str, account):
        self.name = name
        self.path = Path("/srv/maxwell") / name
        self.project = f"maxwell-{name}"
        require_private(self.path, account.pw_uid)
        deploy = self.path / "deploy.env"
        require_private(deploy, account.pw_uid, directory=False)
        self.values = parse_settings(deploy.read_text())
        socket = Path(f"/run/user/{account.pw_uid}/docker.sock")
        expected = {"INSTANCE_ID": name, "INSTANCE_DIR": str(self.path), "ENGINE_SOCKET": str(socket)}
        if any(self.values[key] != value for key, value in expected.items()):
            raise ValueError("deployment identity, directory, or engine socket mismatch")
        if socket.is_symlink() or not stat.S_ISSOCK(socket.stat().st_mode) or socket.stat().st_uid != account.pw_uid:
            raise ValueError("engine socket is not owned by the service user")
        if not all(IMAGE.fullmatch(self.values[key]) for key in ("APP_IMAGE", "WEB_IMAGE")):
            raise ValueError("invalid image reference")
        if not self.values["WEB_PORT"].isdigit() or not 1024 <= int(self.values["WEB_PORT"]) <= 65535:
            raise ValueError("WEB_PORT must be between 1024 and 65535")
        self.env = {"HOME": account.pw_dir, "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "XDG_RUNTIME_DIR": str(socket.parent), "DOCKER_HOST": f"unix://{socket}",
                    "COMPOSE_DISABLE_ENV_FILE": "1", **self.values}
        info = json.loads(self.docker("info", "--format", "{{json .}}"))
        if not any(option == "name=rootless" or option.startswith("name=rootless,")
                   for option in info.get("SecurityOptions", [])):
            raise ValueError("Docker endpoint is not rootless; refusing rootful fallback")
        for root in ROOTS:
            directory = self.path / root
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError(f"missing or redirected state directory: {root}")

    def docker(self, *args: str) -> str:
        result = subprocess.run(["docker", *args], env=self.env, capture_output=True, text=True)
        if result.returncode or result.stderr.strip():
            raise RuntimeError(f"Docker {args[0]} failed or wrote diagnostics; inspect the private engine directly")
        return result.stdout

    def compose(self, *args: str, log_format: str = "auto") -> None:
        command = ["docker", "compose", "--project-name", self.project,
                   "--project-directory", str(CHECKOUT), "--env-file", "/dev/null",
                   "-f", str(CHECKOUT / "compose.yaml"), *args]
        if args[0] == "logs":
            if __name__ == "__main__" and not __package__:
                from log_filter import follow_logs
            else:
                from scripts.log_filter import follow_logs
            follow_logs(command, self.env, output_format=log_format)
        else:
            result = subprocess.run(command, env=self.env)
            if result.returncode:
                raise RuntimeError("Compose command failed")

    def inventory(self) -> list[dict]:
        ids = self.docker("ps", "-aq").split()
        containers = json.loads(self.docker("inspect", *ids)) if ids else []
        return select_owned(containers, self.name, self.project)

    def helper(self, program: str, *, writable: bool = False) -> list[str]:
        args = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
                "--label", f"maxwell.instance={self.name}", "--label", "maxwell.kind=backup",
                "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE", "--cap-add", "CHOWN",
                "--cap-add", "FOWNER", "--security-opt", "no-new-privileges:true"]
        for root in ROOTS:
            mode = "" if writable else ",readonly"
            args += ["--mount", f"type=bind,src={self.path / root},dst=/instance/{root}{mode}"]
        return [*args, "--entrypoint", "python", self.values["APP_IMAGE"], "-c", program, self.name]


def select_owned(containers: list[dict], name: str, project: str) -> list[dict]:
    """Require ownership labels before any container can be stopped or removed."""
    owned = []
    for item in containers:
        labels = item.get("Config", {}).get("Labels") or {}
        compose = labels.get("com.docker.compose.project") == project
        managed = labels.get("maxwell.instance") == name
        matching_name = item.get("Name", "").lstrip("/").startswith(project + "-")
        if not (compose or managed or matching_name):
            continue
        if compose:
            if labels.get("maxwell.instance", name) != name:
                raise ValueError("conflicting instance ownership labels")
            if labels.get("com.docker.compose.service") not in {"bot", "api", "web", "ollama", "ollama-pull"}:
                raise ValueError("unexpected service in instance project")
            if labels.get("com.docker.compose.project.config_files") != str(CHECKOUT / "compose.yaml"):
                raise ValueError("Compose container belongs to another checkout")
        elif not managed or labels.get("maxwell.kind") not in {"shell", "site"}:
            raise ValueError("container name has missing or foreign ownership labels")
        owned.append(item)
    return owned


def writer_order(item: dict) -> int:
    labels = item["Config"].get("Labels") or {}
    return {"bot": 0, "api": 1, "web": 3, "ollama": 4, "ollama-pull": 4}.get(labels.get("com.docker.compose.service"), 2)


def stop_running(instance: Instance, containers: list[dict]) -> None:
    for item in sorted(containers, key=writer_order):
        if item["State"]["Running"]:
            instance.docker("stop", "--time", "45", item["Id"])


def quiesce(instance: Instance, running: list[dict]) -> list[dict]:
    """Stop container creators before discovering their final set of children."""
    containers = instance.inventory()
    running.extend(item for item in containers if item["State"]["Running"])
    stop_running(instance, [item for item in containers if writer_order(item) < 2])
    containers = instance.inventory()
    known = {item["Id"] for item in running}
    running.extend(item for item in containers if item["State"]["Running"] and item["Id"] not in known)
    stop_running(instance, [item for item in containers if writer_order(item) >= 2])
    return containers


def lifecycle(instance: Instance, action: str, *, log_format: str = "auto") -> None:
    if action in {"stop", "down"}:
        containers = quiesce(instance, [])
        if action == "down":
            for item in containers:
                labels = item["Config"].get("Labels") or {}
                if labels.get("maxwell.kind") in {"site", "shell"}:
                    instance.docker("rm", item["Id"])
            instance.compose("down", "--timeout", "45")
    else:
        instance.inventory()
        if action == "restart":
            instance.compose("restart", "--timeout", "45", "bot", "api")
        elif action in {"up", "start"}:
            instance.compose("up", "-d", "--wait", "--wait-timeout", "300")
        else:
            instance.compose("logs", "--follow", "--tail", "100", log_format=log_format)


def archive_outside(path: Path, instance: Instance) -> Path:
    target = path.expanduser().absolute()
    if any(parent.is_symlink() for parent in (target, *target.parents)):
        raise ValueError("archive path cannot contain symlinks")
    target = target.resolve()
    if target.is_relative_to(instance.path):
        raise ValueError("archive must be outside the instance directory")
    return target


def backup(instance: Instance, destination: Path) -> None:
    """Stop all writers, stream only state roots, and restore the running set."""
    destination = archive_outside(destination, instance)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    running = []
    complete = False
    try:
        with os.fdopen(fd, "wb") as output:
            quiesce(instance, running)
            result = subprocess.run(instance.helper(ARCHIVE_PROGRAM), env=instance.env,
                                    stdout=output, stderr=subprocess.PIPE)
            if result.returncode or result.stderr.strip():
                raise RuntimeError("backup helper failed; archive is incomplete")
            output.flush()
            os.fsync(output.fileno())
            complete = True
    finally:
        if not complete:
            destination.unlink(missing_ok=True)
        if running:
            ids = [item["Id"] for item in sorted(running, key=writer_order, reverse=True)]
            instance.docker("start", *ids)


def validate_archive(archive: tarfile.TarFile, expected_instance: str) -> None:
    """Accept only same-identity data files, directories, and in-root links."""
    if archive.pax_headers.get("maxwell.instance") != expected_instance:
        raise ValueError("archive identity mismatch; cross-instance cloning is unsupported")
    members = archive.getmembers()
    names = {}
    links = set()
    for member in members:
        name = member.name.rstrip("/")
        parts = name.split("/")
        if not name or name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("unsafe archive member path")
        if parts[0] not in ROOTS or name in names:
            raise ValueError("unexpected or duplicate archive root/member")
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError("archive contains a special file")
        if member.uid < 0 or member.gid < 0:
            raise ValueError("archive contains invalid numeric ownership")
        if len(parts) == 1 and not member.isdir():
            raise ValueError("archive roots must be directories")
        if member.issym() or member.islnk():
            target = member.linkname
            base = posixpath.dirname(name) if member.issym() else ""
            resolved = posixpath.normpath(posixpath.join(base, target))
            if target.startswith("/") or resolved.split("/")[0] != parts[0]:
                raise ValueError("archive link escapes its state root")
            links.add(name)
        names[name] = member
    for name, member in names.items():
        if any(str(parent) in links for parent in Path(name).parents):
            raise ValueError("archive member descends through a link")
        if member.islnk():
            target = names.get(posixpath.normpath(member.linkname))
            if target is None or not target.isfile():
                raise ValueError("hardlink must reference a regular archived file")
    if not all(root in names for root in ROOTS):
        raise ValueError("archive must contain all four state directories")


def restore(instance: Instance, source: Path) -> None:
    """Restore into empty directories only; never start services automatically."""
    source = archive_outside(source, instance)
    if instance.inventory():
        raise ValueError("restore requires a fresh instance without owned containers")
    if any(any((instance.path / root).iterdir()) for root in ROOTS):
        raise ValueError("restore refuses nonempty state directories")
    with source.open("rb", buffering=0) as archive_file:
        with tarfile.open(fileobj=archive_file, mode="r:*") as archive:
            validate_archive(archive, instance.name)
        archive_file.seek(0)
        result = subprocess.run(instance.helper(RESTORE_PROGRAM, writable=True), env=instance.env,
                                stdin=archive_file, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode or result.stderr.strip():
            raise RuntimeError("restore failed; target remains stopped and may contain partial data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance")
    parser.add_argument("action", choices=("up", "start", "stop", "restart", "logs", "down", "backup", "restore"))
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--format", dest="log_format", choices=("auto", "console", "plain", "jsonl"),
                        help="logs only: auto/console use a capable input+output TTY, otherwise legacy plain; jsonl emits every received line")
    args = parser.parse_args()
    if args.log_format is not None and args.action != "logs":
        parser.error("--format is only available for logs")
    if (args.action in {"backup", "restore"}) != (args.archive is not None):
        parser.error("backup/restore require an archive path; other commands do not")
    if args.action == "logs":
        sys.dont_write_bytecode = True
        account = service_account(args.instance, for_logs=True)
    else:
        account = service_account(args.instance)
    instance = Instance(args.instance, account)
    if args.action == "logs":
        lifecycle(instance, args.action, log_format=args.log_format or "auto")
        return
    lock_path = instance.path / ".operations.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "backup":
            backup(instance, args.archive)
        elif args.action == "restore":
            restore(instance, args.archive)
        else:
            lifecycle(instance, args.action)


if __name__ == "__main__":
    main()
