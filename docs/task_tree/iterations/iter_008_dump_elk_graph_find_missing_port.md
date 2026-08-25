# Iteration 8: Dump ELK Graph, Find Missing Port

**Metadata**:
- **Iteration #**: 8
- **Task Tree Level**: L3
- **Parent Task**: L3_trace_evidence
- **Created**: 2026-08-25 22:50 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

Dump the actual ELK graph before layout, identify all port emits vs port refs, find missing port IDs.

## 📋 Expected Result

Get definitive list of missing port IDs and which edges reference them.

## 🔬 Actual Result / Observation

After 3 failed dump approaches (sed IndentationError, PYTHONSTARTUP only for interactive, monkey-patch wrong import path), finally used the `edit` tool to insert clean dump at line 1806 of `elk_bridge.py`.

**Dump stats**:
- 1 root children, 1309 root edges
- **422 port emits**, 306 port refs
- **EXACTLY 1 MISSING**: `port_picorv32_wb_dot_picorv32_core_dot_clk`

**Offending edge**:
```json
{
  "id": "e1308",
  "sources": ["sig_clk_wire"],
  "targets": ["port_picorv32_wb_dot_picorv32_core_dot_clk"],
  "_meta": {"kind": "connection", "stroke": "purple", "v15_added": true}
}
```

## 💡 Other Valuable Info

- The `edit` tool handles multi-line Python indentation correctly (unlike sed)
- The `_meta.v15_added: true` is a key clue — edge added by V15 cross-instance code (`_emit_cross_instance_connection_edges`, line 1934+)
- Dumped graph saved to `/tmp/picorv32_wb_elk_graph.json` (1MB)

## 🔄 Next Action

Apply Fix #1: Add CONNECTION edge handler to `_referenced_input_fulls` collection.