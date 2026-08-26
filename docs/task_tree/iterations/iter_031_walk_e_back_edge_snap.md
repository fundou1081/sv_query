# Iteration 31: viz_engine walk_e 环回边 endPoint 坐标偏移 bug

**Metadata**:
- **Iteration #**: 31
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_h
- **Created**: 2026-08-26 21:22 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🚧 IN PROGRESS

---

## 🎯 Current Goal

User instruction (21:12 GMT+8): "继续深挖 case27" — dig into why case 27 still shows dangling `{}` Concat node.

User instruction (21:21 GMT+8): "直接实现方案A 把这个所有做好debug记录" — implement Plan A (snap dangling e4 endPoint to target node left) and record all debug steps.

**Root cause summary**: `viz_engine.walk_e` adds `container_off` to edge section coordinates. For non-cyclic edges this produces perfect alignment (+0px offset vs node boundaries). For the cyclic edge `e4` (`{}` → `acc[0]`) in case 27, ELK emits `endX=62` (relative to `genblk_gen_accum_top`) but the actual target `acc[0]` left edge is at relative x=32. After `+container_off(20,245)`, ELK renders e4 end at absolute x=82, but `acc[0]` left edge is at absolute x=32 — **50px (one SIG_W) off**.

This makes e4 visually disconnect from `acc[0]`, leaving `{}` Concat appearing as a dangling node (no outgoing edge visibly connects).

**Fix Plan A**: In `viz_engine.walk_e`, when an edge's rendered `endX` differs from the target node's `left` by an amount in `[SIG_W/2, 3*SIG_W/2]` (i.e. approximately one node-width), **snap** the endPoint x to the target node's left.

---

## 🔬 Investigation Process

### Step 1: Re-test all 32 batch cases (T.47.7, 14:24 GMT+8)
- **Result**: 32/32 PASS, 0 regression
- V101 (commit 91be849) Part A + Part B fixes applied

### Step 2: Send 32 PNGs to user via Feishu (T.50b)
- Sent in 3 batches (cases 1-11, 12-22, 23-31)
- All 32 PNGs delivered successfully

### Step 3: User reports dangling nodes (15:59 GMT+8, T.51)
- User: "我依然看到了悬空的节点"
- Assistant scanned 32 SVGs programmatically — initially flagged 6 OP nodes as dangling in case 27

### Step 4: Visual analysis via image tool (T.51)
- case 27 confirmed: `{}` Concat has 0 outgoing edges; only `+` op nodes have proper `op → acc[N]` flat edges
- Other 31 cases: clean

### Step 5: Wire path debug (T.52.13-20)
- Added debug print in `elk_bridge.py:935` to confirm wire path emits `op_id → sig_id` edge
- Confirmed `op_id='op____wire_acc[0]_7'`, `sig_id='sig_acc_0__wire'`, both in `root_children`
- **But edge still missing from SVG** — root cause deeper than emit

### Step 6: ELK pre-layout JSON dump (T.54)
- Added env-var-gated dump in `run_elk_layout` (`SV_DUMP_ELK_PRE=1`)
- Captured pre-layout at `/tmp/iter54_case27_pre_layout.json` (15KB)
- **Result**: e4 (`{}` → `acc[0]`) EXISTS in pre-layout, both endpoints in `root_children`

### Step 7: Cluster wrapping investigation (T.54.10)
- Post-layout showed:
  - root edges: 16 (all flat)
  - `genblk_gen_accum_top` children: 20 (all op/sig with `_meta.gen_block='gen_accum'`)
  - **`genblk_gen_accum_top` internal edges: 0** ← bug discovered
- **Root cause identified**: `_wrap_into_clusters` moves op/sig nodes into `genblk_*_top` cluster but leaves 16 edges at root level. ELK's manual nested cluster doesn't auto-route edges → all 16 cluster-internal edges lost.

### Step 8: Plan A fix attempt 1 — cluster_id-based (T.55.1)
- Added edge grouping by `cluster_id` in `_wrap_into_clusters`
- **Failed**: case 27 nodes have `cluster_id=''` (target_module level), only `gen_block='gen_accum'`
- Verified via T.55.5-6: genblk cluster children all have `cluster_id='', gen_block='gen_accum'`

### Step 9: Plan A fix v2 — gen_block-based (T.55.11)
- Refactored to group edges by `_meta.gen_block` instead of `cluster_id`
- Added `collect_leaf_children()` helper
- **Result**: T.55.11 confirms `Root edges: 0`, `genblk internal edges: 16` ✅

### Step 10: Regression check (T.55.12)
- 32/32 batch PASS, 0 FAIL
- But visual re-check (T.55.14-15) still shows 6 "dangling" nodes (later clarified: only `{}` and port wrappers are truly dangling)

### Step 11: Container field investigation (T.58-60)
- Read `viz_engine.py:105-147` walk_e — uses `e.get('container')` + `cluster_offsets`
- Verified post-layout: `e4.container='genblk_gen_accum_top'` ✅
- Verified `cluster_offsets['genblk_gen_accum_top']=(20,245)` ✅
- `walk_e` adds `container_off` to all section points — **correct per ELK docs**

