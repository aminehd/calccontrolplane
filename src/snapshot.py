import json
from pathlib import Path


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


def route(name, spec):
    return {
        "match": {"prefix": spec.get("route", f"/{name}")},
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
    routes = sorted(
        (route(n, s) for n, s in services.items()),
        key=lambda r: len(r["match"]["prefix"]),
        reverse=True,
    )
    return {
        "version": "1",
        "clusters": [cluster(n, s) for n, s in services.items()],
        "routes": routes,
    }


def envoy_sidecar(path: Path, listen_port=9001, admin_port=9901):
    snapshot = build(path)
    return {
        "admin": {"address": {"socket_address": {"address": "0.0.0.0", "port_value": admin_port}}},
        "static_resources": {
            "listeners": [
                {
                    "name": "egress",
                    "address": {
                        "socket_address": {"address": "127.0.0.1", "port_value": listen_port}
                    },
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
                                            {
                                                "name": "envoy.filters.http.router",
                                                "typed_config": {
                                                    "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                                                },
                                            }
                                        ],
                                    },
                                }
                            ]
                        }
                    ],
                }
            ],
            "clusters": snapshot["clusters"],
        },
    }


if __name__ == "__main__":
    print(json.dumps(build(Path("config/services.yaml")), indent=2))
