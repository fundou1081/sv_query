# ELK.js 使用手册 v1.0

> 为 sv_query dataflow 可视化迁移编写的 ELK.js 深入参考文档
> 最后更新: 2026-08-04

---

## 1. 概述

ELK.js (Eclipse Layout Kernel) 是一个**纯布局引擎**，只做节点位置计算和边路由，不做渲染。
- npm: `elkjs` (最新版 0.12.0)
- 核心算法: **layered** (Sugiyama 分层布局)，专为有向数据流图设计
- 特点: 原生支持 ports（端口）、compound graphs（嵌套 scope 框）、orthogonal edge routing（直角连线）
- 渲染配合: elkjs-svg、sprotty、React Flow 等

---

## 2. 输入 JSON 结构

### 2.1 最小结构

```json
{
  "id": "root",
  "layoutOptions": {
    "elk.algorithm": "layered",
    "elk.direction": "RIGHT"
  },
  "children": [
    { "id": "a", "width": 80, "height": 40 },
    { "id": "b", "width": 80, "height": 40 }
  ],
  "edges": [
    { "id": "e1", "sources": ["a"], "targets": ["b"] }
  ]
}
```

### 2.2 带 Ports（端口）

```json
{
  "id": "a",
  "width": 80, "height": 40,
  "ports": [
    {
      "id": "a_out",
      "properties": { "port.side": "EAST" }
    }
  ]
}
```

```json
// edge 需要指定 port:
{ "id": "e1", "sources": ["a"], "targets": ["b"],
  "sourcePort": "a_out", "targetPort": "b_in" }
```

### 2.3 带 Labels

```json
{ "id": "a", "width": 80, "height": 40,
  "labels": [{ "text": "sum_ab", "fontSize": 10, "fontName": "Courier" }]
}
```

### 2.4 Compound Graph（嵌套 Scope 框）

```json
{
  "id": "root",
  "children": [
    // compound node — ELK 会把它渲染为子图的容器框
    { "id": "scope1",
      "layoutOptions": { "elk.algorithm": "layered", "elk.direction": "RIGHT" },
      "labels": [{ "text": "mux: sel" }],
      "children": [
        { "id": "s1_a", "width": 60, "height": 30 },
        { "id": "s1_b", "width": 60, "height": 30 }
      ],
      "edges": [
        { "id": "s1_e", "sources": ["s1_a"], "targets": ["s1_b"] }
      ],
      // scope 本身的端口（用于跨层级连线）
      "ports": [
        { "id": "scope1_in", "properties": { "port.side": "WEST" } },
        { "id": "scope1_out", "properties": { "port.side": "EAST" } }
      ]
    },
    { "id": "result", "width": 80, "height": 30 }
  ],
  // cross-hierarchy edge: scope → 外部节点
  "edges": [
    { "id": "e1", "sources": ["scope1"], "targets": ["result"],
      "sourcePort": "scope1_out", "targetPort": "result_in" }
  ]
}
```

⚠️ **Compound graph 的 cross-hierarchy edges 需要显式启用**：
```json
"layoutOptions": {
  "elk.layered.crossHierarchy": "true"
}
```

### 2.5 Port 属性

| 属性 | 说明 | 可选值 |
|------|------|--------|
| `port.side` | 端口在节点的哪一侧 | `WEST`, `EAST`, `NORTH`, `SOUTH`, `UNDEFINED` |
| `port.index` | 端口排序索引 | int (默认 0) |
| `port.borderOffset` | 端口距边框偏移 | double (默认 0) |

⚠️ **Port 不要设 `width`/`height`**：port 尺寸会导致边缘终点 y 偏移（见 §7 "已知问题"）

---

## 3. Layout Options（关键配置）

### 3.1 布局算法

| 选项 | 默认 | 说明 |
|------|------|------|
| `elk.algorithm` | — | `layered` (Sugiyama), `force`, `mrtree`, `radial`, `stress` |
| `elk.direction` | `UNDEFINED` | `RIGHT` (左→右), `DOWN` (上→下), `LEFT`, `UP` |
| `elk.edgeRouting` | `UNDEFINED` | `ORTHOGONAL` (直角), `POLYLINE`, `SPLINES`, `UNDEFINED` |

### 3.2 Port Constraints

| 值 | 说明 |
|----|------|
| `FREE` | ELK 自由选择端口位置 |
| `FIXED_SIDE` | 端口位置由 ELK 在指定侧上安排（默认） |
| `FIXED_ORDER` | 端口有序排列在指定侧 |
| `FIXED_POS` | 端口坐标由用户指定，ELK 不移动 |
| `FIXED_RATIO` | 保持端口比例 |

