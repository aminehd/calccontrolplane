# calccontrolplane

The control plane for the mesh.

`config/services.yaml` is the source of truth: it declares each calculator, its
address and the `op` that reaches it. `src/lib/xds.py` compiles that into Envoy
clusters and routes, and `src/cmd/server.py` serves them at `/topology`, `/lds`
and `/cds`.

`src/` is split by what a file is, not by topic:

```
src/lib/   xds.py                         no sockets, no state, importable
src/cmd/   server.py syncer.py extproc.py the three programs this image runs
```

One image, three entry points, each run by a different pod:

| program | runs as |
| --- | --- |
| `cmd/server.py` | the `controlplane` pod, the image default |
| `cmd/syncer.py` | a sidecar in the `coordinator` pod |
| `cmd/extproc.py` | the `extproc` pod |

```
config/
  services.yaml          the only file a human edits
  coordinator/
    bootstrap.yaml       static: node id, and to read xDS from /etc/envoy/xds
    lds.yaml             dynamic: the egress listener, with the ext_proc filter
    cds.yaml             dynamic: the clusters
  calculator/
    envoy.yaml           static: ingress on :8080 -> the app on :8081
```

`make xds` regenerates the three `config/coordinator/` files from
`services.yaml`. Their `version_info` is a hash of `services.yaml`, so a change
there is visible to Envoy.

Two of those three sit next to Envoy:

- `src/cmd/syncer.py` polls `/lds` and `/cds` and writes them into the coordinator's
  `emptyDir`, which is what makes Envoy reload without a restart. A ConfigMap
  cannot do this: its `..data` symlink swap does not trip Envoy's inotify watch.
- `src/cmd/extproc.py` is the ext_proc server. It buffers the request body, reads
  `op`, and sets the `x-op` header with `clear_route_cache`, so the body decides
  which calculator serves the request.

Every file reads top down: the entry point first, then what it calls, down to
the leaves.

`make test` runs the tests.
