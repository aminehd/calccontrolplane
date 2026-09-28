import json
from pathlib import Path

from envoycontrolplane.cluster import Cluster
from envoycontrolplane.listener import Listener
from envoycontrolplane.services import ServiceCatalog
from envoycontrolplane.snapshot import Bootstrap, Snapshot
from networkingcommons.route_header import OpRouteHeader

CONFIG = Path(__file__).resolve().parents[1] / "config"


def snapshot_of(path):
    return Snapshot.from_catalog(ServiceCatalog.from_file(path), OpRouteHeader())


def rendered(document):
    return json.dumps(document, indent=2) + "\n"


def test_a_snapshot_has_one_cluster_per_service_plus_the_external_processor(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text("adder:\n  op: add\nquiet:\n  port: 1\n")
    names = [c.name for c in snapshot_of(path).clusters]
    assert names == ["adder", "quiet", "extproc"]


def test_only_routable_services_get_a_route(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text("adder:\n  op: add\nquiet:\n  port: 1\n")
    (listener,) = snapshot_of(path).listeners
    assert [r.cluster for r in listener.routes] == ["adder"]


def test_every_document_carries_the_catalog_version(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text("adder:\n  op: add\n")
    snapshot = snapshot_of(path)
    version = ServiceCatalog.from_file(path).version
    assert snapshot.lds()["version_info"] == snapshot.cds()["version_info"] == version


def test_each_resource_is_tagged_with_its_xds_type(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text("adder:\n  op: add\n")
    snapshot = snapshot_of(path)
    assert snapshot.lds()["resources"][0]["@type"] == Listener.type_url
    assert {r["@type"] for r in snapshot.cds()["resources"]} == {Cluster.type_url}


def test_the_bootstrap_points_envoy_at_the_xds_files():
    bootstrap = Bootstrap("coordinator").to_envoy()
    assert bootstrap["node"] == {"id": "coordinator", "cluster": "calcmesh"}
    assert bootstrap["dynamic_resources"]["lds_config"]["path"] == "/etc/envoy/xds/lds.yaml"
    assert bootstrap["dynamic_resources"]["cds_config"]["path"] == "/etc/envoy/xds/cds.yaml"


def test_the_committed_config_is_exactly_what_the_classes_produce():
    snapshot = snapshot_of(CONFIG / "services.yaml")
    coordinator = CONFIG / "coordinator"
    assert (coordinator / "lds.yaml").read_text() == rendered(snapshot.lds()), "run make xds"
    assert (coordinator / "cds.yaml").read_text() == rendered(snapshot.cds()), "run make xds"
    assert (coordinator / "bootstrap.yaml").read_text() == rendered(Bootstrap("coordinator").to_envoy())
