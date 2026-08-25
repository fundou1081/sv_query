# L1 Task: Plan B — Real Project Visualization

**Status**: 🟡 IN PROGRESS (Step G blocked)
**Created**: 2026-08-25 23:48 GMT+8
**Parent**: (top-level)

---

## 🎯 Goal

Make `sv_query visualize dataflow` work end-to-end on real-world SystemVerilog projects (darkriscv, picorv32, serv, etc.) — not just synthetic golden cases.

## 📋 Sub-Tasks (L2)

| L2 | Title | Status | Commit |
|----|-------|--------|--------|
| Step A | Initial real-project integration | ✅ CLOSED | `915c284` 等 |
| Step B | Bit-port parent emission (darkriscv DLEN fix) | ✅ CLOSED | `6e8256c` |
| Step C+D | Branch differentiator + label compaction | ✅ CLOSED | `8e98abd` |
| Step E | Recursion limit workaround | ✅ CLOSED | (in F) |
| **Step F** | **Cycle detection (picorv32_pcpi_mul fix)** | ✅ CLOSED | `a939d68` |
| **Step G** | **Cross-module port edge (picorv32_wb)** | 🔴 BLOCKED | TBD |

## 🔥 Active Issue: Step G

**Bug**: `RuntimeError: ELK layout failed: Referenced shape does not exist: port_picorv32_wb_dot_picorv32_core_dot_clk`

**Root cause (CONFIRMED via dump)**:
- Edge `e1308, kind=connection` at root level, source `sig_clk_wire`, target `port_picorv32_wb_dot_picorv32_core_dot_clk`
- Edge added by `_emit_cross_instance_connection_edges` (line 1934+) with `_meta.v15_added: True`
- Port shape **nowhere** in graph (root + nested both empty)

**Failed fixes** (both reverted):
- Fix #1: Add CONNECTION to `_referenced_input_fulls` walk → 422 → 436 emits, target still missing
- Fix #2: Make `_post_existing` recursive → no effect

**Next iteration**: Read `_map_to_elk_id` and trace exactly how the port ID is generated. Find what code path SHOULD have emitted it but didn't.

## 📚 Related Documents

- Case study: `docs/debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md`
- Debug mindset skill: `docs/debugging_lessons/debug-mindset-skill.md`
- Step G investigation: `docs/debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md`
- Task tree overview: `docs/task_tree/overview.md`

---

**Owner**: 方豆 / QClaw
**Last update**: 2026-08-25 23:48 GMT+8