# Plan B Step G — picorv32_wb Port Edge Investigation (In Progress)

> **Status**: 🟡 IN PROGRESS (Mode 2: TRACE EVIDENCE ongoing, transitioning to Mode 3)
> **Date**: 2026-08-25 22:28-23:30 GMT+8
> **Author**: 方豆 / QClaw (debug-mindset-switcher in active use)

---

## 🎯 TL;DR

**Bug**: ELK layout fails on `picorv32_wb` (real-project test):
```
RuntimeError: ELK layout failed: ELK layout error: 
org.eclipse.elk.graph.json.JsonImportException: Referenced shape does not exist:
port_picorv32_wb_dot_picorv32_core_dot_clk
```

**Hypothesis (high confidence, NOT yet verified)**: The `_resolve_port_id` function returns `port_picorv32_wb_dot_picorv32_core_dot_clk` (nested port path) for **edge source/target references**, but the **port-shape emit loop** only walks **top-level ports of target module**, never the **inner-instance ports** (`picorv32_wb.picorv32_core.clk`). Mismatch: ref exists, shape doesn't.

**Why dump attempts failed**: sed patch caused IndentationError; PYTHONSTARTUP only runs in interactive Python; monkey-patch import path was wrong (`trace.core` vs project structure).

**Next step**: Use the `edit` tool (handles multi-line Python correctly) to insert a clean dump at line 1808 of `elk_bridge.py`, run picorv32_wb, capture the graph, find the actual mismatch.

---

## 📚 What Was Clarified (Mode 1: Verify Assumption)

### Bug Class
- **Type**: ELK "Referenced shape does not exist"
- **Pattern**: edge source/target references a port ID, but no shape with that ID was emitted
- **Related fixes already in place**:
 - Plan B Step B1 (`6e8256c`): defensive emit at line 1688 for missing ports
 - Plan B Step B1 v2 (line 1750+): post-wrap defensive check after `_wrap_into_clusters`

### Files Involved
- `src/trace/core/graph/viz/elk_bridge.py` (main viz → ELK translation)
- `src/trace/core/graph/viz/viz_data_builder.py` (VizData construction)
- `src/trace/core/graph/viz/viz_engine.py` (entry point for `render_dataflow`)
- `sim/tests/integration/test_real_project_viz.py` (real-project test)

### Test Status (Before Step G)
- ✅ `darkriscv` (273KB DOT)
- ✅ `picorv32_core` (full picorv32.v with target=picorv32_core)
- ❌ **`picorv32_wb`** (target=picorv32_wb, fails with port-ref error)

### Related Code Locations (9 "Referenced shape does not exist" mentions)
| Line | Purpose | Status |
|------|---------|--------|
| 156 | comment: multi-instance dedup | (info) |
| 361 | comment: emit-side miss | (info) |
| 384 | comment: full-path port ID | (info) |
| 419 | comment: darkriscv DLEN fix | (info, fixed) |
| 1441 | comment: dedup_map full path fix | (info, fixed) |
| **1658** | **darkriscv DLEN fix (Step B)** | ✅ |
| **1688** | **defensive emit (Step B1)** | ✅ |
| **2091** | **golden test offset fix** | ✅ |

**Gap**: picorv32_wb cross-module port (target.wb.inner_inst.port) NOT yet covered.

---

## 🔍 What Was Investigated (Mode 2: Trace Evidence)

### Phase 1: Capture Error
- Ran `python3 run_cli.py visualize dataflow --file ~/my_dv_proj/picorv32/picorv32.v --module picorv32_wb --no-strict --dot /tmp/picorv32_wb.dot`
- Got exact error: `Referenced shape does not exist: port_picorv32_wb_dot_picorv32_core_dot_clk`

### Phase 2: Trace Code Paths
- `_resolve_port_id(full_path, role, ...)` at line 148:
 - For multi-instance ports → returns `port_{_safe(full_path)}`
 - For unique short names → returns `port_{_sn}`
- `_port_id_for_input`/`_port_id_for_output` at lines 314-315
- `_referenced_input_fulls`/`_referenced_output_fulls` (line 337-409): collect all port paths referenced by edges
- Main emit loop at lines 425+ walks these sets to emit port shapes
- Defensive emit at line 1688 (Plan B Step B1)
- Post-wrap defensive check at line 1750+ (Plan B Step B1 v2)

### Phase 3: Identify Gaps
- **Hypothesis 1 (DISPROVEN)**: `_wrap_into_clusters` adds nested edges that bypass defensive check
 - Verified: `new_edges` at line 1233 are just `root_edges` with stroke metadata, no new port refs
- **Hypothesis 2 (CURRENT, NOT VERIFIED)**: The port emit loop misses nested instance ports
 - `_resolve_port_id` returns full-path ID for `picorv32_wb.picorv32_core.clk`
 - But port emit loop only emits ports **from `viz.nodes` with `port_side='left'/'right'`**
 - Nested instance ports may not have `port_side` set → never emitted → ELK ref fails

