"""Copies the served snapshot onto disk, where the coordinator's Envoy watches.

A ConfigMap mount cannot do this: its update is a symlink swap, which does not
fire the file event Envoy waits for. Real files written into an emptyDir do.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Json = dict[str, Any]


# --------------------------------------------------------------------------
# Poll, and write what changed
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Syncer:
    fetch: Callable[[str], Json]
    out: Path
    period: int = 5
    documents: tuple[str, ...] = ("lds", "cds")

    def sync_once(self) -> list[str]:
        written = []
        for name in self.documents:
            document = self.fetch(name)
            if write_if_changed(self.out / f"{name}.yaml", document):
                written.append(f"{name}@{document['version_info']}")
        return written

    def run(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                written = self.sync_once()
                if written:
                    print(f"wrote {', '.join(written)}", flush=True)
            except Exception as exc:
                print(f"sync failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(self.period)


def fetch_from(control_plane: str) -> Callable[[str], Json]:
    def fetch(name: str) -> Json:
        with urllib.request.urlopen(f"{control_plane}/{name}", timeout=5) as response:
            return json.load(response)

    return fetch


# --------------------------------------------------------------------------
# Atomic write: Envoy sees the whole old file or the whole new one
# --------------------------------------------------------------------------

def write_if_changed(target: Path, document: Json) -> bool:
    body = json.dumps(document, indent=2) + "\n"
    if target.exists() and target.read_text() == body:
        return False
    tmp = target.with_suffix(".tmp")
    tmp.write_text(body)
    tmp.replace(target)
    return True


if __name__ == "__main__":
    control_plane = os.environ.get("CONTROL_PLANE_URL", "http://controlplane:18000")
    out = Path(os.environ.get("XDS_DIR", "/etc/envoy/xds"))
    period = int(os.environ.get("SYNC_PERIOD", "5"))
    print(f"syncer up, polling {control_plane} every {period}s into {out}", flush=True)
    Syncer(fetch_from(control_plane), out, period).run()
