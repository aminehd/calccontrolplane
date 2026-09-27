import hashlib
import json
from pathlib import Path

LISTENER_TYPE = "type.googleapis.com/envoy.config.listener.v3.Listener"
CLUSTER_TYPE = "type.googleapis.com/envoy.config.cluster.v3.Cluster"
EXTPROC_CLUSTER = "extproc"
ROUTE_HEADER = "x-op"


def parse(path: Path):
    services = {}
    current = None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            current = line.rstrip(":")
            services[current] = {}
        elif current:
            key, _, value = line.strip().partition(":")
            services[current][key.strip()] = value.strip()
    return services


def version_of(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def cluster(name, spec):
    return {
        "name": spec.get("cluster", name),
        "type": "STRICT_DNS",
        "lb_policy": "ROUND_ROBIN",
        "connect_timeout": "1s",
        "load_assignment": {
            "cluster_name": spec.get("cluster", name),
            "endpoints": [
                {
                    "lb_endpoints": [
                        {
                            "endpoint": {
                                "address": {
                                    "socket_address": {
                                        "address": spec.get("address", name),
                                        "port_value": int(spec.get("port", 80)),
                                    }
                                }
                            }
                        }
                    ]
                }
            ],
        },
    }


def extproc_cluster(address="extproc", port=18001):
    return {
        "name": EXTPROC_CLUSTER,
        "type": "STRICT_DNS",
        "connect_timeout": "1s",
        "typed_extension_protocol_options": {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions",
                "explicit_http_config": {"http2_protocol_options": {}},
            }
        },
        "load_assignment": {
            "cluster_name": EXTPROC_CLUSTER,
            "endpoints": [
                {
                    "lb_endpoints": [
                        {
                            "endpoint": {
                                "address": {
                                    "socket_address": {"address": address, "port_value": port}
                                }
                            }
                        }
                    ]
                }
            ],
        },
    }


def ext_proc_filter():
    return {
        "name": "envoy.filters.http.ext_proc",
        "typed_config": {
            "@type": "type.googleapis.com/envoy.extensions.filters.http.ext_proc.v3.ExternalProcessor",
            "grpc_service": {"envoy_grpc": {"cluster_name": EXTPROC_CLUSTER}},
            "processing_mode": {
                "request_header_mode": "SEND",
                "request_body_mode": "BUFFERED",
                "response_header_mode": "SKIP",
                "response_body_mode": "NONE",
            },
            "message_timeout": "2s",
        },
    }


def op_route(name, spec):
    return {
        "match": {
            "prefix": "/",
            "headers": [{"name": ROUTE_HEADER, "string_match": {"exact": spec["op"]}}],
        },
        "route": {
            "cluster": spec.get("cluster", name),
            "timeout": spec.get("timeout", "5s"),
            "retry_policy": {
                "retry_on": "5xx,reset,connect-failure",
                "num_retries": int(spec.get("retries", 0)),
            },
        },
    }


def build(path: Path):
    services = parse(path)
    return {
        "version": version_of(path),
        "clusters": [cluster(n, s) for n, s in services.items()] + [extproc_cluster()],
        "routes": [op_route(n, s) for n, s in services.items() if "op" in s],
        "ops": {s["op"]: n for n, s in services.items() if "op" in s},
    }


def listener(path: Path, listen_port=9001):
    snapshot = build(path)
    return {
        "name": "egress",
        "address": {"socket_address": {"address": "127.0.0.1", "port_value": listen_port}},
        "filter_chains": [
            {
                "filters": [
                    {
                        "name": "envoy.filters.network.http_connection_manager",
                        "typed_config": {
                            "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                            "stat_prefix": "egress",
                            "route_config": {
                                "name": "local",
                                "virtual_hosts": [
                                    {
                                        "name": "calculators",
                                        "domains": ["*"],
                                        "routes": snapshot["routes"],
                                    }
                                ],
                            },
                            "http_filters": [
                                ext_proc_filter(),
                                {
                                    "name": "envoy.filters.http.router",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                                    },
                                },
                            ],
                        },
                    }
                ]
            }
        ],
    }


def bootstrap(node_id, admin_port=9901, xds_dir="/etc/envoy/xds"):
    return {
        "node": {"id": node_id, "cluster": "calcmesh"},
        "admin": {
            "address": {"socket_address": {"address": "0.0.0.0", "port_value": admin_port}}
        },
        "dynamic_resources": {
            "lds_config": {"path": f"{xds_dir}/lds.yaml", "resource_api_version": "V3"},
            "cds_config": {"path": f"{xds_dir}/cds.yaml", "resource_api_version": "V3"},
        },
    }


def lds(path: Path, listen_port=9001):
    return {
        "version_info": version_of(path),
        "resources": [dict(listener(path, listen_port), **{"@type": LISTENER_TYPE})],
    }


def cds(path: Path):
    return {
        "version_info": version_of(path),
        "resources": [dict(c, **{"@type": CLUSTER_TYPE}) for c in build(path)["clusters"]],
    }


if __name__ == "__main__":
    print(json.dumps(build(Path("config/services.yaml")), indent=2))
