import hashlib
import inspect
import json
import os
import re
import stat
import tarfile
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from scripts.instance import SLUG, validate_archive

FORMAT = "maxwell-interpreter-link-v1"
INTERPRETER = "/usr/bin/python3"

RECONSTRUCT_PROGRAM = '''payload = json.load(sys.stdin, object_pairs_hook=unique_object)
if not isinstance(payload, dict) or payload.keys() != {"record", "approved_link"}:
    raise ValueError("invalid reconstruction request")
record = payload["record"]
validate_record(record, sys.argv[1], payload["approved_link"])
link = record["link"]
for kind in ("uid", "gid"):
    ranges = [tuple(map(int, line.split())) for line in Path("/proc/self/" + kind + "_map").read_text().splitlines()]
    if not any(start <= link[kind] < start + count for start, outside, count in ranges):
        raise ValueError("link owner is outside the rootless mapping")
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
with ExitStack() as descriptors:
    parent = os.open("/instance", flags)
    descriptors.callback(os.close, parent)
    parts = link["name"].split("/")
    for component in parts[:-1]:
        parent = os.open(component, flags, dir_fd=parent)
        descriptors.callback(os.close, parent)
    parent_stat = os.fstat(parent)
    os.symlink(link["target"], parts[-1], dir_fd=parent)
    os.chown(parts[-1], link["uid"], link["gid"], dir_fd=parent, follow_symlinks=False)
    atime = link["atime_ns"]
    if atime is None:
        atime = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False).st_atime_ns
    os.utime(parts[-1], ns=(atime, link["mtime_ns"]), dir_fd=parent, follow_symlinks=False)
    os.utime(parent, ns=(parent_stat.st_atime_ns, parent_stat.st_mtime_ns))
'''


def approved_name(name: str) -> None:
    if not isinstance(name, str):
        raise ValueError("approved link must be an archive-relative path")
    parts = name.split("/")
    if (len(parts) < 2 or parts[0] != "shell" or parts[-1] != "python3"
            or any(part in {"", ".", ".."} for part in parts) or "\0" in name):
        raise ValueError("approved link must be a canonical shell python3 path")


def artifact_path(path: Path, *, existing: bool) -> Path:
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("artifact paths cannot contain symlinks")
    if existing:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("artifact must be a regular file")
    elif path.exists():
        raise FileExistsError("compatibility artifacts must not already exist")
    return path


def original_link(archive: tarfile.TarFile, expected_instance: str, approved_link: str) -> tarfile.TarInfo:
    approved_name(approved_link)
    members = archive.getmembers()
    selected = [member for member in members if member.name.rstrip("/") == approved_link]
    if len(selected) != 1:
        raise ValueError("archive must contain exactly one approved link entry")
    link = selected[0]
    if (link.name != approved_link or not link.issym() or link.linkname != INTERPRETER
            or link.size != 0 or link.mode != 0o777):
        raise ValueError("approved entry is not the supported interpreter symlink")
    view = [member.replace(linkname="python3") if member is link else member for member in members]
    validate_archive(SimpleNamespace(pax_headers=archive.pax_headers, getmembers=lambda: view), expected_instance)
    names = {member.name.rstrip("/"): member for member in members}
    for parent in PurePosixPath(approved_link).parents:
        if str(parent) != "." and (str(parent) not in names or not names[str(parent)].isdir()):
            raise ValueError("approved link ancestors must be archived directories")
    return link


def timestamp_ns(value: str | int | float) -> int:
    number = Decimal(str(value)) * 1_000_000_000
    if not number.is_finite() or number != number.to_integral_value() or not -(2**63) <= number < 2**63:
        raise ValueError("link timestamp cannot be preserved at Linux nanosecond precision")
    return int(number)


def link_record(member: tarfile.TarInfo) -> dict:
    return {
        "name": member.name, "target": member.linkname, "uid": member.uid, "gid": member.gid,
        "mode": member.mode, "mtime_ns": timestamp_ns(member.pax_headers.get("mtime", member.mtime)),
        "atime_ns": timestamp_ns(member.pax_headers["atime"]) if "atime" in member.pax_headers else None,
    }


