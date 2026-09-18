import copy
import hashlib
import io
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import instance as ops
from scripts import instance_backup_compat as compat

APPROVED = "shell/runtime/bin/python3"


def entry(name, kind=tarfile.REGTYPE, target=""):
    member = tarfile.TarInfo(name)
    member.type = kind
    member.linkname = target
    member.mode = 0o777 if kind == tarfile.SYMTYPE else 0o700
    member.uid, member.gid = os.getuid(), os.getgid()
    member.mtime = 1_700_000_000
    return member


def entries():
    return [*(entry(root, tarfile.DIRTYPE) for root in ops.ROOTS),
            entry("shell/runtime", tarfile.DIRTYPE), entry("shell/runtime/bin", tarfile.DIRTYPE),
            entry(APPROVED, tarfile.SYMTYPE, compat.INTERPRETER)]


def write_tar(path, members, identity="curie", metadata_digest=None):
    headers = {"maxwell.instance": identity}
    if metadata_digest is not None:
        headers["maxwell.compat.link_sha256"] = metadata_digest
    with tarfile.open(path, "w", pax_headers=headers) as archive:
        for member in members:
            archive.addfile(member, io.BytesIO(b"x" * member.size) if member.isfile() else None)
    return path


def make_pair(tmp_path, members=None):
    raw = write_tar(tmp_path / "raw.tar", entries() if members is None else members)
    derived, sidecar = tmp_path / "derived.tar", tmp_path / "link.json"
    record = compat.derive(raw, derived, sidecar, "curie", approved_link=APPROVED)
    return raw, derived, sidecar, record


def run_reconstruction(root, record, *, identity="curie", payload=None, program=None):
    script, request = compat.reconstruction_request(record, "curie", approved_link=APPROVED)
    script = script if program is None else program
    script = script.replace('os.open("/instance", flags)', f"os.open({str(root)!r}, flags)")
    return subprocess.run([sys.executable, "-c", script, identity],
                          input=request if payload is None else payload, capture_output=True)


@pytest.fixture
def actual_pair(tmp_path):
    source = tmp_path / "source"
    for root in ops.ROOTS:
        (source / root).mkdir(parents=True)
    (source / APPROVED).parent.mkdir(parents=True)
    (source / APPROVED).symlink_to(compat.INTERPRETER)
    os.utime(source / APPROVED, ns=(1_700_000_000_125000000, 1_700_000_000_125000000), follow_symlinks=False)
    os.utime((source / APPROVED).parent, ns=(1_600_000_000_125000000, 1_600_000_000_500000000))
    (source / "shell/payload").write_bytes(bytes(range(256)))
    os.link(source / "shell/payload", source / "shell/hardlink")
    (source / "shell/relative").symlink_to("payload")
    (source / "shell/interpreter-alias").symlink_to("runtime/bin/python3")
    (source / "config/prompt").write_text("synthetic only", encoding="utf-8")
    (source / "sites/index.html").write_text("synthetic site", encoding="utf-8")
    with sqlite3.connect(source / "data/fixture.db") as database:
        database.execute("CREATE TABLE fixture (value TEXT)")
        database.execute("INSERT INTO fixture VALUES ('synthetic memory')")
    program = ops.ARCHIVE_PROGRAM.replace('Path("/instance")', f"Path({str(source)!r})")
    archived = subprocess.run([sys.executable, "-c", program, "curie"], capture_output=True)
    assert archived.returncode == 0, archived.stderr.decode()
    assert archived.stderr == b""
    raw = tmp_path / "raw.tar"
    raw.write_bytes(archived.stdout)
    before = (source / APPROVED).lstat()
    derived, sidecar = tmp_path / "derived.tar", tmp_path / "link.json"
    record = compat.derive(raw, derived, sidecar, "curie", approved_link=APPROVED)
    assert raw.read_bytes() == archived.stdout
    after = (source / APPROVED).lstat()
    assert (after.st_ino, after.st_uid, after.st_gid, after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_ino, before.st_uid, before.st_gid, before.st_mtime_ns, before.st_ctime_ns)
    assert os.readlink(source / APPROVED) == compat.INTERPRETER
    return source, raw, derived, sidecar, record


