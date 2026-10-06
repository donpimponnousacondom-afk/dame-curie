import ctypes
import fcntl
import json
import os
import shutil
import stat
import sys
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import PurePosixPath


FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
RENAME_NOREPLACE = 1


class Refused(Exception):
    pass


@contextmanager
def root_directory(path):
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != "/" or ".." in parts:
        raise Refused()
    traversal_flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", FLAGS if len(parts) == 1 else traversal_flags)
    try:
        for index, part in enumerate(parts[1:], start=1):
            child = os.open(part, FLAGS if index == len(parts) - 1 else traversal_flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def identity(fd):
    value = os.fstat(fd)
    return [value.st_dev, value.st_ino]


def valid_name(name):
    if not name or name.startswith(".") or "/" in name or name == "_images":
        raise Refused()


def owner_bytes(fd, token):
    return json.dumps({"token": token, "identity": identity(fd)}, separators=(",", ":")).encode("ascii")


@contextmanager
def owner_file(fd, namespace, create=False):
    flags = os.O_RDWR | os.O_CREAT if create else os.O_RDONLY
    marker_fd = os.open(f".{namespace}-publisher-owner", flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
    try:
        value = os.fstat(marker_fd)
        if (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
                or value.st_mode & 0o077 or value.st_uid != os.getuid()):
            raise Refused()
        yield marker_fd
    finally:
        os.close(marker_fd)


def marker(fd, token, namespace):
    with owner_file(fd, namespace) as marker_fd:
        if os.read(marker_fd, 512) != owner_bytes(fd, token):
            raise Refused()


def child_directory(root, name, expected):
    valid_name(name)
    fd = os.open(name, FLAGS, dir_fd=root)
    if expected and identity(fd) != expected:
        os.close(fd)
        raise Refused()
    return fd


def claim_name(token, namespace):
    if str(uuid.UUID(token)) != token:
        raise Refused()
    return f".{namespace}-publisher-claim-" + token


@contextmanager
def preparation(root, token, namespace, create):
    name = claim_name(token, namespace)
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=root)
        except FileExistsError:
            pass
    fd = os.open(name, FLAGS, dir_fd=root)
    try:
        value = os.fstat(fd)
        if value.st_uid != os.getuid() or value.st_mode & 0o077 or set(os.listdir(fd)) - {f".{namespace}-publisher-owner"}:
            raise Refused()
        yield name, fd
    finally:
        os.close(fd)


def prepare_marker(fd, token, namespace):
    payload = owner_bytes(fd, token)
    with owner_file(fd, namespace, create=True) as marker_fd:
        if not payload.startswith(os.read(marker_fd, 512)):
            raise Refused()
        os.ftruncate(marker_fd, 0)
        os.lseek(marker_fd, 0, os.SEEK_SET)
        if os.write(marker_fd, payload) != len(payload):
            raise Refused()
        os.fsync(marker_fd)
    os.fsync(fd)


def rename_noreplace(root, source, destination):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if not hasattr(libc, "renameat2"):
        raise Refused()
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(root, os.fsencode(source), root, os.fsencode(destination), RENAME_NOREPLACE) != 0:
        raise OSError(ctypes.get_errno(), "atomic site claim refused")


def cleanup_claim(root, token, namespace):
    try:
        os.stat(claim_name(token, namespace), dir_fd=root, follow_symlinks=False)
    except FileNotFoundError:
        return
    marker_name = f".{namespace}-publisher-owner"
    with preparation(root, token, namespace, create=False) as (name, fd):
        if marker_name in os.listdir(fd):
            with owner_file(fd, namespace) as marker_fd:
                if not owner_bytes(fd, token).startswith(os.read(marker_fd, 512)):
                    raise Refused()
            os.unlink(marker_name, dir_fd=fd)
        value = os.stat(name, dir_fd=root, follow_symlinks=False)
        if [value.st_dev, value.st_ino] != identity(fd):
            raise Refused()
        os.rmdir(name, dir_fd=root)
        os.fsync(root)


def claim(root, request):
    name, token = request["name"], request["token"]
    namespace = request["marker_namespace"]
    valid_name(name)
    with ExitStack() as stack:
        try:
            fd = child_directory(root, name, request["site_identity"])
        except FileNotFoundError:
            hidden, prepared = stack.enter_context(preparation(root, token, namespace, create=True))
            prepare_marker(prepared, token, namespace)
            value = os.stat(hidden, dir_fd=root, follow_symlinks=False)
            if [value.st_dev, value.st_ino] != identity(prepared):
                raise Refused()
            try:
                rename_noreplace(root, hidden, name)
            except FileExistsError:
                pass
            fd = child_directory(root, name, [])
        stack.callback(os.close, fd)
        marker(fd, token, namespace)
        os.fchmod(fd, 0o755)
        os.fsync(fd)
        os.fsync(root)
        cleanup_claim(root, token, namespace)
        return {"site_identity": identity(fd)}


def remove(root, request):
    name, namespace = request["name"], request["marker_namespace"]
    marker_name = f".{namespace}-publisher-owner"
    valid_name(name)
    cleanup_claim(root, request["token"], namespace)
    try:
        fd = child_directory(root, name, request["site_identity"])
    except (FileNotFoundError, NotADirectoryError) as error:
        if isinstance(error, NotADirectoryError) and request["site_identity"]:
            raise
        return {}
    try:
        names = os.listdir(fd)
        if names == [] and request["site_identity"]:
            pass
        else:
            try:
                marker(fd, request["token"], namespace)
            except (FileNotFoundError, Refused):
                if request["site_identity"]:
                    raise
                return {}
            for child in names:
                if child == marker_name:
                    continue
                value = os.stat(child, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(value.st_mode):
                    shutil.rmtree(child, dir_fd=fd)
                else:
                    os.unlink(child, dir_fd=fd)
            os.unlink(marker_name, dir_fd=fd)
            os.fsync(fd)
        current = os.stat(name, dir_fd=root, follow_symlinks=False)
        if [current.st_dev, current.st_ino] != identity(fd):
            raise Refused()
        os.rmdir(name, dir_fd=root)
        os.fsync(root)
    finally:
        os.close(fd)
    return {}


def run(request, rsync_args=()):
    namespace = request["marker_namespace"]
    if namespace not in ("dame-curie", "curie"):
        raise Refused()
    with ExitStack() as stack:
        sites = stack.enter_context(root_directory(request["site_root"]))
        images = stack.enter_context(root_directory(request["image_root"]))
        roots = [identity(sites), identity(images)]
        if request["roots"] and request["roots"] != roots:
            raise Refused()
        action = request["action"]
        if action in {"claim", "remove"}:
            fcntl.flock(sites, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = {}
        if action == "probe":
            result = {"roots": roots}
        elif action == "claim":
            result = claim(sites, request)
        elif action == "remove":
            result = remove(sites, request)
        elif action in {"site", "archive"}:
            destination = images
            if action == "site":
                destination = child_directory(sites, request["name"], request["site_identity"])
                stack.callback(os.close, destination)
                marker(destination, request["token"], namespace)
            os.fchdir(destination)
            os.execvp("rsync", ["rsync", *rsync_args])
        else:
            raise Refused()
        return result


def main():
    try:
        result = run(json.loads(sys.argv[1]), sys.argv[2:])
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError, KeyError, Refused):
        sys.exit(73)


if __name__ == "__main__":
    main()
