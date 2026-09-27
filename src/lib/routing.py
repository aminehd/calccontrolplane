"""Which op a request body is asking for.

Pure python, no protobuf and no grpc, so the routing decision can be read and
tested on its own. cmd/extproc.py wraps it in the Envoy wire format.

An unroutable body gives "", which matches no route, and Envoy answers 404.
That is deliberate: guessing an op would send the request somewhere wrong.
"""
import json


def op_from_body(body):
    try:
        request = json.loads(body or b"{}")
    except (ValueError, TypeError):
        return ""
    if not isinstance(request, dict):
        return ""
    op = request.get("op", "")
    return op if isinstance(op, str) else ""