def test_real_split_restore_and_last_link_roundtrip(tmp_path, actual_pair):
    source, raw, derived, sidecar, record = actual_pair
    assert compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED) == record
    assert derived.stat().st_mode & 0o777 == sidecar.stat().st_mode & 0o777 == 0o600
    with tarfile.open(raw) as archive:
        with pytest.raises(ValueError, match="escapes"):
            ops.validate_archive(archive, "curie")
    with tarfile.open(derived) as archive:
        ops.validate_archive(archive, "curie")
        assert APPROVED not in archive.getnames()
    restored = tmp_path / "restored"
    restored.mkdir()
    program = ops.RESTORE_PROGRAM.replace('"/instance"', repr(str(restored)))
    result = subprocess.run([sys.executable, "-c", program], input=derived.read_bytes(), capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == result.stderr == b""
    assert not (restored / APPROVED).is_symlink()
    reconstructed = run_reconstruction(restored, record)
    assert reconstructed.returncode == 0, reconstructed.stderr.decode()
    assert reconstructed.stdout == reconstructed.stderr == b""
    assert os.readlink(restored / APPROVED) == compat.INTERPRETER
    link = (restored / APPROVED).lstat()
    assert (link.st_uid, link.st_gid, link.st_mtime_ns, stat.S_IMODE(link.st_mode)) == (
        record["link"]["uid"], record["link"]["gid"], record["link"]["mtime_ns"], 0o777)
    for name in ("shell/payload", "config/prompt", "sites/index.html", "data/fixture.db"):
        assert (restored / name).read_bytes() == (source / name).read_bytes()
        assert (restored / name).stat().st_uid == (source / name).stat().st_uid
        assert (restored / name).stat().st_gid == (source / name).stat().st_gid
    assert (restored / "shell/payload").stat().st_ino == (restored / "shell/hardlink").stat().st_ino
    assert os.readlink(restored / "shell/relative") == "payload"
    assert os.readlink(restored / "shell/interpreter-alias") == "runtime/bin/python3"
    with sqlite3.connect(restored / "data/fixture.db") as database:
        assert database.execute("SELECT value FROM fixture").fetchall() == [("synthetic memory",)]


def test_roundtrip_preserves_restored_parent_timestamps(tmp_path, actual_pair):
    _, _, derived, _, record = actual_pair
    root = tmp_path / "restored"
    root.mkdir()
    program = ops.RESTORE_PROGRAM.replace('\"/instance\"', repr(str(root)))
    result = subprocess.run([sys.executable, "-c", program], input=derived.read_bytes(), capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    parent = (root / APPROVED).parent
    assert parent.stat().st_mtime_ns == 1_600_000_000_500000000
    os.utime(parent, ns=(1_600_000_000_125000000, parent.stat().st_mtime_ns))
    before = parent.stat()
    reconstructed = run_reconstruction(root, record)
    assert reconstructed.returncode == 0, reconstructed.stderr.decode()
    assert reconstructed.stdout == reconstructed.stderr == b""
    after = parent.stat()
    assert (after.st_atime_ns, after.st_mtime_ns) == (before.st_atime_ns, before.st_mtime_ns)
    assert (root / APPROVED).is_symlink()


def test_generic_direct_restore_still_rejects_absolute_link(tmp_path, actual_pair):
    _, raw, _, _, _ = actual_pair
    root = tmp_path / "direct"
    root.mkdir()
    program = ops.RESTORE_PROGRAM.replace('"/instance"', repr(str(root)))
    result = subprocess.run([sys.executable, "-c", program], input=raw.read_bytes(), capture_output=True)
    assert result.returncode != 0
    assert b"AbsoluteLinkError" in result.stderr
    assert not (root / APPROVED).is_symlink()


@pytest.mark.parametrize("approved", ["python3", "data/runtime/bin/python3", "shell/runtime/bin/python",
                                      "/shell/python3", "shell/../python3", "shell//python3",
                                      "shell/./python3", "shell/python3/", "shell/\0/python3", None])
def test_operator_path_must_be_exact_canonical_shell_python3(tmp_path, approved):
    raw = write_tar(tmp_path / "raw.tar", entries())
    with pytest.raises(ValueError):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=approved)
    assert not (tmp_path / "derived.tar").exists()
    assert not (tmp_path / "link.json").exists()


@pytest.mark.parametrize("field,value", [
    ("linkname", "/etc/passwd"), ("linkname", "/usr/bin/python3.14"),
    ("linkname", "../../../usr/bin/python3"), ("linkname", "//usr/bin/python3"),
    ("type", tarfile.LNKTYPE), ("type", tarfile.REGTYPE), ("type", tarfile.DIRTYPE),
    ("mode", 0o644), ("size", 1), ("uid", -1), ("gid", -1), ("name", APPROVED + "/"),
])
def test_derive_rejects_unsupported_approved_entry(tmp_path, field, value):
    members = entries()
    setattr(members[-1], field, value)
    raw = write_tar(tmp_path / "raw.tar", members)
    original = raw.read_bytes()
    with pytest.raises(ValueError):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)
    assert raw.read_bytes() == original
    assert not (tmp_path / "derived.tar").exists()
    assert not (tmp_path / "link.json").exists()


