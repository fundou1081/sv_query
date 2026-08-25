# Iteration 7: Start picorv32_wb Investigation (Plan B Step G)

**Metadata**:
- **Iteration #**: 7
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-25 22:28 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

User request: "好的，那么继续 调查 plan b 的step g，port 相关的问题。先理清现状，深入调查。"

Begin Mode 1 (VERIFY ASSUMPTION) per debug-mindset-switcher skill — clarify current state.

## 📋 Expected Result

- Find prior mentions of picorv32_wb in docs (memory notes, daily notes)
- Identify the bug class
- Find related code paths

## 🔬 Actual Result / Observation

✅ Found via `memory/2026-08-25.md` line 99:
> "`picorv32_wb`: NEW ELK bug 'Referenced shape does not exist: port_picorv32_wb_dot_picorv32_core_dot_clk' — 跨模块 port 引用 (Plan B Step G 待做)"

✅ Found 9 references to "Referenced shape does not exist" in `src/trace/core/graph/viz/elk_bridge.py`
- Bug class: **port-id mismatch** (edge ref → no shape)
- Similar bugs already fixed: darkriscv (Step B1), golden cases (Step B1 v2)
- picorv32_wb is a NEW variant not covered by existing fixes

## 💡 Other Valuable Info

- Memory search via `memory_search` was unavailable (no OpenAI key); fell back to direct file grep
- Found test fixture at `sim/tests/integration/test_real_project_viz.py` — only `picorv32_core` is tested
- Need to add picorv32_wb to the test list

## 🔄 Next Action

Run picorv32_wb to capture exact error (enter Mode 2: Trace Evidence).