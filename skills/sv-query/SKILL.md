---
name: sv-query
description: Read-only SystemVerilog query + objective verification for RTL debug. Use when a snapshot tag or filelist is available and the question is "who drives/loads X", "how does X reach Y", "why is X conditional", "find source evidence", or "verify a driver/path claim". Core: drivers, loads, paths, dataflow, controlflow, trace evidence/profile, verify consistency/claim/structural. Do NOT use for lint/simulation/physical design, coverage generation, typo ranking, or interactive UI.
---

# sv-query — agent query + verify protocol

`sv_query` is the installed CLI (fallback: `python3 run_cli.py` from the repo).
It is **read-only with respect to RTL**: queries do not modify RTL/project files.
`snapshot save` and `filelist prune --apply` write cache/requested output files only.

> The command surface is defined by `sv_query capabilities --json`.
> Do not trust stale command lists in docs or memory.

## 0. Scope

Use it for:

- canonical signal id / aliases / hierarchy / ports / params
- drivers / loads / structural paths / dataflow / conditions
- source evidence and waveform-path alignment metadata
- objective verification: `verified` / `contradicted` / `unknown`

Do **not** use it for:

- lint, compile sign-off, simulation values, waveform dump
- coverage generation, typo detection/ranking
- full-design visualization or interactive debug UI
- exp commands as a fact source

## 1. Discover first

```bash
sv_query capabilities --json --recommended -q
sv_query capabilities --json -q
sv_query snapshot list --json -q          # top-level JSON array, not an envelope
```

Only use exp when the user explicitly asks:

```bash
sv_query capabilities --json --include-exp -q
# audit / diagnose / trace impact / trace overview / review render / architecture graph
# hidden, unstable, heuristic; no schema/claim contract
```

## 2. Prefer snapshot, fallback to source

If a snapshot tag exists, do **not** rebuild from RTL:

```bash
sv_query drivers top.u.data --from-snapshot "$TAG" --depth 1 --json -q
sv_query loads   top.u.data --from-snapshot "$TAG" --depth 1 --json -q
sv_query paths   top.a top.y --directed --canonical --from-snapshot "$TAG" --json -q
```

Source/filelist mode:

```bash
sv_query drivers top.u.data -f top.sv --depth 1 --json -q
sv_query drivers top.u.data --filelist rtl.f --depth 1 --json -q
```

Build a snapshot when one does not exist (one-time cost):

```bash
sv_query filelist prune --filelist all.f --top top --output top.f --apply --json -q
sv_query snapshot save top.sv --filelist top.f --tag "$TAG" --json -q
```

Snapshot support is command-specific. It works for graph queries such as
`drivers/loads/paths/dataflow/verify claim/verify consistency/instances/ports/connections/hierarchy`;
semantic/source commands (`class`, `constraints`, `covergroups`, `controlflow`, `scope`,
`params`, `graph`, `trace profile`) require `--filelist`. `trace evidence` accepts
`--from-snapshot`; its `source_location` may be null and `is_verified` false when
the snapshot cannot recover source (the evidence object itself remains keyed).

See [references/snapshot.md](references/snapshot.md).

## 3. Query protocol: D → S → Q → E → V

### D. Discover scope

```bash
sv_query instances --from-snapshot "$TAG" --json -q
sv_query hierarchy --from-snapshot "$TAG" --depth 3 --json -q  # deep trees may need 4+
sv_query ports <instance> --from-snapshot "$TAG" --json -q
sv_query connections <instance> --from-snapshot "$TAG" --json -q
```

`connections` accepts **instance paths only**, not module names.

### S. Scope / local graph (source mode)

```bash
sv_query scope <instance> --filelist rtl.f --json -q
sv_query params <instance> --filelist rtl.f --json -q
sv_query graph subgraph <seed> --depth 2 --direction in \
  --edge-kinds driver,connection --max-nodes 80 --filelist rtl.f --json -q
```

Control/mux branches are a separate edge kind:

