# Dataflow 可视化渲染流水线

> 最后更新: 2026-08-09
> 关联文件: `src/trace/core/graph/viz/{viz_engine, elk_bridge, viz_data_builder, viz_data_models}.py` + `src/trace/core/graph/viz/elk_layout.js`

本文档解释 sv_query 的 dataflow 可视化渲染完整流水线, 回答 "ELK 和 SVG 是什么关系, ELK 怎么用" 的问题。

---

## 1. 核心结论: ELK ≠ SVG, 是流水线的两个阶段

| 技术 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **ELK.js** | **布局引擎** (算位置) | JSON (节点 + 边的拓扑) | JSON (带 x/y/w/h 的位置) |
| **SVG** | **渲染格式** (画图) | 坐标 + 样式 | XML 矢量字符串 |
| **rsvg-convert** | **光栅化** (SVG→PNG) | SVG 文件 | PNG 文件 |

类比: **ELK 是建筑师** (画蓝图算坐标), **SVG 是施工队** (按坐标砌墙), **PNG 是照片**。

- 改布局算法 → 改 ELK options (不动 SVG)
- 改颜色 / 样式 → 改 `_render_svg_direct` (不动 ELK)
- 两者正交, 各管一段

---

## 2. 三层流水线 (实际跑的流程)

```
┌────────────────────────────────────────────────────────┐
│ ① 数据层 (Python)
│    viz_data_models.py: VizData 节点/边/元数据 dataclass
│    viz_data_builder.py: build_viz_data() 从 graph 构建 VizData
│    关键字段:
│      - viz.nodes[i].id / .port_side (left/right/none)
│      - viz.edges[i].src / .dst / .condition_chain / .source_op
│      - viz.meta.datapath.expr_trees: dict[str, Tree]  (来自 driver_extractor)
└────────────────────────────────────────────────────────┘
                          ↓ 序列化
┌────────────────────────────────────────────────────────┐
│ ② 布局层 (Python elk_bridge.py → Node.js elk_layout.js → ELK.js 0.12+)
│    elk_bridge.py:
│      - viz_to_elk(viz)            → condition 分支图
│      - expr_trees_to_elk(trees)   → 表达式树图
│      - full_graph_to_elk(viz)     → 全图 (含 instance box)
│    elk_layout.js (29 行):
│      - stdin 读 ELK JSON, 调 elk.layout(), stdout 输出
│      - 桥接 Node.js (npm: elkjs) 与 Python (subprocess)
│    ELK.js 内部: Sugiyama layered 算法
│      1. 分层 (topological sort)
│      2. 顺序 (crossing minimization)
│      3. 坐标分配 (x/y assignment)
│      4. 边的折线 (orthogonal edge routing)
└────────────────────────────────────────────────────────┘
                          ↓ 布局后 JSON (含 x/y/w/h + bendPoints)
┌────────────────────────────────────────────────────────┐
│ ③ 渲染层 (Python _render_svg_direct in viz_engine.py)
│    - walk_n() 递归遍历 layout, 累加 compound offset → 全局坐标
│    - walk_e() 同理累加边 section 坐标
│    - 拼 SVG: <rect> (node), <path> (edge), <text> (label), <marker> (箭头)
│    - minidom.parseString().toprettyxml(indent='  ') 输出
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│ ④ 光栅化 (外部命令, 不在 Python 里)
│    rsvg-convert -w 1400 input.svg -o output.png
│    飞书 message channel 发送 PNG
└────────────────────────────────────────────────────────┘
```

---

## 3. ELK 关键概念速查

### 3.1 节点 (Node)

```json
{
  "id": "sig_a_with_ternary_dot_y_sel_b",
  "width": 40,
  "height": 20,
  "labels": [{"text": "a", "fontSize": 8}],
  "layoutOptions": {"elk.padding": "[top=8,left=4]"}
}
```

### 3.2 Compound 容器 (可嵌套)

```json
{
  "id": "case_with_ternary_dot_y",
  "labels": [{"text": "case (sel_a, sel_b)"}],
  "children": [branch_1, branch_2, branch_3],
  "edges": [内部边],
  "layoutOptions": {"elk.direction": "DOWN"}
}
```

