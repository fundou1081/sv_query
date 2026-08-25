# L3 Task: Understand Bug Class (Step G)

**Status**: ✅ CLOSED
**Parent**: L2_plan_b_step_g
**Closed**: 2026-08-25 22:30

---

## 🎯 Goal

Identify what type of bug picorv32_wb triggers — reuse lessons from prior fixes (Step B for darkriscv, etc.).

## 📋 Outcome

✅ Identified: **port-id mismatch** class.

- ELK reports "Referenced shape does not exist" when an edge references a port ID that has no shape with that ID in the graph.
- This class was hit before:
 - `darkriscv.DLEN[0/1/2]` — fixed by Plan B Step B (commit `6e8256c`)
 - `golden_hier_top.u_off.offset` — fixed by Plan B Step B v3 (bit-port parent emission)
- picorv32_wb's case is a new variant: **inner-instance port path** (`picorv32_wb.picorv32_core.clk`)

## 📚 Related

- See iteration `iter_001_run_real_project_suite.md` and `iter_002_identify_failing_picorv32_subtargets.md`