import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import xds

SERVICES = ROOT / "config" / "services.yaml"


@pytest.fixture
def cfg(tmp_path):
    body = """\
adder:
  op: add
  cluster: adder
  address: adder
  port: 8080
  timeout: 3s
  retries: 2
"""
    path = tmp_path / "services.yaml"
    path.write_text(body)
    return path


def test_parse_reads_nested_keys(cfg):
    services = xds.parse(cfg)
    assert services == {
        "adder": {
            "op": "add",
            "cluster": "adder",
            "address": "adder",
            "port": "8080",
            "timeout": "3s",
            "retries": "2",
        }
    }


def test_cluster_points_at_the_service_address(cfg):
    spec = xds.parse(cfg)["adder"]
    c = xds.cluster("adder", spec)
    sock = c["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"][
        "socket_address"
    ]
    assert (c["name"], sock["address"], sock["port_value"]) == ("adder", "adder", 8080)


def test_routes_match_on_the_header_not_the_path(cfg):
    routes = xds.topology(cfg)["routes"]
    assert len(routes) == 1
    match = routes[0]["match"]
    assert match["prefix"] == "/"
    assert match["headers"] == [
        {"name": "x-op", "string_match": {"exact": "add"}}
    ]
    assert routes[0]["route"]["cluster"] == "adder"
    assert routes[0]["route"]["timeout"] == "3s"


def test_extproc_cluster_speaks_http2(cfg):
    clusters = {c["name"]: c for c in xds.topology(cfg)["clusters"]}
    assert set(clusters) == {"adder", "extproc"}
    opts = clusters["extproc"]["typed_extension_protocol_options"][
        "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"
    ]
    assert "http2_protocol_options" in opts["explicit_http_config"]


def test_egress_listener_runs_ext_proc_before_the_router(cfg):
    hcm = xds.egress_listener(cfg)["filter_chains"][0]["filters"][0]["typed_config"]
    names = [f["name"] for f in hcm["http_filters"]]
    assert names == ["envoy.filters.http.ext_proc", "envoy.filters.http.router"]


def test_bootstrap_reads_xds_from_disk():
    boot = xds.bootstrap("coordinator")
    assert boot["node"]["id"] == "coordinator"
    assert boot["dynamic_resources"]["lds_config"]["path"] == "/etc/envoy/xds/lds.yaml"
    assert boot["dynamic_resources"]["cds_config"]["path"] == "/etc/envoy/xds/cds.yaml"
    assert boot["admin"]["address"]["socket_address"]["address"] == "0.0.0.0"


def test_version_changes_when_services_change(cfg):
    before = xds.version_of(cfg)
    cfg.write_text(cfg.read_text().replace("3s", "9s"))
    assert xds.version_of(cfg) != before


def test_xds_resources_carry_their_type(cfg):
    assert xds.lds(cfg)["resources"][0]["@type"].endswith("listener.v3.Listener")
    assert all(r["@type"].endswith("cluster.v3.Cluster") for r in xds.cds(cfg)["resources"])
    assert xds.lds(cfg)["version_info"] == xds.version_of(cfg)


def test_committed_config_is_in_sync_with_services_yaml():
    import json

    live = xds.version_of(SERVICES)
    for name in ("lds", "cds"):
        on_disk = json.loads((ROOT / "config" / "coordinator" / f"{name}.yaml").read_text())
        assert on_disk["version_info"] == live, f"{name}.yaml is stale, run make xds"
