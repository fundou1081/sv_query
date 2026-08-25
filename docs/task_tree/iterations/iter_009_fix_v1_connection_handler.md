# Iteration 9: Fix v1 — CONNECTION Handler (FAILED)

**Metadata**:
- **Iteration #**: 9
- **Task Tree Level**: L3
- **Parent Task**: L3_fix_v1_connection_handler
- **Created**: 2026-08-25 23:00 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: ❌ FAILED (reverted)

---

## 🎯 Current Goal

Add CONNECTION edge handling to `_referenced_input_fulls` collection at line 405 of `elk_bridge.py`. The edge `e1308` is `kind='connection'`, which the existing walk skips (only walks DRIVER + BIT_SELECT).

## 📋 Expected Result

picorv32_wb should pass — `picorv32_wb.picorv32_core.clk` would be added to referenced_input_fulls, then emitted at line 425+.

## 🔬 Actual Result / Observation

Dump stats AFTER fix:
- 436 port emits (UP from 422, +14 new emits from CONNECTION handler)
- 306 port refs (unchanged)
- **STILL 1 MISSING**: `port_picorv32_wb_dot_picorv32_core_dot_clk`

The fix added 14 other ports, but NOT the target port. This means either:
- `picorv32_wb.picorv32_core.clk` is NOT in `input_paths` (so the CONNECTION handler can't match)
- OR the CONNECTION edge's `dst` field is something other than the full path

## 💡 Other Valuable Info

- The fix was reverted via backup `/tmp/elk_bridge.py.bak`
- Even after fix, golden regression still passes (no regression introduced)
- Bug is more subtle than "CONNECTION edges aren't being walked"

## 🔄 Next Action

Try Fix v2: make `_post_existing` defensive check recursive (so it sees nested port shapes).