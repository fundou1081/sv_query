# Command decision tree

> `sv_query capabilities --json` is authoritative. All core commands are read-only.
> Flags go after the leaf command.

## 1. Pick the command

| User asks | Command |
|---|---|
| Who drives X? | `drivers X --depth 1` |
| Who reads X? | `loads X --depth 1` |
| Is there a directed path A→B? | `paths A B --directed --canonical` |
| All paths / variants? | `paths A B --directed --all --max 20` |
| Value/data flow with conditions/latency? | `dataflow analyze A B --max-paths 5` |
| Why is X driven this way? | `controlflow analyze X` |
| Where is X assigned? | `trace evidence X` |
| Declaration / clock / reset / sequential? | `trace profile X` |
| What structure is around X? | `graph subgraph X --depth 2` |
| Does this claim hold? | `verify claim --claim ...` |
| Is the graph self-consistent? | `verify consistency --checks connection` |
| Structural sibling finding? | `verify structural` (symmetry only; not typo product) |
| Class / constraint / covergroup facts? | `class`, `trace constraints`, `trace covergroups` |

## 2. Common templates

```bash
# discovery
sv_query capabilities --json --recommended -q
sv_query snapshot list --json -q

# direct neighbors (snapshot)
sv_query drivers top.u.data --from-snapshot "$TAG" --depth 1 --json -q
sv_query loads   top.u.data --from-snapshot "$TAG" --depth 1 --json -q

# paths
sv_query paths top.a top.y --directed --canonical --from-snapshot "$TAG" --json -q
sv_query paths top.a top.y --directed --all --max 20 --from-snapshot "$TAG" --json -q

# source mode
sv_query drivers top.u.data -f top.sv --depth 1 --json -q
sv_query dataflow analyze top.a top.y --max-paths 5 -f top.sv --json -q
sv_query controlflow analyze top.y -f top.sv --json -q
sv_query trace evidence top.y -f top.sv --json -q
sv_query trace profile  top.y -f top.sv --json -q
```

## 3. Flags: do not confuse

| Flag | Applies to | Meaning |
|---|---|---|
| `--depth/-d` | drivers/loads | `1` = direct; omit = recursive |
| `--max-results/-N` | drivers/loads | post-cap `count`; `driver_count` remains pre-cap |
| `--max/-n` | `paths --all` | max returned paths |
| `--max-paths/-n` | `dataflow analyze` | max returned paths |
| `--max-nodes/--max-edges` | graph subgraph | local graph budget |
| `--max-findings` | verify structural | finding cap |
| `--directed/-d` | paths | follow data direction only |
| `--canonical` | paths | deterministic structural variant |
| `--include-clock/--include-reset` | loads (and fanout) | include sensitivity edges |

## 4. Snapshot vs source

Use `--from-snapshot` for graph queries when a tag exists. Use `--filelist`/`-f`
for semantic/source commands and for evidence/profile. See [snapshot.md](snapshot.md).

## 5. exp commands

`audit`, `diagnose`, `trace impact`, `trace overview`, `review render`,
`architecture graph` are hidden/unstable/heuristic. Only use when asked, and label
the result as exp/heuristic, never as a verified fact.
