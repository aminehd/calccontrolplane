.PHONY: xds topology test

PY := .venv/bin/python
SNAPSHOT := import sys, json; sys.path.insert(0, 'src'); from pathlib import Path; \
	from envoycontrolplane.services import ServiceCatalog; \
	from envoycontrolplane.snapshot import Bootstrap, Snapshot; \
	from networkingcommons.route_header import OpRouteHeader; \
	s = Snapshot.from_catalog(ServiceCatalog.from_file(Path('config/services.yaml')), OpRouteHeader())

xds:
	$(PY) -c "$(SNAPSHOT); out = Path('config/coordinator'); \
	out.joinpath('bootstrap.yaml').write_text(json.dumps(Bootstrap('coordinator').to_envoy(), indent=2) + '\n'); \
	out.joinpath('lds.yaml').write_text(json.dumps(s.lds(), indent=2) + '\n'); \
	out.joinpath('cds.yaml').write_text(json.dumps(s.cds(), indent=2) + '\n'); \
	print('config/coordinator at version', s.version)"

topology:
	$(PY) -c "$(SNAPSHOT); print(json.dumps(s.topology(), indent=2))"

test:
	$(PY) -m pytest tests -q
