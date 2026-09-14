from .config import Config
from .scan import Scanner
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

    def reconcile(self) -> None:
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

    def remove_site(self, name: str, site: Site) -> None:
        site.deleting = True
        self.state.save()
        request = self.transport.request("remove", self.state.roots, name, site)
        self.transport.control(request)
        del self.state.sites[name]
        self.state.save()
