"""Serve the compiled config over HTTP.

Four read only endpoints and no state. The syncer polls /lds and /cds; /snapshot
is for humans.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import snapshot

PORT = int(os.environ.get("PORT", "18000"))
CONFIG = Path(os.environ.get("SERVICES_FILE", "config/services.yaml"))


def serve():
    print(f"control plane up on {PORT}, services from {CONFIG}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        view = VIEWS.get(self.path)
        if view is None:
            self._send({"paths": sorted(VIEWS)})
        else:
            self._send(view(CONFIG))

    def _send(self, obj, code=200):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# --------------------------------------------------------------------------
# The endpoint table
#
# Each view is called with CONFIG, so services.yaml is re-read on every single
# request. That looks wasteful and is the point: the file is a mounted
# ConfigMap, so the next request after Kubernetes swaps it already reflects the
# change. Cache it and live updates stop working.
#
# An unknown path replies with the list of real ones, which beats a bare 404
# when you are poking at it by hand.
# --------------------------------------------------------------------------

VIEWS = {
    "/health": lambda config: {"ok": True},
    "/snapshot": snapshot.build,
    "/lds": snapshot.lds,
    "/cds": snapshot.cds,
}


if __name__ == "__main__":
    serve()
