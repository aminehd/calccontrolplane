.PHONY: config snapshot

config:
	python3 -c "from pathlib import Path; import sys, json; sys.path.insert(0,'src'); import snapshot; \
	Path('config/sidecar-worker.yaml').write_text(json.dumps(snapshot.envoy_sidecar(Path('config/services.yaml')), indent=2) + '\n')"
	@echo "config/sidecar-worker.yaml regenerated"

snapshot:
	python3 src/snapshot.py
