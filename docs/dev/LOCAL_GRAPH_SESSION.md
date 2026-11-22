# Local GraphSession — P194.2d / P195.5

> **Status**: local/stdio query session; verify/scope/instances explicitly unsupported.
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

GraphSession does not import CLI/Typer. Use it as a context manager:

```python
with GraphSession(filelist="design.f") as gs:
    gs.graph_nodes()
# close is idempotent; later calls raise RuntimeError("GraphSession is closed")
```

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
graph_nodes
graph_edges
drivers
loads
paths
dataflow
version (builtin)
```

Deliberately unsupported (return `E_UNSUPPORTED_OP`):

```text
verify_claim
verify_consistency
scope
instances
stats
```

The machine-readable version is
`capabilities --json` → `json_contract.session`. It is the source of truth for
ops and the success/failure envelope.

### Session envelope

```json
{"ok": true, "op": "drivers", "result": {...}}
{"ok": false, "op": "verify_claim",
 "error_code": "E_UNSUPPORTED_OP",
 "error": {"type": "UnsupportedOperation", "message": "unsupported op: verify_claim"}}
```

`request_id`, when supplied, is echoed. One graph is built/hydrated per process;
`refresh()` checks source identity per request.

## 5. Invalidation and lifecycle

`GraphSession.refresh()` checks the current BuildIdentity. If source content
changed, it creates a fresh tracer and rebuilds; `generation` increments and the
stdio server calls refresh before every request. Snapshot sessions are immutable
and skip refresh.

Old graph objects are not mutated (Python references cannot be invalidated);
callers must re-fetch `gs.graph` / re-run queries after `generation` changes.

The stdio loop uses `with GraphSession(...)` and `try/finally`; a client closing
stdout is handled as `BrokenPipeError` without a traceback. `close()` is
idempotent, and use-after-close raises `RuntimeError` rather than
`AttributeError`.

## 6. Cache policy

- GraphSession defaults to `use_cache=True`;
- cache hit/miss/snapshot is exposed via `cache_info()`;
- no network listener; RTL stays local.


## 7. Known gaps (P196, 2026-11-22)

Independent review reproduced:

- legacy snapshot without MIG is now rejected explicitly for MIG queries
  (`SnapshotCapabilityError`, P196.1); the graph is not emptied;
- `GraphSession(file=...)` refresh still does not re-read disk (P196.3);
- malformed/startup/refresh stdio errors do not use the structured envelope
  (P196.2).

Do not claim full snapshot/session correctness until P196.2–P196.3 are done.
