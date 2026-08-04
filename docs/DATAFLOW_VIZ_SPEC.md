# 数据流图可视化 Spec (V10)

> 最后更新: 2026-08-04 14:55
> 状态: 已确认
> 布局引擎: ELK.js (替换 Graphviz dot)
> 渲染: SVG (Python/Node.js 桥接)

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
