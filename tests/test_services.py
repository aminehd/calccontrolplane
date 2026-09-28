from envoycontrolplane.services import Service, ServiceCatalog

YAML = """\
adder:
  op: add
  address: adder
  port: 8080
  timeout: 7s
  retries: 2

sidecarless:
  address: somewhere
  port: 9000
"""


def test_a_service_reads_every_field_from_its_spec():
    service = Service.from_spec(
        "adder", {"op": "add", "address": "adder", "port": "8080", "timeout": "7s", "retries": "2"}
    )
    assert service == Service(
        name="adder", address="adder", port=8080, cluster="adder", op="add", timeout="7s", retries=2
    )


def test_missing_fields_fall_back_to_defaults():
    service = Service.from_spec("adder", {})
    assert (service.address, service.port, service.cluster) == ("adder", 80, "adder")
    assert (service.op, service.timeout, service.retries) == (None, "5s", 0)


def test_a_service_is_routable_only_when_it_declares_an_op():
    assert Service.from_spec("adder", {"op": "add"}).routable
    assert not Service.from_spec("sidecarless", {}).routable


def test_the_catalog_loads_every_service_in_file_order(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text(YAML)
    catalog = ServiceCatalog.from_file(path)
    assert [s.name for s in catalog.services] == ["adder", "sidecarless"]
    assert [s.name for s in catalog.routable] == ["adder"]


def test_the_catalog_version_changes_when_the_file_changes(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text(YAML)
    before = ServiceCatalog.from_file(path).version
    path.write_text(YAML.replace("7s", "9s"))
    after = ServiceCatalog.from_file(path).version
    assert before != after and len(before) == 8


def test_comments_and_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "services.yaml"
    path.write_text("# a comment\n\nadder:\n  # inside\n  op: add\n")
    assert ServiceCatalog.from_file(path).services[0].op == "add"
