import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import snapshot

PORT = int(os.environ.get("PORT", "18000"))
CONFIG = Path(os.environ.get("SERVICES_FILE", "config/services.yaml"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send({"ok": True})
            return
        if self.path == "/snapshot":
            self._send(snapshot.build(CONFIG))
            return
        self._send({"paths": ["/health", "/snapshot"]})

    def log_message(self, *args):
        pass


print(f"control plane up on {PORT}, services from {CONFIG}", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
