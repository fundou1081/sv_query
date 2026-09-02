# Iteration 14: Apply Fix v3 — Emit Port Shapes for Instance Ports

**Metadata**:
- **Iteration #**: 14
- **Task Tree Level**: L3
- **Parent Task**: L3_investigate_alternate_path
- **Created**: 2026-08-26 00:05 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: ✅ SUCCESS — picorv32_wb now passes!

---

## 🎯 Current Goal

Apply Fix v3 based on root cause from iteration 13: in `_emit_cross_instance_connection_edges`, after building `_instance_ports` and emitting wire nodes, also emit `port_in`/`port_out` shapes for each instance port that's referenced by a CONNECTION edge.

## 📋 Expected Result

- picorv32_wb should pass — `port_picorv32_wb_dot_picorv32_core_dot_clk` shape now exists in graph
- Golden regression 5/5 still PASS
- No regression on darkriscv, serv, zipbones
- picorv32_pcpi_mul, picorv32_axi, picorv32_regs still PASS

## 🔬 Actual Result / Observation

**🎉 SUCCESS!**

**Step 1**: Found the right insertion point at line 2023 (after wire nodes emit, before edge emit loop).

**Step 2**: Applied Fix v3 via `edit` tool — added ~30 lines emitting `port_in`/`port_out` shapes for each instance port that's referenced by a CONNECTION edge.

**Step 3**: Ran `python3 run_cli.py visualize dataflow --file ~/my_dv_proj/openrtl/picorv32/picorv32.v --module picorv32_wb --no-strict --dot /tmp/picorv32_wb_v3.dot`:
- Output ends with `<svg>` tag (not error traceback)
- DOT/SVG file generated: **539813 bytes** (~540KB)
- picorv32_wb now PASSES

**Step 4**: Ran golden regression: **5/5 PASS** in 1.46s — no regression introduced.

## 💡 Other Valuable Info

- The fix only emits port shapes for instance ports that **also appear in the dedup maps** (i.e., they have a `port_side` set in viz.nodes). This avoids emitting shapes for instance ports that were never properly classified.
- Each instance port shape uses the same ID as `_map_to_elk_id` would return (Branch 1), so edge refs and shape IDs match.
- Layout constraint (`FIRST`/`LAST`) mirrors the main emit loop (line 425+).
- Failed Fix #1 (CONNECTION handler to `_referenced_input_fulls`) and Fix #2 (recursive `_post_existing`) targeted the wrong layer. Fix v3 targets the actual source: `_emit_cross_instance_connection_edges` is where the missing port IDs originate.

## 🔄 Next Action

✅ Fix verified. Now create iteration 15 (verify other sub-targets + darkriscv/serv/zipbones) and commit Plan B Step G.