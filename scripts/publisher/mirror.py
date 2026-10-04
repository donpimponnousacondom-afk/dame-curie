import os
from pathlib import Path

from .common import ScanIncomplete, directory, identity
from .config import Config
from .scan import Scanner, Snapshot
from .staging import Staging
from .state import Site, State
from .transport import Transport


class Mirror:
    def __init__(self, config: Config, state: State, transport: Transport):
        self.config = config
        self.state = state
        self.transport = transport
        self.staging = Staging(config.staging)
        self.scanner = Scanner(
            config.source, self.staging.blobs, config.private_paths, marker_namespace=config.marker_namespace,
        )
        self.published: dict[str, Snapshot] = {}
        self.expected: dict[str, Snapshot] = {}
        self.manifests: dict[str, dict] = {}
        self.remote_signatures: dict[str, str] = {}
        self.inventory_count = 0
        self.inventory_hashed = 0
        self.inventory_errors: dict[str, str] = {}

    def local_inventory(self) -> tuple[set[str], dict]:
        with directory(self.config.source) as root:
            if identity(os.fstat(root)) != self.state.source_identity:
                raise ScanIncomplete("source root replacement refused")
            present = set(os.listdir(root))
        requests = {}
        self.inventory_errors = {}
        for name in sorted(present):
            if not self.scanner.allowed(Path(name)):
                continue
            previous = self.expected.get(name)
            try:
                snapshot = self.scanner.scan_site(name, self.state.source_identity, copy=previous is None)
                if previous is not None and snapshot.signatures != previous.signatures:
                    snapshot = self.scanner.scan_site(name, self.state.source_identity)
            except ScanIncomplete as error:
                self.inventory_errors[name] = str(error)
                continue
            if Path(name) not in snapshot.directories:
                continue
            if previous is None or snapshot.signatures != previous.signatures:
                manifest = snapshot.manifest(name)
                if manifest != self.manifests.get(name):
                    self.remote_signatures.pop(name, None)
                self.expected[name], self.manifests[name] = snapshot, manifest
            site = self.state.sites.get(name, Site(""))
            requests[name] = dict(self.manifests[name], token=site.token, identity=site.identity,
                                  signature=self.remote_signatures.get(name, ""))
        return present, requests

    def inventory(self) -> set[str]:
        present, requests = self.local_inventory()
        for name in self.expected.keys() - requests.keys() - self.inventory_errors.keys():
            self.expected.pop(name)
            self.manifests.pop(name)
            self.remote_signatures.pop(name, None)
            self.published.pop(name, None)
        request = self.transport.request("inventory", [], "", Site(""))
        request["sites"] = requests
        response = self.transport.control(request)
        if self.state.roots != response["roots"]:
            self.state.roots = response["roots"]
            self.state.save()
        repairs = set(response["different"])
        self.remote_signatures.update(response["verified"])
        for name in requests:
            if name in repairs:
                self.published.pop(name, None)
                self.remote_signatures.pop(name, None)
            else:
                self.published[name] = self.expected[name]
        repairs.update(name for name, site in self.state.sites.items()
                       if site.deleting or name not in present)
        self.inventory_count = len(requests)
        self.inventory_hashed = response["hashed"]
        return repairs

    def reconcile(self) -> None:
        self.published.clear()
        self.staging.prune_unlinked_blobs()
        snapshot = self.scanner.scan(self.state.source_identity)
        self.staging.materialize(snapshot)
        if not self.state.source_identity:
            self.state.source_identity = snapshot.root_identity
            self.state.save()
        request = self.transport.request("probe", [], "", Site(""))
        roots = self.transport.control(request)["roots"]
        if self.state.roots != roots:
            self.state.roots = roots
            self.state.save()
        for name in sorted(tuple(self.state.sites)):
            site = self.state.sites[name]
            if site.deleting or name not in snapshot.present:
                self.remove_site(name, site)
        for name in sorted(snapshot.sites):
            site = self.state.sites.get(name)
            if site is None:
                site = self.state.add_site(name)
            claim = self.transport.request("claim", self.state.roots, name, site)
            site.identity = self.transport.control(claim)["site_identity"]
            self.state.save()
            request = self.transport.request("site", self.state.roots, name, site)
            self.transport.sync(self.staging.tree / name, request, delete=True)
        images = self.staging.tree / "_images"
        if images.is_dir():
            request = self.transport.request("archive", self.state.roots, "", Site(""))
            self.transport.sync(images, request, delete=False)

    def reconcile_site(self, name: str, force: bool = False) -> bool:
        self.staging.prune_unlinked_blobs()
        metadata = self.scanner.scan_site(name, self.state.source_identity, copy=False)
        previous, site = self.published.get(name), self.state.sites.get(name)
        pending = site is not None and site.deleting
        if (
            not force and previous is not None and not pending
            and metadata.root_identity == previous.root_identity
            and metadata.signatures == previous.signatures and metadata.present == previous.present
        ):
            return False
        snapshot = self.scanner.scan_site(name, self.state.source_identity or metadata.root_identity)
        if not self.state.source_identity:
            self.state.source_identity = snapshot.root_identity
            self.state.save()
        if (
            not force and previous is not None and not pending
            and snapshot.root_identity == previous.root_identity
            and snapshot.signatures.get(Path(name), ())[:2] == previous.signatures.get(Path(name), ())[:2]
            and snapshot.directories == previous.directories and snapshot.files == previous.files
        ):
            self.published[name] = snapshot
            self.staging.prune_unlinked_blobs()
            return False
        self.staging.materialize_site(name, snapshot)
        self.published.pop(name, None)
        publishable = name in snapshot.sites or name == "_images" and Path(name) in snapshot.directories
        if site is not None or publishable:
            request = self.transport.request("probe", [], "", Site(""))
            roots = self.transport.control(request)["roots"]
            if self.state.roots != roots:
                self.state.roots = roots
                self.state.save()
        changed = False
        if site is not None and (pending or name not in snapshot.present):
            self.remove_site(name, site)
            changed = True
            self.published.pop(name, None)
            site = None
        if publishable:
            if name == "_images":
                request = self.transport.request("archive", self.state.roots, "", Site(""))
                self.transport.sync(self.staging.tree / name, request, delete=False)
            else:
                if site is None:
                    site = self.state.add_site(name)
                claim = self.transport.request("claim", self.state.roots, name, site)
                claimed_identity = self.transport.control(claim)["site_identity"]
                if site.identity != claimed_identity:
                    site.identity = claimed_identity
                    self.state.save()
                request = self.transport.request("site", self.state.roots, name, site)
                self.transport.sync(self.staging.tree / name, request, delete=True)
            self.published[name] = snapshot
            self.expected[name], self.manifests[name] = snapshot, snapshot.manifest(name)
            self.remote_signatures.pop(name, None)
            changed = True
        else:
            self.published.pop(name, None)
        return changed

    def remove_site(self, name: str, site: Site) -> None:
        site.deleting = True
        self.state.save()
        request = self.transport.request("remove", self.state.roots, name, site)
        self.transport.control(request)
        del self.state.sites[name]
        self.state.save()
