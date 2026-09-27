import json
import os
import time
import urllib.request
from pathlib import Path

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://controlplane:18000")
OUT = Path(os.environ.get("XDS_DIR", "/etc/envoy/xds"))
PERIOD = int(os.environ.get("SYNC_PERIOD", "5"))


def run():
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


def sync_once():
    changed = []
    for name in ("lds", "cds"):
        resource = fetch(name)
        if write_if_changed(OUT / f"{name}.yaml", resource):
            changed.append(f"{name}@{resource['version_info']}")
    return changed


def write_if_changed(target, resource):
    body = json.dumps(resource, indent=2) + "\n"
    if target.exists() and target.read_text() == body:
        return False
    tmp = target.with_suffix(".tmp")
    tmp.write_text(body)
    tmp.replace(target)
    return True


def fetch(name):
    with urllib.request.urlopen(f"{CONTROL_PLANE_URL}/{name}", timeout=5) as response:
        return json.load(response)


if __name__ == "__main__":
    run()
