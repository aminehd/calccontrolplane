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


VIEWS = {
    "/health": lambda config: {"ok": True},
    "/snapshot": snapshot.build,
    "/lds": snapshot.lds,
    "/cds": snapshot.cds,
}


if __name__ == "__main__":
    serve()
