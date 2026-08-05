# V100 ELK Compound Graph — 完整做法与原理

> 日期: 2026-08-05  
> 状态: 已完成  
> 基于是: dag-vis/data-flow 项目 (@dag-vis 13:00:00 Wed 2026-08-05)  
> 编译来源: 代码实际实现 (elk_bridge.py + elk_svg_renderer.py) + 迭代历史

---

## 1. 核心思路

用 **ELK.js 原生 compound graph (INCLUDE_CHILDREN 模式)** 实现 scope 嵌套，
**不再 SVG 后补 scope 框**。

ELK 在一次布局调用中同时计算所有层级的坐标：
- case scope 框的尺寸和位置
- branch scope 框的尺寸和位置
- 所有 leaf node 的位置
- 所有跨层级边的路由

```
VizData (condition_chain)      →  ELK compound tree     →  SVG
case {sel==2'b10, sel==2'b1,              root              purple/green rects
      sel==2'b0, sel==default}      ┌───────┼───────┐     + signals + ops
                                    │       │       │     + port nodes
                            case(sel)  port_a..d  port_y   + orthogonal edges
                          ┌────┼────┐
                     branch    branch  ...
                    sig_c      sig_a sig_b
                                   │  /
                                 op(+)
```

---

## 2. ELK 树结构设计

### 2.1 层级布局

```
root (INCLUDE_CHILDREN, RIGHT 方向)
├── port_{name} × N        ← FIRST layer constraint, PORT_IN
├── port_y                 ← LAST layer constraint, PORT_OUT
└── case_{dst}             ← compound node, DOWN 方向
    ├── cond_sel_{dst}     ← 1×1 invisible anchor, FIRST layer (内部)
    ├── branch_{dst}_{cond} ← compound node, RIGHT 方向
    │   ├── sig_{...}      ← signal leaf
    │   └── op_{...}       ← operator leaf
    ├── branch_{dst}_{cond2}
    │   └── ...
    └── ...
```

### 2.2 为什么用 compound graph

ELK 的 `INCLUDE_CHILDREN` 模式一次处理所有层级：
- **自动计算 scope 框尺寸** — 不再手动算 bbox
- **自动路由跨层级边** — PORT_IN → branch 内 signal 自动正交连接
- **自动排列内部节点** — branch 内 signal + op 按 RIGHT 方向排列

之前 V12 flat layout 的问题：
- 所有节点打平在 root.children，scope 框靠 SVG 后补
- 部分边没有 sections，需要 fallback 路由
- scope 框需要从 member_ids 反算 bbox

### 2.3 关键约束

| 节点类型 | ELK 配置 | 作用 |
|----------|---------|------|
| PORT_IN | `layerConstraint: FIRST` | 固定在最左列 |
| PORT_OUT | `layerConstraint: LAST` | 固定在最右列 |
| cond_sel (case 内) | `layerConstraint: FIRST` | case scope 最顶部，接收 sel 连线 |
| case scope | `direction: DOWN` | 内部 branch 竖排 |
| branch scope | `direction: RIGHT` | 内部 signal + op 横排 |
| root | `hierarchyHandling: INCLUDE_CHILDREN` | 一次性布局所有层级 |

---

## 3. 数据流转换：VizData → ELK JSON

### 3.1 Phase 0: 边分类

```python
for edge in viz.edges:
    if edge.condition_chain is not empty:
        cond_by_dst[edge.dst].append(edge)  → 条件边，归入 case scope
    else:
        regular.append(edge)                → 普通信号边，归入 flat 层
```

### 3.2 Phase 1: PORT_IN 节点

```python
for name in input_names:
    root.children.append({
        'id': f'port_{name}', 'width': 44, 'height': 20,
        'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
        '_meta': {'kind': 'port_in'},
    })
```

### 3.3 Phase 2: PORT_OUT 节点

```python
root.children.append({
    'id': f'port_{output_name}', 'width': 44, 'height': 20,
    'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
    '_meta': {'kind': 'port_out'},
})
```