我们 case 框的紫色虚线框 = compound 节点的背景 `<rect>` (在 `_render_svg_direct` 中由 `compounds` 列表生成)。

### 3.3 边 (Edge)

```json
{
  "id": "e1",
  "sources": ["port_a"],
  "targets": ["sig_a_..."],
  "sections": [{
    "startPoint": {"x": 100, "y": 50},
    "endPoint":   {"x": 200, "y": 50},
    "bendPoints": [{"x": 150, "y": 50}]
  }]
}
```

- `sources`/`targets` 是**逻辑端点** (节点 ID)
- `sections` 是**实际画的折线** (含 bend points)

### 3.4 layoutOptions (算法控制)

| Option | 含义 | 例子 |
|--------|------|------|
| `elk.algorithm` | 算法 | `layered` (Sugiyama) |
| `elk.direction` | 流向 | `RIGHT` / `DOWN` / `UP` / `LEFT` |
| `elk.spacing.nodeNode` | 节点间距 | `12` |
| `elk.padding` | 内边距 | `[top=14,left=0,right=10,bottom=8]` |
| `elk.layered.layering.layerConstraint` | 强制层级 | `FIRST` (放第一层) |

---

## 4. 4 条渲染路径 (viz_engine.py:render_dataflow)

`render_dataflow()` 根据 viz.edges 的特性分派到不同 ELK 构造函数:

```python
# viz_engine.py:228-243 (commit c047aba 之后)
has_uncond_op  = any(边有 source_op 且无 condition 且非 BIT_SELECT)
has_call_edge  = any(边有 source_op == 'Call')
has_cond_edges = any(边有 condition_chain 或 condition)

if has_uncond_op or has_call_edge:
    # → expr_trees_to_elk
elif has_cond_edges:
    # → get_layout (= viz_to_elk)
elif expr_trees:
    # → expr_trees_to_elk
else:
    # → get_layout (fallback)
```

### 4.1 路径总览

| 路径 | 触发条件 | 函数 | 适合的 case |
|------|----------|------|-------------|
| **表达式树** | 无条件数据运算链 | `expr_trees_to_elk` | case1,2,3,4,5,6,13,24,28 |
| **cond 分支框** | 只有 case/if 条件边 | `get_layout` (→ `viz_to_elk`) | case7,8,9,15,16,17 |
| **全图 (mode='all')** | 显式 mode='all' | `full_graph_to_elk` | case26 (层级 module) |
| **fallback** | 兜底 | `get_layout` | — |

### 4.2 为什么不合并一条路径?

- **case/if 分支** 需要 case 框 (compound) + branch 子框 + cond 信号连线 → **必须用 viz_to_elk** 生成 compound 结构
- **数据运算链** (scale/valid 等) 需要表达式树嵌套 → **必须用 expr_trees_to_elk** 把 op/signal 嵌成树
- **混合** (case21 case+function) 函数调用边在 viz_to_elk 会崩 (`Referenced shape does not exist`) → **强制 expr_trees_to_elk**
- 所以**路由判断必须精准**, 不能简单 `if expr_trees:`

### 4.3 函数调用边特殊处理

`source_op == 'Call'` 强制走 expr_trees, 因为:
- expr_trees 把 `op: Call` 作为树的子节点, 自然表达函数调用关系
- viz_to_elk 只处理 `op: add/mul/and/or/...`, 不认识 Call

---

## 5. 关键代码位置

| 文件 | 行号 | 内容 |
|------|------|------|
| `viz_engine.py` | 21-148 | `_render_svg_direct()` 渲染器 (拼 SVG) |
| `viz_engine.py` | 197-269 | `render_dataflow()` 路由 + 4 路径 |
| `viz_engine.py` | 232 | `expr_trees = dict(raw_expr_trees)` (无 dedup) |
| `elk_bridge.py` | 386-388 | case_children 列表 (循环内重置!) |
| `elk_bridge.py` | 401-405 | sel_sigs 收集 (整个 chain) |
| `elk_bridge.py` | 509-570 | `full_graph_to_elk()` (mode='all') |
| `elk_layout.js` | 全 29 行 | Node.js ↔ ELK.js 桥接 |

