import json
from pathlib import Path


def _parse(path: Path):
    services = {}
    current = None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            current = line.rstrip(":")
            services[current] = {}
        elif current:
            key, _, value = line.strip().partition(":")
            services[current][key.strip()] = value.strip()
    return services


def build(path: Path):
    services = _parse(path)
    clusters = []
    for name, spec in services.items():
        clusters.append(
            {
                "name": spec.get("cluster", name),
                "type": "STRICT_DNS",
                "connect_timeout": "1s",
                "load_assignment": {
                    "cluster_name": spec.get("cluster", name),
                    "endpoints": [
                        {
                            "lb_endpoints": [
                                {
                                    "endpoint": {
                                        "address": {
                                            "socket_address": {
                                                "address": spec.get("address", name),
                                                "port_value": int(spec.get("port", 80)),
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ],
                },
            }
        )
    return {"version": "1", "clusters": clusters}


if __name__ == "__main__":
    print(json.dumps(build(Path("config/services.yaml")), indent=2))
