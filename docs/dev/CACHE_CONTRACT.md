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

**Known gap (2026-11-22):** `+define+` and filelist-declared `+incdir+` lines are
currently skipped because they are not files; headers under a filelist `+incdir+`
are not hashed. This is tracked as P195.1 and blocks the cache-correctness claim.

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
  "cache_schema": "3.0",
  "build_identity": {...}
}
```

Current graph cache owns **graph only**. MIG/class/path-resolver capabilities are
not yet cached; commands that require them must not treat this entry as complete.
**Known gap (2026-11-22):** the current `drivers`/`loads`/GraphSession paths are
not yet capability-enforced; a graph-only hit can leave MIG unset. Tracked as
P195.2.

A missing manifest or missing required capability is a **miss**, not a partial
hit. Old entries without the manifest are rebuilt.

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
