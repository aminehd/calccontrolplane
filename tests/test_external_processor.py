from envoy.service.ext_proc.v3 import external_processor_pb2 as pb

from envoydataplane.external_processor import ExternalProcessor
from networkingcommons.route_header import OpRouteHeader


def process(*messages):
    return list(ExternalProcessor(OpRouteHeader()).Process(iter(messages), context=None))


def headers():
    return pb.ProcessingRequest(request_headers=pb.HttpHeaders())


def body(raw):
    return pb.ProcessingRequest(request_body=pb.HttpBody(body=raw))


def mutation(response):
    common = response.request_body.response
    (header,) = common.header_mutation.set_headers
    return header.header.key, header.header.raw_value.decode(), common.clear_route_cache


def test_every_message_gets_exactly_one_reply():
    assert len(process(headers(), body(b'{"op":"add"}'))) == 2


def test_the_headers_phase_passes_through_unchanged():
    (reply,) = process(headers())
    assert reply.WhichOneof("response") == "request_headers"
    assert not reply.request_headers.response.HasField("header_mutation")


def test_the_body_phase_sets_the_route_header_from_the_op():
    (reply,) = process(body(b'{"op":"mul","a":6,"b":7}'))
    assert mutation(reply)[:2] == ("x-op", "mul")


def test_the_route_cache_is_cleared_so_envoy_routes_again():
    (reply,) = process(body(b'{"op":"add"}'))
    assert mutation(reply)[2] is True


def test_the_header_overwrites_anything_the_client_sent():
    (reply,) = process(body(b'{"op":"add"}'))
    option = reply.request_body.response.header_mutation.set_headers[0]
    assert option.append_action == option.OVERWRITE_IF_EXISTS_OR_ADD


def test_an_unroutable_body_sets_an_empty_value():
    (reply,) = process(body(b"garbage"))
    assert mutation(reply)[:2] == ("x-op", "")
