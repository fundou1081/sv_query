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

## 七、V100: ELK Compound Graph（✅ 已实现）

> 日期: 2026-08-05 13:37
> 状态: ✅ 已实现并 commit
> Commits: d5bd09c, e74245d, 14acdd0
> 方案: 用 ELK 原生 compound graph (INCLUDE_CHILDREN) 替代 flat layout + SVG 后补 scope 框

### 7.1 为什么从 V12 flat 迁移到 compound graph

**V12 问题**：flat layout（所有节点在 root 下），SVG 渲染器事后计算 scope 框 (post-layout bbox from member positions)。Scope 框不是 ELK 原生布局，导致：
- 框和内容脱节、视觉差
- scope 框 bbox 算法不够精确
- 无法利用 ELK 的层级 spacer 和 cross-hierarchy edge routing

**V100 方案**：让 ELK 原生处理 scope 嵌套（compound graph），ELK 自动计算 scope 框尺寸和位置。

### 7.2 核心架构

```
root (hierarchyHandling: INCLUDE_CHILDREN, RIGHT)
├── PORT_IN: port_sel, port_c, port_d, port_b, port_a  (FIRST layer constraint)
├── PORT_OUT: port_y  (LAST layer constraint)
├── case scope (compound, 无 w/h, ELK 自算)
│   ├── layoutOptions: DOWN direction  (branches 竖排)
│   ├── cond_sel anchor (1x1, 不渲染)  — port_sel 连到这里
│   ├── branch_2b10 (compound, RIGHT)
│   │   └── sig_c
│   ├── branch_default (compound, RIGHT)
│   │   └── sig_d
│   ├── branch_2b1 (compound, RIGHT)
│   │   ├── sig_a, sig_b
│   │   ├── op_Add
│   │   └── edges: sig_a→op_Add, sig_b→op_Add
│   └── branch_2b0 (compound, RIGHT)
│       └── sig_a
└── root edges (跨层级):
    port_c→sig_c, port_d→sig_d, port_b→sig_b, port_a→sig_a(b0), port_a→sig_a(b1)
    sig_c→port_y, sig_d→port_y, sig_a0→port_y, op_Add→port_y
    port_sel→cond_sel_anchor
```

### 7.3 ELK 配置关键点

```python
ELK_OPTIONS = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',  # ← 关键！
}

# PORT_IN/OUT: layer constraint 固定左右列
port_node['layoutOptions'] = {'elk.layered.layering.layerConstraint': 'FIRST'}   # LEFT
port_node['layoutOptions'] = {'elk.layered.layering.layerConstraint': 'LAST'}    # RIGHT

# Case scope: DOWN 方向让 branches 竖排
case_scope['layoutOptions'] = {
    'elk.direction': 'DOWN',
    'elk.padding': '[top=14,left=10,right=10,bottom=8]',
    'elk.spacing.nodeNode': '10',
}

# Branch scope: RIGHT 方向让 signal→op 水平排列
branch_scope['layoutOptions'] = {
    'elk.direction': 'RIGHT',
    'elk.padding': '[top=16,left=10,right=10,bottom=8]',
    'elk.spacing.nodeNode': '12',
}
```

### 7.4 三层节点布局

| 层级 | 节点类型 | size | 渲染 | 说明 |
|------|----------|------|------|------|
| Root | PORT_IN | 44×20 | 灰色小框 | FIRST layer constraint, 左侧列 |
| Root | PORT_OUT | 44×20 | 灰色小框 | LAST layer constraint, 右侧 |
| Case scope | compound | 自算 | 紫色实线框 | 不设 w/h, ELK 自动扩到包含所有 branch |
| Branch scope | compound | 自算 | 绿色虚线框 | 每个 condition label 一个 |
| Branch 内 | signal | 50×24 | 白底黑框, 绿色 Courier | 短信号名 |
| Branch 内 | op | 24×24 | 灰底小框, Bold | +, −, × 等 |
| Branch 内 | cond_sel_anchor | 1×1 | 不渲染 | port_sel 连线目标，只占 ELK 位置 |

### 7.5 边路由（全由 ELK 生成）

所有边都由 ELK orthogonal routing 生成 sections，0 fallback。

| 边类型 | 挂载位置 | 示例 |
|--------|----------|------|
| PORT_IN → branch signal | root edges | `port_c → sig_c` |
| Branch 内 signal → op | branch edges | `sig_a → op_Add` |
| Signal/op → PORT_OUT | root edges | `sig_c → port_y` |
| port_sel → case anchor | root edges | `port_sel → cond_sel_anchor` |
| sel select 虚线 | SVG 渲染器 | 从 port_sel 画台阶线到 case scope 顶边 |

### 7.6 关键 bug 修复

**Bug: branch 内线段坐标偏移**（commit 14acdd0）
- ELK 对 branch compound node 内的 edge sections 使用 **PARENT 坐标**（相对于 branch node）
- `_collect_edges` 必须递归累加 compound node 的 x/y 偏移，转换到 ROOT 坐标
- 根因：ELK 默认 `json.edgeCoords: CONTAINER`，branch 内的 section 坐标是相对于 branch compound node 而非 root

```python
def _collect_edges(node, out, px, py):
    """递归收集边，PARENT→ROOT 坐标转换"""
    nx = (node.get('x', 0) or 0) + px
    ny = (node.get('y', 0) or 0) + py
    for e in node.get('edges', []):
        ec = dict(e)
        for sec in ec.get('sections', []):
            # 偏移 startPoint/endPoint/bendPoints 到 ROOT 坐标
            sec['startPoint'] = {'x': sec['startPoint']['x'] + nx, 'y': ...}
            ...
        out.append(ec)
    for c in node.get('children', []):
        _collect_edges(c, out, nx, ny)
```

### 7.7 结果 (golden_dataflow_9_case)

- **11/11 边**，全有 ELK sections（0 no-section）
- 1 紫色 case scope + 4 绿色 branch scope
- 5 PORT_IN (LEFT) + 1 PORT_OUT (RIGHT)
- 5 signal nodes + 1 op_Add + 1 cond_sel_anchor (1×1 不渲染)
- 所有边由 ELK orthogonal routing 生成

### 7.8 动手前参考

- `~/my_proj/elkjs/examples/hierarchical_modules.js` — ELK compound graph 原型
- `~/my_proj/elkjs/MANUAL.md` — elkjs 手册（坐标系 PARENT/ROOT/CONTAINER）
- `~/my_proj/elkjs/PARAMETERS.md` — 参数参考（hierarchyHandling, layerConstraint, compoundNode）
- `/tmp/test_elk_compound.js` — Node.js 原型验证脚本（case9 场景）
