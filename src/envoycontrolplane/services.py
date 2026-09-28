"""The services declared in services.yaml: what the mesh should contain."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


# --------------------------------------------------------------------------
# One service
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Service:
    name: str
    address: str
    port: int
    cluster: str
    op: str | None = None
    timeout: str = "5s"
    retries: int = 0

    @property
    def routable(self) -> bool:
        return bool(self.op)

    @classmethod
    def from_spec(cls, name: str, spec: dict[str, str]) -> Service:
        return cls(
            name=name,
            address=spec.get("address", name),
            port=int(spec.get("port", 80)),
            cluster=spec.get("cluster", name),
            op=spec.get("op") or None,
            timeout=spec.get("timeout", "5s"),
            retries=int(spec.get("retries", 0)),
        )


# --------------------------------------------------------------------------
# All of them
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ServiceCatalog:
    services: tuple[Service, ...]
    version: str

    @classmethod
    def from_file(cls, path: Path) -> ServiceCatalog:
        data = path.read_bytes()
        specs = parse(data.decode())
        return cls(
            services=tuple(Service.from_spec(name, spec) for name, spec in specs.items()),
            version=hashlib.sha256(data).hexdigest()[:8],
        )

    @property
    def routable(self) -> tuple[Service, ...]:
        return tuple(s for s in self.services if s.routable)


# --------------------------------------------------------------------------
# A deliberately tiny yaml reader: top level keys, indented pairs, strings
# --------------------------------------------------------------------------

def parse(text: str) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            current = line.rstrip(":")
            specs[current] = {}
        elif current:
            key, _, value = line.strip().partition(":")
            specs[current][key.strip()] = value.strip()
    return specs
