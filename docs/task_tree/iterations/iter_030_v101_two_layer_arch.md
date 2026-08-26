# Iteration 30: V101 Two-Layer Architecture — viz_to_elk Routing Fix

**Metadata**:
- **Iteration #**: 30
- **Task Tree Level**: L2
- **Parent Task**: L2_v101_objective_first_redesign
- **Created**: 2026-08-26 14:23 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🚧 IN PROGRESS (T.46 implementation pending)

---

## 🎯 Current Goal

User instruction (13:24:37 GMT+8): "看起来不是我想要的... q1 没问题, q2 也没问题, q3 还是保留这些优化项目, 但和主功能解耦, q4 先维持现状, q5 彻底重构... 这个方案继续平台."

User instruction (13:26:48 GMT+8): "开工"

User instruction (13:57:25 GMT+8): "继续, 要先确认所有的图和代码都能对应上."

User instruction (14:12:37 GMT+8): "走选项B"

User instruction (14:22:52 GMT+8): "继续, 做好iteration记录"

**Goal**: 实现 V101 objective-first 重新设计 — 主功能层 (真理层) 100% 1:1 忠实呈现, PR1+ 优化层解耦成可选后处理. 同时修复 viz_to_elk 路径 routing, 让所有 ternary case 走 expr_trees flat 路径, 让 ?:(sel) op 节点能在 SVG 中正确显示.

**Commit gate**: 必须所有图都能跟代码 1:1 对应 (用户原话: "要先确认所有的图和代码都能对应上").

---

## 🔬 Investigation Process

### Step 1: 用户决策矩阵 (T.41, 13:16:37 GMT+8)

5 个问题 Q1-Q5 + toggle 决策:

| # | 问题 | 决策 | 含义 |
|---|------|------|------|
| Q1 | 悬空节点期望 | (a) 如实呈现代码 | 承认悬空是代码事实, 不修代码 |
| Q2 | 用途 | 代码审查 | 主要场景是审查真实代码结构 |
| Q3 | PR1+ 优化 | 保留 + 解耦 | 主功能层干净, PR1+ 后处理 |
| Q4 | edge kind | 维持现状 | 不拆分 kind/style |
| Q5 | SVG 视觉 | 彻底重构 | 接受破坏性变更 |
| toggle | 单/双模式 | 不考虑 | 单一真理层模式 |

### Step 2: 用户修正决策 (T.42, 13:24:37 GMT+8)

修正: Q3 改"全撤 PR1+"为"保留+解耦". 核心诉求 — **主功能层 1:1 真理, PR1+ 后处理层 (解耦)**.

### Step 3: T.42 关键发现 — PR1+ 实际已归档

| 维度 | 之前假设 | 实际 |
|------|---------|------|
| PR1+ 在 elk_bridge.py 主代码 | ✅ 假设在 | ❌ 已归档到 `_archived_dot/` |
| 当前主代码结构 | 混合 | 三层: viz_to_elk / expr_trees_to_elk → _wrap_into_clusters → ELK layout |

**结论**: 用户关于"PR1+ 解耦"的诉求**实际已满足**. 不需要做 T.44/T.45 (加 `--no-optimize` flag). 实施计划调整:

| Step | 任务 | 状态 |
|------|------|------|
| T.43 | Part A: expr_trees_to_elk 加 op → dst flat 边 | ✅ 完成 |
| ~~T.44~~ | ~~加 --no-optimize flag~~ | ❌ 跳过 (无需) |
| T.45 | 1:1 验证 | ✅ 完成 (发现 4/5 case 不对应) |
| T.46 | viz_to_elk 路由修复 | 🚧 IN PROGRESS |

### Step 4: Part A 修复 (T.43, 13:30 GMT+8)

**修复**: `src/trace/core/graph/viz/elk_bridge.py:570-603` 在 `render_ternary` 函数末尾加 `op → lhs` flat 边 emission.

**关键设计**:
- 不改 `render_ternary` 函数签名 (不需要 `dst_short` 参数)
- 从 `node_id` 反推 `lhs_short` (OP_TERNARY ID 格式 `f"{parent_module}.{lhs_short}.ternary_{sel}"`)
- kind 选 `'dataflow'` (中性, 不耦合 case_item / branch_true / branch_false 视觉约束)

**32 batch 验证**: 32/32 PASS ✅
- 8 个之前 Part B 失败的 case 全部恢复
- ternary/case 相关 case 字节数普遍增加 (证明新边被 emit)

