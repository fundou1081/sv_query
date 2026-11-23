# P194.5 initial local measurement (2026-11-23)

> **Status**: initial evidence only; **not** an external benchmark.
> **HEAD**: `fa8453e9` (P194.4); PyPI 0.3.6 does not include P194.2f–P194.4.
> **Machine**: macOS arm64, Python 3.11.4, pyslang 11.0.0.

## 1. Four-op session amortization

Task: `graph_nodes + drivers + paths + verify_consistency`, warm cache.

| design | 4 CLI calls | 1 session / 4 requests | time ratio |
|---|---:|---:|---:|
| picorv32 | 6,477 ms | 2,248 ms | 2.88x |
| SERV | 11,394 ms | 3,931 ms | 2.90x |
| verilog-axi | 138,080 ms | 46,907 ms | 2.94x |

The gain is one build instead of four; it is not a claim about query accuracy.

## 2. Cross-process cache coverage

`graph nodes` realizes warm cache:

```text
picorv32   2,339 -> 247 ms
SERV       3,845 -> 281 ms
verilog-axi 46,447 -> 665 ms
```

`stats`, `drivers`, `paths`, `verify consistency` were cold approximately equal
to warm in this setup; they rebuild the MIG/full graph per process. This is a
known cache-coverage gap for P194.5 follow-up.

## 3. Fresh-agent trial (small fixture)

A 112-line / 804-token fixture took:

```text
capabilities --json: ~20,424 tokens (bytes/4 heuristic)
20 CLI investigation calls: ~15,964 stdout tokens
source-only baseline: 804 tokens for one full read
```

This is directional evidence that, on a tiny design, sv_query increases token
cost while reducing manual cross-module stitching. It does not establish token
savings on large designs.

## 4. Observed friction

- `capabilities --json` is ~72 KB; the documented first call dominates cost.
- `controlflow` returned empty conditions with `condition_status=complete` for an
  inline continuous-assign condition; the semantics need an explicit scope label.
- `drivers` repeats `condition_paths[].analysis{}`; `trace evidence` repeats
  module source in `enclosing_chain`.
- Claim type/key schema is not discoverable in capabilities.
- Session `paths` and CLI `paths --directed` used different graph views.
- `--quiet` is opt-in; JSON consumers still pay stderr/conversation noise.

## 5. Non-claims

This document does **not** claim:

- third-party external validation, HWE/VeriBugBench results, or ground-truth accuracy;
- actual provider token counts/billing (bytes/4 only);
- speedup vs another tool;
- large-SoC scale or variance/confidence intervals.

Exact reproduction notes and raw worker reports remain outside the repository;
the measurements above are the durable summary.
