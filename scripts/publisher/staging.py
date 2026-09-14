import os
import shutil
from pathlib import Path

from .common import PublisherError, private_directory
from .scan import BlobStore, Snapshot


class Staging:
    def __init__(self, root: Path):
        private_directory(root)
        self.root = root
        self.blobs = BlobStore(root / "objects")
        self.tree = root / "current"
        for path in (self.blobs.path, self.tree):
            path.mkdir(mode=0o700, exist_ok=True)
            private_directory(path)

    def materialize(self, snapshot: Snapshot) -> None:
        self.prune_tree(self.tree, Path("."), snapshot)
        for relative in sorted(snapshot.directories, key=lambda path: len(path.parts)):
            (self.tree / relative).mkdir(mode=0o700, exist_ok=True)
        for relative, digest in snapshot.files.items():
            target, blob = self.tree / relative, self.blobs.path / digest
            if target.exists() and os.path.samestat(target.stat(), blob.stat()):
                continue
            temporary = target.parent / ".publisher-link"
            if temporary.exists():
                temporary.unlink()
            os.link(blob, temporary)
            os.replace(temporary, target)
        self.prune_blobs(set(snapshot.files.values()))

    def prune_tree(self, path: Path, relative: Path, snapshot: Snapshot) -> None:
        for entry in path.iterdir():
            child = relative / entry.name
            if entry.is_symlink():
                raise PublisherError("staging symlink refused")
            if entry.is_dir() and child in snapshot.directories:
                self.prune_tree(entry, child, snapshot)
            elif child not in snapshot.files or entry.is_dir():
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            elif child in snapshot.directories:
                entry.unlink()

    def prune_unlinked_blobs(self) -> None:
        for blob in self.blobs.path.iterdir():
            if blob.is_symlink() or not blob.is_file():
                raise PublisherError("staging object type refused")
            if blob.stat().st_nlink == 1:
                blob.unlink()

    def prune_blobs(self, retained: set[str]) -> None:
        for blob in self.blobs.path.iterdir():
            if blob.is_symlink() or not blob.is_file():
                raise PublisherError("staging object type refused")
            if blob.name not in retained:
                blob.unlink()
