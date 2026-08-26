# Iteration 26: Emit BRANCH_FALSE Edges (Same as BRANCH_TRUE)

**Metadata**:
- **Iteration #**: 26
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 09:09 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🟡 IN PROGRESS

---

## 🎯 Current Goal

User instruction (09:08:56 GMT+8): "修改设计规则，branch false 也应该画出来，和branch true 一样的处理方式"

**Requirement**: Modify the design rule so that **BRANCH_FALSE edges are also drawn**, with the **same handling as BRANCH_TRUE**.

## 📋 Background

From iter_025 investigation:
- Currently `elk_bridge.py` line 46: `⚠️ BRANCH_FALSE 边: 不存在独立 edge — false 分支跟 true 分支一样通过 port → sig_*_b* 表示`
- Currently `elk_bridge.py` line 42: `✅ BRANCH_TRUE 等价边: 已 emit (root_edges, line 1418-1421, kind=signal)`
- **Asymmetry**: BRANCH_TRUE is emitted, BRANCH_FALSE is not.

## 📋 Plan

1. **Phase 1**: Find where BRANCH_TRUE is emitted (line 1418-1421 of elk_bridge.py)
2. **Phase 2**: Add similar logic for BRANCH_FALSE
3. **Phase 3**: Test on ternary_scope and array_index
4. **Phase 4**: Re-run all 32 basic scenarios
5. **Phase 5**: Commit + send updated images to user

## 🔬 Investigation Progress

(in progress)

## 🔄 Next Action

Read the BRANCH_TRUE emit code at line 1418-1421 of elk_bridge.py