---

## 6. 调试技巧

### 6.1 dump 中间 ELK JSON

```python
import json
from trace.run_cli import main

# 跑 viz 命令时, 在 viz_engine.py:render_dataflow() 出口加:
print(json.dumps(elk, indent=2))  # ELK 输入 JSON
# 或
print(json.dumps(layout, indent=2))  # ELK 输出 (带 x/y)
```

### 6.2 手动调 ELK.js

```bash
cd ~/my_dv_proj/sv_query
echo '{"id":"root","layoutOptions":{"elk.direction":"RIGHT"},"children":[{"id":"a","width":80,"height":40,"labels":[{"text":"a"}]},{"id":"b","width":80,"height":40,"labels":[{"text":"b"}]}],"edges":[{"id":"e","sources":["a"],"targets":["b"]}]}' | \
node src/trace/core/graph/viz/elk_layout.js | jq .
```

### 6.3 节点 kind 与 SVG 样式对应

`_render_svg_direct` 中 `kind` 决定 fill/stroke/rx/fontSize:

| kind | fill | stroke | 用途 |
|------|------|--------|------|
| `port_in` | `#e8e8e8` | `#999` | 左侧输入端口 |
| `port_out` | `#e8e8e8` | `#666` | 右侧输出端口 |
| `op` | `#fff3e0` | `#e65100` | 运算符 (add/mul/...) |
| `signal` | `#fff9c4` | `#f9a825` | 信号节点 |
| `const` | `#e0f2f1` | `#00695c` | 常量字面量 |
| `condition_anchor` | (skip) | — | 1×1 选择器锚点 |

### 6.4 边的 kind 与线型

| ekind | stroke | dash |
|-------|--------|------|
| `condition_select` | `#989898` | `6,3` (虚线) |
| 其他 (默认) | `#555555` | 实线 |

---

## 7. 常见问题

### Q1: 为什么不用 elkjs-svg?

elkjs-svg 是 ELK 官方提供的 SVG 渲染包, 但它**不支持我们的中文标签** / 自定义 kind 样式 / compound 背景虚线框。`_render_svg_direct` 是手写的 SVG 渲染器, 完全控制样式。

### Q2: 为什么不直接用 Graphviz?

- Graphviz 布局算法固定, 不支持 compound graph 嵌套布局
- 不支持 orthogonal edge routing (直角连线)
- 算法调优空间小, 不如 ELK 的 100+ layoutOptions
- 历史原因: ELK 是从 Graphviz 迁移过来的 (V5 era 之前)

### Q3: ELK 是 Java 吗?

是 Eclipse Layout Kernel (Java 项目), 但 elkjs 是 JS 移植版 (npm: `elkjs`)。我们用 elkjs, 通过 Node.js subprocess 调起。

### Q4: 如何切换布局算法?

`elk_bridge.py` 构造 ELK JSON 时改 `layoutOptions['elk.algorithm']`:
- `layered` (Sugiyama) — 当前默认
- `force` (力导向)
- `stress` (应力)
- `mrtree` (树形)
- `radial` (径向)

### Q5: rsvg-convert 是必须的吗?

不是必须, 但 rsvg-convert (librsvg) 比 Python 的 cairosvg / Pillow 更精确地实现 SVG 规范。如果不需要 PNG, 直接保存 SVG 字符串即可。

---

## 8. 相关文档

- [ELK_JS_GUIDE.md](./ELK_JS_GUIDE.md) — ELK.js 0.12 API 详细参考 (输入 JSON 结构, layoutOptions 列表)
- [VIZ_DATA_SVG_SPEC.md](./VIZ_DATA_SVG_SPEC.md) — VizData 数据结构 + SVG 输出规范
- [VIZ_DESIGN_SPEC.md](./VIZ_DESIGN_SPEC.md) — 可视化设计 spec
- [VIZ_COMMANDS.md](./VIZ_COMMANDS.md) — 用户命令接口
- [DATAFLOW.md](./DATAFLOW.md) — dataflow 功能概述