```bash
sv_query graph subgraph <ternary-or-control-node> --edge-kinds branch \
  --depth 2 --filelist rtl.f --json -q
sv_query graph nodes --kind OP_TERNARY --filelist rtl.f --json -q
```

### Q. Query facts

Direct neighbors must use `--depth 1`:

```bash
sv_query drivers <ID> --from-snapshot "$TAG" --depth 1 --json -q
sv_query loads   <ID> --from-snapshot "$TAG" --depth 1 --json -q

# default: one path, suitable for shortest/minimal questions
sv_query paths <SRC> <DST> --directed --from-snapshot "$TAG" --json -q
# canonical: max-nodes deterministic variant, for "most granular" deep chains
sv_query paths <SRC> <DST> --directed --canonical --from-snapshot "$TAG" --json -q
# all variants
sv_query paths <SRC> <DST> --directed --all --max 20 --from-snapshot "$TAG" --json -q

sv_query dataflow analyze <SRC> <DST> --max-paths 5 --from-snapshot "$TAG" --json -q
sv_query controlflow analyze <ID> --filelist rtl.f --json -q
sv_query trace frontier <ID> --direction fanin --from-snapshot "$TAG" --json -q
```

`--depth 1` is direct (distance=1). Without it, fanin/fanout recurse to the end
and can mix terminal/control sources into the answer.

### E. Evidence

```bash
sv_query trace evidence <ID> --filelist rtl.f --json -q
sv_query trace evidence <ID> --from-snapshot "$TAG" --json -q   # may be null
sv_query trace profile  <ID> --filelist rtl.f --json -q
```

`trace evidence` points to the assignment/always line. `trace profile.source`
points to the declaration/driver. Snapshot mode may return `evidence:null`.

### V. Verify before concluding

```bash
# signal = target; driver = source (fanin(signal) must contain driver)
sv_query verify claim --claim '{"type":"driver","signal":"S","driver":"D"}' \
  --from-snapshot "$TAG" --json -q

sv_query verify claim --claim '{"type":"path","from":"A","to":"B"}' \
  --from-snapshot "$TAG" --json -q

sv_query verify consistency --checks connection --from-snapshot "$TAG" --json -q
```

For `verify claim`, read `result.status`: `verified` / `contradicted` / `unknown`.
`unknown` is not false. For a claim with a missing endpoint, report the status,
not a boolean. For `verify consistency`, read `result.verified`,
`unknown_checks[]`, and `checks[].checked`; there is no top-level `result.status`.

## 4. Field contract (the short list)

| Query | Identity | Count / budget |
|---|---|---|
| `drivers` | `result.signals[0].drivers[].id`; `driver_count` counts distinct DRIVER-edge sources (can include PORT_IN/CONST); excludes CLOCK/RESET/CONNECTION/BRANCH and self | `count` (all returned nodes, post-cap), `pre_filter_count`, `truncated`, `truncated_by_depth` |
| `loads` | `result.signals[0].loads[].id` | `count`, `pre_filter_count`, `truncated` |
| `paths --canonical` | `found`, `hop_count`, `path`, `candidate_count`, `canonical_policy` | `truncated` |
| `paths --all` | `count`, `all_paths` | `truncated`, `truncation_reason` |
| `dataflow analyze` | `is_reachable`, `paths[]`, `search_status` | `truncated`, `truncation_reason` |
| `trace evidence` | `result.signals[0].evidence.source_location`, `source_text` | `credibility_score`, `is_verified` |
| `verify claim` | `result.status` | `result.machine.unknown_kind` |
| `verify consistency` | `verified`, `checks[].status`, `checks[].checked`, `checks[].violations` | `coverage_complete`, `unknown_checks`, `total_violations` |

`count` is the returned item count after cap. `driver_count` is a separate
count of **DRIVER-edge sources**; it can include PORT_IN/CONST, excludes
CLOCK/RESET/CONNECTION/BRANCH and self, and is **not capped** by `--max-results`.
For “list all direct drivers”, use `count`/`drivers[].id`, not `driver_count`.
`pre_filter_count` is the count before cap.
`truncated_by_depth=true` means more edges exist below the depth boundary.

