# Iteration 13: Read _map_to_elk_id (V15 Cross-Instance Code)

**Metadata**:
- **Iteration #**: 13
- **Task Tree Level**: L3
- **Parent Task**: L3_investigate_alternate_path
- **Created**: 2026-08-25 23:55 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🟡 IN PROGRESS

---

## 🎯 Current Goal

Per user instruction (23:48:34): "继续深入调查，方向错误不要紧，做好迭代记录."

Investigate WHY edge `e1308` references `port_picorv32_wb_dot_picorv32_core_dot_clk` but no port shape with that ID is emitted.

Previous fixes (#1 CONNECTION handler, #2 recursive _post_existing) didn't work because they targeted the wrong layer. Now read `_map_to_elk_id` (called from `_emit_cross_instance_connection_edges` at line ~2050+) to understand:
1. How the port ID is generated
2. What code path SHOULD have emitted the corresponding port shape
3. Why that code path didn't run

## 📋 Expected Result

Find the actual root cause — likely a code path that emits the port ID as an edge target without first adding the corresponding port shape to the graph.

## 🔬 Actual Result / Observation (in progress)

**Step 1**: Find `_map_to_elk_id` definition

✅ Found at line 2062.

**Step 2**: Read `_map_to_elk_id` body (lines 2062-2099):

```python
def _map_to_elk_id(path, _instance_ports, _wire_nodes, _all_top_ports,
                     _input_dedup_map=None, _output_dedup_map=None):
    # [V15 fix 5] 顺序调整: 先查 instance port
    if path in _instance_ports:                            # BRANCH 1
        return 'port_' + path.replace('.', '_dot_')
    if path in _all_top_ports:                              # BRANCH 2
        # ... dedup-aware logic
        if '.' in path:
            return f'port_{path.replace(".", "_dot_")}'
        return f'port_{path}'
    if path in _wire_nodes:                                 # BRANCH 3
        short = path.rsplit('.', 1)[-1] if '.' in path else path
        return f'sig_{short}_wire'
    return None                                             # BRANCH 4
```

**ROOT CAUSE (FINAL, CONFIRMED)**:

For `path = 'picorv32_wb.picorv32_core.clk'`:
- Branch 1 fires: returns `'port_picorv32_wb_dot_picorv32_core_dot_clk'`
- This ID is used as edge target (line ~2056)
- **However, the corresponding port shape (`kind='port_in'`) is never emitted!**

In `_emit_cross_instance_connection_edges` (line 1934+), the function builds:
- `_instance_ports` (line 1950-1954): collects instance ports where `cid and side` ✓
- `_input_dedup_map` / `_output_dedup_map` (line 1958-1965): collects ALL ports where `port_side='left'/'right'` (regardless of `cid`) ✓

But **NEITHER** adds the port shape to `root_children` as `kind='port_in'`! The only shapes added to `root_children` are:
- Wire nodes (`sig_{short}_wire`, line 2012-2023)
- Connection edges (line 2056, 2074)

So instance ports like `picorv32_wb.picorv32_core.clk` are referenced by edges but never appear as nodes in the graph.

## 💡 Other Valuable Info

- The instance port ID pattern is `port_<full_path_with_dots_replaced_by_dot_>` — same as the main emit loop
- The main emit loop at line 425+ DOES emit port shapes for ports in `_referenced_input_fulls` / `_referenced_output_fulls`
- But instance ports are NOT added to these sets because the CONNECTION-edge handler (iter 9) only added the explicit `e.dst` string, and the CONNECTION edge in `viz.edges` has `e.dst = 'picorv32_wb.picorv32_core.clk'`, but my CONNECTION fix checked against `_input_path_set`/`_output_path_set`, not `_instance_ports`

## 🔄 Next Action

Design and apply Fix v3: in `_emit_cross_instance_connection_edges`, after building `_instance_ports`, also add corresponding port shapes to `root_children` for each instance port that's referenced by an edge.

## 📌 Pending (to be filled in next iteration)

- Iteration 14: Apply Fix v3 (emit port shape for instance ports)
- Iteration 15: Verify with picorv32_wb (should now pass)
- Iteration 16: Verify no regression on golden + darkriscv + serv + zipbones
- Iteration 17: Commit Plan B Step G + update docs