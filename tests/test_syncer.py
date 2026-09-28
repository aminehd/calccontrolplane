import json

from envoycontrolplane.syncer import Syncer, write_if_changed


def document(version):
    return {"version_info": version, "resources": []}


def test_a_new_file_is_written(tmp_path):
    target = tmp_path / "lds.yaml"
    assert write_if_changed(target, document("v1"))
    assert json.loads(target.read_text()) == document("v1")


def test_identical_content_is_not_rewritten(tmp_path):
    target = tmp_path / "lds.yaml"
    write_if_changed(target, document("v1"))
    assert not write_if_changed(target, document("v1"))


def test_no_temp_file_is_left_behind(tmp_path):
    write_if_changed(tmp_path / "lds.yaml", document("v1"))
    assert [p.name for p in tmp_path.iterdir()] == ["lds.yaml"]


def test_sync_once_writes_every_document_and_reports_versions(tmp_path):
    served = {"lds": document("v1"), "cds": document("v1")}
    syncer = Syncer(fetch=served.__getitem__, out=tmp_path)
    assert syncer.sync_once() == ["lds@v1", "cds@v1"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cds.yaml", "lds.yaml"]


def test_sync_once_reports_only_what_changed(tmp_path):
    served = {"lds": document("v1"), "cds": document("v1")}
    syncer = Syncer(fetch=served.__getitem__, out=tmp_path)
    syncer.sync_once()
    served["lds"] = document("v2")
    assert syncer.sync_once() == ["lds@v2"]
