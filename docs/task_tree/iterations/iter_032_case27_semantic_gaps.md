# Iteration 32: case27 3-Gap Investigation (Plan A not converged)

**Metadata**:
- **Iteration #**: 32
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_h (follow-up to iter_031)
- **Created**: 2026-08-26 21:55 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🚧 **KNOWN ISSUES** — investigation completed, no fix landed

---

## 🎯 Original Goal

User instruction (15:59 GMT+8): "我依然看到了悬空的节点" — verify iter_031's `{}` Concat fix is correct vs SV code logic.

User instruction (21:21 GMT+8): "直接实现方案A 把这个所有做好debug记录" — fix all discovered gaps + record everything.

User instruction (21:38 GMT+8): "我想要先确认 singal graph 的结果是否正确，是否符合代码逻辑" — 1:1 truth-layer verification.

User instruction (21:43 GMT+8): "修复 1 2 3" — fix all 3 gaps.

User instruction (21:49 GMT+8): "按你推荐的做" — use A2 (test-first, fix in stages).

User instruction (21:52 GMT+8): "继续A" — continue Plan A.

User instruction (21:55 GMT+8): "继续A1" — continue grinding Plan A1.

---

## 📊 Outcome Summary

iter_031 (back-edge snap, `c146b0a`) was a **clean win**: 32/32 batch PASS, 5/5 1:1 ✅, 0悬空 nodes.

iter_032 (semantic completeness) was **NOT completed** — 3 real gaps discovered but **0 of 3 were resolved** after multiple fix attempts. **Plan A was not converged** in this session.

A failing test (`test_case27_1to1_truth.py`) is committed as untracked WIP, locking in the 3 gaps as red tests so any future session can pick up.

---

## 🔬 Investigation Process

### T.68: 1:1 semantic check — 3 real gaps confirmed

User asked: "are the graph results correct vs code logic?"

After iter_031 visual fix, ran a structured comparison of case27 SVG vs SV source.

**3 real gaps identified**:

| Gap | SV 期望 | SVG 实际 |
|---|---|---|
| 1: generate unfold | `acc[1], acc[2], acc[3], acc[4]` | 4× `acc[i]` 模板 |
| 2: 4 × `*` mul ops | `prod = data * weights[0/1/2/3]` | 0 × `*` op |
| 3: sum_out ternary | `(acc[N] > {W{1'b1}}) ? 8'd255 : acc[N][?:0]` | 0 × `?:` + sum_out port 缺失 |

### T.69-T.71: Diagnostic deep-dive