@pytest.mark.parametrize("extra", [
    (APPROVED, tarfile.SYMTYPE, compat.INTERPRETER),
    ("shell/second/python3", tarfile.SYMTYPE, compat.INTERPRETER),
    (APPROVED + "/after", tarfile.REGTYPE, ""),
    ("shell/hardlink", tarfile.LNKTYPE, APPROVED),
    ("shell/escape", tarfile.SYMTYPE, "/etc/passwd"),
    ("shell/escape", tarfile.SYMTYPE, "../../outside"),
    ("config/../escape", tarfile.REGTYPE, ""),
    ("data/device", tarfile.CHRTYPE, ""),
    ("shell/runtime", tarfile.DIRTYPE, ""),
])
def test_original_graph_rejections_precede_any_output(tmp_path, extra):
    raw = write_tar(tmp_path / "raw.tar", [*entries(), entry(*extra)])
    outside = tmp_path / "outside"
    outside.write_bytes(b"untouched")
    with pytest.raises(ValueError):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)
    assert outside.read_bytes() == b"untouched"
    assert not (tmp_path / "derived.tar").exists()
    assert not (tmp_path / "link.json").exists()


@pytest.mark.parametrize("ancestor", [None, tarfile.SYMTYPE, tarfile.REGTYPE])
def test_original_graph_requires_real_archived_ancestors(tmp_path, ancestor):
    members = [member for member in entries() if member.name != "shell/runtime"]
    if ancestor is not None:
        members.insert(-1, entry("shell/runtime", ancestor, "elsewhere" if ancestor == tarfile.SYMTYPE else ""))
    raw = write_tar(tmp_path / "raw.tar", members)
    with pytest.raises(ValueError):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)


def test_derive_requires_one_link_and_same_identity(tmp_path):
    raw = write_tar(tmp_path / "raw.tar", entries()[:-1])
    with pytest.raises(ValueError, match="exactly one"):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)
    write_tar(raw, entries(), identity="other")
    with pytest.raises(ValueError, match="identity"):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)


@pytest.mark.parametrize("occupied", ["derived.tar", "link.json", "raw.tar"])
def test_derive_never_overwrites_existing_artifacts_or_source(tmp_path, occupied):
    raw = write_tar(tmp_path / "raw.tar", entries())
    original = raw.read_bytes()
    output = tmp_path / occupied
    if output != raw:
        output.write_bytes(b"keep existing")
    with pytest.raises(FileExistsError):
        compat.derive(raw, raw if output == raw else tmp_path / "derived.tar",
                      tmp_path / "link.json", "curie", approved_link=APPROVED)
    assert raw.read_bytes() == original
    if output != raw:
        assert output.read_bytes() == b"keep existing"


@pytest.mark.parametrize("which", ["raw", "derived", "sidecar", "parent"])
def test_artifact_symlinks_are_rejected_without_following(tmp_path, which):
    raw = write_tar(tmp_path / "raw.tar", entries())
    derived, sidecar = tmp_path / "derived.tar", tmp_path / "link.json"
    alias = tmp_path / "alias"
    if which == "parent":
        alias.symlink_to(tmp_path, target_is_directory=True)
        derived = alias / "derived.tar"
    else:
        alias.symlink_to(raw)
        raw, derived, sidecar = {
            "raw": (alias, derived, sidecar), "derived": (raw, alias, sidecar),
            "sidecar": (raw, derived, alias),
        }[which]
    with pytest.raises(ValueError, match="symlinks"):
        compat.derive(raw, derived, sidecar, "curie", approved_link=APPROVED)
    assert alias.is_symlink()


def test_derive_rejects_same_output_path(tmp_path):
    raw = write_tar(tmp_path / "raw.tar", entries())
    path = tmp_path / "artifact"
    with pytest.raises(ValueError, match="distinct"):
        compat.derive(raw, path, path, "curie", approved_link=APPROVED)
    assert not path.exists()


