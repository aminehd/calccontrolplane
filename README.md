# calccontrolplane

The control plane for the mesh. `config/services.yaml` declares the calculators and
their routes; `src/snapshot.py` turns that into Envoy clusters and routes;
`src/server.py` serves the result at `/snapshot`.

`make config` regenerates `config/sidecar-worker.yaml` from `services.yaml` —
that file is what every worker's Envoy runs.
