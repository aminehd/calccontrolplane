# calcnetworking

The networking for the mesh: the Envoy control plane, the data plane external
processor, and the one contract they share.

```
src/
  networkingcommons/
    route_header.py        RouteHeader, OpRouteHeader    the header routes match on
  envoycontrolplane/       config time, never sees a request
    services.py            Service, ServiceCatalog       what services.yaml declares
    cluster.py             Cluster, Endpoint             where upstreams live
    listener.py            Listener, Route               how requests are routed
    snapshot.py            Snapshot, Bootstrap           everything one Envoy is given
    server.py              the control plane program
    syncer.py              copies the snapshot next to Envoy
  envoydataplane/          request time, sees every request
    external_processor.py  ExternalProcessor             sets the route header from the body
```

Class names follow Envoy's own vocabulary, so the docs and the code use the same
words. `networkingcommons` holds only what both planes import.

`config/services.yaml` is the only file a human edits. `make xds` regenerates
`config/coordinator/` from it, and a test fails if the committed files drift.

One image runs three programs:

| program | runs as |
| --- | --- |
| `python -m envoycontrolplane.server` | the `controlplane` pod, the image default |
| `python -m envoycontrolplane.syncer` | a sidecar in the `coordinator` pod |
| `python -m envoydataplane.external_processor` | the `extproc` pod |

Setup and tests:

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
make test
```
