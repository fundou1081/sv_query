# 数据流图可视化 Spec (V11 + V100)

> 最后更新: 2026-08-05 11:45
> 状态: 已确认
> 布局引擎: ELK.js (替换 Graphviz dot) — V100 FLAT layout
> 渲染: SVG (Python/Node.js 桥接)
> **V100: All nodes at module level, ELK generates ALL edges, scope boxes from leaf positions**

## 迁移决定 (2026-08-04)

Graphviz dot 无法精确控制连线端口方向（入口左侧、出口右侧、直连上下），
且 `splines=ortho` + port 存在已知 bug (Graphviz #1415)。

**决定**：迁移到 **ELK.js (Layered algorithm)**：
- 原生支持 port side (WEST/EAST) 精确控制连线端口
- orthogonal edge routing 直角连线
- compound graph 嵌套 scope 框
- cross-hierarchy edges 跨 scope 等价边
- 布局与渲染分离，输出坐标和折线点

**架构**：
```
Python (sv_query) → VizData → JSON ──→ Node.js (elk.js) → 布局坐标
                                    ──→ Python SVG 渲染器 → .svg/.png
```

## 核心原则

1. **数据层只产出数据，绘图层只消费数据**
2. **条件边保留可见连线** — 蓝色虚线+条件标签，不跳过 muxed_pairs
3. **同名信号等价连线** — 灰色无箭头线，跨 cluster 连
4. **PORT_IN/CONST 过滤** — 所有出边都是条件边的不纳图
5. **能 scope 内连线就不穿 scope** — 只跨 scope 边界时才用等价连线
6. **Module scope 包含所有 port** — port 是 scope 内的节点
7. **Scope 内 OP → port 的路径**：先到 scope 边缘 → 再等价连到 port

---

## 一、Scope 层次结构

```
┌─ [Module Scope] ternary_mixed ──────────────────────────────┐
│  ports: [a] [b] [c] [d] [e]         [y] [z]                 │
│                                                              │
│  # Stage 层：普通数据流 OP                                   │
│  a→+←b → sum_ab    c→-←d → sub_cd    e→×←8'd3 → prod_e    │
│                                                              │
│  ┌─ scope: y (选择: sel) ──────┐                             │
│  │ ┌─[T] sel───┐ ┌─[F] !(sel)─┐│                             │
│  │ │sum_ab→+→y │ │sub_cd→>>→y ││                             │
│  │ │ 8'd10─┘   │ │  2──┘      ││                             │
│  │ └───────────┘ └────────────┘│                             │
│  └─────────────────────────────┘                             │
│                                                              │
│  ┌─ scope: z (选择: mode) ─────┐                             │
│  │ ┌─[F] !(mode)─┐             │                             │
│  │ │ sub_cd→z    │             │                             │
│  │ └─────────────┘             │                             │
│  │ ┌─[T] mode────────────────┐ │                             │
│  │ │ ┌─内scope(选择: sel)──┐ │ │                             │
│  │ │ │[T]sum_ab→z          │ │ │                             │
│  │ │ │[F]prod_e→z          │ │ │                             │
│  │ │ └─────────────────────┘ │ │                             │
│  │ └─────────────────────────┘ │                             │
│  └─────────────────────────────┘                             │
│                                                              │
│  等价连线（灰色无箭头，跨 cluster）：                         │
│    sum_ab(stage) ←→ sum_ab(scope_y) ←→ sum_ab(scope_z)      │
│    sub_cd(stage) ←→ sub_cd(scope_y) ←→ sub_cd(scope_z)      │
│    prod_e(stage) ←→ prod_e(scope_z)                          │
│    port(y) ←→ y(scope内出口)                                 │
│    port(z) ←→ z(scope内出口)                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、连线规则

### 2.1 信号等价连线

**样式**：`[style=solid color="#9e9e9e" dir=none penwidth=1.5]`

**触发**：同名信号跨越 cluster 边界（scope↔stage、scope↔scope、port↔scope）

**收集时机**：scope 渲染时记录分支信号名，scope 渲染完成后统一在 DOT 顶层输出等价边

### 2.2 Stage 层连线

| 边类型 | 样式 |
|--------|------|
| 信号→OP→信号 | 黑色实线 |
| 条件边（带 condition_chain） | scope 已表达条件 — **跳过 muxed_pairs** |
| 无条件的 mux 边 | 跳过（muxed_pairs） |

### 2.3 连线方向

| 规则 | 说明 |
|------|------|
| 节点入口线 | 统一从**左侧**进入 |
| 节点出口线 | 统一从**右侧**出去 |
| 直连线 | 只能**上下**方向（同列对齐） |
| 等价连线（灰色无箭头） | 不限制方向 |

DOT 配置：`rankdir=LR`, `splines=ortho`, 用 `rank=same` 保证同列对齐。

### 2.4 Scope 内部连线

| 边类型 | 样式 |
|--------|------|
| 分支信号→OP→scope 目标 | 分支颜色实线 |
| scope 内 OP→port | 先连到 port 代理节点，再用等价线连 port |
| 常量→OP | 蓝色实线 `#1565c0` |
| 同条件兄弟信号→OP | 绿色实线 `#2e7d32` |

### 2.4 Module Scope

- 最外层 cluster 框
- 包含所有 port 节点（PORT_IN/PORT_OUT）
- port 到内部信号的等价连线

---

## 三、实施

### 3.1 数据层（不改）

- `driver_extractor.py`：标记 `source_op`、`condition_chain`
- `viz_data_builder.py`：`_enrich_datapath_info` + PORT_IN/CONST 过滤

### 3.2 绘图层

1. Module scope 框 + port 节点
2. Stage 层 OP + 非 OP 边（条件边保留）
3. 条件 scope 框 + 分支渲染
4. 信号等价边（跨 cluster，灰色无箭头）
5. Scope 内 OP → port 等价连线

---

## 四、验证

- 11/11 DOT binary OP validation PASS
- 0 个 orphan 节点
- 所有跨 scope 同名信号有等价连线

---

## 五、Edge Routing 策略（V11 新增）

### 5.1 问题背景

ELK.js 对 **module 层（跨 compound）的边无法生成 sections**。
原因：PORT_IN/OUT 和 branch dummy 节点在不同 compound 层级，
ELK 的 `crossHierarchy` 选项只为同层节点生成路由，跨层级边返回 0 sections。

因此需要 fallback 路由算法处理这些无-section 的边。

### 5.2 当前方案：Stair-Step Above Scope（阶梯式上方绕行）

选型过程：
- V92 H-V-H 直角 → 中间线穿过节点 ❌
- V93 上方 channel → 线太直，拐角生硬
- **V94/V95 阶梯式** → 小横步让拐角更自然 ✅ **最终选择**
- V96 斜角 → 太简洁，缺视觉层次
- V97 贝塞尔 → 曲线不够"电路图"风格

**最终采用：V95 阶梯+上方（stair-step above scope）**

### 5.3 路由算法伪代码

```
function draw_edge_fallback(source_leaf, target_leaf, scopes):
    sx = source.right_edge.x()
    sy = source.center_y()
    tx = target.left_edge.x()
    ty = target.center_y()

    // Find routing ceiling: above the parent case/ifelse scope
    ceiling_y = min(source.top, target.top) - 8
    if enclosing_case_scope_found:
        ceiling_y = min(ceiling_y, case_scope.top - 4)
    if ceiling_y >= min(sy, ty):
        ceiling_y = min(sy, ty) - 12

    // Small horizontal step (6px) before vertical turns
    h_step = 6

    // 6-segment polyline path:
    path = [
        M(sx, sy),                    // exit source
        L(sx + h_step, sy),           // small horizontal step right
        L(sx + h_step, ceiling_y),    // go up to ceiling
        L(tx - h_step, ceiling_y),    // traverse horizontally
        L(tx - h_step, ty),           // go down
        L(tx, ty),                    // enter target
    ]
    draw_polyline(path, arrow_at_end)
```

### 5.4 Example: golden_dataflow_9_case

```
      sel a  b  c  d               y
      [  ][ ][ ][ ][ ]           [  ]
       │   │  │  │  │             │
   ┌───┘   │  │  │  │             │
   │       │  │  │  │    ╭────────┼─────────╮
   │ ┌─────┼──┼──┼──┼────┤  PORT  │  PORT   │
   │ │     │  │  │  │  ╭─┼───────┼──┐      │
   │ │  ╔══╪══╪══╪══╪══╪═╪═══════╪══╪══╗  │
   │ │  ║  │  │  │  │  │ │       │  │  ║  │
   ▼ ▼  ║  │  │  │  │  │ ▼       ▼  │  ║  │
  ┌─────╫──┼──┼──┼──┼──┼──────────┼──╫──┐│
  │ ┌───╫──┼──┼──┼──┼──┼──────────┼──╫─┐││
  │ │[c]╫──┼──┼──┼──┼──┼──────────┼──╫─┤││
  │ │   ╫  │  │  │  │  │          │  ║ │││
  │ │   ║  │  │  │  │  │          │  ║ │││
  │ │sel==╫─┼──┼──┼──┼──┼──────────┼──╫─┤││
  │ │2'b10║  │  │  │  │  │          │  ║ │││
  │ └──┬──║──┼──┼──┼──┼──┼──────────┼──╫─┘││
  │    ╰──╬══╪══╪══╪══╪══╪══════════╪══╬──╯│
  │       ║  │  │  ┌┼┐ │  │          │  ║   │
  │ ┌─────╫──┼──┼──┤+├─┼──┼──────────┼──╫┐  │
  │ │     ║  │  │  └┼┘ │  │          │  ║│  │
  │ │sel==╫──┼──┼──┼──┼──┼──────────┼──╫│  │
  │ │2'b1 ║[a][b]  │  │  │          │  ║│  │
  │ └──┬──╬══╪══╪══╪══╪═╪══════════╪══╬╪──╯│
  │    ╰──╬──╫──╫──╫──╫─╫──╫───────╫──╬╪──╯│
  │       ║  ║  ║  ║  ║ ║  ║       ║  ║   │
  │ ╔══╦══╩══╩══╩══╩═╩═╪══╪═══════╪══╩══╗ │
  │ ║  │  │  │  ┌──┐    │  │       │     ║ │
  │ ║sel│==│2'b│00│─────┼──┼───────┼─────╫─┘
  │ ║  │  └──┘  [a]    │  │       │     ║
  │ ║  │  ┌──┐  ┌──┐   │  │       │     ║
  │ ║sel│==│de│fault│───┼──┼───────┼─────╫──
  │ ║  │  └──┘  [d]    │  │       │     ║
  │ ╚══╩═══════════════╧══╧═══════╧═════╝
  │       case (sel)
  └── module: golden_dataflow_9_case.sv

  ═══ = stair-step fallback edge (绕到 scope 上方)
  ─── = ELK-generated edge (branch 内部)
  ╭╮ = edge enters from left / exits from right
```

### 5.5 关键文件

- `src/trace/core/graph/viz/elk_bridge.py` — ELK JSON 构建，PORT_IN/OUT 作为真实节点
- `src/trace/core/graph/viz/elk_svg_renderer.py` —
  - `_draw_edge_channel()` — 阶梯式 fallback router
  - `_gather_scopes()` — 收集 scope 框坐标用于 ceiling 计算
  - `_gather_leaves()` — 收集叶子节点全局坐标
  - `_gather_edges()` — 收集边 + sections（ELK 生成的路由点）

---

## 六、V100: FLAT Layout（2026-08-05）✅ 最终方案

### 6.1 为什么从 V75 compound 改为 V100 flat

**V75 问题**：使用 ELK compound nesting（嵌套 hierarchy）时，PORT_IN/OUT 和
branch signal/op/dummy 节点在不同 compound 层级，ELK 的 `crossHierarchy` 无法
为跨层级边生成 sections。

- V75 结果：16 条边中 10 条没有 sections，需要 fallback 路由器
- fallback 路由器（stair-step）只能猜测边走向，无法感知 ELK 布局的全局信息

**V100 方案**：把所有节点（PORT_IN, signal, op, dummy, PORT_OUT）放在 module 层
（flat），ELK 用 `RIGHT` 方向一次性布局所有节点和边。

### 6.2 V100 架构

```
elk_bridge.py:
  1. 从 VizData 提取条件边 → case/branch 分组
  2. PORT_IN/OUT 节点 → layerConstraint (FIRST/LAST) → 左/右列
  3. 每个 branch 内的 signal/op/dummy_out 节点 unpack 到 module 层
  4. 跨 branch 同名列去重 (flat_seen_eids set)
  5. 条件选择信号 (sel) → case_cond_input dummy (仅 ELK 占位，不渲染)
  6. ELK options: direction=RIGHT, orthogonal edge routing

elk_svg_renderer.py:
  1. _build_scope_boxes(): 从 leaf 坐标后处理计算 case/branch scope 框
  2. _draw_scopes_flat(): 绘制 scope 框 + 内嵌标签 (y+14 在框内左上角)
  3. _draw_ports_v100(): 从 leaves_by_id 定位 port 节点，画 port 框和文本
  4. _draw_edges_flat(): 使用 ELK sections 画所有数据边（无 fallback）
  5. _draw_nodes_flat(): 画 signal/op 节点，跳过 dummy/port/condition_input
  6. _draw_condition_edges(): 画 sel→scope 的条件选择虚线
```

### 6.3 Sel 条件选择连线：台阶状折线

**错误尝试历程**：

| 版本 | 方案 | 问题 |
|------|------|------|
| v1 | 贝塞尔曲线 `M C` | 飞书渲染成斜线，不够"电路图"风格 |
| v2 | 折线 `M L(6px) L(tx)` | 水平段仅 6px，台阶不明显，飞书渲染可能近似斜线 |
| v3 | 台阶伸入 scope `→ 40px → ↓ → ←` | 最后一段往左拐，违反左→右数据流 |
| v4 | 从 scope 顶部进入 `→ 40px → ↓` | sel 垂直线和 scope 填充 rect 重叠 |

**最终方案 (v5)**：

路径：`M sx sy L step_x sy L step_x ty`，`step_x = max(sx + 40, tx)`

- 从 port 右边缘出发，至少 40px 水平段 → 垂直向下进入 scope 顶部
- 全程 `→↓` 流，没有左拐
- `condition_input` dummy 节点不在 SVG 中渲染（仅在 ELK 中占位）

### 6.4 标签内嵌 Scope 框

**错误尝试**：

| 版本 | 方案 | 问题 |
|------|------|------|
| v1 | 标签在 scope 框外上方 `y - 4` | 飞书可能裁切到框外文字 |
| v2 | 标签在框内 `y + 14` + `dominant-baseline: hanging` | 某些渲染器可能不支持 dominant-baseline |

**最终方案**：标签在框内左上角 `x + 8, y + 14`，branch scope 额外 +16px 高度预留标签空间，case scope 额外 +18px。

### 6.5 关键去重逻辑

- `flat_seen_eids`: 跨 branch 信号节点去重（如 `a` 同时出现在 `sel==2'b0` 和 `sel==2'b1`）
- `port_signal_added`: port→signal 边去重（同一 port 不应连同一个 signal 多次）
- `op_added`: op→branch_out 边去重（同一 op 在同一 branch 内只连一次）

### 6.6 V100 结果 (golden_dataflow_9_case)

- 14 条边，0/14 no-section（100% ELK 原生）
- 节点：5 PORT_IN + 1 PORT_OUT + 4 signal + 1 op (+ 不渲染的 1 condition_input dummy)
- 去重：0 重复节点，0 重复边


---

## 七、V12→V100 增量改动：Scope 层级深度 + 渲染顺序

> 日期: 2026-08-05 13:23
> 状态: 技术方案评估完成，待实现
> 背景: 方豆发参考图（case (sel) 紫色大框 + 绿色虚线分支框 + 双行 condition/value 节点）
> 决策: 不改 elk_bridge 主逻辑（viz_to_elk），只改 `_build_scope_map` + SVG 渲染

### 7.1 当前 V12 基线数据评估

**VizData 结构**（golden_dataflow_9_case）：
- 6 个节点: 5 PORT_IN (sel, a, b, c, d) + 1 PORT_OUT (y)
- 5 条边: 全部带 condition_chain，4 个不同条件标签 + 1 个 Add OP
- 条件标签: `sel == 2'b10`, `sel == default`, `sel == 2'b1`, `sel == 2'b0`
- `datapath.op_index['y']` = {'ops': ['Add'], 'consts': []}

**V12 `_build_scope_map` 的问题**：
- 只有一个 scope，所有 5 条边的 src+dst 打平到同一 scope
- depth 全是 1
- scope label = `mux: sel=sel == 2'b0`（取第一条边的条件，不准确）
- 没有 case scope（紫色外层）和 branch scope（绿色内层）的层级区分

### 7.2 参考图结构（方豆提供）

```
┌─ case (sel) 紫色实线大框 ─────────────────────────────────┐
│                                                             │
│  ┌─ sel == 2'b10 绿色虚线框 ─┐                              │
│  │  [c]                       │──→ y                        │
│  └───────────────────────────┘                              │
│  ┌─ sel == default 绿色虚线框 ─┐                             │
│  │  [d]                       │──→ y                        │
│  └───────────────────────────┘                              │
│  ┌─ sel == 2'b1 绿色虚线框 ─┐                                │
│  │  [b]                       │──→ + ──→ y                  │
│  └───────────────────────────┘                              │
│  ┌─ sel == 2'b0 绿色虚线框 ─┐                                │
│  │  [a]                       │──→ + ──→ y                  │
│  └───────────────────────────┘                              │
│                                                             │
│  绿色大框（无标签，包裹所有 4 个分支）                         │
└─────────────────────────────────────────────────────────────┘
```

Scope 层级深度：
- depth=0: case scope（紫色实线 #f3e5f5 / #7b1fa2）
- depth=1: 绿色大框（无标签，包裹所有分支）← 当前暂不实现
- depth=2: branch scope（绿色虚线 #f1f8e9 / #1b5e20，每条件一个）

### 7.3 改动范围（仅 2 个函数）

| 文件 | 函数 | 改动 |
|------|------|------|
| `elk_bridge.py` | `_build_scope_map()` | **重写**：按 condition 分组 → 每条件一个 branch scope (depth=1) + case scope (depth=0)。`member_ids` 按条件分组，只含该条件的 signal/op 节点 |
| `elk_svg_renderer.py` | `_draw_scopes()` / `render_svg()` | 渲染顺序改为 scope bg → edges → nodes → scope labels（标签最上层）。标签从框外 `y-6` 改为框内 `x+8, y+14`。按 depth 降序渲染（外层后画，作为背景） |

**不需要改的部分**：
- `viz_to_elk()` — 节点/边构建逻辑不动
- `run_elk_layout()` — ELK 布局引擎不动
- `_draw_node()` / `_draw_edge()` — 节点/边的绘制逻辑不动
- elk_svg_renderer 的其他渲染函数

### 7.4 `_build_scope_map()` 新算法（伪代码）

```python
def _build_scope_map(viz):
    cond_by_dst = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        if chain: cond_by_dst[e.dst].append(e)

    scope_map = {}
    scope_idx = 0

    for dst_id, cedges in cond_by_dst.items():
        if len(cedges) < 2: continue  # 不是 case 语句
        
        scope_idx += 1
        case_id = f'scope_{scope_idx}'
        
        # 提取 sel 信号名
        sel_sig = extract_sel_signal(cedges)  # from condition_chain
        
        # 按 condition label 分组
        by_cond = defaultdict(list)
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            by_cond[chain[-1]].append(e)
        
        # 为每个 condition 建 branch scope
        case_members = []
        for cond_label, edges in by_cond.items():
            scope_idx += 1
            branch_id = f'scope_{scope_idx}'
            members = set()
            for e in edges:
                members.add(_elk_id(e.src))
                members.add(_elk_id(e.dst))
                # 如果有 OP，也加入
                if getattr(e, 'source_op', None):
                    members.add(make_op_id(e))
            scope_map[branch_id] = {
                'depth': 1, 'label': cond_label,
                'member_ids': list(members),
            }
            case_members.extend(members)
        
        # Case scope（外层）
        scope_map[case_id] = {
            'depth': 0, 'label': f'case ({sel_sig})',
            'member_ids': list(set(case_members)),
        }
    
    return scope_map
```

### 7.5 SVG 渲染改动

**渲染 z-order**（render_svg 内）：
```python
# 当前 V12:
_draw_scopes(svg, layout, scope_map)   # scope 框 + label 一起画
_draw_stages(svg, layout, stage_map)
_draw_edges(...)
_draw_node(...)

# V100 改动后:
_draw_scopes_bg(svg, layout, scope_map)     # 仅 scope 背景填充 + 边框
_draw_stages(svg, layout, stage_map)
_draw_edges(...)
_draw_node(...)
_draw_scopes_labels(svg, layout, scope_map) # scope 标签（最上层）
```

**`_draw_scopes_bg` 逻辑**：
- 按 depth 降序排序（depth 大的先画 = 内层先画）
- 对每个 scope：画背景 rect + 边框 rect
- dashed 仅对 depth >= 1 的 scope

**`_draw_scopes_labels` 逻辑**：
- 标签位置从 `min_y - 6` 改为 `min_y + 14`（框内左上角）
- 只画有 label 的 scope

### 7.6 决策确认（与方豆讨论）

| 问题 | 决策 |
|------|------|
| branch scope 分组 | 1 个 condition label → 1 个绿色虚线框，**不合并** |
| 分支节点 label | 单行 condition 文字（非双行 condition+value） |
| 绿色大框（无标签，包裹所有分支）| **本次不实现**，后续再加 |
| PORT_IN/OUT 布局 | **不改**，沿用 V12 的 viz_to_elk() 逻辑 |

### 7.7 预期效果

改动后 golden_dataflow_9_case 的 scope_map 应产出：

```
scope_1 (case_scope): depth=0  label='case (sel)'
  member_ids=[all signal + op nodes]

scope_2: depth=1  label='sel == 2'b10'  member_ids=[c, y]
scope_3: depth=1  label='sel == default'  member_ids=[d, y]
scope_4: depth=1  label='sel == 2'b1'  member_ids=[a, b, y, op_Add]
scope_5: depth=1  label='sel == 2'b0'  member_ids=[a, y]
```

渲染：4 个绿色虚线框（各含对应信号）嵌套在 1 个紫色实线 case 框内。标签在框内左上。