### 3.4 Phase 3: 条件边 → case/branch scope

**数据来源**: `cond_by_dst` dict — 按目标输出分组的所有条件边。

对每个 target (唯一的 dst_id):

```
Step A: 提取 sel 信号名（从 condition_chain[0]）
        → "sel == 2'b10" → sel_label = "sel"

Step B: 按条件值分组 → by_cond = {
          "sel == 2'b10":  [edge_c],
          "sel == 2'b1":   [edge_a, edge_b],
          "sel == 2'b0":   [edge_a],
          "sel == default": [edge_d],
        }

Step C: 对每个组创建 branch compound node:
  - 提取 source_op → 创建 op 节点（+、− 等）
  - 提取 src 信号 → 创建 signal 节点（去重）
  - 创建 branch 内边: signal → op（如果有 op）
  - branch compound 节点: RIGHT 方向，padding [16,10,10,8]

Step D: 创建 ROOT edges:
  - PORT_IN → branch signal（跨层级，ELK 自动路由）
  - branch signal/op → PORT_OUT（跨层级）
```

**Branch compound node 结构**:

```json
{
  "id": "branch_with_case_dot_y_sel____2_b1",
  "_meta": {"kind": "branch", "label": "sel == 2'b1"},
  "layoutOptions": {"elk.direction": "RIGHT", "elk.padding": "[top=16,left=10,right=10,bottom=8]"},
  "children": [
    {"id": "sig_a_with_case_dot_y_sel____2_b1", "_meta": {"kind": "signal"}},
    {"id": "sig_b_with_case_dot_y_sel____2_b1", "_meta": {"kind": "signal"}},
    {"id": "op_Add_with_case_dot_y_sel____2_b1", "_meta": {"kind": "op"}}
  ],
  "edges": [
    {"sources": ["sig_a_..."], "targets": ["op_Add_..."]},
    {"sources": ["sig_b_..."], "targets": ["op_Add_..."]}
  ]
}
```

### 3.5 Phase 3b: sel → case scope 连线

**当前方案** (commit `07fe342`):

```python
# 1×1 invisible anchor 放在 case scope 内部最顶部
cond_sel = {
    'id': f'cond_sel_{sd}',
    'width': 1, 'height': 1,
    'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
    '_meta': {'kind': 'condition_anchor'},
}
case_children.insert(0, cond_sel)

# PORT_IN(sel) → cond_sel（跨层级边）
root_edges.append({
    'sources': [f'port_{sel}'],
    'targets': [f'cond_sel_{sd}'],
    '_meta': {'kind': 'condition_select'},
})
```

**原理**: ELK INCLUDE_CHILDREN 模式自动处理跨层级边。port_sel 在 root 层（FIRST），cond_sel 在 case scope 内（FIRST），ELK 自动计算正交路由从 port_sel 到 cond_sel。

**已知限制**: 见第 7 节。

---

## 4. Scope 颜色与样式

| Scope | fill | stroke | stroke-width | rx | dashed |
|-------|------|--------|-------------|-----|--------|
| case | #f3e5f5 | #7b1fa2 | 1.5 | 6 | No |
| branch | #f1f8e9 | #1b5e20 | 1.2 | 4 | Yes (5,3) |

**Scope label 渲染**:
- 位置: 框内左上角 `(node.x + 6, node.y + 13)`
- case: 10px Bold #7b1fa2 (紫色)
- branch: 8px Normal #1b5e20 (绿色)

**节点渲染**:

| 节点类型 | fill | stroke | font |
|----------|------|--------|------|
| port | #eeeeee | #888888 | 8px Courier #555 |
| signal | #ffffff | #333333 | 9px Courier #2e7d32 (绿色) |
| op | #f0f0f0 | #666666 | 9px Helvetica Bold #333 |

---

## 5. SVG 渲染流程

### 5.1 z-order (从底到顶)

