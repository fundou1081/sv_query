# L2 Task: Plan B Step F — Cycle Detection (picorv32_pcpi_mul)

**Status**: ✅ CLOSED
**Parent**: L1_plan_b_real_project_visualization
**Closed**: 2026-08-25 22:00 (commit `a939d68`)
**Documentation commit**: `9eab9ed`

---

## 🎯 Goal

Fix picorv32_pcpi_mul RecursionError by detecting cycles in matched_tree recursion.

## 📋 Outcome

✅ Commit `a939d68` "feat(viz): [Plan B Step F] cycle detection + expression_tree cleanup".

**Fix**: Added `_being_rendered: set` + try/finally + `op_id = None` default to `elk_bridge.py:684`. The set prevents revisiting signals that are currently being rendered (not just already-cached ones).

**Verification**:
- picorv32_pcpi_mul: 679KB DOT generated ✅
- Golden regression: 5/5 PASS ✅
- No regression on darkriscv, serv, zipbones ✅

## 📚 Documentation

- Case study: `docs/debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md` (17860 bytes)
- Daily note: `memory/2026-08-25.md`
- This task tree: `docs/task_tree/overview.md`