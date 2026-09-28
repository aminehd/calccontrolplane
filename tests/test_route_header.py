import pytest

from networkingcommons.route_header import OpRouteHeader, RouteHeader


def test_op_route_header_declares_that_it_is_a_route_header():
    assert RouteHeader in OpRouteHeader.__mro__


def test_the_header_is_named_x_op_by_default():
    assert OpRouteHeader().name == "x-op"


def test_the_matcher_is_an_exact_match_on_the_header():
    assert OpRouteHeader().matcher("add") == {"name": "x-op", "string_match": {"exact": "add"}}


def test_the_matcher_uses_the_configured_header_name():
    assert OpRouteHeader("x-model").matcher("gpt")["name"] == "x-model"


def test_the_value_is_the_op_field_of_a_json_body():
    assert OpRouteHeader().value_from_body(b'{"op":"mul","a":6,"b":7}') == "mul"


@pytest.mark.parametrize(
    "body",
    [b'{"a":1}', b"", None, b"not json", b"[1,2]", b'"text"', b'{"op":7}', b'{"op":null}'],
)
def test_an_unroutable_body_gives_an_empty_value(body):
    assert OpRouteHeader().value_from_body(body) == ""


def test_the_value_is_kept_verbatim():
    assert OpRouteHeader().value_from_body(b'{"op":" ADD "}') == " ADD "


def test_what_ext_proc_sets_is_what_the_route_matches():
    header = OpRouteHeader()
    value = header.value_from_body(b'{"op":"sub"}')
    assert header.matcher(value)["string_match"]["exact"] == "sub"
