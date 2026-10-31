import ctypes
import errno
import fcntl
import hashlib
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
def root_directory(path, create=False):
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != "/" or ".." in parts:
        raise Refused()
    traversal_flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", FLAGS if len(parts) == 1 else traversal_flags)
    try:
        for index, part in enumerate(parts[1:], start=1):
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
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
            raise Refused("owner marker must be a private regular file owned by the SSH user")
        yield marker_fd
    finally:
        os.close(marker_fd)


def marker(fd, token, namespace):
    with owner_file(fd, namespace) as marker_fd:
        if os.read(marker_fd, 512) != owner_bytes(fd, token):
            raise Refused("owner marker token or directory identity does not match")


def child_directory(root, name, expected):
    valid_name(name)
    fd = os.open(name, FLAGS, dir_fd=root)
    if expected and identity(fd) != expected:
        os.close(fd)
        raise Refused("site directory identity does not match saved identity")
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


def prepare_marker(fd, token, namespace, replace=False):
    payload = owner_bytes(fd, token)
    with owner_file(fd, namespace, create=True) as marker_fd:
        if not replace and not payload.startswith(os.read(marker_fd, 512)):
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
            fd = child_directory(root, name, [])
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
        prepare_marker(fd, token, namespace, replace=True)
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
        fd = child_directory(root, name, [])
    except (FileNotFoundError, NotADirectoryError) as error:
        if isinstance(error, NotADirectoryError) and request["site_identity"]:
            raise
        return {}
    try:
        names = os.listdir(fd)
        if names == [] and request["site_identity"]:
            pass
        else:
            prepare_marker(fd, request["token"], namespace, replace=True)
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


def inventory_stat(value):
    return [value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns]


def inventory_file(parent, name, expected):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
    try:
        if inventory_stat(os.fstat(fd)) != inventory_stat(expected):
            raise Refused("remote file changed during inventory")
        digest = hashlib.sha256()
        while block := os.read(fd, 1024 * 1024):
            digest.update(block)
        if inventory_stat(os.fstat(fd)) != inventory_stat(expected):
            raise Refused("remote file changed during hashing")
        return digest.hexdigest()
    finally:
        os.close(fd)


def inventory_tree(fd, prefix, metadata, rows, content, marker_name, selected=None):
    before = inventory_stat(os.fstat(fd))
    metadata.append([prefix, *before])
    rows.append([prefix, "d", stat.S_IMODE(before[2])])
    names = sorted(os.listdir(fd)) if selected is None else sorted(selected)
    for name in names:
        if prefix == "." and name == marker_name:
            continue
        path = name if prefix == "." else prefix + "/" + name
        value = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(value.st_mode):
            child = os.open(name, FLAGS, dir_fd=fd)
            try:
                if inventory_stat(os.fstat(child)) != inventory_stat(value):
                    raise Refused("remote directory changed during inventory")
                inventory_tree(child, path, metadata, rows, content, marker_name)
            finally:
                os.close(child)
        else:
            metadata.append([path, *inventory_stat(value)])
            kind = "f" if stat.S_ISREG(value.st_mode) else "other"
            row = [path, kind, stat.S_IMODE(value.st_mode)]
            if kind == "f":
                row.append(inventory_file(fd, name, value) if content else "")
            rows.append(row)
    if inventory_stat(os.fstat(fd)) != before or selected is None and sorted(os.listdir(fd)) != names:
        raise Refused("remote directory changed during inventory")


def inventory_digest(rows):
    return hashlib.sha256(json.dumps(sorted(rows), separators=(",", ":")).encode()).hexdigest()


def inventory(sites, images, roots, request):
    result = {"roots": roots, "different": [], "verified": {}, "hashed": 0}
    marker_name = f".{request['marker_namespace']}-publisher-owner"
    for name, expected in request["sites"].items():
        try:
            with ExitStack() as stack:
                fd, selected = images, expected.get("files")
                if name != "_images":
                    fd = child_directory(sites, name, expected["identity"])
                    stack.callback(os.close, fd)
                    marker(fd, expected["token"], request["marker_namespace"])
                metadata, rows = [], []
                inventory_tree(fd, ".", metadata, rows, False, marker_name, selected)
                signature = hashlib.sha256(json.dumps([roots, sorted(metadata)], separators=(",", ":")).encode()).hexdigest()
                if signature == expected["signature"]:
                    continue
                if inventory_digest([row[:2] for row in rows]) != expected["shape"]:
                    result["different"].append(name)
                    continue
                hashed_metadata, content = [], []
                inventory_tree(fd, ".", hashed_metadata, content, True, marker_name, selected)
                result["hashed"] += 1
                if sorted(metadata) != sorted(hashed_metadata):
                    raise Refused("remote tree changed during hashing")
                if inventory_digest(content) == expected["tree"]:
                    result["verified"][name] = signature
                else:
                    result["different"].append(name)
        except (OSError, Refused):
            result["different"].append(name)
    return result


def run(request, rsync_args=()):
    namespace = request["marker_namespace"]
    if namespace not in ("dame-curie", "curie"):
        raise Refused()
    with ExitStack() as stack:
        create = request["action"] in {"probe", "inventory"}
        sites = stack.enter_context(root_directory(request["site_root"], create=create))
        images = stack.enter_context(root_directory(request["image_root"], create=create))
        roots = [identity(sites), identity(images)]
        if request["roots"] and request["roots"] != roots:
            raise Refused("remote root identities do not match saved identities")
        action = request["action"]
        if action in {"claim", "remove"}:
            fcntl.flock(sites, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = {}
        if action == "probe":
            result = {"roots": roots}
        elif action == "inventory":
            result = inventory(sites, images, roots, request)
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
        request = json.load(sys.stdin) if sys.argv[1] == "-" else json.loads(sys.argv[1])
        result = run(request, sys.argv[2:])
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError, KeyError, Refused) as error:
        location = error.__traceback__
        while location.tb_next is not None:
            location = location.tb_next
        detail = f"{type(error).__name__} in {location.tb_frame.f_code.co_name} (guard.py:{location.tb_lineno})"
        if isinstance(error, Refused) and str(error):
            detail += f": {error}"
        if isinstance(error, OSError):
            detail += f": {errno.errorcode.get(error.errno, 'UNKNOWN')}"
            if error.errno is not None:
                detail += f" ({os.strerror(error.errno)})"
        print(f"publisher-guard: {detail}", file=sys.stderr)
        sys.exit(73)


if __name__ == "__main__":
    main()
