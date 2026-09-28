"""The external processor: reads each request body and sets the route header.

Envoy opens one gRPC stream per HTTP request and sends one message per phase.
Every message needs exactly one reply, or the request stalls until the filter's
message_timeout.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent import futures

import grpc
from envoy.config.core.v3 import base_pb2
from envoy.service.ext_proc.v3 import external_processor_pb2 as pb
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as pbg

from networkingcommons.route_header import OpRouteHeader, RouteHeader


# --------------------------------------------------------------------------
# One stream per request
# --------------------------------------------------------------------------

class ExternalProcessor(pbg.ExternalProcessorServicer):
    def __init__(self, header: RouteHeader) -> None:
        self.header = header

    def Process(
        self,
        stream: Iterator[pb.ProcessingRequest],
        context: grpc.ServicerContext | None,
    ) -> Iterator[pb.ProcessingResponse]:
        for message in stream:
            if message.WhichOneof("request") == "request_body":
                yield self.on_body(message.request_body.body)
            else:
                yield pass_headers_through()

    def on_body(self, body: bytes) -> pb.ProcessingResponse:
        value = self.header.value_from_body(body)
        print(f"body seen, {self.header.name}={value!r}", flush=True)
        return set_route_header(self.header.name, value)


# --------------------------------------------------------------------------
# Replies, in Envoy's wire format
# --------------------------------------------------------------------------

def pass_headers_through() -> pb.ProcessingResponse:
    return pb.ProcessingResponse(request_headers=pb.HeadersResponse())


def set_route_header(name: str, value: str) -> pb.ProcessingResponse:
    option = base_pb2.HeaderValueOption(
        header=base_pb2.HeaderValue(key=name, raw_value=value.encode()),
        append_action=base_pb2.HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
    )
    common = pb.CommonResponse(
        header_mutation=pb.HeaderMutation(set_headers=[option]),
        clear_route_cache=True,
    )
    return pb.ProcessingResponse(request_body=pb.BodyResponse(response=common))


if __name__ == "__main__":
    header = OpRouteHeader(os.environ.get("ROUTE_HEADER", "x-op"))
    port = int(os.environ.get("PORT", "18001"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pbg.add_ExternalProcessorServicer_to_server(ExternalProcessor(header), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    print(f"external processor up on {port}, routing on {header.name}", flush=True)
    server.start()
    server.wait_for_termination()