### Step 5: 1:1 验证 — 发现 4/5 case 不对应 (T.45, 13:57+)

5 个 user-flagged case 的 SV `?` op 数 vs SVG `?:` labels 数:

| Case | SV `?` op | SVG `?:` | 一致性 |
|------|----------|---------|--------|
| 25_array_index | 3 | 3 | ✅ 完美 (Part A 修复确认) |
| 11_ternary_scope | 2 | 0 | ❌ 缺失 2 个 |
| 14_ternary_chain | 1 | 0 | ❌ 缺失 1 个 |
| 18_nested_ternary | 6 | 0 | ❌ 缺失 6 个 |
| 20_ternary_scope_nested | 3 | 0 | ❌ 缺失 3 个 |

**根因**: 4/5 个 ternary case 走 `viz_to_elk` 路径 (case compound 嵌套, 不 emit flat `?:` op 节点). 只有 array_index 走 `expr_trees_to_elk` 路径.

**证据** (T.45.15-17):
- case 11/14/18/20 SVG 用 `case (sel_a, sel_b)` / `!(sel_b)` / `ternary_sel_a/b` 这种 case-style label
- case 25 SVG 有 3 个 `?:` label, 跟 SV 完全对应

### Step 6: viz_to_elk 路由分析 (T.46, 14:00+)

**关键代码** (`src/trace/core/graph/viz/elk_bridge.py:1874-1948`):

```python
def _compute_routing(viz):
    raw_expr_trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    expr_trees = dict(raw_expr_trees)
    has_uncond_op = any(...)  # 任何 uncond op 边
    has_call_edge = any(...)  # Call 边
    has_cond_edges = any(...) # 条件边 (ternary / case)
    return raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges


def _build_elk_for_viz(viz):
    raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges = _compute_routing(viz)
    
    # 路径 1: uncond op / call → expr_trees_to_elk
    if has_uncond_op or has_call_edge:
        if expr_trees:
            ...  # expr_trees 路径 (有 ?: op)
        else:
            elk = viz_to_elk(viz)  # fallback
    
    # 路径 2: case/if 条件边 → viz_to_elk (case compound, 无 ?: op)
    elif has_cond_edges:
        elk = viz_to_elk(viz)  # ← 问题: ternary 也走这条
    
    # 路径 3: 纯 expr_trees → expr_trees_to_elk
    elif expr_trees:
        ...  # expr_trees 路径
    
    # 路径 4: fallback → viz_to_elk
    else:
        elk = viz_to_elk(viz)
    
    return elk
```

**问题诊断**:
- `has_cond_edges` 不区分 ternary 和 case
- ternary case 走路径 2 → `viz_to_elk` → case compound 嵌套 → 看不到 `?:` op 节点

**已有 hint** (T.46.6, line ~1497):
```python
# [FIX 2026-08-26 iter_026+] 检测当前 dst 是 ternary 还是 case
_is_ternary_dst = False
if viz is not None:
    for _vn in viz.nodes:
        if getattr(_vn, 'kind', '') == 'OP_TERNARY':
            _vn_id = getattr(_vn, 'id', '')
            if _vn_id.startswith(dst_id + '.') or _vn_id == dst_id:
                _is_ternary_dst = True
                break
```

V6.x 已经有 ternary 检测 (在 viz_to_elk 内), 但**仅用于边 kind 命名** (`branch_true` vs `branch_false`), **没用于路由决策**.

### Step 7: 实施选项分析 (T.45 末, 14:12+)

用户选了 **选项 B**: 修 viz_to_elk 路由, 让 ternary 走 expr_trees flat 路径.

**实施方向**:
- 修改 `_compute_routing`: 加 `has_ternary_op` boolean (检测 viz.nodes 里的 OP_TERNARY)
- 修改 `_build_elk_for_viz`: 如果 `has_ternary_op=True`, 走 `expr_trees_to_elk` 路径 (优先于 viz_to_elk)
- 这样所有 ternary-bearing vizes 都看到 `?:` op 节点 + Part A 的 `op → lhs` flat 边

**备选方案 (备查)**:
- A: Commit Part A + 注释 (1 case 1:1, 4 case 不对应, 不推荐)
- C: 只 commit 注释, Part A 留作下一轮 (Part A 代码留在 working tree)
- ❌ 双管齐下 (同时改 viz_to_elk 内部 emit + 改路由) — 太复杂, 不必要