### Phase 4: Failed Dump Attempts
1. **sed-based patch**: Created `IndentationError` because inserted code was inside `if proc.returncode != 0:` block without proper indentation
 - Fix: Reverted via backup
2. **PYTHONSTARTUP**: Only triggers in interactive Python, not script invocation
3. **Monkey-patch wrapper**: `from trace.core.graph.viz import elk_bridge` failed with `ModuleNotFoundError` (wrong package path)

---

## 🎯 Root Cause Analysis (Best Guess — NOT YET VERIFIED)

**The bug is most likely in the port-shape emit loop.**

When picorv32_wb instantiates picorv32_core:
- ELK edge references `port_picorv32_wb_dot_picorv32_core_dot_clk`
- This ID comes from `_resolve_port_id('picorv32_wb.picorv32_core.clk', 'in', ...)`
- The `_safe(full_path)` → `picorv32_wb_dot_picorv32_core_dot_clk`

But the corresponding **port shape** is never emitted because:
- The emit loop walks `input_paths` (line 286), which is filled from `viz.nodes` where `port_side == 'left'`
- Inner instance ports (`picorv32_wb.picorv32_core.clk`) probably have `port_side == ''` or some other value
- They're added to `input_short_to_fulls` via the **same** walk (line 305), so `_resolve_port_id` produces the full-path ID
- But the **emit** walk doesn't include them → shape not created → ELK fails

**Verification needed**: Dump ELK graph and grep for:
- Are there ANY port shapes with `_meta.kind == 'port_in'` or `'port_out'`?
- Specifically: is `port_picorv32_wb_dot_picorv32_core_dot_clk` among the emitted shapes?
- Are there edges referencing it but no shape with that ID?

---

## 🛠️ Proposed Fix (Mode 3 — Pending Verification)

### Fix Option A: Extend Emit Loop to Include Nested Instance Ports
- Modify the `input_paths`/`output_paths` walk (line 286) to ALSO include nested instance ports
- Risk: could double-emit top-level ports, break existing tests
- Effort: 30min + verification

### Fix Option B: Defensive Emit ALL Referenced Port IDs (Not Just Short-Missing)
- Modify the defensive check at line 1688 to ALSO emit nested ports that are referenced but not in `_existing_port_ids`
- Safer because it doesn't change emit logic, just adds fallbacks
- Risk: low (already a fallback layer)
- Effort: 15min + verification

### Fix Option C: Strip Nested Instance from Edge Port References
- Modify `_resolve_port_id` to drop nested instance prefix if the port is also available at top level
- Cleaner but changes ID semantics
- Risk: medium (might break other tests that rely on full-path ID)

**Recommended**: Option B (safest, consistent with existing defensive pattern)

---

## 📋 Next Steps (Resuming Investigation)

1. **G.13 (PENDING)**: Use `edit` tool to insert clean dump at line 1808 of `elk_bridge.py` (preserves indentation properly)
2. Run picorv32_wb → capture graph → grep for missing port ID
3. Based on finding, apply Fix Option B (or whichever fits)
4. Verify with golden regression (5/5 pass) + picorv32_wb (now passes)
5. Test with picorv32_axi, picorv32_pcpi_mul (other sub-targets)
6. Commit Plan B Step G + update debugging_lessons

---

## 📚 Debug Mindset Application (This Document is the Meta-Skill in Action)

Per the **debug-mindset-switcher** skill I created earlier tonight:

| Time | Mode | Action | Outcome |
|------|------|--------|---------|
| 22:28-22:30 | Mode 1: Verify Assumption | Read memory, daily notes, code locations | ✅ Found bug class |
| 22:30-22:32 | Mode 2: Trace Evidence (first capture) | Run picorv32_wb, capture error | ✅ Got exact error msg |
| 22:32-22:50 | Mode 2: Trace Evidence (deeper) | Read code paths, identify hypotheses | ✅ Found 2 hypotheses |
| 22:50-23:00 | Mode 2: Trace Evidence (dump attempts) | Try sed/PYTHONSTARTUP/monkey-patch | ❌ All 3 approaches failed |
| 23:00-23:30 | Mode 5: Write Down (THIS DOCUMENT) | Document findings, propose next steps | 🟡 In progress |

**Lesson learned (applying my own skill)**:
- ✅ User's "先理清现状" correctly triggered Mode 1 first
- ✅ User's "深入调查" correctly triggered Mode 2 next
- ❌ I tried too many dump approaches in parallel (should have used one at a time)
- ✅ Per skill soft rule, "Stuck >1h = forced switch" → entered Mode 5 to write down
- 🔄 Resume with single, clean dump approach (use `edit` tool, not sed)

---

## 🔗 Related Documents

- Case study: `docs/debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md` (Step F precedent)
- Mindset skill: `docs/debugging_lessons/debug-mindset-skill.md` (5 modes + switch rules)
- Daily note: `memory/2026-08-25.md`
- Plan B Step F fix: commit `a939d68`
- Plan B Step B1 defensive emit: commit `6e8256c`

---

**Next action (resuming)**: Use `edit` tool to cleanly insert dump at line 1808, capture picorv32_wb graph, verify hypothesis.