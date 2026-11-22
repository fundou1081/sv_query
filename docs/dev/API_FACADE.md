# Python API facade and deprecation policy — P194.3

> **Stable entry**: `sv_query.QueryClient` / `sv_query.open_query`
> **Transport seam**: `sv_query.Session`
> **Low-level graph owner**: `sv_query.graph_session.GraphSession`
> **Internal**: `sv_query.trace.*`

## 1. Public layers

| Layer | Stability | Use |
|---|---|---|
| `QueryClient` / `open_query` | stable | preferred Python entry; one graph + `execute(request)` |
| `Session` | stable contract | custom transports / handler injection |
| `GraphSession` | supported low-level | direct graph methods and stdio adapter |
| `sv_query.trace.*` | internal | implementation, no compatibility promise |

`QueryClient` is a thin facade, not a second query implementation:

```python
from sv_query import open_query

with open_query(filelist="design.f") as client:
    client.execute({"op": "graph_nodes"})
    client.execute({"op": "drivers", "signal": "top.sig"})
```

## 2. Deprecation policy

- Public facade changes are announced in `CHANGELOG.md` and docs.
- A deprecated public symbol gets a `DeprecationWarning` when practical, and
  remains available for **at least one minor release** before removal.
- Removal happens only in a documented breaking release; no silent deletion or
  behavior change.
- `sv_query.trace.*` is internal: no deprecation window is promised.
- CLI aliases (`trace fanin` / `trace fanout`) follow the command-surface
  ratchet; changing them requires an explicit registry/baseline update.
- Additive fields/options are preferred over renames; see the JSON contract.

## 3. Non-goals

- `QueryClient` does not replace the CLI.
- `Session` remains transport-independent and does not own a graph.
- `GraphSession` remains the no-CLI graph API used by the stdio adapter.
