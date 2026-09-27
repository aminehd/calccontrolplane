.PHONY: xds topology test

xds:
	python3 -c "from pathlib import Path; import sys, json; sys.path.insert(0,'src'); import xds; \
	cfg = Path('config/services.yaml'); out = Path('config/coordinator'); \
	out.joinpath('bootstrap.yaml').write_text(json.dumps(xds.bootstrap('coordinator'), indent=2) + '\n'); \
	out.joinpath('lds.yaml').write_text(json.dumps(xds.lds(cfg), indent=2) + '\n'); \
	out.joinpath('cds.yaml').write_text(json.dumps(xds.cds(cfg), indent=2) + '\n'); \
	print('config/coordinator at version', xds.version_of(cfg))"

topology:
	python3 src/xds.py

test:
	python3 -m pytest tests -q
