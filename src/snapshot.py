"""Compile services.yaml into Envoy config.

Pure functions: text in, dicts out. Nothing here opens a socket or holds state,
which is why every part of it is testable without a cluster.

Read top down. The file opens with the three documents Envoy consumes and ends
at the two leaves that read bytes off disk.
"""
import hashlib
import json
from pathlib import Path

HCM_TYPE = "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
LISTENER_TYPE = "type.googleapis.com/envoy.config.listener.v3.Listener"
CLUSTER_TYPE = "type.googleapis.com/envoy.config.cluster.v3.Cluster"
ROUTER_TYPE = "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
EXT_PROC_TYPE = "type.googleapis.com/envoy.extensions.filters.http.ext_proc.v3.ExternalProcessor"
HTTP_OPTIONS_TYPE = "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions"
EXTPROC_CLUSTER = "extproc"
ROUTE_HEADER = "x-op"


# --------------------------------------------------------------------------
# What Envoy consumes
#
# Three documents, and Envoy treats them very differently.
#
# bootstrap is static: Envoy reads it once at startup from a file, and it only
# says who this proxy is and where to look for the rest. It can never change
# without a restart.
#
# lds and cds are dynamic: the listener (ports, filters, routes) and the
# clusters (upstreams). Both carry version_info, a hash of services.yaml, which
# is how Envoy decides whether what it just read is new.
# --------------------------------------------------------------------------

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


def bootstrap(node_id, admin_port=9901, xds_dir="/etc/envoy/xds"):
    return {
        "node": {"id": node_id, "cluster": "calcmesh"},
        "admin": {"address": socket("0.0.0.0", admin_port)},
        "dynamic_resources": {
            "lds_config": {"path": f"{xds_dir}/lds.yaml", "resource_api_version": "V3"},
            "cds_config": {"path": f"{xds_dir}/cds.yaml", "resource_api_version": "V3"},
        },
    }


# --------------------------------------------------------------------------
# The one read of services.yaml
#
# Everything above calls this. It is the only place the file is turned into
# clusters and routes, so lds and cds can never disagree about the topology.
#
# A service gets a route only if it declares an op. That is the whole rule for
# what is reachable: no op, no route, and the coordinator is the example. It
# sits in the mesh without being routable.
# --------------------------------------------------------------------------

def build(path: Path):
    services = parse(path)
    return {
        "version": version_of(path),
        "clusters": [cluster(n, s) for n, s in services.items()] + [extproc_cluster()],
        "routes": [op_route(n, s) for n, s in services.items() if "op" in s],
        "ops": {s["op"]: n for n, s in services.items() if "op" in s},
    }


def listener(path: Path, listen_port=9001):
    return {
        "name": "egress",
        "address": socket("127.0.0.1", listen_port),
        "filter_chains": [
            {
                "filters": [
                    {
                        "name": "envoy.filters.network.http_connection_manager",
                        "typed_config": http_connection_manager(build(path)["routes"]),
                    }
                ]
            }
        ],
    }


def http_connection_manager(routes):
    return {
        "@type": HCM_TYPE,
        "stat_prefix": "egress",
        "route_config": {
            "name": "local",
            "virtual_hosts": [{"name": "calculators", "domains": ["*"], "routes": routes}],
        },
        "http_filters": [ext_proc_filter(), router_filter()],
    }


# --------------------------------------------------------------------------
# The builders
#
# One dict each, and this is where the op becomes a routing decision.
#
# op_route matches on a header, never on the path, because the path is always
# /calc. ext_proc puts the op in that header after reading the body, so the
# route table is the second half of a handshake with extproc.py: this file
# decides what x-op values mean, that file decides what x-op says.
#
# Order matters in a real route list, first match wins, but these are mutually
# exclusive exact matches so any order behaves the same.
# --------------------------------------------------------------------------

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


def ext_proc_filter():
    return {
        "name": "envoy.filters.http.ext_proc",
        "typed_config": {
            "@type": EXT_PROC_TYPE,
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


def router_filter():
    return {"name": "envoy.filters.http.router", "typed_config": {"@type": ROUTER_TYPE}}


def cluster(name, spec):
    return {
        "name": spec.get("cluster", name),
        "type": "STRICT_DNS",
        "lb_policy": "ROUND_ROBIN",
        "connect_timeout": "1s",
        "load_assignment": endpoints(
            spec.get("cluster", name), spec.get("address", name), int(spec.get("port", 80))
        ),
    }


def extproc_cluster(address="extproc", port=18001):
    return {
        "name": EXTPROC_CLUSTER,
        "type": "STRICT_DNS",
        "connect_timeout": "1s",
        "typed_extension_protocol_options": {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": HTTP_OPTIONS_TYPE,
                "explicit_http_config": {"http2_protocol_options": {}},
            }
        },
        "load_assignment": endpoints(EXTPROC_CLUSTER, address, port),
    }


# --------------------------------------------------------------------------
# Shapes Envoy repeats
#
# Envoy nests an address four levels deep and asks for it everywhere. These two
# exist so that nesting is written once.
#
# STRICT_DNS in cluster() is doing real work: Envoy re-resolves the name in the
# background, so when Kubernetes replaces a pod the traffic follows without any
# config change. A real mesh would push pod IPs over EDS instead; letting
# kube-dns do it is the honest shortcut for one laptop.
# --------------------------------------------------------------------------

def endpoints(cluster_name, address, port):
    return {
        "cluster_name": cluster_name,
        "endpoints": [{"lb_endpoints": [{"endpoint": {"address": socket(address, port)}}]}],
    }


def socket(address, port):
    return {"socket_address": {"address": address, "port_value": port}}


# --------------------------------------------------------------------------
# The leaves
#
# A deliberately tiny yaml reader: top level keys, two space indented pairs,
# everything a string. No dependency, and it fails loudly on anything fancier.
#
# version_of hashes the file rather than the parsed result, so reformatting the
# yaml counts as a change. That is the conservative direction: a spurious reload
# is cheap, a missed one leaves Envoy serving stale routes.
# --------------------------------------------------------------------------

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


if __name__ == "__main__":
    print(json.dumps(build(Path("config/services.yaml")), indent=2))
