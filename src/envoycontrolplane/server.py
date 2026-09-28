"""The control plane: serves each Envoy its snapshot over HTTP."""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from envoycontrolplane.services import ServiceCatalog
from envoycontrolplane.snapshot import Snapshot
from networkingcommons.route_header import OpRouteHeader, RouteHeader

Json = dict[str, Any]


# --------------------------------------------------------------------------
# The server: services.yaml is re-read on every request, so a ConfigMap
# update shows up on the very next GET
# --------------------------------------------------------------------------

class ControlPlaneServer(ThreadingHTTPServer):
    def __init__(self, config: Path, header: RouteHeader, port: int) -> None:
        self.config = config
        self.header = header
        self.views: dict[str, Callable[[], Json]] = {
            "/health": lambda: {"ok": True},
            "/topology": lambda: self.snapshot().topology(),
            "/lds": lambda: self.snapshot().lds(),
            "/cds": lambda: self.snapshot().cds(),
        }
        super().__init__(("0.0.0.0", port), Handler)

    def snapshot(self) -> Snapshot:
        return Snapshot.from_catalog(ServiceCatalog.from_file(self.config), self.header)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server: ControlPlaneServer

    def do_GET(self) -> None:
        view = self.server.views.get(self.path)
        self._send(view() if view else {"paths": sorted(self.server.views)})

    def _send(self, document: Json) -> None:
        body = json.dumps(document, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


if __name__ == "__main__":
    config = Path(os.environ.get("SERVICES_FILE", "config/services.yaml"))
    port = int(os.environ.get("PORT", "18000"))
    print(f"control plane up on {port}, services from {config}", flush=True)
    ControlPlaneServer(config, OpRouteHeader(), port).serve_forever()
