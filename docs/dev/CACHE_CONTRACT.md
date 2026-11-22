# Graph cache contract — P194.2a

> **Status**: correctness contract; cache remains default-off in this phase.
> **Investigation**: [p1942_cold_start_investigation_2026-11-21](../architecture/p1942_cold_start_investigation_2026-11-21.md)
> **Date**: 2026-11-21

## 1. BuildIdentity

Every graph cache key comes from one typed object:

```python
BuildIdentity(
    source_hash,          # filelist/source closure content (includes incdirs)
    include_dirs,
    preprocess_macros,
    inject_timescale,
    top_modules,
    target_module,
    bit_bridge,
    cache_schema,         # CACHE_VERSION
    graph_semantics,     # GRAPH_SEMANTICS_VERSION
    pyslang_version,
    sv_query_version,
)
```

A command must never assemble a key by concatenating strings.

### Invalidation rules

Changing any field must produce a different key:

- source/filelist/header content;
- include dirs;
- preprocess/timescale/top/target/bit-bridge options;
- cache schema or graph semantics version;
- pyslang or sv_query version.

`compute_filelist_hash` uses the production `parse_filelist` closure: all nested
filelists, resolved source bytes, `+define+` values, filelist `+incdir+` dirs and
all HDL headers under those dirs are hashed. Sources mode hashes explicit
include-dir headers. Missing/unreadable closure members raise `CacheKeyError`
(explicit cache miss), never skip. P195.1.

### Extractor semantics

`GRAPH_SEMANTICS_VERSION` must be bumped when an extractor changes what graph is
produced from the same inputs. This is a manual discipline (like `CACHE_VERSION`);
a code change alone cannot prove extractor semantics changed.

## 2. Payload manifest

Every entry self-describes:

```json
{
  "capabilities": ["graph"],
  "graph_semantics": "1",
  "cache_schema": "3.1",
  "build_identity": {...}
}
```

Current graph cache owns **graph only**. MIG/class/path-resolver capabilities are
not cached. `build_graph(required_capabilities=...)` only hydrates an entry when
the manifest covers every requested capability; trace/GraphSession callers request
`{"graph", "mig"}`, so a graph-only hit is a miss and rebuilds with MIG. P195.2.

A missing manifest or missing required capability is a **miss**, not a partial
hit. Old entries without the manifest are rebuilt. P195.1 covers closure hashing;
P195.2 covers capability enforcement (MIG).

## 3. Default policy

`build_graph(use_cache=False)` remains the library default. Opt-in surface:

- trace commands (`drivers`/`loads`/...) already used it;
- P194.2b adds `graph nodes`, `graph edges`, `graph subgraph` with `--no-cache`;
- `stats` is intentionally not enabled yet: its `modules`/elaboration-error path
  still needs MIG/metadata beyond `graph` capability.

## 4. Tests

- every identity field changes the key;
- manifest declares only `graph`;
- entry without manifest rebuilds (not hydrated);
- cold/warm output parity is still required when P194.2b enables commands.

## 5. Non-goals

- no MIG/class cache in P194.2a;
- no session/server in P194.2a;
- no incremental rebuild.
