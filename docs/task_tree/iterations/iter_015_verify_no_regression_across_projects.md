# Iteration 15: Verify No Regression Across Projects

**Metadata**:
- **Iteration #**: 15
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 00:10 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: ✅ SUCCESS — all projects pass, no regression

---

## 🎯 Current Goal

After Fix v3 in iteration 14, verify no regression on:
- Other picorv32 sub-targets (pcpi_mul, pcpi_div, axi, regs)
- darkriscv (already worked before)
- Golden regression (5/5 must still pass)

## 📋 Expected Result

All projects that worked before should still work. Only picorv32_wb should change from FAIL → PASS.

## 🔬 Actual Result / Observation

✅ ALL VERIFIED:

| Project/Sub-target | Status | DOT size |
|--------------------|--------|----------|
| picorv32_wb | ✅ NEW PASS (was failing) | 539813 bytes |
| picorv32_pcpi_mul | ✅ still PASS (no regression) | 679591 bytes |
| picorv32_pcpi_div | ✅ still PASS (no regression) | 679591 bytes |
| picorv32_axi | ✅ still PASS (no regression) | 558947 bytes |
| picorv32_regs | ✅ still PASS (no regression) | 2249 bytes |
| darkriscv | ✅ still PASS (no regression) | 273167 bytes |
| serv | ❌ FileNotFoundError (PRE-EXISTING, not from this fix) | n/a |
| Golden regression | ✅ 5/5 PASS (no regression) | n/a |

**serv.v FileNotFoundError** is a pre-existing issue — the file isn't at `/Users/fundou/my_dv_proj/openrtl/serv/serv.v`. This was a problem before my fix and is unrelated to Plan B Step G. Should investigate separately (out of scope for this task).

## 💡 Other Valuable Info

- Fix v3 is **purely additive** — it adds port shapes that were missing without changing any existing emit logic
- The defensive emit at line 1750+ (Plan B Step B1 v2) was still in place but didn't trigger for this case (because the port was truly never emitted anywhere)
- Fix v3 emits port shapes **at root level** with `_meta._plan_b_g_v15: True` so future debugging can trace this fix

## 🔄 Next Action

Commit Plan B Step G (Fix v3 + this iteration's verification) and update overview.md.