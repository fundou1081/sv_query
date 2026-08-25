# Iteration 3: picorv32_pcpi_mul Traceback Analysis

**Metadata**:
- **Iteration #**: 3
- **Task Tree Level**: L3
- **Parent Task**: L3_identify_root_cause
- **Created**: 2026-08-25 18:00 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

Analyze RecursionError traceback for picorv32_pcpi_mul to find true root cause (after user's "为什么会有2000层" challenge).

## 📋 Expected Result

Verify the "2000 layers" hypothesis by checking actual source structure.

## 🔬 Actual Result / Observation

- `grep -c "wire" picorv32_pcpi_mul.sv` → **5 wires** (NOT 2000!)
- `wc -l picorv32_pcpi_mul.sv` → 119 lines total
- Hypothesis DISPROVEN — there are only 5 wires in the entire module

**Real cycle found** (via traceback frame analysis):
```
mul_finish → pcpi_wait_q → mul_waiting → mul_finish  (5 wires forming cycle)
```

Frame count: most frames in `_safe()` and `render_tree()` at line ~684 of `elk_bridge.py`.

## 💡 Other Valuable Info

- `_signal_cache` was read-only — could not break cycle
- 1.5h wasted on wrong hypothesis before user challenge

## 🔄 Next Action

Apply Fix #4 v3 with `_being_rendered` set + try/finally.