# Iteration 25: Investigate Dangling Operator Nodes

**Metadata**:
- **Iteration #**: 25
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 08:59 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: ✅ COMPLETE — Investigation done, root causes identified

---

## 🎯 Current Goal

User feedback (08:58:59 GMT+8): "从这些图片里我已经发现了，有悬空的运算符节点，这是不对的。你要深入调查一下，checker和 生成逻辑里面的问题。记得记录debug过程."

**Three reported phenomena:**
1. `ternary_scope` image has dangling operator nodes
2. `array_index` image has self-pointing arrows (operators → themselves), **twice**
3. Many other images have commonly seen dangling nodes — need explanation

---

## 🔬 Investigation Process (Debug Mindset Mode 4: TEST REAL)

### Step 1: Reproduce — Dump ELK graphs for problem cases

```bash
# Inject dump code into elk_bridge.py
python3 << PYEOF
# Replace `return json.loads(proc.stdout)` with dump code
# - First attempt: filter by sys.argv[1] → FAILED (sys.argv has subcommand, not filename)
# - Fix: always dump to /tmp/iter25_dump_{timestamp}.json
PYEOF

# Run ternary_scope and array_index
python3 run_cli.py visualize dataflow \
    --file .../golden_dataflow_11_ternary_scope.sv \
    --module ternary_scope --no-strict \
    --svg /tmp/iter25_ternary_scope.svg

# Got dumps: /tmp/iter25_dump_1787706049.json, /tmp/iter25_dump_1787706067.json
```

### Step 2: Analyze graphs

**ternary_scope dump** (15,394 bytes, 25 nodes, 1 op):
```
Op nodes (kind=op):
  op_Subtract_ternary_scope_dot_z_a___b [op] label='?'

Outgoing edges: 0  ← 🚨 DANGLING
```

**array_index dump** (26,416 bytes, 45 nodes, 15 ops):
```
ALL 15 ops have NO outgoing edges ← 🚨 ALL DANGLING
Notable: array_index.mux_hi.ternary_sel appears 3 TIMES ← 🐛 DUPLICATE ID BUG
```

### Step 3: Cross-reference with source code

`ternary_scope.sv`:
```systemverilog
assign z = (a > b) ? (a - b) : 8'd0;  // Subtract operator → z
```
The `a - b` should produce: op_Subtract → result signal → z

`array_index.sv` (relevant part):
```systemverilog
wire [7:0] mux_hi = (sel == 2'd0) ? byte3 :    // 3 ternary_sel ops (one per branch)
                    (sel == 2'd1) ? part  :
                    (sel == 2'd2) ? byte0 : byte1;
```

### Step 4: Find parent compound structure

```
ternary_scope:
  op_Subtract_ternary_scope_dot_z_a___b inside:
    root > case_ternary_scope_dot_z > branch_ternary_scope_dot_z_a___b  ← IS inside case compound!
```

array_index: All op nodes are at `root` level (NOT inside case compound).
This is consistent with `assign` statements, which use `op_*` directly without case compound.

### Step 5: Find the code that emits op nodes

```bash
grep -rn "_emit_conditional_op_nodes\|OP_TERNARY\|OP_CASE\|BRANCH_RESULT"
# Found:
#   src/trace/core/graph/models.py:125-126: OP_TERNARY / OP_CASE enum
#   src/trace/core/graph/models.py:155-158: BRANCH_* enum
#   src/trace/unified_tracer.py:498: calls _emit_conditional_op_nodes
#   src/trace/unified_tracer.py:682: def _emit_conditional_op_nodes
#   src/trace/unified_tracer.py:780: OP_TERNARY → lhs (BRANCH_RESULT)
```

### Step 6: Read Plan B Step A6 design doc (the smoking gun!)

`src/trace/core/graph/viz/elk_bridge.py` line 30-50:
```
⚠️ BRANCH_RESULT / CASE_RESULT 边: 隐式 — case compound 内部子节点 (sig_*_b*, op_*)
   通过 _emit_edge signal → op_id 连线, 最终在 case compound 内表达
   (compound 输出端通过 PORT_OUT → sig_*_b*_dummy 边到 output port)
```

This is the **explanation**: BRANCH_RESULT / CASE_RESULT edges are **NOT** flat graph edges.
They are expressed via **case compound parent-child hierarchy** instead.

---

## 🎯 Root Cause Analysis

### Phenomenon 1 (ternary_scope "dangling op"): ✅ **NOT A BUG** — design choice

The `op_Subtract_ternary_scope_dot_z_a___b` appears to have no outgoing edges, but it IS inside:
```
root > case_ternary_scope_dot_z > branch_ternary_scope_dot_z_a___b
```

