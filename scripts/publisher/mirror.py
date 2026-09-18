from pathlib import Path

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
        self.scanner = Scanner(config.source, self.staging.blobs, config.private_paths)
        self.published: dict[str, Snapshot] = {}

    def reconcile(self) -> None:
        self.published.clear()
        self.staging.prune_unlinked_blobs()
        snapshot = self.scanner.scan(self.state.source_identity)
        self.staging.materialize(snapshot)
        if not self.state.source_identity:
            self.state.source_identity = snapshot.root_identity
            self.state.save()
        request = self.transport.request("probe", self.state.roots, "", Site(""))
        roots = self.transport.control(request)["roots"]
        if not self.state.roots:
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

    def reconcile_site(self, name: str) -> None:
        self.staging.prune_unlinked_blobs()
        metadata = self.scanner.scan_site(name, self.state.source_identity, copy=False)
        previous, site = self.published.get(name), self.state.sites.get(name)
        pending = site is not None and site.deleting
        if (
            previous is not None and not pending
            and metadata.root_identity == previous.root_identity
            and metadata.signatures == previous.signatures and metadata.present == previous.present
        ):
            return
        snapshot = self.scanner.scan_site(name, self.state.source_identity or metadata.root_identity)
        if not self.state.source_identity:
            self.state.source_identity = snapshot.root_identity
            self.state.save()
        if (
            previous is not None and not pending
            and snapshot.root_identity == previous.root_identity
            and snapshot.signatures.get(Path(name), ())[:2] == previous.signatures.get(Path(name), ())[:2]
            and snapshot.directories == previous.directories and snapshot.files == previous.files
        ):
            self.published[name] = snapshot
            self.staging.prune_unlinked_blobs()
            return
        self.staging.materialize_site(name, snapshot)
        self.published.pop(name, None)
        if site is not None and (pending or name not in snapshot.present):
            self.remove_site(name, site)
            self.published.pop(name, None)
            site = None
        publishable = name in snapshot.sites or name == "_images" and Path(name) in snapshot.directories
        if publishable:
            if not self.state.roots:
                request = self.transport.request("probe", [], "", Site(""))
                self.state.roots = self.transport.control(request)["roots"]
                self.state.save()
            if name == "_images":
                request = self.transport.request("archive", self.state.roots, "", Site(""))
                self.transport.sync(self.staging.tree / name, request, delete=False)
            else:
                if site is None:
                    site = self.state.add_site(name)
                if not site.identity:
                    claim = self.transport.request("claim", self.state.roots, name, site)
                    site.identity = self.transport.control(claim)["site_identity"]
                    self.state.save()
                request = self.transport.request("site", self.state.roots, name, site)
                self.transport.sync(self.staging.tree / name, request, delete=True)
            self.published[name] = snapshot
        else:
            self.published.pop(name, None)

    def remove_site(self, name: str, site: Site) -> None:
        site.deleting = True
        self.state.save()
        request = self.transport.request("remove", self.state.roots, name, site)
        self.transport.control(request)
        del self.state.sites[name]
        self.state.save()
