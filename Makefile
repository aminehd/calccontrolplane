.PHONY: xds snapshot test

xds:
	python3 -c "from pathlib import Path; import sys, json; sys.path.insert(0,'src'); import snapshot; \
	cfg = Path('config/services.yaml'); out = Path('config/coordinator'); \
	out.joinpath('bootstrap.yaml').write_text(json.dumps(snapshot.bootstrap('coordinator'), indent=2) + '\n'); \
	out.joinpath('lds.yaml').write_text(json.dumps(snapshot.lds(cfg), indent=2) + '\n'); \
	out.joinpath('cds.yaml').write_text(json.dumps(snapshot.cds(cfg), indent=2) + '\n'); \
	print('config/coordinator at version', snapshot.version_of(cfg))"

snapshot:
	python3 src/snapshot.py

test:
	python3 -m pytest tests -q