| Turn | What | Finding |
|---|---|---|
| T.69.1-3 | `--debug-trace` flag probe | doesn't exist in this codebase |
| T.70.1-7 | pyslang native API probes | pyslang v11.0.0 API differs from what codebase was written for |
| T.71.1-13 | Build_graph / SignalGraph probe | got correct API path `from trace.unified_tracer import UnifiedTracer` |
| T.71.15 | Dump `_expr_trees`, `_gen_iter_map`, `_gen_block_map` | `_expr_trees` has concrete keys `acc[1..4]` ✓; `_gen_iter_map = {acc[1]:0, acc[2]:1, acc[3]:2, acc[4]:3}` ✓ |
| T.73.1 | Dump `viz.edges` for case27 | **`expression` field contains the entire SV source file + NUL byte** for each edge; `source_signal='acc'` (collapsed base name) |
| T.73.2 | Read `_get_signal` ElementSelect handler | Already handles `acc[i]` with ctx-fold (line 575-602) — works for LHS/DST |
| T.73.3 | Read `_build_signal_source` | Uses `_parse_bit_range(rhs_name)` which strips `acc[0]` → `acc` for `source_signal` field |
| T.73.4 | Read `_get_readable_expr` | Lines 1666-1690 — **whole source file leak root cause** |
| T.74.1-prep | pyslang probe for sum_out assign | API mismatch (RootSymbol.members doesn't exist in v11) |

### T.72: Test-first approach (committed)

Wrote `sim/tests/test_case27_1to1_truth.py` (7KB):
- `test_gap_1_acc_unfolded_4_unique_iterations` — Gap 1 assertion
- `test_gap_2_four_multiply_ops_for_prod` — Gap 2 assertion
- `test_gap_3_sum_out_ternary_op` — Gap 3 assertion
- `test_iter031_e4_back_edge_aligned` — iter_031 regression check (PASS)

Baseline run: **3 failures (as expected), 1 pass (iter_031 regression)**.

### T.72.3-T.72.7: Fix attempt 1 (F1)

**F1 v1** — post-process `_expr_trees` in `viz_data_builder.py` to replicate template keys with concrete ones via `_gen_iter_map`.

Result: **No test changed**. Why: `_expr_trees` already had concrete keys — the real issue is somewhere else.

**F1 v2** — recursive leaf-label rewrite inside tree_dict.

Result: **No test changed**. Why: I was operating on the wrong code path.

**Both F1 attempts reverted** in T.77.1.

### T.74-T.75: Fix attempt 2 (F3)

**F3** — modify `_get_readable_expr` to extract RHS-only syntax (avoid whole-assignment stringification).

Result: **No test changed**. Why: F3 addressed the `expression` field pollution but didn't address Gap 3's "missing `?:` op + missing `sum_out` port" — different symptom of a different code path.

F3 reverted in T.77.1.

### T.76-T.77: Honest stop

After 6 fix attempts with **0 tests moving from FAIL to PASS**, recommended Plan A1.2 (clean handoff). User said "继续A1"; continued for one more iteration, then executed A1.2 rollback in T.77.1.

---

## 🎯 Root Cause Analysis (Best Current Understanding)

| Gap | Root cause (best theory) | Code path |
|---|---|---|
| **Gap 1** (`acc[i]` 模板 label in SVG) | `_build_signal_source` calls `_parse_bit_range(rhs_name)` which strips bit_range, collapsing `acc[0]` → `acc` for `source_signal` field. For RHS like `acc[i]`, `_get_signal` correctly substitutes via `_fold_constant(selector, ctx)` to give `acc[0]`/`acc[1]`/etc. — but then `_parse_bit_range` strips back to base `acc`. The concrete name is lost at the parse_bit_range step. | `driver_extractor.py:_build_signal_source` (~line1577), `_parse_bit_range` |
| **Gap 2** (4 `*` ops missing) | `wire [W-1:0] prod = data * weights[i];` inside generate block is a **wire-declaration-with-initializer**, not a continuous assign. `_create_net_decl_edges` walks net declarations but doesn't iterate generate-block bodies — only top-level wires get `_store_expr_tree` called. **The 4 `prod` instances in generate block are completely invisible** to expression tree capture. | `driver_extractor.py:_create_net_decl_edges` (~line1122); need generate-body iteration |
| **Gap 3** (`?:` op + `sum_out` port missing) | `assign sum_out = (acc[N] > {W{{1'b1}}}) ? 8'd255 : acc[N][?:0]` is at module top level (outside generate). Two sub-issues: (a) `N` is a parameter, pyslang may reduce the whole RHS to `ConstantValue` rather than `ConditionalOp`, causing `_store_expr_tree` to early-return; (b) nested replication `{W{{1'b1}}}` may confuse the parser. Result: NO `_expr_trees[generate_loop.sum_out]` entry, so the entire output subtree is missing from viz. | `driver_extractor.py:_store_expr_tree` (line 179), needs parameter-folded-RHS handling |

---

## 📋 Recommended Next Steps (for future session)

1. **Start fresh with pyslang v11 documentation** — this codebase was written against an older pyslang API. Get a working `_get_all_assignments` walker that returns both top-level AND generate-block-level ContinuousAssign AND wire-decl-with-init.
2. **Fix Gap 1**: thread `genvar_ctx` through `_build_signal_source` so `_parse_bit_range` doesn't strip the concrete index. Or change `_parse_bit_range` to preserve `[N]` for array refs (only strip for bit-slice `[N:M]`).
3. **Fix Gap 2**: in `_create_net_decl_edges`, iterate GenerateBlock children and emit per-iteration wire instances (`prod[0]`, `prod[1]`, ..., each with its own `_expr_trees` entry).
4. **Fix Gap 3**: in `_store_expr_tree`, don't early-return when `syntax` is empty/None — fall back to semantic AST evaluation. For parameter-folded RHS, build tree from the semantic `ConditionalOp` / `BinaryOp` directly without depending on `syntax` text.

**The failing test `sim/tests/test_case27_1to1_truth.py` provides immediate validation**: any fix that makes all 3 gaps pass will be visible in the test output.

---

## 📁 Artifacts in this iteration

| Artifact | Status |
|---|---|
| `sim/tests/test_case27_1to1_truth.py` (7KB) | ✅ committed as untracked WIP — failing test for 3 gaps + iter_031 regression check |
| `docs/task_tree/iterations/iter_032_case27_semantic_gaps.md` (this file) | ✅ created |
| F1 v1 + v2 (viz_data_builder.py +96 lines) | ❌ reverted in T.77.1 |
| F3 v1 (_get_readable_expr RHS-only) | ❌ reverted in T.77.1 |
| iter_031 (`c146b0a`) | ✅ committed and intact — visual back-edge snap still working |

---

## 🚦 State at end of this iteration

- ✅ **iter_031 visual fix is intact and working** (32/32 batch PASS, e4 back-edge aligned)
- ❌ **3 known semantic gaps in case27 are NOT resolved** (gap test fails as expected)
- ✅ **Failing test is committed as WIP** for future sessions
- ✅ **All diagnostic findings documented** (this file + conversation history)
- ⏸ **Plan A1 abandoned** after 6 unsuccessful attempts; recommended clean handoff

---

## 📝 Lessons Learned

1. **Don't trust 32/32 batch PASS as full truth coverage** — case27's 3 gaps passed all structural tests but failed semantic verification. Need 1:1 truth-layer tests for each SV construct pattern (generate, ternary, etc.).
2. **pyslang v11 API divergence** — this codebase's wrappers (`_parse_assign`, `_handle_normal_assign`, etc.) were written against older pyslang API. Several `AttributeError` blockers during investigation. Future sessions should budget time for API surface mapping.
3. **Fix-at-symptom ≠ fix-at-root** — F1 v1/v2 and F3 each fixed *something* but not the *test*. Always read the test failure message to understand which assertion failed, then trace back to code path.
4. **Token-burn management** — 6 fix attempts at 30+ tool calls each = 200+ tool calls with 0 tests moving. Earlier "stop grinding" decision would have saved 2-3 hours. The honest stop recommendation should be acted on faster next time.

---

**End of iteration 32. Hand off state: visual fix intact, 3 gaps documented with failing test, no production changes pending.**