def validate_record(record: dict, expected_instance: str, approved_link: str) -> None:
    approved_name(approved_link)
    if not isinstance(expected_instance, str) or not SLUG.fullmatch(expected_instance):
        raise ValueError("invalid expected instance")
    if not isinstance(record, dict) or record.keys() != {"format", "instance", "archive_sha256", "link"}:
        raise ValueError("invalid compatibility record fields")
    if record["format"] != FORMAT or record["instance"] != expected_instance:
        raise ValueError("compatibility format or identity mismatch")
    if not isinstance(record["archive_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["archive_sha256"]):
        raise ValueError("invalid compatibility archive digest")
    link = record["link"]
    if not isinstance(link, dict) or link.keys() != {"name", "target", "uid", "gid", "mode", "mtime_ns", "atime_ns"}:
        raise ValueError("invalid compatibility link fields")
    if link["name"] != approved_link or link["target"] != INTERPRETER:
        raise ValueError("compatibility link differs from the operator approval")
    if any(type(link[kind]) is not int or link[kind] < 0 for kind in ("uid", "gid")):
        raise ValueError("invalid compatibility link owner")
    if type(link["mode"]) is not int or link["mode"] != 0o777:
        raise ValueError("unsupported Linux symlink mode")
    for kind in ("mtime_ns", "atime_ns"):
        if kind == "atime_ns" and link[kind] is None:
            continue
        if type(link[kind]) is not int or not -(2**63) <= link[kind] < 2**63:
            raise ValueError("invalid compatibility link timestamp")


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate compatibility record key")
        result[key] = value
    return result


def metadata_digest(record: dict) -> str:
    metadata = {key: record[key] for key in ("format", "instance", "link")}
    return hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_pair(derived_archive: Path, sidecar: Path, expected_instance: str, *, approved_link: str) -> dict:
    archive_path = artifact_path(derived_archive, existing=True)
    record_path = artifact_path(sidecar, existing=True)
    record = json.loads(record_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    validate_record(record, expected_instance, approved_link)
    with archive_path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != record["archive_sha256"]:
            raise ValueError("compatibility archive digest mismatch")
        source.seek(0)
        with tarfile.open(fileobj=source, mode="r:*") as archive:
            if archive.pax_headers.get("maxwell.compat.link_sha256") != metadata_digest(record):
                raise ValueError("compatibility link metadata digest mismatch")
            validate_archive(archive, expected_instance)
            link = tarfile.TarInfo(approved_link)
            link.type, link.linkname, link.mode = tarfile.SYMTYPE, INTERPRETER, 0o777
            link.uid, link.gid = record["link"]["uid"], record["link"]["gid"]
            combined = [*archive.getmembers(), link]
            original_link(SimpleNamespace(pax_headers=archive.pax_headers, getmembers=lambda: combined),
                          expected_instance, approved_link)
    return record


def write_filtered_archive(source: tarfile.TarFile, omitted: tarfile.TarInfo, record: dict, output) -> None:
    headers = {**source.pax_headers, "maxwell.compat.link_sha256": metadata_digest(record)}
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT, pax_headers=headers) as target:
        for member in source.getmembers():
            if member is omitted:
                continue
            with ExitStack() as content:
                stream = content.enter_context(source.extractfile(member)) if member.isfile() else None
                target.addfile(member, stream)


def derive(raw_archive: Path, derived_archive: Path, sidecar: Path, expected_instance: str, *, approved_link: str) -> dict:
    source_path = artifact_path(raw_archive, existing=True)
    archive_path = artifact_path(derived_archive, existing=False)
    record_path = artifact_path(sidecar, existing=False)
    if archive_path == record_path:
        raise ValueError("archive and companion record must be distinct")
    with tarfile.open(source_path, mode="r:*") as source:
        member = original_link(source, expected_instance, approved_link)
        record = {"format": FORMAT, "instance": expected_instance, "archive_sha256": "0" * 64,
                  "link": link_record(member)}
        validate_record(record, expected_instance, approved_link)
        with ExitStack() as incomplete:
            fd = os.open(archive_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            incomplete.callback(archive_path.unlink)
            with os.fdopen(fd, "wb") as output:
                write_filtered_archive(source, member, record, output)
                output.flush()
                os.fsync(output.fileno())
            with archive_path.open("rb") as output:
                record["archive_sha256"] = hashlib.file_digest(output, "sha256").hexdigest()
            fd = os.open(record_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            incomplete.callback(record_path.unlink)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(record, output, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            validate_pair(archive_path, record_path, expected_instance, approved_link=approved_link)
            incomplete.pop_all()
    return record


def reconstruction_request(record: dict, expected_instance: str, *, approved_link: str) -> tuple[str, bytes]:
    validate_record(record, expected_instance, approved_link)
    program = "\n".join((
        "import json, os, re, sys\nfrom contextlib import ExitStack\nfrom pathlib import Path",
        f"FORMAT = {FORMAT!r}\nINTERPRETER = {INTERPRETER!r}\nSLUG = re.compile({SLUG.pattern!r})",
        inspect.getsource(approved_name), inspect.getsource(validate_record), inspect.getsource(unique_object),
        RECONSTRUCT_PROGRAM,
    ))
    payload = json.dumps({"record": record, "approved_link": approved_link}).encode("utf-8")
    return program, payload