### 3.3 Layered 算法专属

| 选项 | 默认 | 说明 |
|------|------|------|
| `elk.layered.spacing.nodeNodeBetweenLayers` | `20` | 层间节点间距 |
| `elk.layered.spacing.nodeNode` | `20` | 同层节点间距 |
| `elk.layered.crossingMinimization.strategy` | `LAYER_SWEEP` | 交叉最小化策略 |
| `elk.layered.nodePlacement.strategy` | `BRANDES_KOEPF` | 节点放置策略 |
| `elk.layered.considerModelOrder.strategy` | `NONE` | 模型顺序保持策略 |
| `elk.layered.mergeEdges` | `false` | 合并平行边 |
| `elk.layered.crossHierarchy` | `false` | ⚠️ 必须开启才能支持 compound graph 跨层边 |
| `elk.layered.feedbackEdges` | `false` | 反馈边处理 |

### 3.4 Spacing

| 选项 | 默认 | 说明 |
|------|------|------|
| `elk.spacing.nodeNode` | `20` | 节点间距 |
| `elk.spacing.edgeNode` | `10` | 边与节点间距 |
| `elk.spacing.edgeEdge` | `10` | 边间距 |
| `elk.spacing.portPort` | `10` | 端口间距 |
| `elk.padding` | `new ElkPadding(12)` | 全局内边距 |

---

## 4. 输出 JSON 结构

```json
{
  "id": "root",
  "children": [
    {
      "id": "a",
      "x": 12, "y": 12,           // 节点绝对坐标
      "width": 80, "height": 40,   // 节点尺寸
      "labels": [{ "text": "a", "x": 0, "y": 0 }],  // label 相对于节点
      "ports": [
        {
          "id": "a_out",
          "x": 0, "y": 20,         // ⚠️ 端口相对于节点，不是绝对坐标
          "width": 4, "height": 32,
          "properties": { "port.side": "EAST" }
        }
      ]
    }
  ],
  "edges": [
    {
      "id": "e1",
      "sources": ["a"], "targets": ["b"],
      "sourcePort": "a_out", "targetPort": "b_in",
      "sections": [
        {
          "id": "e1_s0",
          "startPoint": { "x": 92, "y": 32 },   // 边起点 — 绝对坐标
          "endPoint": { "x": 112, "y": 32 },     // 边终点 — 绝对坐标
          "bendPoints": [],                       // 折线拐点 — 绝对坐标
          "incomingShape": "a",
          "outgoingShape": "b"
        }
      ]
    }
  ]
}
```

**关键约定**：
- `child.x`, `child.y` = 节点左上角绝对坐标
- `port.x`, `port.y` = 端口相对于节点左上角
- `section.startPoint`, `section.endPoint`, `bendPoints[]` = 绝对坐标
- **port 绝对坐标 = child.x + port.x, child.y + port.y**

---

## 5. 渲染三方库对比

### 5.1 elkjs（纯布局）
- 只有布局，没有渲染
- 输出 x/y/bendPoints，需要自己渲染

### 5.2 elkjs-svg（布局 → SVG）
- npm: `elkjs-svg`
- **不负责 layout**！需要传入已布局的 graph（带 x/y）
- 默认样式：rect opacity=0.8, fill=#6094CC
- 不适合我们的场景（需要自定义样式、箭头、虚线等）

### 5.3 HDElk（简化 DSL → ELK JSON）
- 简洁的文本 DSL 生成 ELK JSON
- 适合手动编写，不适合程序化生成

### 5.4 React Flow + ELK.js
- 前端交互式图表
- 有 React 依赖，不适合服务端出图

### 5.5 自己渲染（我们的方案）
- Python 生成 ELK JSON → ELK.js 布局 → Python cairosvg 渲染 SVG
- 优点：完全自定义样式、颜色、箭头、scope 框
- 是目前最符合我们需求的方案

---

## 6. 设计建议（针对我们的 dataflow 图）

### 6.1 Port 策略

```
{ "id": "a",
  "ports": [
    // 输入端口：WEST 侧，不设 width/height
    { "id": "a_in", "properties": { "port.side": "WEST" } },
    // 输出端口：EAST 侧，不设 width/height
    { "id": "a_out", "properties": { "port.side": "EAST" } }
  ]
}
```

⚠️ **不要给 port 设 width/height** — 会导致 edge endpoint y 偏移