@pytest.mark.parametrize("stage", ["write_filtered_archive", "validate_pair"])
def test_failed_derivation_removes_only_its_new_outputs(tmp_path, monkeypatch, stage):
    raw = write_tar(tmp_path / "raw.tar", entries())
    before = raw.read_bytes()
    monkeypatch.setattr(compat, stage, Mock(side_effect=OSError("synthetic failure")))
    with pytest.raises(OSError, match="synthetic failure"):
        compat.derive(raw, tmp_path / "derived.tar", tmp_path / "link.json", "curie", approved_link=APPROVED)
    assert raw.read_bytes() == before
    assert not (tmp_path / "derived.tar").exists()
    assert not (tmp_path / "link.json").exists()


def test_pair_digest_detects_archive_changes(tmp_path):
    _, derived, sidecar, _ = make_pair(tmp_path)
    with derived.open("ab") as output:
        output.write(b"changed")
    with pytest.raises(ValueError, match="digest"):
        compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED)


@pytest.mark.parametrize("scope,field,value", [
    ("record", "format", "unknown"), ("record", "instance", "other"),
    ("record", "archive_sha256", "0" * 64), ("record", "archive_sha256", "invalid"),
    ("record", "extra", "forged"), ("link", "name", "shell/different/python3"),
    ("link", "name", "shell/../python3"), ("link", "target", "/etc/passwd"),
    ("link", "uid", -1), ("link", "gid", True), ("link", "uid", "0"),
    ("link", "uid", os.getuid() + 1), ("link", "mtime_ns", 1_700_000_000_000000001),
    ("link", "mode", 0o644), ("link", "mtime_ns", True),
    ("link", "mtime_ns", 2**63), ("link", "atime_ns", "now"), ("link", "extra", "forged"),
])
def test_pair_rejects_forged_record_fields(tmp_path, scope, field, value):
    _, derived, sidecar, record = make_pair(tmp_path)
    target = record if scope == "record" else record["link"]
    target[field] = value
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED)


def test_pair_rejects_duplicate_json_keys(tmp_path):
    _, derived, sidecar, record = make_pair(tmp_path)
    sidecar.write_text('{"format":"forged",' + json.dumps(record)[1:], encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED)


@pytest.mark.parametrize("extra", [
    (APPROVED, tarfile.REGTYPE, ""), (APPROVED, tarfile.DIRTYPE, ""),
    (APPROVED + "/later", tarfile.REGTYPE, ""),
    ("shell/alias", tarfile.LNKTYPE, APPROVED),
])
def test_pair_rechecks_combined_graph_even_with_matching_digest(tmp_path, extra):
    _, derived, sidecar, record = make_pair(tmp_path)
    write_tar(derived, [*entries()[:-1], entry(*extra)], metadata_digest=compat.metadata_digest(record))
    record["archive_sha256"] = hashlib.sha256(derived.read_bytes()).hexdigest()
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED)


def test_pair_rechecks_archive_identity_even_with_matching_digest(tmp_path):
    _, derived, sidecar, record = make_pair(tmp_path)
    write_tar(derived, entries()[:-1], identity="other", metadata_digest=compat.metadata_digest(record))
    record["archive_sha256"] = hashlib.sha256(derived.read_bytes()).hexdigest()
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        compat.validate_pair(derived, sidecar, "curie", approved_link=APPROVED)


def test_pax_nanoseconds_and_optional_atime_are_preserved(tmp_path):
    members = entries()
    members[-1].pax_headers = {"mtime": "1700000000.123456789", "atime": "1700000001.987654321"}
    _, _, _, record = make_pair(tmp_path, members)
    assert record["link"]["mtime_ns"] == 1_700_000_000_123456789
    assert record["link"]["atime_ns"] == 1_700_000_001_987654321
    root = tmp_path / "restored"
    (root / APPROVED).parent.mkdir(parents=True)
    result = run_reconstruction(root, record)
    assert result.returncode == 0, result.stderr.decode()
    info = (root / APPROVED).lstat()
    assert info.st_mtime_ns == record["link"]["mtime_ns"]
    assert info.st_atime_ns == record["link"]["atime_ns"]


