import json
import os
import time
import urllib.request
from pathlib import Path

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://controlplane:18000")
OUT = Path(os.environ.get("XDS_DIR", "/etc/envoy/xds"))
PERIOD = int(os.environ.get("SYNC_PERIOD", "5"))


def fetch(name):
    with urllib.request.urlopen(f"{CONTROL_PLANE_URL}/{name}", timeout=5) as r:
        return json.load(r)


def sync_once():
    changed = []
    for name in ("lds", "cds"):
        body = json.dumps(fetch(name), indent=2) + "\n"
        target = OUT / f"{name}.yaml"
        if not target.exists() or target.read_text() != body:
            tmp = target.with_suffix(".tmp")
            tmp.write_text(body)
            tmp.replace(target)
            changed.append(f"{name}@{json.loads(body)['version_info']}")
    return changed


OUT.mkdir(parents=True, exist_ok=True)
print(f"syncer up, polling {CONTROL_PLANE_URL} every {PERIOD}s into {OUT}", flush=True)
while True:
    try:
        changed = sync_once()
        if changed:
            print(f"wrote {', '.join(changed)}", flush=True)
    except Exception as exc:
        print(f"sync failed: {type(exc).__name__}: {exc}", flush=True)
    time.sleep(PERIOD)