---

## 📋 实施计划 (剩余)

| Step | 任务 | 状态 |
|------|------|------|
| T.47.3 | 修改 `_compute_routing` 加 `has_ternary_op` | ⏳ pending |
| T.47.4 | 修改 `_build_elk_for_viz` ternary 走 expr_trees | ⏳ pending |
| T.47.5 | 32 batch regression (期望 32/32 PASS) | ⏳ pending |
| T.47.6 | 5 case 1:1 验证 (期望全部 `?:` labels 都出现) | ⏳ pending |
| T.48 | 更新 docs (ARCHITECTURE / VIZ_COMMANDS / CHANGELOG / README) | ⏳ pending |
| T.49 | Commit V101 | ⏳ pending |
| T.50 | Push to origin | ⏳ pending |
| T.51 | 重新生成 SVG + 发飞书 | ⏳ pending |
| T.52 | 报告 | ⏳ pending |

---

## 📊 关键数据汇总

### Part A 修复 (T.43, 13:30 GMT+8)

| 指标 | 值 |
|------|-----|
| 修改文件 | `src/trace/core/graph/viz/elk_bridge.py` (+69 / -60) |
| 新增行 | 33 行 (Part A 修复 + V101 注释 + Part B revert) |
| 32 batch | 32/32 PASS ✅ |
| array_index 字节数变化 | 16770 → 17835 (+1065) |
| 之前 Part B 失败的 case | 8 个 → 全部恢复 ✅ |

### 1:1 验证 (T.45, 13:57+)

| Case | SV `?` op | SVG `?:` | 修复前 | 修复后 (期望) |
|------|----------|---------|--------|----------------|
| 11_ternary_scope | 2 | 0 → **2** | ❌ | ✅ |
| 14_ternary_chain | 1 | 0 → **1** | ❌ | ✅ |
| 18_nested_ternary | 6 | 0 → **6** | ❌ | ✅ |
| 20_ternary_scope_nested | 3 | 0 → **3** | ❌ | ✅ |
| 25_array_index | 3 | 3 → **3** | ✅ | ✅ (Part A 已修) |

### 用户决策链 (T.41-42)

```
10:23 (om_x100b67d0ac796ca0c3b420e85f6c090)
  → "我要更改这个设计, 让我们先客观的代码可视化出来, 然后在考虑怎么优化"
10:49 (om_x100b67d10cb6e4a0c4bca835fe49d71)
  → "继续完成" (强调 1:1)
11:14 (om_x100b67d1ee79b0a4c366e6a821a057b)
  → "先commit 再做A"
11:46 (om_x100b67d25786c8a0c00e163935cb76d)
  → "按照1先revert" (因 Part B 引入 7 regression)
13:16 (om_x100b67d32737d0b0c4f2f7dc4cac0ab)
  → Q1-Q5 全答 (初始版本, Q3 撤 PR1+)
13:24 (om_x100b67d3c79d7cb8c244456fb85a1da)
  → Q3 改 "保留 PR1+, 但和主功能解耦" (修正)
13:26 (om_x100b67d3df4670a8c31cb5d15a73665)
  → "开工"
13:57 (om_x100b67dc4a9ce0b4c1199405075d893)
  → "继续, 要先确认所有的图和代码都能对应上" (1:1 验证 gate)
14:12 (om_x100b67dc739e8080c4424000ebb43cf)
  → "走选项B" (修 viz_to_elk 路由)
14:22 (om_x100b67dc2d0640a8c22ebbe876d6f70)
  → "继续, 做好iteration记录" (本文档)
```

---

## 🚨 教训 / Lessons

1. **不要先做实施再做设计** — Part A 修复前没有先做 1:1 验证, 导致 commit 时才发现 4/5 case 仍未修
2. **每次实施前先验证假设** — T.45 证明 array_index 之外的 4 个 case 走 viz_to_elk 路径, 不在 Part A 修复范围
3. **edge kind 命名跟视觉颜色耦合** 是 V6.x 设计缺陷 (Part B 引入 7 regression 就是这个根因)
4. **iteration 记录要详细** — 用户多次强调"记得记录debug过程" / "做好iteration记录"

---

## 🛑 当前 session 中断点

**下一步**: T.47.3 — 修改 `_compute_routing` 和 `_build_elk_for_viz` 让 ternary 走 expr_trees 路径.

**预计完成时间**: 14:25-14:45 GMT+8 (实施 + 验证)