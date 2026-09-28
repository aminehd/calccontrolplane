import json
import threading
import urllib.request

import pytest

from envoycontrolplane.server import ControlPlaneServer
from networkingcommons.route_header import OpRouteHeader


@pytest.fixture
def running(tmp_path):
    config = tmp_path / "services.yaml"
    config.write_text("adder:\n  op: add\n  timeout: 7s\n")
    server = ControlPlaneServer(config, OpRouteHeader(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield config, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def test_health(running):
    _, base = running
    assert get(f"{base}/health") == {"ok": True}


def test_lds_and_cds_are_served(running):
    _, base = running
    assert get(f"{base}/lds")["resources"][0]["name"] == "egress"
    assert [c["name"] for c in get(f"{base}/cds")["resources"]] == ["adder", "extproc"]


def test_every_request_rereads_services_yaml(running):
    config, base = running
    before = get(f"{base}/lds")["version_info"]
    config.write_text("adder:\n  op: add\n  timeout: 11s\n")
    after = get(f"{base}/lds")
    assert after["version_info"] != before
    route = after["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"]
    assert route["route_config"]["virtual_hosts"][0]["routes"][0]["route"]["timeout"] == "11s"


def test_an_unknown_path_lists_the_real_ones(running):
    _, base = running
    assert get(f"{base}/nope") == {"paths": ["/cds", "/health", "/lds", "/topology"]}
