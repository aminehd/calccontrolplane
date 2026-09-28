from envoycontrolplane.cluster import socket_address
from envoycontrolplane.listener import Listener, Route
from envoycontrolplane.services import Service
from networkingcommons.route_header import OpRouteHeader

ADDER = Service.from_spec("adder", {"op": "add", "timeout": "7s", "retries": "2"})


def test_a_route_matches_the_header_and_sends_to_the_services_cluster():
    route = Route.for_service(ADDER, OpRouteHeader()).to_envoy()
    assert route == {
        "match": {"prefix": "/", "headers": [OpRouteHeader().matcher("add")]},
        "route": {
            "cluster": "adder",
            "timeout": "7s",
            "retry_policy": {"retry_on": "5xx,reset,connect-failure", "num_retries": 2},
        },
    }


def test_a_route_uses_whichever_header_it_is_given():
    route = Route.for_service(ADDER, OpRouteHeader("x-model")).to_envoy()
    assert route["match"]["headers"][0]["name"] == "x-model"


def listener_config(listener):
    return listener.to_envoy()["filter_chains"][0]["filters"][0]["typed_config"]


def test_the_listener_is_the_coordinators_localhost_egress_port():
    listener = Listener(routes=()).to_envoy()
    assert listener["name"] == "egress"
    assert listener["address"] == socket_address("127.0.0.1", 9001)


def test_the_listener_carries_every_route_in_one_virtual_host():
    routes = (Route.for_service(ADDER, OpRouteHeader()),)
    hosts = listener_config(Listener(routes))["route_config"]["virtual_hosts"]
    assert hosts == [{"name": "calculators", "domains": ["*"], "routes": [routes[0].to_envoy()]}]


def test_ext_proc_runs_before_the_router():
    filters = listener_config(Listener(routes=()))["http_filters"]
    assert [f["name"] for f in filters] == ["envoy.filters.http.ext_proc", "envoy.filters.http.router"]


def test_ext_proc_buffers_the_body_and_calls_the_external_processor_cluster():
    ext_proc = listener_config(Listener(routes=()))["http_filters"][0]["typed_config"]
    assert ext_proc["grpc_service"] == {"envoy_grpc": {"cluster_name": "extproc"}}
    assert ext_proc["processing_mode"]["request_body_mode"] == "BUFFERED"


def test_a_listener_knows_its_xds_type():
    assert Listener.type_url == "type.googleapis.com/envoy.config.listener.v3.Listener"
