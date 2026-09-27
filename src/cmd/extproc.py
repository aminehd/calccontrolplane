"""Route on the request body, as an Envoy external processor.

Envoy opens one grpc stream per http request and sends one message per phase.
Every message needs exactly one reply or the request stalls until the filter's
message_timeout, so an unhandled phase is answered rather than dropped.

Which phases arrive is set by lib.xds.ext_proc_filter: the request headers,
then the whole body at once because the mode is BUFFERED. Both response phases
are skipped, since nothing here touches the reply.
"""
import os
from concurrent import futures

import grpc
from envoy.config.core.v3 import base_pb2
from envoy.service.ext_proc.v3 import external_processor_pb2 as pb
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as pbg

from lib.routing import op_from_body

PORT = int(os.environ.get("PORT", "18001"))
ROUTE_HEADER = os.environ.get("ROUTE_HEADER", "x-op")


# --------------------------------------------------------------------------
# The server
# --------------------------------------------------------------------------

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pbg.add_ExternalProcessorServicer_to_server(BodyRouter(), server)
    server.add_insecure_port(f"0.0.0.0:{PORT}")
    print(f"ext_proc up on {PORT}, routing on {ROUTE_HEADER}", flush=True)
    server.start()
    server.wait_for_termination()


# --------------------------------------------------------------------------
# One stream per request
# --------------------------------------------------------------------------

class BodyRouter(pbg.ExternalProcessorServicer):
    """A grpc adapter and nothing else.

    The base class and the method name Process are generated from the ext_proc
    proto, so this shape is not a choice. It only picks a handler per phase;
    the handlers below hold everything worth reading.
    """

    def Process(self, stream, context):
        for message in stream:
            handle = PHASES.get(message.WhichOneof("request"), acknowledge)
            yield handle(message)


def on_request_body(message):
    op = op_from_body(message.request_body.body)
    print(f"body seen, op={op!r} -> {ROUTE_HEADER}", flush=True)
    return route_on(op)


def acknowledge(message):
    return pb.ProcessingResponse(request_headers=pb.HeadersResponse())


PHASES = {"request_body": on_request_body}


# --------------------------------------------------------------------------
# Envoy wire format
# --------------------------------------------------------------------------

def route_on(op):
    return pb.ProcessingResponse(request_body=pb.BodyResponse(response=set_routing_header(op)))


def set_routing_header(op):
    return pb.CommonResponse(
        header_mutation=pb.HeaderMutation(set_headers=[overwrite(ROUTE_HEADER, op)]),
        clear_route_cache=True,
    )


def overwrite(name, value):
    return base_pb2.HeaderValueOption(
        header=base_pb2.HeaderValue(key=name, raw_value=value.encode()),
        append_action=base_pb2.HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
    )


if __name__ == "__main__":
    serve()
