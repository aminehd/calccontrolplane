"""Decide the route from the request body."""
import json
import os
from concurrent import futures

import grpc
from envoy.config.core.v3 import base_pb2
from envoy.service.ext_proc.v3 import external_processor_pb2 as pb
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as pbg

PORT = int(os.environ.get("PORT", "18001"))
HEADER = os.environ.get("ROUTE_HEADER", "x-op")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pbg.add_ExternalProcessorServicer_to_server(Processor(), server)
    server.add_insecure_port(f"0.0.0.0:{PORT}")
    print(f"ext_proc up on {PORT}, routing header {HEADER}", flush=True)
    server.start()
    server.wait_for_termination()


class Processor(pbg.ExternalProcessorServicer):
    def Process(self, request_iterator, context):
        for request in request_iterator:
            if request.WhichOneof("request") == "request_body":
                yield route_on(op_in(request.request_body.body))
            else:
                yield carry_on()


def route_on(op):
    return pb.ProcessingResponse(request_body=pb.BodyResponse(response=set_header(HEADER, op)))


def carry_on():
    return pb.ProcessingResponse(request_headers=pb.HeadersResponse())


# --------------------------------------------------------------------------
# Header mutation
# --------------------------------------------------------------------------

def set_header(name, value):
    return pb.CommonResponse(
        header_mutation=pb.HeaderMutation(set_headers=[header_value(name, value)]),
        clear_route_cache=True,
    )


def header_value(name, value):
    return base_pb2.HeaderValueOption(
        header=base_pb2.HeaderValue(key=name, raw_value=value.encode()),
        append_action=base_pb2.HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
    )


def op_in(body):
    try:
        op = json.loads(body or b"{}").get("op", "")
    except Exception as exc:
        print(f"bad body: {exc}", flush=True)
        op = ""
    print(f"body seen, op={op!r} -> {HEADER}", flush=True)
    return op


if __name__ == "__main__":
    serve()
