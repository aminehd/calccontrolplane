"""Snapshots: everything one Envoy is given, at one version."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from envoycontrolplane.cluster import Cluster, socket_address
from envoycontrolplane.listener import Listener, Route
from envoycontrolplane.services import ServiceCatalog
from networkingcommons.route_header import RouteHeader

Json = dict[str, Any]


# --------------------------------------------------------------------------
# The dynamic config: listeners and clusters, served over xDS
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Snapshot:
    version: str
    listeners: tuple[Listener, ...]
    clusters: tuple[Cluster, ...]

    @classmethod
    def from_catalog(cls, catalog: ServiceCatalog, header: RouteHeader) -> Snapshot:
        routes = tuple(Route.for_service(s, header) for s in catalog.routable)
        clusters = tuple(Cluster.for_service(s) for s in catalog.services)
        return cls(
            version=catalog.version,
            listeners=(Listener(routes),),
            clusters=clusters + (Cluster.external_processor(),),
        )

    def lds(self) -> Json:
        return self._discovery(self.listeners)

    def cds(self) -> Json:
        return self._discovery(self.clusters)

    def topology(self) -> Json:
        return {
            "version": self.version,
            "listeners": [listener.to_envoy() for listener in self.listeners],
            "clusters": [cluster.to_envoy() for cluster in self.clusters],
        }

    def _discovery(self, resources: tuple[Listener | Cluster, ...]) -> Json:
        return {
            "version_info": self.version,
            "resources": [dict(r.to_envoy(), **{"@type": r.type_url}) for r in resources],
        }


# --------------------------------------------------------------------------
# The static config: read once at startup, says where the dynamic config is
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Bootstrap:
    node_id: str
    admin_port: int = 9901
    xds_dir: str = "/etc/envoy/xds"

    def to_envoy(self) -> Json:
        return {
            "node": {"id": self.node_id, "cluster": "calcmesh"},
            "admin": {"address": socket_address("0.0.0.0", self.admin_port)},
            "dynamic_resources": {
                "lds_config": {"path": f"{self.xds_dir}/lds.yaml", "resource_api_version": "V3"},
                "cds_config": {"path": f"{self.xds_dir}/cds.yaml", "resource_api_version": "V3"},
            },
        }
