# sv_query known limitations (English)

> **Status**: English summary, 2026-11-21.
> **Full detail**: [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md) is the canonical,
> more detailed record. This page gives external users the boundaries that
> matter before trusting a query result.

## 1. Beta / validation scope

sv_query is a 0.3.x beta. Core queries are read-only and JSON-first, but:

- external semantic completeness is **not** claimed;
- the CVA6 value case (P187) is **non-blind**: cases were selected from fix
  diffs; it is not an automatic-discovery benchmark;
- the P192 blind comparison is **N=1, same model, symptom known**; it does not
  establish accuracy or speedup;
- no HWE-Bench/VeriBugBench result is claimed.

## 2. Pyslang / frontend limits

Known frontend boundaries include:

- generate-if/else edge cases;
- `ElementSelect` parsing;
- pyslang memory limits on very large designs;
- old snapshot `EdgeKind`/`NodeKind` compatibility checks;
- covergroup elaboration builtin-shadow limits.

When the frontend cannot extract a fact, core commands must return an explicit
error/`unknown`; they must not invent a verified result.

## 3. Bit-level precision

Bit-level tracing is precise only where sv_query models the operator/connection.
It is **bus-granular** for cases such as:

- comparisons;
- variable shifts;
- some arithmetic/concatenation combinations;
- dynamic memory indices (`precision=unknown`).

Bus endpoints may have bit-select children. Use:

```bash
sv_query drivers <bus> --json            # has_bit_select_drivers / bit_nodes
sv_query graph nodes --match <bus>       # drill into a slice
sv_query drivers '<bit-node>' --evidence
```

`dataflow` can keep `is_reachable=false` for a bus endpoint while reporting
`bit_node_paths_exist=true`; false is not silently rewritten to unknown.

## 4. Paths and dataflow

`paths` returns a **canonical structural path**, not a “shortest/most likely”
path.

`dataflow` is a bounded search:

- budget/timeout exhaustion → `is_reachable=null` + `unknown`;
- `truncated`/`sample` output must not be read as `verified`;
- CLOCK/RESET edges are timing annotations, not data edges.

## 5. Snapshots

- snapshots do not contain source text;
- newer snapshots have edge evidence; older snapshots may not;
- `build_phase=hydrated` MIG/class semantics are incomplete;
- only a subset of core commands support `--from-snapshot`;
- old snapshots without MIG fail explicitly (`E_SNAPSHOT_NO_MIG`).

`trace evidence --no-cache` is currently a no-op for cache policy.

## 6. CLI / JSON contract

- `core`: read-only, JSON, stable schema;
- `experimental`/`exp`: no compatibility promise;
- check both `ok` and `error_code`; exit code alone is not the contract;
- unknown signals in `drivers`/`loads`/`trace evidence`/`trace profile` return
  `rc=0`, `ok=false`, `E_SIGNAL_NOT_FOUND` (hybrid business-error exceptions);
- other core failures are `rc=1`, `ok=false`.

The command surface is ratcheted at 45 canonical / 39 visible / 2 aliases
(32 standard / 13 direct envelopes).

## 7. Evidence quality

- `trace impact` risk scores are **uncalibrated heuristics**, not measurements;
- source-location evidence can be incomplete for snapshot/hydrated sources;
- a query result with no evidence is not necessarily a verified fact;
- `unknown` / `partial` must be preserved by agents, not rounded to false.

## 8. Performance

Cold graph construction can be seconds to tens of seconds depending on design
size. Warm in-graph queries are much faster. Do not use a warm number as a cold
startup expectation. For repeated work, save/use a snapshot where supported.

## 9. Privacy / telemetry

sv_query does not require uploading RTL or query content to produce local query
results. Treat RTL as confidential: keep filelists and designs local, and do not
paste proprietary RTL into public issues. A desensitized reproducer policy is
tracked separately in the trial-readiness plan.

## 10. Fixed limitations worth knowing

- `diagnose timescale` now detects `MissingTimeScale` on mixed designs
  (some files with a time scale, some without); analysis paths still inject a
  default time scale.
- Historical absolute-path test symlinks and private development assets were
  removed from the public tree (P193.1/P193.2).
