# Iteration 4: Fix v3 Cycle Detection

**Metadata**:
- **Iteration #**: 4
- **Task Tree Level**: L3
- **Parent Task**: L3_prototype_fix
- **Created**: 2026-08-25 19:30 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

Apply Fix #4 v3 — add `_being_rendered` set + try/finally + `op_id = None` default to `elk_bridge.py:684`.

## 📋 Expected Result

picorv32_pcpi_mul should pass (generate DOT). Golden regression still 5/5 PASS.

## 🔬 Actual Result / Observation

- Fix #4 v1 (initial): used `op_id = f"sig_{_safe(label)}"` as fake ID → ELK "Referenced shape does not exist: sig_clk" (new error)
- Fix #4 v2: removed fake sig_id, used independent `_being_rendered` set
- Fix #4 v3: added `op_id = None` default to avoid UnboundLocalError
- **Fix #4 v3 FINAL**: ✅ picorv32_pcpi_mul generates 679KB DOT
- Golden regression: 5/5 PASS
- No regression on darkriscv, serv, zipbones

## 💡 Other Valuable Info

- The cache-only design (read-only `_signal_cache`) couldn't break cycles; needed a separate "currently rendering" set
- try/finally is critical — must clean up `_being_rendered` even on exception

## 🔄 Next Action

Document + commit Plan B Step F (cycle detection).