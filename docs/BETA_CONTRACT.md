# sv_query beta contract (0.3.x)

> **Status**: external beta contract, 2026-11-21.
> **Purpose**: set expectations before users trust a query result.
> **Detailed boundaries**: [KNOWN_LIMITATIONS_EN](KNOWN_LIMITATIONS_EN.md) /
> [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md) (canonical detail).

## 1. Stable surface

These are the parts external users may rely on in 0.3.x:

- **core CLI commands** and their JSON success/failure envelopes;
- `sv_query capabilities --json` as the authoritative command surface;
- read-only behavior: sv_query does not modify RTL/project files;
- explicit error codes and `ok` / `rc` semantics;
- source evidence fields where the command documents them;
- `verified` / `contradicted` / `unknown` as distinct states.

`core` is read-only + JSON + stable schema. Additive optional fields may appear
in patch releases; existing required keys/types and failure semantics should not
change without a documented contract change.

## 2. No promise

These are **not** guaranteed in 0.3.x:

- semantic completeness for all SystemVerilog;
- accuracy/recall on arbitrary real designs;
- external benchmark parity (HWE-Bench/VeriBugBench etc.);
- `exp/` command behavior, fields, or existence;
- performance; cold-start or large-design memory use;
- bit-level precision where the model is bus-granular (comparisons, variable
  shifts, dynamic indices, some arithmetic/concatenation);
- old snapshots from previous schema/MIG versions;
- any automatic discovery of unknown bugs.

`exp` changes are bug-fix-only, with no compatibility promise.

## 3. Evidence grades

```text
verified      evidence satisfies the documented claim/contract
partial       some evidence exists but coverage is incomplete
unknown       not enough evidence / search budget exhausted / unsupported endpoint
contradicted  evidence conflicts with the claim
```

`unknown` is **not** false. Agents must preserve `unknown`/`partial`, not round
them to a confident answer. `sample`/`truncated` must not be reported as
`verified`.

## 4. Bit precision

Bit-level tracing is precise only where sv_query models the operator/connection.
Bus queries may expose bit-select children via `bit_nodes` /
`has_bit_select_drivers`; `dataflow` can keep `is_reachable=false` while
`bit_node_paths_exist=true`. Drill into the slice before claiming influence.

## 5. Performance expectation

Warm in-graph queries are typically milliseconds. Cold graph construction can be
seconds to tens of seconds depending on design size; a large design can be much
slower. Do not use a warm number as a cold-start expectation. Use snapshots where
supported for repeated work.

## 6. Snapshot surface

Only a subset of core commands support `--from-snapshot`. Snapshots store derived
graph data, not source text; old snapshots may lack edge evidence/MIG and fail
explicitly (`E_SNAPSHOT_NO_MIG`).

## 7. CLI / JSON failure semantics

- `core` operational failure → `rc=1`, `ok=false`, structured `errors[]`;
- hybrid business failures for unknown targets in `drivers` / `loads` /
  `trace evidence` / `trace profile` → `rc=0`, `ok=false`,
  `error_code=E_SIGNAL_NOT_FOUND`;
- look at both `ok` and `error_code`; exit code alone is not the contract.

Command surface is ratcheted:

```text
45 canonical / 39 default-visible / 2 aliases
32 standard / 13 direct
```

## 8. Validated evidence (scoped)

- CVA6 historical fixes: **non-blind** case study (selected from fix diffs);
- P192 blind comparison: **N=1, same model, symptom known**;
- no claim of general external accuracy/speedup.

Links:

- [CVA6 value cases](validation/P187_VALUE_CASES_CVA6_2026-11-19.md)
- [P192 blind comparison](validation/P192_BLIND_COMPARE_2026-11-20.md)

## 9. Privacy

No telemetry or RTL upload in the installed runtime. See
[PRIVACY](PRIVACY.md). Miss reports must use
[MISS_REPORT_GUIDE](MISS_REPORT_GUIDE.md) and a desensitized fixture or
structural-only description.

## 10. Feedback loop

A useful external beta report includes:

```text
query + version
expected conclusion
actual rc/ok/error_code/JSON fields
safe minimal fixture or structural-only description
```

See [MISS_REPORT_GUIDE](MISS_REPORT_GUIDE.md).