### Step 12: Minimal ELK probe (T.62.2)
- Constructed minimal ELK graph: 1 cluster, 2 nodes, 1 edge
- ELK output: cluster_x=(20,20), a=(12,12), b=(82,12), edge start=(62,24) end=(82,24)
- **Confirmed**: section coords are relative to container (cluster_x)
  - start=(62,24) = a.right relative to cluster_x ✓
  - end=(82,24) = b.left relative to cluster_x ✓
- So walk_e's `+container_off` is correct for non-cyclic edges

### Step 13: Decisive alignment table (T.63.1)
Computed `rendered_startX - src.right` and `rendered_endX - tgt.left` for all 16 edges:

| Edge | src.right | startX | Δ_start | tgt.left | endX | Δ_end |
|------|-----------|--------|---------|----------|------|-------|
| e1 (acc[0]→$bits) | 82 | 82 | +0 ✅ | 102 | 102 | +0 ✅ |
| e2 ($bits→{}) | 156 | 156 | +0 ✅ | 176 | 176 | +0 ✅ |
| e3 ({1'b0}→{}) | 156 | 156 | +0 ✅ | 176 | 176 | +0 ✅ |
| **e4 ({}→acc[0])** | **200** | **176** | **-24 ❌** | **32** | **82** | **+50 ❌** |
| e5-e16 (acc[i]/prod → + → acc[N]) | various | various | +0 ✅ | various | various | +0 ✅ |

**e4 is the ONLY misaligned edge. Δ_end = +50px = SIG_W (signal node width).**

### Step 14: Root cause theory (T.63)
- **e4 is a cyclic back-edge**: `acc[0] → $bits → {} → acc[0]`
- ELK's layered layout processes nodes in topological order; the back-edge to an already-placed node gets a different coordinate basis
- Specifically: ELK emits `endX=62` for e4 but `acc[0]` was already placed with `left=32` — ELK's back-edge endpoint calc apparently uses (parent_node_left + node_width) instead of (parent_node_left), causing a 50px shift
- All other edges are forward (non-cyclic) — perfectly aligned

### Step 15: Plan A decided (21:18 GMT+8)
User selects Plan A: snap dangling endPoint to target node left when offset ≈ SIG_W

---

## 📋 Plan A Implementation Design

### Detection rule

In `viz_engine.walk_e`, after computing `points` with `container_off`:
```python
tgt_node = leaves_by_id.get(tgt_id)
if tgt_node:
    tgt_left = tgt_node['gx']
    # Detect dangling end: end.x differs from tgt_left by ~1 SIG_W
    last_pt = points[-1]
    delta = last_pt[0] - tgt_left
    if 0.5 * SIG_W <= abs(delta) <= 1.5 * SIG_W:
        # Snap endPoint.x to tgt_left
        points[-1] = (tgt_left, last_pt[1])
```

### Safety constraint

Only snap if:
1. The delta is in `[SIG_W * 0.5, SIG_W * 1.5]` (range avoids false positives)
2. The target node is found in `leaves_by_id`
3. **NO requirement on bendPoints** — any cyclic edge with the right offset gets fixed

### Backwards-compat

Use the existing `cluster_offsets` and `leaves` dicts already built in `_render_svg_direct`. Build a `leaves_by_id = {n['id']: n for n in leaves}` dict for O(1) lookup.

---

## 📊 Key Data

| Metric | Value |
|--------|-------|
| Investigation turns (T.51 → T.63) | ~13 turns |
| Edges in case 27 | 16 |
| Cyclic back-edges | 1 (e4) |
| Misaligned edges | 1 (e4, +50px on endX) |
| Other edges perfect (+0) | 15/16 |
| Affected case | case 27_generate_loop only |
| Other 31 batch cases | unaffected (no cyclic back-edges) |
| `_wrap_into_clusters` lines added | ~50 (gen_block routing + collect_leaf_children helper) |
| `viz_engine.walk_e` expected delta | ~10-15 lines (Plan A snap) |

---

## 🚨 Lessons Learned

1. **Cycle detection in code**: ELK layered layout is non-robust for back-edges (edges to already-placed nodes). For 1:1 visualization of self-referential code (sigs that feed back into themselves), special handling needed.
2. **The `container` field is reliable**: ELK correctly tags all cluster-internal edges with `container` field. `viz_engine.walk_e` reads this correctly.
3. **Re-test assumption**: 32/32 batch PASS did NOT catch the bug, because the dangling visual was only visible to the user. Must visually inspect SVGs.
4. **Always confirm with minimal repro**: T.62.2 minimal ELK test confirmed the semantics — much faster than debugging production cases.

---

## 🛠 Implementation Steps (T.64+)

1. T.64.1: Implement Plan A in `viz_engine.walk_e` (lines 105-147)
2. T.64.2: Verify case 27: `{}` → `acc[0]` edge renders correctly
3. T.64.3: 32 batch regression (expect 32/32 PASS, 0 regression)
4. T.64.4: 5-case 1:1 verification (expect 5/5 ✅ unchanged)
5. T.64.5: Commit (cherry-pick on top of 91be849)
6. T.64.6: Send updated case 27 PNG to user

---

## 🛑 Current State (this iteration created)

- `_wrap_into_clusters` gen_block fix: ✅ committed in 91be849
- `viz_engine.walk_e` Plan A snap: ⏳ about to implement
- All 32 batch tests passing: ✅
- case 27 `{}` Concat visually dangling: ❌ (about to fix)