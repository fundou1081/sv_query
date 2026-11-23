# Code-smell / robustness audit (2026-11-23)

> **Scope**: HEAD `68452fd0`; read-only independent audits.
> **Disposition**: remediation tracked as P197. No release claim is changed here.

## Highest-impact findings

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F1 | P1 | `verify consistency` reports `verified:true` with zero checks executed | `cli/core/semantic/verify.py` `_coverage_complete`/`verified`; `_check_bit_mapping` never increments skipped | zero checks => `unknown`; coverage false |
| F2 | P1 | session `verify_claim` path verdict can disagree with CLI | `trace/core/query/session_ops.py` vs `cli/core/semantic/verify.py`; endpoint/bidirectional checks absent | single shared claim implementation |
| F3 | P1 | filelist `refresh()` silently keeps stale graph when closure becomes unreadable | `graph_session.py` + `_build_identity` returning `None` | explicit refresh failure / rebuild |
| F4 | P1 | session `paths` unknown endpoint returns `found:false` | `graph_session.py` paths | structured `E_SIGNAL_NOT_FOUND` parity |
| F5 | P1 | mixed if/case + inline assign controlflow reports `complete` | `controlflow_analyzer.py` early return | downgrade when any driver unmodelled |
| F6 | P1 | P194.5i regression fixture has no alias node; test is vacuous | `test_p194_5i_depth_alias.py`; audit probe | construct real dangling alias graph |
| F7 | P1 | `load_graph()` bypasses snapshot capability guard | `unified_tracer.py` load_graph vs build_graph guard | key guard on hydrated-without-sources |
| F8 | P1 | graph cache manifest declares only `graph`; MIG builds never hit, claimed MIG not restored | `build_identity.py` manifest + cache hydrate | store/rehydrate real capabilities or reject |
| F9 | P1 | quiet is process-global; CLI mutates `sys.argv`; library calls still print stderr | `cli/main.py`, `compiler.py`, `graph_builder.py` | explicit context, let Typer own flags |
| F10 | P2 | session/CLI connection consistency check diverges | `session_ops.py` vs `verify.py` | shared check |
| S1 | P1 | shift amount parsed from expression text; `4'd2` read as 4 | `query/signal.py` `_expr_source_bits` | semantic shift operand |
| S2 | P1 | reset classification by name/source substring | `source_assignment.py`, `trace_evidence.py` | semantic branch classification |
| S3 | P1 | evidence `is_verified` by leaf-name substring | `trace/core/trace_evidence.py` | compare resolved LHS identity |

## Other P2

- `_expand_bit_children` uses ID prefix over the whole graph;
- bit index/range parsed from node IDs despite metadata fields;
- FSM state/reset and ternary/concat classification from strings;
- `confidence="high"` ignores bit/coarse/truncated provenance;
- `instances --depth 1` counts dots in full paths;
- diagnostic fallbacks return `[]`/`0` but look like success;
- cache singleton ignores later `SVQ_CACHE_DIR` changes;
- `check_core_except` keyword-marker gate is weaker than explicit status.

## Non-findings

P194.5i alias decision now uses BIT_SELECT + parent + bit_range; compact markers
retained; CLI `verify claim` endpoint matching is the correct reference; snapshot
MIG guard works on the normal build path; cache/snapshot writes are atomic;
stdio envelopes are structured.

## Remediation

P197.1 through P197.10 in PLAN.md. P194.5d remains blocked until P197.1-P197.3
and the P194.5e-h items land.