```
1. _draw_scope_bgs()       — scope 背景填充 + 边框
   (按 depth 降序: 内层先画 → 外层覆盖)

2. _draw_edges()            — 所有边 (polyline + arrow marker)
   跳过 condition_anchor 和 invisible 边

3. _draw_leaves()           — 所有叶子节点 (矩形 + 文字)
   跳过 condition_anchor

4. _draw_scope_labels()     — scope 标签文字 (最上层)
```

### 5.2 坐标转换：PARENT → ROOT

ELK 输出 PARENT 坐标系。SVG renderer 需要转换为 ROOT 坐标。

**_collect_nodes** — 递归遍历，累加 parent 坐标:
```python
global_x = node.x + case.x + branch.x
global_y = node.y + case.y + branch.y
```

**_collect_edges** — 同样的累加，对每条边的 section startPoint/endPoint/bendPoints:
```python
shifted_startPoint.x = original.startPoint.x + case.x + branch.x
```

**为什么需要这一步**: ELK compound graph 中，子节点的坐标是相对于其 compound parent 的。branch 内的 sig 的 x 是相对于 branch 的，而 branch 的 x 又是相对于 case 的。要画在 SVG 上，必须把所有层级累加到根。

### 5.3 不可见锚点的处理

`cond_sel` 锚点 (1×1) 和 invisible 边都不渲染：
- `_draw_leaves` 跳过 `kind == 'condition_anchor'`
- `_draw_edges` 跳过 `_meta.invisible == True`

---

## 6. 完整参数速查

### 6.1 ELK 全局配置

```python
ELK_OPTIONS = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.padding': '[top=20,left=20,right=20,bottom=20]',
    'elk.spacing.nodeNode': '25',
    'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
}
```

### 6.2 Scope Padding

| Scope | padding |
|-------|---------|
| Root | [20,20,20,20] |
| Case | [14,0,10,8] ← left=0 让 cond_sel 靠近左边框 |
| Branch | [16,10,10,8] |

### 6.3 Node 尺寸

| 节点 | width × height |
|------|---------------|
| PORT_IN/OUT | 44 × 20 |
| Signal | 50 × 24 |
| OP | 24 × 24 |
| cond_sel anchor | 1 × 1 |

### 6.4 SVG 画布偏移

| 参数 | 值 |
|------|-----|
| OX | 40 |
| OY | 50 |

---

## 7. 已知限制

### 7.1 sel → case 连线无法精确到边框边缘

**根因**: ELK **不支持 edge target = compound node**。边必须连到 leaf node，所以 cond_sel leaf anchor 必须在 case scope **内部**。compound padding 把内部 leaf 从边框向内推。

**决策 (2026-08-05 14:59)**: 维持当前 ELK 原生版本，不切回 SVG 直画。

**未来改进**: 混合方案（ELK 路由 + SVG 末段延长 5-10px），或等 ELK 支持 compound-node port edges。

---

## 8. 迭代历史

| Commit | 描述 |
|--------|------|
| `d5bd09c` | feat: V100 compound graph (INCLUDE_CHILDREN) |
| `e74245d` | fix: sel→case 边定位问题 |
| `69e91d8` | feat: edge styles — driver arrows, signal grey |
| `7eba4c3` | fix: sel→case 水平线到左边框 |
| `40662e3` | fix: cond_sel anchor + 不可见边 |
| `dc68683` | fix: 跳过 invisible 边渲染 |
| `0c953f6` | fix: cond_sel 放回 case scope 内部 |
| `07fe342` | fix: case scope left padding 10→0 |

---

## 9. 验证方法

```bash
cd ~/my_dv_proj/sv_query
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find . -name '*.pyc' -delete 2>/dev/null
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 /tmp/gen_viz_case9.py
```

预期输出:
- `case9_v100.png` — 紫色 case 框 + 4 个绿色 branch 虚线框
- 12 edges, 12/12 with sections（100% ELK native）
- sel 线从 port_sel 右边缘水平连接到 case scope 左边框附近
