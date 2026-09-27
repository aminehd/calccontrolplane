import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lib.routing import op_from_body


@pytest.mark.parametrize(
    "body, expected",
    [
        (b'{"op":"add","a":1,"b":2}', "add"),
        (b'{"op":"mul","a":1,"b":2}', "mul"),
        (b'{"a":1,"b":2}', ""),
        (b'{"op":""}', ""),
        (b"", ""),
        (None, ""),
        (b"not json", ""),
        (b"[1,2,3]", ""),
        (b'"just a string"', ""),
        (b'{"op":7}', ""),
        (b'{"op":null}', ""),
    ],
)
def test_op_from_body(body, expected):
    assert op_from_body(body) == expected


def test_an_unroutable_body_never_guesses():
    for body in (b"{}", b"garbage", b'{"op":{"nested":"thing"}}'):
        assert op_from_body(body) == "", body


def test_the_op_is_taken_verbatim():
    assert op_from_body(b'{"op":"sub"}') == "sub"
    assert op_from_body(b'{"op":"ADD"}') == "ADD"
    assert op_from_body(b'{"op":" add "}') == " add "
