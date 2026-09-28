from envoycontrolplane.cluster import Cluster, Endpoint, socket_address
from envoycontrolplane.services import Service


def test_a_socket_address_is_envoys_address_and_port_shape():
    assert socket_address("adder", 8080) == {
        "socket_address": {"address": "adder", "port_value": 8080}
    }


def test_an_endpoint_wraps_one_address():
    assert Endpoint("adder", 8080).to_envoy() == {"endpoint": {"address": socket_address("adder", 8080)}}


def test_a_cluster_for_a_service_dials_its_address_by_dns():
    service = Service.from_spec("adder", {"address": "adder", "port": "8080"})
    cluster = Cluster.for_service(service).to_envoy()
    assert cluster == {
        "name": "adder",
        "type": "STRICT_DNS",
        "lb_policy": "ROUND_ROBIN",
        "connect_timeout": "1s",
        "load_assignment": {
            "cluster_name": "adder",
            "endpoints": [{"lb_endpoints": [Endpoint("adder", 8080).to_envoy()]}],
        },
    }


def test_every_endpoint_lands_in_one_lb_endpoints_list():
    cluster = Cluster("pool", (Endpoint("a", 1), Endpoint("b", 2))).to_envoy()
    endpoints = cluster["load_assignment"]["endpoints"]
    assert len(endpoints) == 1 and len(endpoints[0]["lb_endpoints"]) == 2


def test_the_external_processor_cluster_speaks_http2():
    cluster = Cluster.external_processor().to_envoy()
    assert cluster["name"] == "extproc"
    assert "lb_policy" not in cluster
    options = cluster["typed_extension_protocol_options"][
        "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"
    ]
    assert options["explicit_http_config"] == {"http2_protocol_options": {}}
    assert cluster["load_assignment"]["endpoints"][0]["lb_endpoints"] == [
        Endpoint("extproc", 18001).to_envoy()
    ]


def test_a_cluster_knows_its_xds_type():
    assert Cluster.type_url == "type.googleapis.com/envoy.config.cluster.v3.Cluster"
