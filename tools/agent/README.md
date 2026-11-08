# svq_query constrained DSH tool

A single-purpose DSH tool that exposes four read-only graph queries against a
**prebuilt** `sv_query` snapshot. It replaces shell/filesystem access in the
agent profile with one narrow, reproducible interface.

| intent | input | compact output |
|---|---|---|
| `fanin` | `snapshot`, `signal`, `depth` | `{ ok, intent, snapshot, signal, drivers, count }` |
| `fanout` | `snapshot`, `signal`, `depth` | `{ ok, intent, snapshot, signal, loads, count }` |
| `neighbors` | `snapshot`, `signal`, `depth` | `{ ok, intent, snapshot, signal, drivers, loads, count }` |
| `path` | `snapshot`, `signal`, `dst` | `{ ok, intent, snapshot, path, count }` |
| `neighborhood` | `snapshot`, `signal`, `depth` | `{ ok, intent, snapshot, signal, nodes, edges, op_ternary, conditions, condition_atoms, count, truncated }` |
| `evidence` | `snapshot`, `signal` | `{ ok, intent, snapshot, signal, evidence: {file,line,source_line,source_context} }` |

`drivers` / `loads` / `path` are arrays of canonical signal IDs. `count` is the
array length for fanin/fanout/neighbors and `hop_count` for path.
`details=true` adds `kind`, `condition`, and `distance` for neighbors.
`neighborhood` performs a bounded fanin BFS and returns node/edge metadata.
`path` requests `paths --all` and defaults to the shortest variant. Pass
`granular=true` to prefer the most-node variant (used by deep-chain tasks).

## Install

```bash
bash tools/agent/install_svq_query_tool.sh
```

The script copies `tools/agent/svq-query-tool/` into
`${DSH_HOME:-$HOME/.dsh}/profiles/node_modules/@svq/query-tool`. Override
`DSH_HOME` to install into another DSH home:

```bash
DSH_HOME=/path/to/dsh bash tools/agent/install_svq_query_tool.sh
```

Runtime requirements:

- `sv_query` on `PATH`, or `SVQ_QUERY_BIN=/abs/path/to/sv_query`
- `SVQ_SNAPSHOT_DIR` pointing at prebuilt snapshots (consumed by `sv_query`)

## Run the Node tests

The compaction logic lives in `compact.js` and the bounded fanin BFS lives in
`neighborhood.js`; both have no third-party dependencies. Tests use only
`node:test` and `node:assert`, and inject a fake query function into the BFS.

```bash
node --test tools/agent/svq-query-tool/test/
```

or from the package directory:

```bash
cd tools/agent/svq-query-tool && npm test
```

Node 20+ is recommended (`node:test` built-in). Tests cover fanin, fanout,
neighbors, path, neighborhood BFS, empty payloads, and explicit failures for
missing/malformed payloads. They do not invoke the `sv_query` binary.

## Use the DSH patch

`tools/agent/svq_query.patch.yml` disables `tool-bash`, `tool-fs`,
`tool-fs-search`, and `tool-skill`, then inserts `@svq/query-tool`:

```bash
dsh --profile headless \
  --patch tools/agent/svq_query.patch.yml \
  "Use only svq_query. ..."
```

Install the tool first (previous section); the patch only references the
package by id/name. Do not combine this patch with profiles that expect shell
or filesystem tools.

## Limitations (exact)

- **Snapshot-only**: queries require a prebuilt snapshot tag; there is no
  source, filelist, `--file`, or build path through this tool.
- **No MIG / connections / instances**: the snapshot used here does not expose
  module-instance graph (MIG) data, so `connections`, `instances`, `ports`,
  `params`, and hierarchy queries are unavailable.
- **Six intents only**: `fanin`, `fanout`, `neighbors`, `path`,
  `neighborhood`, `evidence`; `path` is directed and requires `dst`;
  neighborhood is fanin-only and capped at depth 8. Evidence reads a bounded
  source context for returned nodes only; `SVQ_SOURCE_ROOT` must point at the
  source root.
- **Compact IDs only**: attributes such as conditions, bit ranges, evidence,
  multi-driver status, and truncation flags are dropped by compaction.
- **One signal per call**: no batch queries; `depth` is limited to `1..32`.
- **Read-only**: the tool never writes RTL, snapshots, or project files.
- **Malformed payloads fail loudly**: missing `result`, missing
  `result.signals`, non-array signal fields, non-string IDs, or `ok: false`
  throw instead of returning an empty list.

## Layout

```text
tools/agent/
  README.md
  install_svq_query_tool.sh
  svq_query.patch.yml
  svq-query-tool/
    index.js          # DSH tool registration + sv_query invocation
    compact.js        # pure, dependency-free result compaction
    neighborhood.js   # pure injected-query bounded fanin BFS
    package.json
    test/index.js      # entry so `node --test test/` works across Node versions
    test/compact.test.js
    test/neighborhood.test.js
```