@pytest.mark.parametrize("timestamp", ["1700000000.1234567891", "nan", "inf", str(2**63)])
def test_unpreservable_timestamps_are_rejected(timestamp):
    with pytest.raises(ValueError):
        compat.timestamp_ns(timestamp)


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_reconstruction_never_replaces_an_existing_leaf(tmp_path, kind):
    _, _, _, record = make_pair(tmp_path)
    root = tmp_path / "restored"
    leaf = root / APPROVED
    leaf.parent.mkdir(parents=True)
    if kind == "file":
        leaf.write_bytes(b"keep")
    elif kind == "directory":
        leaf.mkdir()
    else:
        leaf.symlink_to("keep-this-target")
    before = leaf.lstat()
    result = run_reconstruction(root, record)
    assert result.returncode != 0
    assert b"FileExistsError" in result.stderr
    after = leaf.lstat()
    assert (after.st_ino, after.st_mode, after.st_uid, after.st_gid, after.st_mtime_ns) == (
        before.st_ino, before.st_mode, before.st_uid, before.st_gid, before.st_mtime_ns)
    if kind == "file":
        assert leaf.read_bytes() == b"keep"
    elif kind == "symlink":
        assert os.readlink(leaf) == "keep-this-target"


@pytest.mark.parametrize("ancestor", ["shell", "shell/runtime", "shell/runtime/bin"])
def test_reconstruction_does_not_follow_parent_symlinks(tmp_path, ancestor):
    _, _, _, record = make_pair(tmp_path)
    root = tmp_path / "restored"
    redirect = root / ancestor
    redirect.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    remainder = Path(APPROVED).relative_to(ancestor)
    sentinel = outside / remainder
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"outside untouched")
    redirect.symlink_to(outside, target_is_directory=True)
    result = run_reconstruction(root, record)
    assert result.returncode != 0
    assert sentinel.read_bytes() == b"outside untouched"
    assert redirect.is_symlink()


def test_reconstruction_requires_existing_directories(tmp_path):
    _, _, _, record = make_pair(tmp_path)
    root = tmp_path / "restored"
    root.mkdir()
    result = run_reconstruction(root, record)
    assert result.returncode != 0
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("owner", ["uid", "gid"])
def test_reconstruction_checks_rootless_mapping_before_mutation(tmp_path, owner):
    _, _, _, record = make_pair(tmp_path)
    record["link"]["uid"] = record["link"]["gid"] = 0
    record["link"][owner] = 1
    root = tmp_path / "restored"
    (root / APPROVED).parent.mkdir(parents=True)
    program, _ = compat.reconstruction_request(record, "curie", approved_link=APPROVED)
    program = program.replace('Path("/proc/self/" + kind + "_map").read_text()', repr("0 0 1\n"))
    result = run_reconstruction(root, record, program=program)
    assert result.returncode != 0
    assert b"outside the rootless mapping" in result.stderr
    assert not (root / APPROVED).is_symlink()


@pytest.mark.parametrize("tamper", ["target", "path", "owner", "duplicate", "extra"])
def test_reconstruction_revalidates_stdin_before_mutation(tmp_path, tamper):
    _, _, _, record = make_pair(tmp_path)
    root = tmp_path / "restored"
    (root / APPROVED).parent.mkdir(parents=True)
    payload = {"record": copy.deepcopy(record), "approved_link": APPROVED}
    if tamper == "target":
        payload["record"]["link"]["target"] = "/etc/passwd"
    elif tamper == "path":
        payload["record"]["link"]["name"] = "shell/../python3"
    elif tamper == "owner":
        payload["record"]["link"]["uid"] = -1
    elif tamper == "extra":
        payload["extra"] = "forged"
    request = json.dumps(payload)
    if tamper == "duplicate":
        request = '{"approved_link":"forged",' + request[1:]
    result = run_reconstruction(root, record, payload=request.encode())
    assert result.returncode != 0
    assert not (root / APPROVED).is_symlink()


def test_reconstruction_checks_helper_identity(tmp_path):
    _, _, _, record = make_pair(tmp_path)
    root = tmp_path / "restored"
    (root / APPROVED).parent.mkdir(parents=True)
    result = run_reconstruction(root, record, identity="other")
    assert result.returncode != 0
    assert b"identity mismatch" in result.stderr
    assert not (root / APPROVED).is_symlink()


def test_helper_keeps_private_link_metadata_off_argv_and_mounts_only_roots(tmp_path):
    _, _, _, record = make_pair(tmp_path)
    program, payload = compat.reconstruction_request(record, "curie", approved_link=APPROVED)
    assert APPROVED not in program
    assert APPROVED.encode() in payload
    app = ops.Instance.__new__(ops.Instance)
    app.name, app.path, app.values = "curie", Path("/synthetic/curie"), {"APP_IMAGE": "maxwell-app:fixture"}
    args = app.helper(program, writable=True)
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[-1] == "curie"
    mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
    assert mounts == [f"type=bind,src=/synthetic/curie/{root},dst=/instance/{root}" for root in ops.ROOTS]
    assert all(APPROVED not in argument for argument in args)
