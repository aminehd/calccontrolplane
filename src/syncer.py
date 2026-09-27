"""Copy the served config onto disk where Envoy watches.

This process exists because of one Kubernetes detail. Envoy watches its xDS path
with inotify, but a ConfigMap update is a swap of the ..data symlink, and that
does not fire the event Envoy waits for. Mounting lds.yaml from a ConfigMap
means the file changes and Envoy never reloads.

So the coordinator pod gets an emptyDir instead, and this sidecar writes real
files into it.
"""
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


# --------------------------------------------------------------------------
# Writing safely
#
# Write to a temp name, then rename. Rename is atomic, so Envoy reads either the
# whole old file or the whole new one, never a half written one it would reject.
#
# Returning False on identical bytes is what keeps the log quiet: without it
# this would announce a write every five seconds forever.
# --------------------------------------------------------------------------

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
