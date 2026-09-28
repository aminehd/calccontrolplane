"""Clusters and their endpoints: where Envoy sends a request once it is routed."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from envoycontrolplane.services import Service

Json = dict[str, Any]

HTTP_OPTIONS = "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"


# --------------------------------------------------------------------------
# A cluster: a named group of endpoints
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Cluster:
    type_url: ClassVar[str] = "type.googleapis.com/envoy.config.cluster.v3.Cluster"

    name: str
    endpoints: tuple[Endpoint, ...]
    http2: bool = False

    @classmethod
    def for_service(cls, service: Service) -> Cluster:
        return cls(service.cluster, (Endpoint(service.address, service.port),))

    @classmethod
    def external_processor(cls, address: str = "extproc", port: int = 18001) -> Cluster:
        return cls("extproc", (Endpoint(address, port),), http2=True)

    def to_envoy(self) -> Json:
        cluster: Json = {"name": self.name, "type": "STRICT_DNS"}
        if not self.http2:
            cluster["lb_policy"] = "ROUND_ROBIN"
        cluster["connect_timeout"] = "1s"
        if self.http2:
            cluster["typed_extension_protocol_options"] = {
                HTTP_OPTIONS: {
                    "@type": f"type.googleapis.com/{HTTP_OPTIONS}",
                    "explicit_http_config": {"http2_protocol_options": {}},
                }
            }
        cluster["load_assignment"] = {
            "cluster_name": self.name,
            "endpoints": [{"lb_endpoints": [e.to_envoy() for e in self.endpoints]}],
        }
        return cluster


# --------------------------------------------------------------------------
# An endpoint: one address inside a cluster
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Endpoint:
    address: str
    port: int

    def to_envoy(self) -> Json:
        return {"endpoint": {"address": socket_address(self.address, self.port)}}


def socket_address(address: str, port: int) -> Json:
    return {"socket_address": {"address": address, "port_value": port}}
