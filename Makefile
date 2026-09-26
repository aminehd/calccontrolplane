.PHONY: config snapshot

config:
	python3 -c "from pathlib import Path; import sys, json; sys.path.insert(0,'src'); import snapshot; \
	Path('config/coordinator-envoy.yaml').write_text(json.dumps(snapshot.envoy_sidecar(Path('config/services.yaml')), indent=2) + '\n')"
	python3 -c "from pathlib import Path; import sys, json; sys.path.insert(0,'src'); import snapshot; \
	Path('config/coordinator-envoy.yaml').write_text(json.dumps(snapshot.envoy_gateway(Path('config/services.yaml')), indent=2) + '\n')"
	@echo "config/coordinator-envoy.yaml regenerated"

snapshot:
	python3 src/snapshot.py
