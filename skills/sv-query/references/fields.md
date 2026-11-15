# Result fields and failure semantics

## 1. Envelopes

Most core commands use:

```json
{"ok": true, "command": "...", "params": {}, "result": {}, "errors": []}
```

Direct-envelope exceptions (no `ok/result` or command-specific shape):

```text
capabilities, search, paths, instances, hierarchy, ports, params, connections, class,
snapshot save/list/compare/delete
```

`snapshot list` returns a top-level JSON **array**. Always check the command docs in
`capabilities.commands[].envelope`.

## 2. Trace signal fields

`drivers` / `loads`:

```text
result.signals[]                # one per requested signal
  signal, index, count, pre_filter_count, truncated, resolution,
  resolved_signal, candidates, suggestions, error
  drivers[] / loads[]           # nodes
  driver_count                  # drivers only: distinct direct DRIVER sources;
                                # excludes CLOCK/RESET; NOT capped by -N
  driver_conflict               # drivers only, heuristic
  dynamic_index, function_call, runtime_system_call
  conditions[], condition_truncated
  truncated_by_depth, cycles_detected
```

Node fields: `id`, `module`, `kind`, `width`, `distance`, `precision`, `parent`,
`bit_range`, `condition(s)`, evidence (with `--evidence` on drivers/loads).

## 3. Paths

`--canonical`:

```text
found, hop_count, path, candidate_count, canonical_policy, truncated
```

`--all`:

```text
count, all_paths, truncated, truncation_reason, expansions
```

`paths` is a **direct envelope**: `ok/src/dst/...` at top level, not under `result`.
`--canonical` fields live at top level; `--all` fields live at top level.
`paths` with a valid endpoint pair but no route: `ok:true, found:false`.
Unknown endpoint: `ok:false`, rc=1.

## 4. Dataflow

```text
is_reachable, search_status, truncated, truncation_reason,
paths_count, paths[].segments[],
primary_latency_cycles, primary_is_async,
timing_risk, risk_model
```

`timing_risk`/`risk_model` are heuristic labels, not measurement.

Snapshot caveat: a legacy snapshot without MIG can return
`checks[].status=unknown, checked=0` while `coverage_complete=true`.
Read `unknown_checks` and `checks[].checked`; do not treat that as a pass.

## 5. Evidence / profile

`trace evidence`:

```text
result.signals[0].evidence
  source_location {file,line_start,line_end,column}
  source_text, enclosing_always/if/assign/class/constraint,
  enclosing_chain, credibility_score, is_verified
```

`credibility_score ∈ {0.0,0.2,0.4,0.6,1.0}` (0.8 is unreachable). `is_verified`
is a snippet + expression/name cross-check, **not** a proof.

`trace profile`:

```text
type, bit, source {file,line,declaration,driver},
role {is_clock,is_reset,is_enable,is_port},
clocks[], resets[], sequential, driver_count, load_count
```

## 5.1 Frontier

```text
result.frontier[] {signal, reason, ...}
result.summary.frontier_count
```

Reasons include `no_structural_edge`, `instance_boundary`, `cycle_or_all_seen`,
`depth_limit`. Frontier reports where the search stopped, not a proof of no path.

## 6. Failure matrix

| Case | rc | stdout |
|---|---:|---|
| drivers/loads unknown signal | 0 | `ok:false`, `resolution=not_found`, nested `errors[0].error_code` |
| drivers/loads empty neighbors | 0 | `ok:true`, `count=0` |
| paths unknown endpoint | 1 | `ok:false` |
| paths valid, no route | 0 | `ok:true`, `found:false` |
| verify claim unknown | 0 | `ok:true`, `status:"unknown"` |
| missing `-f`/`--filelist` | 1 | command-dependent: graph core often JSON; class/constraints may traceback; controlflow plain text |
| unknown flag | 2 | plain text |
| `--json` audit invalid checks | 1 | plain text, **no JSON** |
| `trace evidence --from-snapshot` bus/legacy | 0 | `evidence:null`; bit nodes may work |

Rules:

- Check `ok` first, then `errors[0].error_code`, then `resolution`/`status`.
- Do not assume rc=0 means found; do not assume rc=1 means no route.
- `-q` is best-effort stderr suppression; keep stderr separate.
