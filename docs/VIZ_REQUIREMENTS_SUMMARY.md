# sv_query 可视化设计文档 V12 — ELK.js 架构

> 状态: 当前实现 (2026-08-04)
> 布局引擎: ELK.js 0.12+ (Sugiyama layered)
> 渲染后端: Python SVG (cairosvg)
> 输出格式: SVG / PNG / DOT (fallback)
>
> 本文档覆盖完整技术细节: 数据模型、ELK JSON 结构、端口定义、坐标计算、边路由规则、scope 框去重算法、渲染 Z-order。

---

## 目录

1. [架构总览](#1-架构总览)
2. [数据模型 (VizData)](#2-数据模型-vizdata)
3. [ELK JSON 构建 (elk_bridge.py)](#3-elk-json-构建-elk_bridgepy)
4. [ELK 布局计算 (elk_layout.js)](#4-elk-布局计算-elk_layoutjs)
5. [SVG 渲染 (elk_svg_renderer.py)](#5-svg-渲染-elk_svg_rendererpy)
6. [Scope 框构建与去重](#6-scope-框构建与去重)
7. [Stage 分层](#7-stage-分层)
8. [边样式规范](#8-边样式规范)
9. [等价连线](#9-等价连线)
10. [颜色方案](#10-颜色方案)
11. [节点渲染细节](#11-节点渲染细节)
12. [已知问题 & 陷阱](#12-已知问题--陷阱)

---

## 1. 架构总览

```
SignalGraph (networkx)
        │
        ▼
viz_data_builder.py          ← 过滤、分类、富化
        │
        ▼
VizData (VizNode[] + VizEdge[] + equiv_edges[])
        │
        ▼
elk_bridge.py               ← 3 步:
  1. viz_to_elk()           ← VizData → ELK JSON (含 scope_map/stage_map 元数据)
  2. run_elk_layout()       ← Node.js elk.js 布局计算
  3. get_layout()           ← 一站式入口
        │
        ▼
ELK Layout JSON (带 x/y/bendPoints 坐标)
        │
        ▼
elk_svg_renderer.py         ← render_svg(layout, config) → SVG 字符串
        │
        ▼
cairosvg (可选)             ← SVG → PNG
```

### 核心文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `elk_bridge.py` | ~440 | VizData→ELK JSON + scope_map/stage_map + 调 ELK.js |
| `elk_layout.js` | ~60 | Node.js 端: `const elk = require('elkjs'); elk.layout(graph)` |
| `elk_svg_renderer.py` | ~410 | ELK 坐标 → SVG rect/path/text elements |
| `viz_engine.py` | ~800 | 入口 render_dataflow() + DOT fallback (旧) |

### 已归档文件 (`_archived_dot/`)

`viz_dot_renderer.py`, `viz_signal_renderer.py`, `viz_compute_renderer.py`,
`viz_control_renderer.py`, `viz_datapath_renderer.py`, `viz_timed_compute_renderer.py`,
`viz_dataflow_scope_renderer.py`, `viz_structure_renderer.py`, `viz_new.py`,
`viz_style.py`, `viz_control_new.py`, `viz_signal_v8.py` — 全部已归档，不再维护。

---

## 2. 数据模型 (VizData)

### 2.1 VizNode 关键字段

```python
@dataclass
class VizNode:
    id: str              # 唯一标识, 如 "top.a", "top.sum_ab"
    label: str           # 短名, 取 id 的最后一段
    module: str          # 所属模块, 如 "top"
    kind: str            # SIGNAL | REG | PORT_IN | PORT_OUT | CONST
    width: tuple | None  # (msb, lsb), 如 (7, 0)
    is_input: bool       # 是否为模块输入
    is_output: bool      # 是否为模块输出
    is_function: bool    # 是否为 function/task 内部信号
    stage_id: int        # pipeline stage id (BSF 深度)
    cycle: int           # 所在 cycle
    risk_level: str      # LOW | MEDIUM | HIGH | CRITICAL
```

### 2.2 VizEdge 关键字段

```python
@dataclass
class VizEdge:
    id: str                       # "src -> dst"
    src: str                      # 源信号完整 ID
    dst: str                      # 目标信号完整 ID
    kind: str                     # DRIVER | CLOCK | RESET | BIT_SELECT | CONNECTION
    expression: str | None        # 驱动表达式, 如 "a + b"
    source_op: str | None         # 操作符, 如 "Add", "GreaterThan", "LogicalShiftRight"
    source_bit_start: int | None  # 源信号位宽起始
    source_bit_end: int | None    # 源信号位宽结束
    source_casts: list[str]       # cast 链, 如 ["$signed"]
    condition_chain: list[str]    # 条件累积链, 如 ["sel", "!(sel)"]
    assign_type: str              # continuous | blocking | nonblocking
    is_conditional: bool          # 是否为条件驱动 (if/case/ternary)
```

### 2.3 condition_chain 语义

`condition_chain` 是 `TraceEdge` → `VizEdge` 透传的 `list[str]` 字段:

```python
# 三目: assign y = sel ? a : b;
VizEdge(a→y, condition_chain=["sel"])
VizEdge(b→y, condition_chain=["!sel"])

# if/else: if (en) y <= a; else y <= b;
VizEdge(a→y, condition_chain=["en"])
VizEdge(b→y, condition_chain=["!en"])

# 嵌套: case(d) { d0: if(e) y<=a; }
VizEdge(a→y, condition_chain=["d == 2'd0", "e"])
```

**互斥分组规则**: 按 `(dst, chain[:-1])` 分组，≥2 条边 → scope。

---

## 3. ELK JSON 构建 (elk_bridge.py)

### 3.1 入口函数

```python
def get_layout(viz: VizData) -> dict:
    """
    VizData → ELK 布局结果 (一站式)
    
    内部调用:
      1. viz_to_elk(viz) → ELK JSON graph
      2. run_elk_layout(graph) → ELK 布局 JSON (带坐标)
      3. 合并 graph._meta 到 result._meta
    """
```

### 3.2 节点注册细节

#### Signal 节点

```python
def _reg_node(node_id: str, label: str, w: int, h: int,
              kind: str = 'signal', **meta) -> str:
    """
    注册 ELK 节点, 返回 ELK-safe ID
    
    每个节点有两个 port:
      - {eid}_in:  port.side=WEST    (输入)
      - {eid}_out: port.side=EAST    (输出)
    
    ID 安全规则 (_elk_id):
      - '.' → '_dot_'       (ELK 不识别点号)
      - '$', "'" → '_'      (替换特殊字符)
      - 首字符若为数字 → 前缀 'n_'
      - 只保留 [a-zA-Z0-9_-]
    """
```

生成的 ELK JSON 节点结构:

```json
{
    "id": "top_sum_ab",
    "width": 100,
    "height": 36,
    "labels": [
        {"text": "sum_ab", "fontSize": 10, "fontName": "Courier"}
    ],
    "ports": [
        {"id": "top_sum_ab_in",  "properties": {"port.side": "WEST"}},
        {"id": "top_sum_ab_out", "properties": {"port.side": "EAST"}}
    ],
    "_meta": {"kind": "SIGNAL"}
}
```

#### OP 节点

当 VizEdge 有 `source_op` 时, 自动分解为 `src → OP → dst`:

```json
{
    "id": "op_Add_sum_ab",
    "width": 24,
    "height": 24,
    "labels": [
        {"text": "+", "fontSize": 9, "fontName": "Helvetica-Bold"}
    ],
    "ports": [
        {"id": "op_Add_sum_ab_in1", "properties": {"port.side": "WEST"}},
        {"id": "op_Add_sum_ab_in2", "properties": {"port.side": "WEST"}},
        {"id": "op_Add_sum_ab_out",  "properties": {"port.side": "EAST"}}
    ],
    "_meta": {"kind": "op", "op_kind": "Add"}
}
```

**OP 节点命名规则**: `op_{op_kind}_{dst_short}`, 如 `op_Add_sum_ab`

#### OP 符号映射 (`_OP_SYM`)

```python
{
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": "≥",
    "Equality": "=", "Inequality": "≠",
    "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
    "LogicalAnd": "&&", "LogicalOr": "||",
    "Ternary": "?:", "Mux": "MUX",
}
```

### 3.3 边生成细节

#### 有 OP 的边 (分解为两段)

```python
# 输入: VizEdge(src="a", dst="sum_ab", source_op="Add")
# 输出: 2 条 ELK edge:

# Edge 1: src → OP
{
    "id": "e1",
    "sources": ["top_a"],
    "targets": ["op_Add_sum_ab"],
    "sourcePort": "top_a_out",
    "targetPort": "op_Add_sum_ab_in1",
    "_meta": {"kind": "signal"}
}

# Edge 2: OP → dst
{
    "id": "e2",
    "sources": ["op_Add_sum_ab"],
    "targets": ["top_sum_ab"],
    "sourcePort": "op_Add_sum_ab_out",
    "targetPort": "top_sum_ab_in",
    "_meta": {"kind": "signal"}
}
```

#### 无 OP 的直连边

```python
# 输入: VizEdge(src="a", dst="y")
# 输出: 1 条 ELK edge:
{
    "id": "e1",
    "sources": ["top_a"],
    "targets": ["top_y"],
    "sourcePort": "top_a_out",
    "targetPort": "top_y_in",
    "_meta": {"kind": "signal"}
}
```

#### 等价连线

```python
# 跨 scope 的同名信号
{
    "id": "e100",
    "sources": ["top_sum_ab"],
    "targets": ["top_sum_ab_scope_y"],
    "sourcePort": "top_sum_ab_out",
    "targetPort": "top_sum_ab_scope_y_in",
    "_meta": {"kind": "equiv", "label": "sum_ab"}
}
```

### 3.4 边类型推断 (`_edge_kind`)

```python
def _edge_kind(e) -> str:
    """从 VizEdge 推断 ELK 边类型"""
    ek = getattr(e, 'kind', '')          # CLOCK, RESET, DRIVER...
    if ek:
        return ek.lower()
    if getattr(e, 'is_conditional', False):
        return 'cond'
    return 'signal'
```

### 3.5 顶层 ELK JSON 结构

```json
{
    "id": "root",
    "layoutOptions": {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.edgeRouting": "ORTHOGONAL",
        "elk.layered.spacing.nodeNodeBetweenLayers": "80",
        "elk.layered.spacing.nodeNode": "30",
        "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
        "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
        "elk.layered.mergeEdges": "false",
        "elk.padding": "[top=40,left=40,bottom=40,right=40]"
    },
    "children": [
        // signal 节点 + OP 节点
    ],
    "edges": [
        // signal 边 + 等价边
    ],
    "_meta": {
        "title": "",
        "scope_map": { /* scope 框元数据 */ },
        "stage_map": { /* stage 分层元数据 */ }
    }
}
```

---

## 4. ELK 布局计算 (elk_layout.js)

### 4.1 Node.js 脚本

```javascript
const elk = require('elkjs');

// 从 stdin 读取 JSON
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
    const graph = JSON.parse(input);
    const elk = new elk.Elk();
    elk.layout(graph)
        .then(result => {
            process.stdout.write(JSON.stringify(result));
        })
        .catch(err => {
            process.stderr.write(err.message);
            process.exit(1);
        });
});
```

### 4.2 布局输出格式

ELK 输出的关键坐标字段:

```json
{
    "id": "root",
    "children": [
        {
            "id": "top_a",
            "x": 52,  "y": 60,           // 节点左上角绝对坐标
            "width": 100, "height": 36,
            "ports": [
                {
                    "id": "top_a_in",
                    "x": 0, "y": 18,      // ⚠️ 相对于节点左上角!
                    "width": 4, "height": 32
                }
            ]
        }
    ],
    "edges": [
        {
            "id": "e1",
            "sources": ["top_a"], "targets": ["top_b"],
            "sourcePort": "top_a_out", "targetPort": "top_b_in",
            "sections": [
                {
                    "startPoint": {"x": 152, "y": 78},   // 绝对坐标
                    "endPoint":   {"x": 192, "y": 78},   // 绝对坐标
                    "bendPoints": []                      // 折线拐点, 绝对坐标
                }
            ]
        }
    ]
}
```

**⚠️ 关键坐标约定:**
- `child.x`, `child.y` = 节点**绝对坐标**
- `port.x`, `port.y` = 端口**相对于节点**的偏移
- `section.startPoint/endPoint/bendPoints` = **绝对坐标**
- port 绝对坐标 = `child.x + port.x`, `child.y + port.y`

**⚠️ Port 不设 width/height**: 设了会导致 edge endpoint y 偏移 6-17px。只设 `port.side` 即可。

---

## 5. SVG 渲染 (elk_svg_renderer.py)

### 5.1 主渲染函数

```python
def render_svg(layout: dict, config: dict | None = None) -> str:
    """
    ELK 布局结果 → 格式化 SVG 字符串
    
    config:
        title: str              # 图标题
        scope_map: dict         # {scope_id: {depth, label, member_ids}}
        stage_map: dict         # {node_elk_id: stage_number}
    
    渲染 Z-order (从底到顶):
        1. Background (全白)
        2. Title (Helvetica Bold 14pt #2e7d32)
        3. Scope 框 (rect + text)
        4. Stage cluster (rect + text)
        5. Edges (path + arrow markers)
        6. Nodes (rect + text)
    
    SVG 尺寸计算:
        svg_w = max(400, max_x + padding*2)  # padding=50
        svg_h = max(200, max_y + padding*2)
    """
```

### 5.2 Defs: 4 种箭头 marker

```xml
<defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#333333"/>
    </marker>
    <marker id="arrow_cond" ... fill="#2563eb"/>
    <marker id="arrow_clk" ... fill="#c62828"/>
    <marker id="arrow_equiv" ... fill="#9e9e9e"/>
</defs>
```

### 5.3 Edge 渲染 (`_draw_edge`)

```python
def _draw_edge(svg, edge, child_map):
    """
    遍历 edge.sections[], 每个 section:
        startPoint → bendPoints[] → endPoint
    转换为 SVG path: M x y L x y L x y ...
    
    边样式选择:
        kind='driver'  → stroke=#333333 marker-end=arrow
        kind='signal'  → stroke=#9e9e9e (无箭头, 灰)
        kind='cond'    → stroke=#2563eb stroke-dasharray=5,3
        kind='equiv'   → stroke=#9e9e9e stroke-dasharray=2,4
        kind='clk/rst' → stroke=#c62828 marker-end=arrow_clk
    
    Edge label (等价边): 标注信号名, 在 endPoint 左上方
        font: Courier 8pt, text-anchor=end
    """
```

**路径生成伪代码:**

```python
def _draw_path(points: list[dict]):
    if len(points) < 2: return
    d = f'M {points[0]["x"]:.1f} {points[0]["y"]:.1f}'
    for pt in points[1:]:
        d += f' L {pt["x"]:.1f} {pt["y"]:.1f}'
    # SVG <path d="..." fill="none" stroke="..." .../>
```

### 5.4 Node 渲染 (`_draw_node`)

```python
def _draw_node(svg, node):
    """
    kind='op':
        - rect: fill=#f0f0f0 stroke=#666666 stroke-width=1.2 rx=2
        - text: Helvetica-Bold 9pt #333333, 居中
    
    kind='signal' (default):
        - rect: fill=#ffffff stroke=#333333 stroke-width=1 rx=3
        - text: Courier 9pt #2e7d32, 居中
    
    text 位置: (x + w/2, y + h/2 + 4)  # 垂直居中偏下 4px
    """
```

### 5.5 Scope 框渲染 (`_draw_scopes`)

```python
def _draw_scopes(svg, layout, scope_map):
    """
    对每个 scope:
    1. 收集 member_ids 对应的 child 节点的坐标
    2. 计算 bounding box:
         min_x = min(c.x for c in members) - margin     # margin=12
         min_y = min(c.y for c in members) - margin
         max_x = max(c.x + c.w for c in members) + margin
         max_y = max(c.y + c.h for c in members) + margin
    3. 渲染:
         - 背景 rect: fill=bg_color rx=6
         - 边框 rect: fill=none stroke=border_color
           - depth=0 (module): 实线
           - depth>0 (condition): stroke-dasharray=5,3
         - 标签 text: Helvetica, 位置 (min_x+8, min_y-6)
           - depth=0: bold 11pt
           - depth>0: normal 9pt
    """
```

**Scope 颜色分层 (SCOPE_COLORS):**

```python
[
    ('#444444', '#fafafa', 2.0),   # depth=0: module, 深灰实线
    ('#1b5e20', '#f1f8e9', 1.5),   # depth=1: 一级条件, 绿虚线
    ('#c62828', '#ffebee', 1.2),   # depth=2: 嵌套, 红虚线
    ('#1565c0', '#e3f2fd', 1.0),   # depth=3+: 蓝虚线
]
```

### 5.6 Stage Cluster 渲染 (`_draw_stages`)

```python
def _draw_stages(svg, layout, stage_map):
    """
    对每个 stage number:
    1. 收集所有 stage_map 中值为该 number 的节点
    2. bounding box (margin=16, y-top 额外-16 给 label 留空间)
    3. 渲染:
         - 背景: fill=#f8faff rx=4
         - 边框: stroke=#2563eb stroke-width=1.5 stroke-dasharray=8,4 rx=4
         - 标签: "Stage N", Helvetica-Bold 10pt #2563eb
    """
```

---

## 6. Scope 框构建与去重

### 6.1 `_build_scope_map` 完整算法

```python
def _build_scope_map(viz: VizData) -> dict:
    """
    输入: VizData (含 condition_chain 的边)
    输出: {scope_id: {depth, label, member_ids, dst}}
    
    算法分两阶段:
    
    Phase 1 — 收集原始成员:
        1. 按 dst 分组所有有条件链的边:
           cond_by_dst[dst_id] = [边1, 边2, ...]
        2. 只保留有 ≥2 条边的 dst (至少互斥才能形成 scope)
        3. 按 chain 长度区分层级:
           - chain 长度 ≤1: 一级 scope (如 scope_y sel=sel)
           - chain 长度 ≥2: 嵌套 scope (如 scope_z sel=mode nested)
        4. 每个 scope 的原始成员 = {
              所有条件边的 src + dst + OP 节点
           }
    
    Phase 2 — 去重:
        1. 按 depth 从深到浅排序 (−depth, dst_name)
           嵌套 scope (depth=2) 优先认领
           同 depth 按 dst 名字排序 (确定性)
        2. 后续 scope 的成员 = 原始成员 − 已被认领的
        3. dst 节点总是强制保留 (scope 的核心标识)
        4. 构建最终 scope_map
    """
```

### 6.2 去重伪代码

```python
# Phase 1: 收集所有 scope
raw_scopes = []
for dst, edges in cond_by_dst.items():
    if len(edges) < 2: continue
    # 按 chain 长度分组
    simple = [e for e in edges if len(e.chain) <= 1]
    nested = [e for e in edges if len(e.chain) >= 2]
    for group, depth in [(simple, 1), (nested, 2)]:
        if group:
            members = {e.src, e.dst, op_node(e)}  # 对每条边
            raw_scopes.append({scope_id, depth, members, dst})

# Phase 2: 去重
claimed = set()
for s in sorted(raw_scopes, key=lambda s: (-s.depth, s.dst)):
    deduped = s.members - claimed
    if s.dst not in deduped:
        deduped.add(s.dst)        # dst 强制保留
    scope_map[s.scope_id] = {depth: s.depth, members: deduped, ...}
    claimed.update(deduped)
```

### 6.3 Module scope

```python
# 额外生成: depth=0 的 module scope
# 成员 = 所有 PORT_IN + PORT_OUT 节点
port_ids = {n.id for n in viz.nodes if n.kind in ('PORT_IN', 'PORT_OUT')}
scope_map['scope_module'] = {
    'depth': 0, 'label': 'module', 'member_ids': list(port_ids)
}
```

---

## 7. Stage 分层

### 7.1 `_build_stage_map`

```python
def _build_stage_map(viz: VizData) -> dict:
    """
    调用 viz_engine.infer_stages_bfs(viz)
    
    BFS: 从 PORT_IN depth=0 开始,
    每过一个 DRIVER 边 depth+1
    回退到 PORT_IN 的步数取最小.
    
    返回: {node_elk_id: stage_number}
    """
```

### 7.2 Stage 划分模式 (spec_datapath.md)

| 模式 | 算法 | 说明 |
|------|------|------|
| `auto` | 有 REG → BFS by reg chain; 无 REG → depth2 | 自动选择 |
| `reg` | 只在 always_ff 的 clock edge 处分 stage | 需要 reg chain |
| `depth2` | inputs → OP 层 → outputs | 纯组合逻辑 2 级 |
| `depth3` | inputs → OP1 → OP2 → outputs | 纯组合逻辑 3 级 |

---

## 8. 边样式规范

### 8.1 类型映射表

| VizEdge.kind | ELK meta.kind | SVG 颜色 | SVG 样式 | 箭头 |
|-------------|---------------|----------|---------|------|
| DRIVER | `driver` | `#333333` | 实线 | ✓ arrow |
| CLOCK | `clk` | `#c62828` | 实线 | ✓ arrow_clk |
| RESET | `rst` | `#c62828` | 实线 | ✓ arrow_clk |
| CONNECTION | `signal` | `#9e9e9e` | 实线 | ✗ |
| (有 condition_chain) | `cond` | `#2563eb` | 虚线 5,3 | ✗ |
| (equiv_edges) | `equiv` | `#9e9e9e` | 虚线 2,4 | ✗ |

### 8.2 条件边标签

条件边的 label 由 `condition_chain` 生成:

```python
# chain=["sel"]        → 标签 "sel"
# chain=["!(sel)"]     → 标签 "!(sel)"
# chain=["d","e"]      → 标签 "d && e" (嵌套)
# chain=["default"]    → 标签 "default"
```

---

## 9. 等价连线

### 9.1 触发条件

同名信号跨越 cluster 边界时生成等价连线:
- scope↔stage (信号在 stage 层和 scope 层各有一份)
- scope↔scope (同一信号出现在多个 scope)
- port↔scope (port 和 scope 内信号之间)

### 9.2 渲染

```python
# VizData.equiv_edges: list[EquivEdge]
# EquivEdge = {src, dst}

for eq in viz.equiv_edges:
    if src in seen_ids and dst in seen_ids and src != dst:
        edges.append({
            ...,
            "_meta": {
                "kind": "equiv",
                "label": short_name  # 标注信号名
            }
        })
```

SVG 渲染:
- 路径: `M ... L ...` (与普通边相同)
- 样式: `stroke="#9e9e9e" stroke-dasharray="2,4" stroke-width="1.5"`
- 标签: Courier 8pt, `text-anchor="end"`, 在 endPoint 左上方

---

## 10. 颜色方案

### 10.1 完整颜色表

```python
C = {
    # 背景
    'bg': '#ffffff',

    # 边
    'signal': '#333333',     # 信号边 (driver)
    'cond': '#2563eb',       # 条件边 (蓝虚线)
    'equiv': '#9e9e9e',      # 等价边 (灰)
    'clk': '#c62828',        # 时钟边 (红)
    'rst': '#c62828',        # 复位边 (红)
    'const': '#1565c0',      # 常量边 (深蓝)

    # 节点
    'node_fill': '#ffffff',
    'node_stroke': '#333333',
    'op_fill': '#f0f0f0',
    'op_stroke': '#666666',

    # Scope
    'scope_fill': 'none',
    'scope_stroke': '#444444',
    'scope_label': '#555555',

    # Stage
    'stage_fill': '#f8faff',
    'stage_stroke': '#2563eb',

    # Text
    'text': '#2e7d32',       # 信号名 (绿色, Courier)
    'op_text': '#333333',    # OP 符号 (黑色, Helvetica-Bold)

    # 虚线
    'cond_dasharray': '5,3',
    'equiv_dasharray': '2,4',
}
```

### 10.2 五色克制原则

来自参考图共识 (viz_v2_design.md):
- **黑 + 白 + 蓝 + 红 + 绿** — 不超过 5 种主色
- 不做过多颜色装饰
- 虚线仅用于 cluster 边框和条件边

---

## 11. 节点渲染细节

### 11.1 节点尺寸

```python
NODE_SIZE = {'width': 100, 'height': 36}   # Signal 节点
OP_SIZE   = {'width': 24,  'height': 24}   # OP 节点 (小矩形)
```

### 11.2 节点类型 → 形状

| kind | SVG rect 样式 | 字体 |
|------|-------------|------|
| `signal` | 白底黑框, stroke-width=1, rx=3 | Courier 9pt #2e7d32 |
| `op` | 灰底灰框, stroke-width=1.2, rx=2 | Helvetica-Bold 9pt #333333 |
| `PORT_IN` | (暂同 signal, 未来八角形) | — |
| `REG` | (暂同 signal, 未来粗边框) | — |

### 11.3 文本居中算法

```python
# 所有文本水平垂直居中
text_x = x + w / 2
text_y = y + h / 2 + 4  # +4 调整 baseline
# text-anchor="middle"
```

---

## 12. 已知问题 & 陷阱

### 12.1 Port width/height 导致 Y 偏移 ⚠️

**现象**: port 设了 `width/height` 后, edge endpoint.y 和节点 center.y 差 6-17px

**根因**: ELK 把 port 当矩形区域, 边连到矩形内部某点

**解决**: port **不设** `width`/`height`, 只设 `port.side`

```json
// ✅ 正确
{"id": "a_out", "properties": {"port.side": "EAST"}}

// ❌ 错误 — 导致 y 偏移
{"id": "a_out", "width": 4, "height": 32, "properties": {"port.side": "EAST"}}
```

### 12.2 Node ID 不能以数字开头

ELK JSON 解析拒绝数字开头的 ID。用 `_elk_id()` 自动加 `n_` 前缀。

### 12.3 section endpoint 不完全等于 port 坐标

即使不设 width/height, edge endpoint 也可能和 port 绝对坐标差 0-2px (浮点舍入)。渲染时不调整 y, 只钳制 x 到节点边缘。

### 12.4 Scope 框重叠

**已修复** (2026-08-04): `_build_scope_map` Phase 2 去重逻辑 — 嵌套 scope 优先认领成员, 同 depth 按 dst 名排序。

### 12.5 Elaboration 在 8GB MBA 上较慢

pyslang elaboration 在 8GB MacBook Air 上需要 30-60s。workaround: 4GB 强分配回收 (`python3 -c "a=bytearray(4*1024**3);del a"`)。

---

## 附录A: 参考文档索引

| 文档 | 内容 |
|------|------|
| `docs/VIZ_DESIGN_SPEC.md` | V6.7 VizData 数据模型规范 |
| `docs/DATAFLOW_VIZ_SPEC.md` | V10 ELK.js 数据流图渲染规范 |
| `docs/VIZ_REVIEW.md` | 代码 review & MUX 增强方案 |
| `docs/VIZ_GOLDEN_PLAN.md` | Golden 参考 + 4 PR 规划 |
| `docs/VIZ_UNDERSTANDING_CRITERIA.md` | 可视化理解度评估标准 |
| `docs/VIZ_COMMANDS.md` | 6 个子命令完整 CLI 参考 |
| `docs/ELK_JS_GUIDE.md` | ELK.js 深入使用手册 |
| `docs/spec_datapath.md` | 定点数计算架构图 Spec |
| `docs/viz_v2_design.md` | 6 个信息维度 + 统一视觉 DNA |
| `docs/condition_branch_design.md` | condition_chain 数据层设计 |
| `docs/select_group_design.md` | select_group 数据结构 |
