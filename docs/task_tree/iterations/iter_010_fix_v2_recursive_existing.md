# Iteration 10: Fix v2 — Recursive _post_existing (FAILED)

**Metadata**:
- **Iteration #**: 10
- **Task Tree Level**: L3
- **Parent Task**: L3_fix_v2_recursive_existing
- **Created**: 2026-08-25 23:10 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: ❌ FAILED (reverted)

---

## 🎯 Current Goal

Make the post-wrap defensive check (line 1750+) recursively collect port shapes from nested children, not just root_children. This way the defensive emit can detect missing ports even if they were emitted at cluster level.

## 📋 Expected Result

The defensive check would see the missing port shape at root level → emit it if missing.

## 🔬 Actual Result / Observation

Dump stats AFTER fix:
- 436 port emits (unchanged from v1)
- 306 port refs (unchanged)
- **STILL 1 MISSING**: `port_picorv32_wb_dot_picorv32_core_dot_clk`

Recursive walk of `_post_existing` made no difference because the port shape is **NOT emitted at any level** (root or nested). It's referenced by edge `e1308` but the corresponding port shape never appears in the graph.

## 💡 Other Valuable Info

- The defensive check works correctly (it does compute missing ports)
- But the missing port is **never emitted by anyone** — neither by the main emit loop nor by any other code path
- This means the bug is upstream of the emit logic — something is FAILING to add the port to `_referenced_input_fulls` even though it's needed

## 🔄 Next Action

Per debug-mindset-switcher skill rule: 3+ fix attempts without success → Mode 5 (Write Down). Revert + write down + send status report to user.