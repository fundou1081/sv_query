# Snapshot-first workflow

## 1. Build once

```bash
# optional: conservative prune to top-reachable filelist
sv_query filelist prune --filelist all.f --top top --output top.f --apply --json -q

# save graph
sv_query snapshot save top.sv --filelist top.f --tag "$TAG" --json -q
sv_query snapshot list --json -q
```

`filelist prune` is dry-run by default; `--apply` writes the output file.

## 2. Query from snapshot

```bash
sv_query drivers <ID> --from-snapshot "$TAG" --depth 1 --json -q
sv_query loads   <ID> --from-snapshot "$TAG" --depth 1 --json -q
sv_query paths   <A> <B> --directed --canonical --from-snapshot "$TAG" --json -q
sv_query dataflow analyze <A> <B> --max-paths 5 --from-snapshot "$TAG" --json -q
sv_query verify claim --claim '{"type":"driver","signal":"S","driver":"D"}' \
  --from-snapshot "$TAG" --json -q
sv_query verify consistency --checks connection --from-snapshot "$TAG" --json -q
```

## 3. Support matrix

`--from-snapshot` is accepted by graph-oriented commands:

```text
drivers, loads, paths, dataflow analyze, trace frontier,
verify claim, verify consistency,
instances, ports, connections, hierarchy
```

Source/semantic commands need `--filelist` (or `-f`):

```text
scope, params, stats, controlflow analyze,
graph nodes/edges/subgraph, class,
trace constraints / covergroups / coverpoints / covergroup,
trace lookup / profile / manifest, search
```

If a command rejects `--from-snapshot`, use the source filelist; do not retry with
different flags blindly.

## 4. Snapshot limits

- Snapshot stores graph + optional MIG; source recovery may be unavailable.
  `trace evidence --from-snapshot` returns a keyed evidence object; when source is
  unavailable, `source_location` may be null or expression-only and
  `is_verified=false` — report the limitation, do not say “no assignment exists”.
- A snapshot is a time-point artifact. If the code changed, rebuild it.
- `snapshot list` returns a top-level array; `snapshot compare` uses tags.