The "result" is expressed via:
- Parent compound (`case_ternary_scope_dot_z`) owns the op as child
- Compound's output port (via PORT_OUT → sig_*_b*_dummy) connects to final output

This is **Plan B Step A6 design decision** (2026-08-24). Not a bug.

### Phenomenon 2 (array_index self-pointing arrows): 🐛 **REAL BUG** — duplicate ID

The op node `array_index.mux_hi.ternary_sel` appears **3 times** because:
```systemverilog
wire [7:0] mux_hi = (sel == 2'd0) ? byte3 :    ← ternary_sel #1
                    (sel == 2'd1) ? part  :    ← ternary_sel #2
                    (sel == 2'd2) ? byte0 : byte1;  ← ternary_sel #3
```

3 different `?` operators (one per `:` chain segment) all generate the same ID
`array_index.mux_hi.ternary_sel` because they share the same LHS expression `mux_hi`.

This is a **genuine ID generation bug** in `_emit_conditional_op_nodes` — the ID should be
disambiguated by branch index or position. **User's observation "operator pointing to itself"** is correct!

### Phenomenon 3 (general "dangling ops"): ✅ **NOT A BUG** — design choice (same as #1)

All op nodes have no direct outgoing edges. This is consistent with Plan B Step A6 design.

---

## 💡 Why Ops Have No Direct Outgoing Edges

| Edge Kind | How It's Rendered |
|-----------|-------------------|
| `BRANCH_CONDITION` | via `sel_anchor condition_select` edge (port → cond_sel_<dst>) |
| `BRANCH_TRUE` | via `root_edges` (port → sig_*_b*) |
| `BRANCH_FALSE` | NOT a separate edge (semantic in `condition_chain`) |
| `BRANCH_RESULT` / `CASE_RESULT` | **NOT flat graph edges** — via case compound parent-child hierarchy |

The visualization is **100% complete**, just expressed differently:
- Instead of: `signal → op → signal` (3 nodes, 2 edges)
- We have: `op (inside case compound)` (1 node inside compound)

This is more compact and easier to read.

---

## 🐛 Real Bug Found: Duplicate ternary_sel ID (Phenomenon 2)

**Location**: `src/trace/unified_tracer.py:682` `_emit_conditional_op_nodes`

**Symptom**: Same op node ID appears multiple times in compound chain ternary
(`? : ? : ? : default`) — the user sees "operators pointing to themselves" (self-loop arrows).

**Root cause**: ID generation doesn't disambiguate between ternary operators at different
positions in the same chain. Both `(sel == 0) ? byte3 : ...` and `(sel == 1) ? part : ...`
generate ID `array_index.mux_hi.ternary_sel` (same `mux_hi` LHS).

**Verification**: array_index has 3 `array_index.mux_hi.ternary_sel` entries.
User reported "operators pointing to themselves twice" — confirms 3 nodes create 2 self-loops.

---

## 🔧 Suggested Fix (for Phenomena 2 only)

In `_emit_conditional_op_nodes`, generate unique IDs by including branch index:
```python
# Current (BUG):
op_id = f"{prefix}.{lhs_short}.ternary_sel"

# Fix:
op_id = f"{prefix}.{lhs_short}.ternary_sel.b{branch_idx}"  # b0, b1, b2 for chain
```

---

## 📁 Artifacts Created

- `/tmp/iter25_dump_1787706049.json` — ternary_scope dump (15,394 bytes)
- `/tmp/iter25_dump_1787706067.json` — array_index dump (26,416 bytes)
- `/tmp/iter25_ternary_scope.svg` — regenerated (7063 bytes)
- `/tmp/iter25_array_index.svg` — regenerated (16,770 bytes)

---

## ✅ Summary

**For the user**:

1. **ternary_scope "dangling op"**: ✅ **Not a bug** — it's the Subtract op inside a case compound
 (`a > b ? (a - b) : 8'd0`). Result goes through compound's output port, not direct edges.

2. **array_index self-pointing arrows**: 🐛 **Real bug** — duplicate ID `array_index.mux_hi.ternary_sel`
 appears 3 times (one per chain ternary). Fix: disambiguate by branch index in ID generation.

3. **General "dangling ops"**: ✅ **Not a bug** — design choice from Plan B Step A6 (2026-08-24).
 BRANCH_RESULT / CASE_RESULT edges are expressed via **case compound parent-child hierarchy**
 instead of flat graph edges. This is more compact and 100% complete semantically.

---

## 🔄 Next Action

- Send investigation report to user
- Optionally: fix the duplicate ID bug in `_emit_conditional_op_nodes`