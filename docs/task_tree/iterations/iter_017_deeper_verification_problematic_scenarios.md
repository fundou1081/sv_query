# Iteration 17: Deeper Verification — Code + Visualization Accuracy

**Metadata**:
- **Iteration #**: 17
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 07:40 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🟡 IN PROGRESS

---

## 🎯 Current Goal

User request (07:37:35 GMT+8): "重跑一下之前有问题的场景，确认一下代码和可视化的结果是否真的准确了。"

Deeper verification beyond "does it generate SVG":
1. Re-run all previously problematic scenarios (picorv32_wb, picorv32_pcpi_mul, darkriscv)
2. **Visually inspect** the SVG output — confirm the previously-missing port is actually emitted as a port_in shape with correct attributes
3. **Code accuracy check** — verify the fix code (commit `52bedd1`) actually does what it claims
4. **No silent regressions** — confirm other cases still render correctly

## 📋 Expected Result

- picorv32_wb SVG contains `port_picorv32_wb_dot_picorv32_core_dot_clk` as a `port_in` shape (FIRST constraint)
- The wire→port edge `sig_clk_wire → port_picorv32_wb_dot_picorv32_core_dot_clk` is present
- Other previously-problematic scenarios all pass without warnings
- picorv32_pcpi_mul (cycle case) still generates correctly
- darkriscv (bit-port case) still generates correctly
- No new ELK warnings

## 🔬 Actual Result / Observation

🎉 **EXCELLENT — all verifications passed:**

### T.17.3 Structural verification (picorv32_wb)
- `emits=446, refs=306, **missing=0**` ✅
- Target port `port_picorv32_wb_dot_picorv32_core_dot_clk` ✅ FOUND as `port_in`
  - label: `"clk"`
  - `plan_b_g_v15` flag: `True` (confirms our fix)
  - `layerConstraint`: `FIRST` (correct for port_in)
- 24 ports emitted by Plan B Step G fix (23 port_out + 1 port_in)
- All labels correct (e.g., `"count_cycle[63:32]"`, `"mem_rdata_q[14:12]"`, `"decoded_rs1[regindex_bits - 1]"`)

### T.17.4 All problematic scenarios — zero missing ports

| Scenario | emits | refs | missing | Size |
|----------|-------|------|---------|------|
| picorv32_wb (was FAILING) | 446 | 306 | **0** | 539813 ✅ |
| picorv32_pcpi_mul (cycle case) | 307 | 41 | **0** | 679591 ✅ |
| darkriscv (bit-port case) | 83 | 21 | **0** | 273167 ✅ |
| picorv32_core (full chip) | 307 | 41 | **0** | 679587 ✅ |
| Golden regression | - | - | - | **5/5 PASS** ✅ |

### T.17.5 Code accuracy check (commit 52bedd1)
- 36 lines added to `_emit_cross_instance_connection_edges` (line 2003+)
- Logic: After wire nodes emit, also emit `port_in`/`port_out` shapes for each instance port referenced by a CONNECTION edge
- Layer constraint: `FIRST` for input, `LAST` for output
- Meta flag: `_plan_b_g_v15: True` for future debugging
- Deduplication via `_v15_emitted_port_ids` set
- Filtering: only emits instance ports that are also top-level ports

### T.17.6 Cleanup verified
- Reverted temp debug injection via `git checkout`
- `grep -c TEMP DEBUG = 0` (no debug code left)
- Sanity: picorv32_wb still 539813 bytes
- Golden: 5/5 PASS in 1.46s

## 💡 Other Valuable Info

- Previous verification (iter 16) only checked "does it run" — this iteration digs into actual content correctness
- Per user: "确认一下代码和可视化的结果是否真的准确了" — both code AND visualization accuracy needed
- This is a "trust but verify" pass
- **Conclusion: 代码 + 可视化结果都真的准确了** ✅

## 🔄 Next Action

Send verification report to user. Task complete.