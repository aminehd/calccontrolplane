"""The header routes match on: the one thing both planes share."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------

class RouteHeader(Protocol):
    name: str

    def value_from_body(self, body: bytes | None) -> str: ...

    def matcher(self, value: str) -> dict[str, Any]: ...


# --------------------------------------------------------------------------
# The op field of a json body
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class OpRouteHeader(RouteHeader):
    name: str = "x-op"

    def value_from_body(self, body: bytes | None) -> str:
        try:
            request = json.loads(body or b"{}")
        except ValueError:
            return ""
        if not isinstance(request, dict):
            return ""
        op = request.get("op")
        return op if isinstance(op, str) else ""

    def matcher(self, value: str) -> dict[str, Any]:
        return {"name": self.name, "string_match": {"exact": value}}
