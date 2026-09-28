"""Listeners and routes: how Envoy decides where a request goes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from envoycontrolplane.cluster import socket_address
from envoycontrolplane.services import Service
from networkingcommons.route_header import RouteHeader

Json = dict[str, Any]

HCM = "envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
EXT_PROC = "envoy.extensions.filters.http.ext_proc.v3.ExternalProcessor"
ROUTER = "envoy.extensions.filters.http.router.v3.Router"


# --------------------------------------------------------------------------
# A listener: the port Envoy accepts requests on, and its filter chain
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Listener:
    type_url: ClassVar[str] = "type.googleapis.com/envoy.config.listener.v3.Listener"

    routes: tuple[Route, ...]
    name: str = "egress"
    address: str = "127.0.0.1"
    port: int = 9001
    external_processor_cluster: str = "extproc"

    def to_envoy(self) -> Json:
        return {
            "name": self.name,
            "address": socket_address(self.address, self.port),
            "filter_chains": [
                {
                    "filters": [
                        {
                            "name": "envoy.filters.network.http_connection_manager",
                            "typed_config": self._connection_manager(),
                        }
                    ]
                }
            ],
        }

    def _connection_manager(self) -> Json:
        return {
            "@type": f"type.googleapis.com/{HCM}",
            "stat_prefix": self.name,
            "route_config": {
                "name": "local",
                "virtual_hosts": [
                    {"name": "calculators", "domains": ["*"], "routes": [r.to_envoy() for r in self.routes]}
                ],
            },
            "http_filters": [ext_proc_filter(self.external_processor_cluster), router_filter()],
        }


# --------------------------------------------------------------------------
# A route: if the header matches, send to that cluster
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Route:
    header_matcher: Json
    cluster: str
    timeout: str
    retries: int

    @classmethod
    def for_service(cls, service: Service, header: RouteHeader) -> Route:
        return cls(header.matcher(service.op), service.cluster, service.timeout, service.retries)

    def to_envoy(self) -> Json:
        return {
            "match": {"prefix": "/", "headers": [self.header_matcher]},
            "route": {
                "cluster": self.cluster,
                "timeout": self.timeout,
                "retry_policy": {"retry_on": "5xx,reset,connect-failure", "num_retries": self.retries},
            },
        }


# --------------------------------------------------------------------------
# Http filters: ext_proc sets the header, then the router routes on it
# --------------------------------------------------------------------------

def ext_proc_filter(cluster: str) -> Json:
    return {
        "name": "envoy.filters.http.ext_proc",
        "typed_config": {
            "@type": f"type.googleapis.com/{EXT_PROC}",
            "grpc_service": {"envoy_grpc": {"cluster_name": cluster}},
            "processing_mode": {
                "request_header_mode": "SEND",
                "request_body_mode": "BUFFERED",
                "response_header_mode": "SKIP",
                "response_body_mode": "NONE",
            },
            "message_timeout": "2s",
        },
    }


def router_filter() -> Json:
    return {"name": "envoy.filters.http.router", "typed_config": {"@type": f"type.googleapis.com/{ROUTER}"}}
