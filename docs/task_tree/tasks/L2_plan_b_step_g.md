# L2 Task: Plan B Step G — Cross-Module Port Edge (picorv32_wb)

**Status**: 🔴 BLOCKED
**Parent**: L1_plan_b_real_project_visualization
**Started**: 2026-08-25 22:28
**Last update**: 2026-08-25 23:48

---

## 🎯 Goal

Fix `RuntimeError: ELK layout failed: Referenced shape does not exist: port_picorv32_wb_dot_picorv32_core_dot_clk` when running `visualize dataflow --module picorv32_wb`.

## 📋 Confirmed Evidence

**Offending edge**:
```json
{
  "id": "e1308",
  "sources": ["sig_clk_wire"],
  "targets": ["port_picorv32_wb_dot_picorv32_core_dot_clk"],
  "_meta": {
    "kind": "connection",
    "stroke": "purple",
    "v15_added": true
  }
}
```

- Edge is at `parent: root` (top-level)
- Edge added by `_emit_cross_instance_connection_edges` (line 1934+) — V15 cross-instance code
- 422 port emits total, 306 port refs, **1 missing port**

## 🔬 Sub-Tasks (L3)

| L3 | Title | Status |
|----|-------|--------|
| Understand_bug_class | Identify bug class is port-id mismatch | ✅ CLOSED |
| Trace_evidence | Find exact offending edge + dump graph | ✅ CLOSED |
| Identify_root_cause | Find why port not emitted | ✅ CLOSED (partial) |
| Fix_v1_connection_handler | Add CONNECTION to referenced walk | ❌ FAILED |
| Fix_v2_recursive_existing | Make defensive check recursive | ❌ FAILED |
| Investigate_alternate_path | Read `_map_to_elk_id` + V15 code | 🟡 ACTIVE |

## ❌ Failed Fixes

- **Fix #1**: CONNECTION edge added to `_referenced_input_fulls` walk → port count 422→436 but target still missing
- **Fix #2**: `_post_existing` recursive walk → no effect (port is nowhere in graph)

Both reverted. `elk_bridge.py` clean. Golden regression 5/5 PASS.

## 🔥 Next Investigation Direction

Per user instruction (23:48:34): continue deep investigation, record every iteration.

Plan:
1. Read `_map_to_elk_id` (called from `_emit_cross_instance_connection_edges` lines ~2050+)
2. Trace exactly how `port_picorv32_wb_dot_picorv32_core_dot_clk` ID is generated
3. Find what code path SHOULD have emitted the port shape but didn't
4. If still unclear, try `__debug__` flag in `viz_to_elk` to log all emit decisions

## 📚 Related Documents

- Investigation: `docs/debugging_lessons/2026-08-25_plan_b_step_g_picorv32_wb_port.md` (9000 bytes)
- Dumped graph: `/tmp/picorv32_wb_elk_graph.json` (1MB)
- Backup of clean state: `/tmp/elk_bridge.py.bak`