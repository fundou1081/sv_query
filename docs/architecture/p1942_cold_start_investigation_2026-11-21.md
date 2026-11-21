# P194.2 cold-start investigation (2026-11-21)

> **Status**: investigation complete; implementation not started.
> **Scope**: current CLI/Session graph reuse, cache completeness, benchmark.
> **Question**: what is the smallest correct way to cut the cold-start cost for
> multi-turn agent queries?

## 1. Measurements

Machine: macOS arm64, Python 3.11.4, pyslang 11.0.0. Single run, wall clock,
isolated `SVQ_CACHE_DIR`/`SVQ_SNAPSHOT_DIR`; absolute numbers are machine/load
dependent.

### 1.1 stats (no graph cache in CLI path)

| design | cold | second run |
|---|---:|---:|
| scheduler_minimal | 0.63 s | 0.30 s |
| verilog-axi | 45.65 s | 47.20 s |

`stats` calls `tracer.build_graph()` without `use_cache`; the second run is a
full rebuild, not a warm cache hit.

### 1.2 trace drivers (graph cache path)

| design | cold | warm |
|---|---:|---:|
| verilog-axi driver query | 46.76 s | 0.90 s |

Cache file: ~652 KB compressed for the 13,940-node verilog-axi graph. The warm
JSON was byte-identical to cold for the sampled signal.

### 1.3 commands that do not use graph cache

On warm cache, these still rebuild (~45 s each on verilog-axi):

```text
paths
dataflow analyze
verify consistency
instances
```

### 1.4 snapshot path

```text
snapshot save --filelist verilog-axi.f --tag perf: 46.21 s, 29 MB
drivers --from-snapshot perf:                       0.78 s
paths --from-snapshot perf:                         0.63 s
dataflow analyze --from-snapshot perf:              0.66 s
verify consistency --from-snapshot perf:            0.59 s
```

Snapshots are a working manual graph cache for the commands that support
`--from-snapshot`.

## 2. Current architecture

### 2.1 Graph cache exists, but is narrow

`UnifiedTracer.build_graph(use_cache=False)` defaults to **off**. Only trace
commands pass `use_cache=not no_cache`; `stats`, `graph nodes/edges`, `paths`,
`dataflow`, `verify`, `instances` rebuild.

Cache key currently includes:

- source/filelist content hash (including incdir HDL files);
- `CACHE_VERSION`;
- target module;
- bit-bridge mode.

It does **not** include:

- `preprocess_macros`;
- `inject_timescale`;
- `top_modules`;
- arbitrary compiler options/version beyond `CACHE_VERSION`.

Those can change graph content. Enabling this cache for more commands without
fixing the key is a correctness risk.

### 2.2 Cache payload is graph-only

`build_graph` cache stores `{"graph_data": ...}` and hydrates `SignalGraph`.
`_init_tracers()` gets `self._module_graph` only if it exists; the cache path does
not persist/rehydrate MIG/class/path-resolver state. Snapshot persists a fuller
state, which is why snapshot queries support paths/dataflow/verify.

### 2.3 Session does not reuse graph

`sv_query/session.py` is a pure request/response seam with injected handlers.
It deliberately owns no tracer/graph. A server/daemon would need an explicit
graph/session cache layer.

### 2.4 Snapshot is a manual cache

Only a subset of core commands supports `--from-snapshot` (P182.5: 13/39).
Saving takes the same cold build cost and produces a large local file; querying
is fast. It is useful for an agent workflow but not automatic.

## 3. Options

### A. Enable graph cache for graph-only commands

Target: `stats`, `graph nodes`, `graph edges`, maybe `graph subgraph`.

- low risk if graph-only;
- must fix cache key first;
- needs `--no-cache` and visible cache status;
- does not help paths/dataflow/MIG commands.

### B. Persist/rehydrate MIG/tracers in graph cache

Target: all read commands.

- medium effort;
- needs serialization contract for MIG/class/path resolver;
- snapshot already has much of this; reuse rather than invent a second format.

### C. Session/server (local only)

A long-lived process holds one tracer and executes requests; one cold build per
project, then warm queries. This is the best fit for multi-turn agents.

- high effort/API surface;
- local server only (no RTL upload);
- can reuse snapshot/cache under the hood;
- requires lifecycle/version/idle policy.

### D. Incremental rebuild

Hash file → affected subgraph; hardest; defer until measurements show A/B/C are
insufficient.

## 4. Recommendation

Do **not** simply flip graph cache on globally.

Order:

1. **Fix cache key correctness** (preprocess/timescale/top_modules/version) and
   add a cache-hit/status test.
2. **Enable graph cache only for graph-only commands** with `--no-cache` and
   explicit status; measure.
3. **Reuse the snapshot state for MIG commands**, or add a local session/server
   that holds the tracer; benchmark against snapshot.
4. Consider incremental rebuild only after real multi-turn data.

The snapshot measurements show the target is achievable: ~46 s once, then
~0.6–0.8 s per query. The missing piece is automatic lifecycle/coverage, not a
faster graph builder.

## 5. Non-claims

- single machine, single run;
- no large-design/EDA regression suite;
- no session/server prototype yet;
- no claim that 26 s from older docs is current (current run ~45 s).

## 6. Decision (2026-11-21)

Based on the review discussion:

- **P194.2a (now)**: correctness contract only — `BuildIdentity`, versioned
  key, payload capability manifest, mutation/parity tests; keep cache default off.
- **P194.2b (next)**: enable graph-only commands, measure cold/warm hit rates.
- **P194.2c (terminal path)**: local session/server holds one graph; snapshot is
  cross-process persistence, not the multi-turn main path.
- **A-full** (unified framework for all commands) is deferred until measurement.

The cache-key omission is treated as a correctness bug, not a performance
optimization.

## 7. P194.2b result (2026-11-21)

Graph cache enabled for pure-graph commands:

```text
graph nodes
graph edges
graph subgraph
```

Each returns cache metadata in `params.cache` (not `result`, so the result
schema stays unchanged):

```json
"cache": {"status": "miss|hit|disabled", "key": "...", "capabilities": ["graph"]}
```

`--no-cache` forces a rebuild.

Measured on verilog-axi (isolated cache):

```text
graph nodes cold: 47.22 s, status=miss
graph nodes warm:  0.85 s, status=hit
```

`graph edges` shares the same BuildIdentity key. `stats` is **not** enabled yet:
it currently uses MIG instances for `modules` and stores elaboration errors;
that belongs to P194.2c/integration with a fuller GraphState.

Cold/warm node IDs are compared in the regression test.


## 8. P194.2c1 local graph session (2026-11-21)

Added a first local-session slice:

```python
from sv_query.graph_session import GraphSession
gs = GraphSession(filelist="design.f")   # one build
gs.graph_nodes(); gs.graph_edges()       # same graph
gs.cache_info()
```

and a hidden stdio adapter:

```bash
sv_query session --serve --filelist design.f
```

One JSON request per line, one response per line; graph nodes/edges only.
`GraphSession(from_snapshot=tag)` hydrates graph+MIG from a snapshot.

Current limit: only graph-only ops are exposed. Drivers/loads/paths/dataflow/
verify remain P194.2e.
