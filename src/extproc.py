import json
import os
from concurrent import futures

import grpc
from envoy.service.ext_proc.v3 import external_processor_pb2 as pb
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as pbg
from envoy.config.core.v3 import base_pb2

PORT = int(os.environ.get("PORT", "18001"))
HEADER = os.environ.get("ROUTE_HEADER", "x-op")


def set_header(name, value):
    mutation = base_pb2.HeaderValueOption(
        header=base_pb2.HeaderValue(key=name, raw_value=value.encode()),
        append_action=base_pb2.HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
    )
    common = pb.CommonResponse(
        header_mutation=pb.HeaderMutation(set_headers=[mutation]),
        clear_route_cache=True,
    )
    return common


class Processor(pbg.ExternalProcessorServicer):
    def Process(self, request_iterator, context):
        for req in request_iterator:
            kind = req.WhichOneof("request")
            if kind == "request_headers":
                yield pb.ProcessingResponse(request_headers=pb.HeadersResponse())
            elif kind == "request_body":
                op = ""
                try:
                    op = json.loads(req.request_body.body or b"{}").get("op", "")
                except Exception as exc:
                    print(f"bad body: {exc}", flush=True)
                print(f"body seen, op={op!r} -> {HEADER}", flush=True)
                yield pb.ProcessingResponse(
                    request_body=pb.BodyResponse(response=set_header(HEADER, op))
                )
            else:
                yield pb.ProcessingResponse(request_headers=pb.HeadersResponse())


server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
pbg.add_ExternalProcessorServicer_to_server(Processor(), server)
server.add_insecure_port(f"0.0.0.0:{PORT}")
print(f"ext_proc up on {PORT}, routing header {HEADER}", flush=True)
server.start()
server.wait_for_termination()