### 6.2 Edge 用 sourcePort/targetPort 精确指定起止端口

```json
{ "id": "e1", "sources": ["a"], "targets": ["b"],
  "sourcePort": "a_out", "targetPort": "b_in" }
```

这样可以保证 ELK 把边从输出端口画到输入端口。

### 6.3 Compound graph 用于 scope 框

```json
{
  "id": "root",
  "layoutOptions": {
    "elk.layered.crossHierarchy": "true",
    "elk.edgeRouting": "ORTHOGONAL"
  },
  "children": [
    { "id": "scope_mux",
      "layoutOptions": { "elk.algorithm": "layered", "elk.direction": "RIGHT" },
      "labels": [{ "text": "mux: sel" }],
      "children": [ /* 条件分支内的信号节点 */ ],
      "edges": [ /* 条件分支内的边 */ ],
      "ports": [{ "id": "scope_mux_out", "properties": { "port.side": "EAST" } }]
    },
    { "id": "y", "width": 100, "height": 36,
      "ports": [{ "id": "y_in", "properties": { "port.side": "WEST" } }] }
  ],
  "edges": [
    { "id": "e1", "sources": ["scope_mux"], "targets": ["y"],
      "sourcePort": "scope_mux_out", "targetPort": "y_in" }
  ]
}
```

---

## 7. 已知问题 & 陷阱

### 7.1 Port width/height 导致 edge endpoint y 偏移 ⚠️⚠️⚠️

**现象**：给 port 设了 `width: 4, height: 32` 后，edge 的 `endPoint.y` 和 target 节点的 center.y 差了 6-17px

**根因**：ELK 把 port 当做矩形区域，边连到 port 区域的某个内部点上，这个点的位置受 port 尺寸影响

**解决方案**：port 不设 `width`/`height` 属性，只设 `port.side`

```json
// ❌ 错误 — 会导致 y 偏移
{ "id": "a_out", "width": 4, "height": 32,
  "properties": { "port.side": "EAST" } }

// ✅ 正确 — 无 y 偏移
{ "id": "a_out",
  "properties": { "port.side": "EAST" } }
```

### 7.2 `section.startPoint/endPoint` 不完全等于 port 绝对坐标

即使 port 不设 width/height，edge endpoint 也不一定精确等于 port 绝对坐标（可能差 0-2px 浮点舍入）。渲染时建议只调 x 到节点边缘，不做 y 调整。

### 7.3 Edge endpoint y 不完全在节点范围内

对于同一 layer 内的水平边（无 bendPoints），edge endpoint y = 节点 center.y ✅。
对于跨 layer 的边（有 bendPoints），endpoint y 可能偏差 1-6px（取决于 ELK 内部路由）。

**渲染策略**：保持 y 不变，只钳制 x 到节点边缘。水平边对齐完美，有 bendPoints 的边也保持 ORTHO。

### 7.4 Node ID 不能以数字开头

ELK JSON 解析会拒绝以数字开头的 ID。

### 7.5 Compound graph 必须显式启用 crossHierarchy

不加 `"elk.layered.crossHierarchy": "true"` 时，compound node 内的边可能随机出错。

### 7.6 JSON 输出中 port.x/port.y 的含义

ELK 输出的 `port.x` / `port.y` 是相对于 **port 自身**的偏移，不是相对 node 的。需要用 `node.x + port.x` 算绝对位置。

---

## 8. 最佳实践总结

1. **Port 不设 width/height** — 避免 edge endpoint y 偏差
2. **用 sourcePort/targetPort** 精确指定端口 — 保证边路由正确
3. **Compound graph 用 crossHierarchy** — 支持嵌套 scope 框 + 跨层边
4. **渲染时只调 x，保持 y** — x 对齐节点边缘，y 保持 ELK 输出不变（保证 ORTHO）
5. **Python 端只产出 JSON** — 不做坐标计算，坐标 100% 来自 ELK.js
6. **每个 edge 只连一个 sourcePort/targetPort** — 如果 signals 有多个 fan-in，ELK 会正确处理

---

## 9. 参考资料

- ELK.js GitHub: https://github.com/kieler/elkjs
- ELK Reference (布局选项): https://eclipse.dev/elk/reference/options.html
- ELK Layered Algorithm: https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html
- Edge Routing 选项: https://eclipse.dev/elk/reference/options/org-eclipse-elk-edgeRouting.html
- React Flow + ELK: https://reactflow.dev/examples/layout/elkjs
- LiveCodes ELK 示例: https://livecodes.io/docs/languages/diagrams
