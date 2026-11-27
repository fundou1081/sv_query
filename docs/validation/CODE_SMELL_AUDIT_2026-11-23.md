# Code-smell / robustness audit (2026-11-23)

> **Scope**: HEAD `68452fd0`; read-only independent audits.
> **Disposition**: P1 remediation landed in P197.1–P197.9; P197.10 reconciles claims/tests and records remaining P2 debt.

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

## P197.10 remediation reconciliation (2026-11-25)

P1s targeted for remediation are fixed and gate-backed; F4 is fixed by P194.5g; F5 by P194.5f; F10 remains tracked (P197.12/P194.5f); no P1 is silently verified.

| ID | Status | Claim | Regression |
|---|---|---|---|
| F1 | fixed | C-07 | `test_verify_coverage.py` |
| F2 | fixed | C-58 | `test_p197_2_verify_parity.py` |
| F3 | fixed | C-67 | `test_p197_3_refresh_guard.py` |
| F4 | fixed (P194.5g) | C-63 verified | `test_p194_5g_paths_errors.py` |
| F5 | fixed (P194.5f) | C-62 verified | `test_p194_5b_controlflow_claims.py` |
| F6 | fixed | C-64/C-70 | `test_p194_5i_depth_alias.py` |
| F7 | fixed | C-67 | `test_p197_3_refresh_guard.py` |
| F8 | fixed | C-45/C-48 | `test_p197_7_mig_cache.py` |
| F9 | fixed | C-71 | `test_p197_8_quiet_context.py` |
| F10 | open (P194.5f/P197.12) | C-62/C-58 | shared connection checks |
| S1 | fixed | C-68 | `test_p197_4_shift_semantic.py` |
| S2 | fixed | C-69 | `test_p197_5_reset_evidence.py` |
| S3 | fixed | C-69 | `test_p197_5_reset_evidence.py` |

P2 disposition:

- fixed: `_expand_bit_children` id-prefix scan; bit index/range id parsing;
  core-except keyword-marker gate; reset substring; cache MIG manifest.
- fixed by P198.10/P198.11: little-endian concat direction, concat IR parity.
- open and tracked: confidence provenance and `instances --depth` (P197.16),
  diagnostic `[]`/`0` fallbacks (P197.16), cache singleton env (P197.16),
  FSM state/reset string classification (P194.5f), remaining except
  name-substring marker (P197.15), evidence RHS substring + compound-reset
  heuristic (P197.14), verify-parity P2 (P197.12).