See [references/fields.md](references/fields.md).

## 5. Failure semantics

- `drivers`/`loads` unknown signal: **rc=0**, `ok:false`,
  `resolution=not_found`; error code is in `errors[0].error_code`.
- `paths` unknown endpoint: **rc=1**, `ok:false`; no path with valid endpoints:
  **rc=0**, `ok:true`, `found:false`.
- Empty neighbor list is a fact: `ok:true`, `count=0`.
- `verify claim` insufficient evidence: `ok:true`, `status:"unknown"`.
- `--json` is not guaranteed on usage/validation errors; always capture
  stdout and stderr separately and check whether stdout parses.
- `-q` suppresses most stderr, not all; do not merge stderr into JSON.

## 6. Pitfalls

1. **`paths` default is undirected.** Always use `--directed` for dataflow direction.
2. **Ternary/mux is not a data path.** `paths` uses DRIVER/CONNECTION; `OP_TERNARY`
   is control/branch. Do not claim a path passes through ternary unless edges show it.
3. **`drivers --depth 1` can include CLOCK/RESET/constant/ternary sources.**
   Check node `kind`/`trace profile` and filter; `loads` excludes CLOCK/RESET by default,
   `--include-clock --include-reset` opts in. `driver_count` is not the same as
   `len(drivers)`; it counts only DRIVER-edge sources.
4. **Bare names are ambiguous.** Use canonical/hierarchical ids from `instances`/`drivers`.
5. **`count` is post-cap, but `driver_count` is not.** Inspect `pre_filter_count`,
   `driver_count`, and `truncated` separately.
6. **Evidence is a source pointer, not proof.** `credibility_score` is discrete
   `{0.0,0.2,0.4,0.6,1.0}`; `is_verified` is snippet+expr/name cross-check.
   `trace evidence` can have null/empty source fields for buses/arrays and can point
   at a reset branch; use `trace profile.source.driver` for the functional assignment.
   Do not dump `enclosing_chain` into context.
7. **Semantic domain is source-only.** `class`/`constraints`/`covergroups`/`controlflow`
   need `--filelist`, not snapshot. Class members must be instance-qualified.
8. **Driver claim orientation.** `signal` is the target; `driver` is the source.
   Reversing them changes verified ↔ contradicted.
9. **`class --member` takes a member name, not an instance-qualified id.**
   It returns `candidates[]`; `--instance` belongs to `trace covergroup`.

Detailed pitfalls and real evidence: [references/pitfalls.md](references/pitfalls.md).

## 7. Semantic domain (source mode only)

```bash
sv_query class <Class> --relations --filelist rtl.f --json -q
sv_query trace constraints top.e.p.addr --filelist rtl.f --json -q
sv_query trace constraint-chain top.e.p.addr top.e.p.len --filelist rtl.f --json -q
sv_query trace covergroups --filelist rtl.f --json -q
sv_query trace covergroup <cg> --instance <inst> --rand --filelist rtl.f --json -q
```

This is **query**, not solver proof: `co-membership` / declared constraints are facts;
UNSAT/SAT/coverage closure are not implied.

See [references/semantics.md](references/semantics.md).

## 8. Output discipline for agents

If the task specifies exact output keys, return **exactly those keys**; do not wrap
them or add extra keys. Otherwise return strict JSON with key facts and an optional
`queries[]` audit log. Never invent ids; use canonical ids from the tool.

```json
{
  "answer": {"drivers": ["..."], "loads": ["..."]},
  "status": "verified|contradicted|unknown|found|not_found",
  "queries": [{"cmd": "drivers ... --depth 1", "ok": true}]
}
```

## 9. References

- [commands.md](references/commands.md) — decision tree + exact command templates
- [fields.md](references/fields.md) — fields, envelopes, failure matrix
- [snapshot.md](references/snapshot.md) — build/prune/list + support matrix
- [pitfalls.md](references/pitfalls.md) — verified failure modes
- [semantics.md](references/semantics.md) — class/constraint/covergroup
- [examples.md](references/examples.md) — worked short/long examples
