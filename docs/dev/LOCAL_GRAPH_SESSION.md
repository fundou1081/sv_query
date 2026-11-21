# Local GraphSession — P194.2d

> **Status**: local/stdio prototype for graph-only queries.
> **Entry**: Python `GraphSession`, hidden `sv_query session --serve`.
> **Date**: 2026-11-21

## 1. Python API

```python
from sv_query.graph_session import GraphSession

gs = GraphSession(filelist="design.f")       # one build
gs.graph_nodes(match="valid")
gs.graph_edges(kind="DRIVER")
gs.graph_nodes()                              # same graph, no rebuild
gs.cache_info()                               # miss/hit/snapshot
gs.close()
```

Snapshot hydration:

```python
gs = GraphSession(from_snapshot="perf")
```

GraphSession does not import CLI/Typer.

## 2. Stdio server

```bash
sv_query session --serve --filelist design.f
```

One JSON request per line, one JSON response per line:

```json
{"op":"graph_nodes","match":"valid"}
{"op":"graph_edges","kind":"DRIVER"}
```

The process builds/hydrates one graph and serves all requests; errors are
per-line responses, not process crashes. This is a local stdio protocol, not a
network server.

## 3. Snapshot

`GraphSession(from_snapshot=tag)` uses `UnifiedTracer.load_snapshot`, which
restores graph + MIG. Snapshot is the cross-process persistence path; GraphSession
is the in-process reuse path.

## 4. Current coverage

```text
graph nodes
graph edges
```

Only graph-only ops are exposed in P194.2d. Drivers/loads/paths/dataflow/verify
still need the full command/session integration; that is P194.2e.

## 5. Cache policy

- GraphSession defaults to `use_cache=True`;
- cache hit/miss/snapshot is exposed via `cache_info()`;
- no network listener; RTL stays local.
