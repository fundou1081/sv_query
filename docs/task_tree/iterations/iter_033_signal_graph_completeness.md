# Iteration 33: Signal Graph Completeness — Gap 3 Fix + Verification

**Metadata**:
- **Iteration #**: 33
- **Task Tree Level**: L2
- **Parent Decision**: `docs/architecture/case27_signal_graph_completeness_decision.md` (D1-D4 locked at 2026-08-26 23:00 GMT+8)
- **Created**: 2026-08-26 23:08 GMT+8
- **Author**: 方豆 / QClaw
- **Status**: 🚧 **NOT STARTED** — waiting for user to (a) pick A/B/C/D definition, (b) say "开工"

---

## 🎯 Goal

Per architectural decision D4 ("signal graph 信息完整 is the core invariant"), implement and verify that **all module-top-level signals (ports + wire declarations + continuous assigns + always blocks) appear 100% in viz nodes/edges**. Specifically:

1. **Fix Gap 3** — module-top-level ternary `?:` op nodes (e.g. `sum_out` in case27) must appear in viz
2. **Write verification test** — define "信息完整" per user's A/B/C/D choice
3. **1:1 batch regression** — confirm no semantic regressions from the Gap 3 fix
4. **Commit + push** — single PR-style commit

---

## 📋 User's Pending Decisions

| Question | Options | Status |
|---|---|---|
| **"信息完整" 具体定义** | A 节点完整 / B 表达式完整 / C 1:1 对应 / D 三层全要 | ⏳ Asked via Feishu `om_x100b67dbb56028a4dd2e6b204608c4f`, awaiting answer |
| **开工信号** | (no "开工" yet) | ⏳ User's last instruction was "记录下来 → 更新文档 → **然后再开工**" — docs being updated, then wait |

---

## 🚧 Pre-work already done

| Item | Where | Status |
|---|---|---|
| Decision doc | `docs/architecture/case27_signal_graph_completeness_decision.md` | ✅ Created |
| `KNOWN_LIMITATIONS.md` updated | Gap 1 + Gap 2 demoted to "accepted limitations" | ✅ Updated |
| `ARCHITECTURE_EVOLUTION.md` updated | Section 七 added with D1-D4 + rejected alternatives | ✅ Updated |
| `VIZ_DESIGN_SPEC.md` updated | (pending — T.90 if user picks D3 visualization flattening implications) | ⏳ |
| `memory/2026-08-26.md` updated | Architectural pivot recorded | ✅ Updated |

---

## 📐 Fix Plan (Gap 3 — module-top-level ternary `?:` op nodes)

### Root cause (T.71-T.83)

`driver_extractor._handle_normal_assign` calls `_store_expr_tree` to walk the RHS AST. When RHS contains a ternary `cond ? a : b`, pyslang's Semantic API evaluates `cond` (which may fold to `ConstantValue` if `cond` uses `PARAM`-resolved widths like `{W{1'b1}}`). The `_store_expr_tree` early-returns on `ConstantValue` siblings, so the `ConditionalOp` (ternary) parent node is lost.

### Hypothesized fix (will validate with diagnostic)

In `_handle_normal_assign`, before walking RHS children, **detach the top-level ternary structure** from any `ConstantValue` leaf. The ternary's `cond / then_expr / else_expr` are syntactically present even when pyslang folds some sub-expressions. We need to:

1. Check if RHS root is a `ConditionalExpression` (pyslang's semantic node for `?:`)
2. If yes, **emit a `?:` op node** in expr_trees and create three child edges (cond → then, cond → else, then → dst, else → dst)
3. Recurse into each branch, applying the same logic to any nested ternaries

### Code locations to investigate

- `src/trace/core/driver_extractor.py` — `_handle_normal_assign` (around line 1100-1200)
- `src/trace/core/graph/viz/expression_tree.py` — `_store_expr_tree` (the early-return path)
- `src/trace/core/graph/viz/viz_data_builder.py` — `?:` op node creation

### Test scaffold

```python
# sim/tests/test_signal_graph_completeness.py (new)
def test_gap_3_top_level_ternary_in_viz():
    """case27 sum_out: (acc[N] > {W{1'b1}}) ? ... : ... must appear in viz as ?: node"""
    # 1. run sv_query visualize dataflow --module generate_loop --output json
    # 2. parse viz JSON
    # 3. assert '?:' op label appears with cond/then/else children
    # 4. assert src-dst mapping matches SV code 1:1
```

### Definition (default — pending user choice)

Until user picks A/B/C/D, default to **A 节点完整**:
- ✅ Module 顶层所有 wire decls + continuous assigns + always blocks 100% 在 viz 节点集
- Test: compare pyslang `compilation.getRoot().topInstances[].body.members` count vs viz node count

---

## 🧪 Verification gate (per V101 policy from T.45)

Before commit:
1. ✅ unit tests pass (no regression in 2958 tests)
2. ✅ case27 1:1 check (SV `?:` count = viz `?:` labels count)
3. ⏳ 32 batch regression (golden dataflow set)
4. ✅ viz SVG visually inspected

---

## 📝 Doc updates required (post-fix)

| Doc | Update |
|---|---|
| `KNOWN_LIMITATIONS.md` | Move Gap 3 from "to-fix" to "已修复" |
| `ARCHITECTURE_EVOLUTION.md` | Append iter_033 outcome to section 七 |
| `VIZ_DESIGN_SPEC.md` | Note Gap 3 fix in section 6 (数据流 op 节点清单) |
| `iter_033_*.md` (this file) | Final outcome + commit hash |

---

## 🔗 Resume method

```bash
cd ~/my_dv_proj/sv_query
git log --oneline -5                          # last commits
git status                                    # working tree state
cat docs/task_tree/iterations/iter_033_*.md   # this file
# Wait for user A/B/C/D answer, then start T.91:
#   - read driver_extractor._handle_normal_assign
#   - identify _store_expr_tree early-return on ConditionalExpression
#   - implement fix
#   - run 32 batch regression
```

---

## 🛑 Status snapshot (2026-08-26 23:08 GMT+8)

- Decision: 🔒 LOCKED
- Docs: ✅ Updated (3 files)
- Code: ⏳ Not started — awaiting user A/B/C/D + "开工"
- Memory: ✅ Recorded