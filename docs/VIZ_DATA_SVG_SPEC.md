# VIZ_DATA_SVG_SPEC.md — 数据层→SVG 渲染 完整映射规范

> 基于 V100 ELK Compound Graph 实现，commit 14acdd0 (2026-08-05)
> 本文档是 DATAFLOW_VIZ_SPEC.md 的补充，专注数据字段→图表元素的精确映射

---

## 1. 整体数据流水线

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SystemVerilog 源码                               │
│  golden_dataflow_9_case.sv / any module with case/ifelse             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ UnifiedTracer.trace_module()
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SignalGraph (TraceNode + TraceEdge)                                 │
│  - 从 pyslang AST 提取的信号图                                       │
│  - 含 condition_chain, source_op 等驱动信息                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ build_viz_data()
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  VizData (纯数据层)                                                   │
│  - nodes: VizNode[]  (port_side, kind)                               │
│  - edges: VizEdge[]  (condition_chain, source_op, kind)              │
│  - meta: {target_module, datapath, ...}                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ viz_to_elk()  ── elk_bridge.py
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ELK JSON (布局层)                                                    │
│  - compound nodes: case scope + branch scopes                        │
│  - leaf nodes: port_{name}, sig_{name}_..., op_{sym}_...             │
│  - edges: root edges (跨层级) + branch edges (内部)                   │
│  - _meta: {kind, label}  on every node/edge                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ run_elk_layout() → Node.js ELK 0.12.0
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ELK Layout JSON (+ x, y, width, height, sections)                   │
│  - 所有节点有坐标，所有边有 section 路由点                           │
│  - compound node 的尺寸由 ELK 自动计算                                │
│  - branch 内 section 坐标是 PARENT 坐标系 (相对 compound node)        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ render_svg()  ── elk_svg_renderer.py
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SVG 输出                                                             │
│  - scope 背景 + 边框 (compound → rect)                               │
│  - edges (polyline + arrow)                                          │
│  - nodes (port/signal/op → rect + text)                              │
│  - scope labels (text, 最上层)                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据层 (VizData)

### 2.1 VizNode 必需字段

| 字段 | 类型 | 含义 | 用于绘图 |
|------|------|------|----------|
| `id` | str | 节点全限定名，如 `with_case.sel` | ELK node id 来源 |
| `kind` | str | 节点类型: `PORT_IN`, `PORT_OUT`, `SIGNAL`, `REG`, `WIRE` 等 | 决定是否创建 ELK port 节点 |
| `port_side` | str | `'left'`=input port, `'right'`=output port, `''`=非 port | **核心**: 决定 PORT_IN/OUT 节点的创建和位置 |
| `label` | str | 显示名称 | ELK label text |
| `module` | str | 所属模块名 | scope 命名参考 |

### 2.2 VizEdge 必需字段

| 字段 | 类型 | 含义 | 用于绘图 |
|------|------|------|----------|
| `id` | str | 边 ID，格式 `"src->dst"` | ELK edge id |
| `src` | str | 源节点 ID | ELK edge sources |
| `dst` | str | 目标节点 ID | ELK edge targets |
| `kind` | str | 边类型: `DRIVER`, `CLOCK`, `RESET`, `CONNECTION`, `BIT_SELECT` | 过滤: CLOCK/RESET/BIT_SELECT 不入图 |
| `condition_chain` | list[str] | 条件链，如 `["sel == 2'b10"]` | **核心**: 有 chain=条件边, 无链=信号边; chain[-1]=条件标签; chain[0]=sel 信号名 |
| `source_op` | str | 源操作符，如 `"Add"`, `"Subtract"` | 创建 OP 节点 (`+`, `−` 等) |

### 2.3 VizData.meta 必需字段

| 字段 | 含义 |
|------|------|
| `target_module` | 目标模块名，用于标题和 module scope label |
| `datapath.op_index` | `{output: {ops: [...], consts: [...]}}` — 操作符索引 |

### 2.4 数据分类逻辑（Phase 0 of viz_to_elk）

```
for edge in viz.edges:
    if edge.kind in ('CLOCK', 'RESET', 'BIT_SELECT'):
        SKIP  ← 不入图
    
    if edge.condition_chain is not empty:
        cond_by_dst[edge.dst].append(edge)  ← 条件边，归属 case scope
    
    else:
        regular.append(edge)  ← 普通信号边，归属 flat 层
```

---

## 3. ELK 桥接层 (elk_bridge.py)

### 3.1 全局 ELK 配置

| ELK 选项 | 值 | 作用 |
|----------|-----|------|
| `elk.algorithm` | `layered` | Sugiyama 分层算法 |
| `elk.direction` | `RIGHT` | 左→右流向 |
| `elk.edgeRouting` | `ORTHOGONAL` | 直角连线 |
| `elk.hierarchyHandling` | `INCLUDE_CHILDREN` | 一次布局所有嵌套层级 |
| `elk.padding` | `[top=20,left=20,right=20,bottom=20]` | 根节点 padding |
| `elk.spacing.nodeNode` | `25` | 同层节点间距 |

### 3.2 VizData → ELK 元素映射表

| VizData 特征 | ELK 元素 | ELK 层级 | ELK 配置 | `_meta.kind` |
|-------------|----------|---------|----------|-------------|
| `VizNode.port_side == 'left'` | `port_{short_name}` | Root children | `layerConstraint: FIRST` | `port_in` |
| `VizNode.port_side == 'right'` | `port_{short_name}` | Root children | `layerConstraint: LAST` | `port_out` |
| `cond_by_dst` 有 ≥2 条边 | `case_{src}` compound | Root children | `direction: DOWN` | `case` |
| `condition_chain[-1]` 的每个唯一值 | `branch_{dst}_{cond}` compound | Case children | `direction: RIGHT` | `branch` |
| `VizEdge.src` (每个 signal) | `sig_{short}_{dst}_{cond}` | Branch children | 无 | `signal` |
| `VizEdge.source_op` | `op_{op}_{dst}_{cond}` | Branch children | 无 | `op` |
| `condition_chain[0]` 的 sel 信号 | `cond_sel_{dst}` (1×1) | Case children | 无 | `condition_anchor` |
| PORT_IN → branch signal | Root edge | Root.edges | 无 | `signal` |
| Signal → OP (branch 内) | Branch edge | Branch.edges | 无 | `signal` |
| OP/signal → PORT_OUT | Root edge | Root.edges | 无 | `signal` |
| port_sel → cond_sel | Root edge | Root.edges | 无 | `condition_select` |

### 3.3 Scope 层级布局配置

| Scope | `elk.direction` | padding | `elk.spacing.nodeNode` | 边框 |
|-------|----------------|---------|------------------------|------|
| Case scope | `DOWN` | `[top=14,left=10,right=10,bottom=8]` | `10` | 紫色实线 |
| Branch scope | `RIGHT` | `[top=16,left=10,right=10,bottom=8]` | `12` | 绿色虚线 |

### 3.4 Node 尺寸定义

| 节点类型 | width | height |
|----------|-------|--------|
| PORT_IN / PORT_OUT | 44 | 20 |
| Signal | 50 | 24 |
| OP | 24 | 24 |
| condition_anchor | 1 | 1 |

### 3.5 ELK ID 生成规则

```
port_{short_name}                    # port_sel, port_a, port_y
sig_{short}_{dst}_{cond}             # sig_c_with_case_dot_y_sel____2_b10
op_{op}_{dst}_{cond}                 # op_Add_with_case_dot_y_sel____2_b1
branch_{dst}_{cond}                  # branch_with_case_dot_y_sel____2_b0
case_{dst}                           # case_with_case_dot_y
cond_sel_{dst}                       # cond_sel_with_case_dot_y
```

`{cond}` = `condition_chain[-1]` 经过 `_safe()` 处理：`'`→`_`, `.`→`_dot_`

---

## 4. SVG 渲染层 (elk_svg_renderer.py)

### 4.1 `_meta.kind` → SVG 渲染映射

| `_meta.kind` | 节点类型 | SVG 渲染 | 颜色/样式 |
|-------------|---------|---------|-----------|
| `port_in` | Leaf | 灰色圆角矩形 + 居中 Courier 文字 | fill=#eeeeee, stroke=#888888, rx=3, font=8px Courier #555 |
| `port_out` | Leaf | 同上 | 同上 |
| `signal` | Leaf | 白色圆角矩形 + 居中 Courier 文字 | fill=#ffffff, stroke=#333333, rx=3, font=9px Courier #2e7d32 (绿色) |
| `op` | Leaf | 灰色小矩形 + 居中 Bold 文字 | fill=#f0f0f0, stroke=#666666, rx=2, font=9px Helvetica Bold #333 |
| `condition_anchor` | Leaf | **不渲染** (1×1 仅占位) | — |
| `case` | Compound | 紫色 scope 框 (背景+边框) | fill=#f3e5f5, stroke=#7b1fa2, 1.5px solid, rx=6 |
| `branch` | Compound | 绿色 scope 框 (背景+虚线边框) | fill=#f1f8e9, stroke=#1b5e20, 1.2px dashed (5,3), rx=4 |

### 4.2 Scope 标签渲染

```
位置: (node.x + 6, node.y + 13)  — 框内左上角
Case:  font-size=10, font-weight=bold, fill=#7b1fa2 (紫色)
Branch: font-size=8, font-weight=normal, fill=#1b5e20 (绿色)
```

### 4.3 渲染 z-order (从底到顶)

```
1. _draw_scope_bgs()       — scope 背景填充 + 边框
   (按 depth 降序排序: 内层先画 → 外层覆盖)
2. _draw_edges()            — 所有边 (polyline + arrow marker)
3. _draw_leaves()           — 所有叶子节点 (矩形 + 文字)
4. _draw_scope_labels()     — scope 标签文字
```

### 4.4 坐标偏移规则

| 层级 | 坐标输出 | 偏移量 | 处理函数 |
|------|---------|--------|---------|
| Root node | (0,0) | — | — |
| Root children (PORT/signal) | ROOT 坐标 | + (0,0) | `_collect_nodes` |
| Case scope children (branch/cond_sel) | PARENT 坐标 | + (case.x, case.y) | `_collect_nodes` 递归累加 |
| Branch 内 children (sig/op) | PARENT 坐标 | + (case.x+branch.x, case.y+branch.y) | 同上 |
| Root edges | ROOT 坐标 | + (0,0) | `_collect_edges` |
| Branch 内 edges | PARENT 坐标 | + (case.x+branch.x, case.y+branch.y) | `_collect_edges` 递归累加 |

**关键**: `_collect_edges` 需要手动对 branch 内 edge section 的 startPoint/endPoint/bendPoints 累加 compound node 的 x/y 偏移。

### 4.5 渲染函数总览

| 函数 | 输入 | 输出 | 逻辑 |
|------|------|------|------|
| `render_svg(layout, config)` | ELK layout JSON | SVG string | 主入口 |
| `_collect_nodes(node, ..., parent_x, parent_y)` | ELK node tree | leaves[], compounds[] | 递归遍历，leaf→leaves, compound→compounds，累加坐标 |
| `_calc_depth(node)` | ELK node | int | 递归深度 (compound nesting level) |
| `_draw_scope_bgs(svg, compounds)` | sorted compounds | SVG rects | 按 depth 降序: 背景 fill → 边框 stroke |
| `_draw_edges(svg, layout)` | layout | SVG paths | 调用 `_collect_edges` → polyline |
| `_collect_edges(node, out, px, py)` | ELK node tree | shifted edges[] | 递归收集 + PARENT→ROOT 坐标转换 |
| `_draw_leaves(svg, leaves)` | leaves[] | SVG rects + texts | 按 `_meta.kind` 分派样式 |
| `_draw_scope_labels(svg, compounds)` | sorted compounds | SVG texts | 框内左上角文字 |

---

## 5. 完整数据流遍历

| 阶段 | 函数 | 输入 | 输出 | 关键操作 |
|------|------|------|------|----------|
| 1. 源码解析 | `UnifiedTracer.trace_module('with_case')` | .sv 文件 | SignalGraph | pyslang AST → TraceNode + TraceEdge |
| 2. 数据构建 | `build_viz_data(signal_graph, options)` | SignalGraph | VizData | 转换端口标记、condition_chain、source_op |
| 3. 边分类 | `viz_to_elk()` Phase 0 | VizData.edges | cond_by_dst{}, regular[] | 按 condition_chain 是否为空分类 |
| 4. PORT 创建 | `viz_to_elk()` Phase 1-2 | VizData.nodes | Root children (port nodes) | port_side='left'→FIRST, 'right'→LAST |
| 5. Branch 构建 | `viz_to_elk()` Phase 3 | cond_by_dst | Branch children (sig+op+edges) | 按 condition label 分组，建 compound nodes |
| 6. Case 组装 | `viz_to_elk()` Phase 4 | Branch children | Case compound node | DOWN direction, 包含所有 branch |
| 7. ELK 布局 | `run_elk_layout(graph)` | ELK JSON | ELK JSON + coords | Node.js subprocess, 算 x/y/w/h/sections |
| 8. 收集节点 | `_collect_nodes(layout, ...)` | Layout JSON | leaves[], compounds[] | 递归遍历，累加 PARENT→ROOT 坐标 |
| 9. 收集边 | `_collect_edges(layout, ...)` | Layout JSON | shifted edges[] | 递归遍历，PARENT→ROOT 坐标转换 |
| 10. Scope 背景 | `_draw_scope_bgs(svg, compounds)` | sorted compounds | SVG rects ×2 | depth 降序 → bg fill → border |
| 11. 连线 | `_draw_edges(svg, layout)` | shifted edges | SVG paths | polyline + arrow marker |
| 12. 节点 | `_draw_leaves(svg, leaves)` | leaves | SVG rects + texts | 按 kind 分派样式 |
| 13. 标签 | `_draw_scope_labels(svg, compounds)` | sorted compounds | SVG texts | 框内左上角 |
| 14. 输出 | `minidom.toprettyxml()` | ET.Element | formatted SVG string | 美化 XML |

---

## 6. 关键参数速查

### 6.1 节点尺寸

| 参数 | 值 | 定义位置 |
|------|-----|----------|
| PORT_W / PORT_H | 44 / 20 | elk_bridge.py |
| SIG_W / SIG_H | 50 / 24 | elk_bridge.py |
| OP_W / OP_H | 24 / 24 | elk_bridge.py |

### 6.2 Scope 颜色

| Scope | fill | stroke | stroke-width | rx | dashed |
|-------|------|--------|-------------|-----|--------|
| case | #f3e5f5 | #7b1fa2 | 1.5 | 6 | No |
| branch | #f1f8e9 | #1b5e20 | 1.2 | 4 | Yes (5,3) |

### 6.3 节点颜色

| 节点 | fill | stroke | font | fill color |
|------|------|--------|------|------------|
| port | #eeeeee | #888888 | 8px Courier | #555555 |
| signal | #ffffff | #333333 | 9px Courier | #2e7d32 |
| op | #f0f0f0 | #666666 | 9px Helvetica Bold | #333333 |

### 6.4 边颜色

| 参数 | 值 |
|------|-----|
| stroke | #555555 |
| stroke-width | 1.5 |
| marker | arrow (9×5 triangle) |

### 6.5 ELK Spacing

| 参数 | 值 | 作用域 |
|------|-----|--------|
| `elk.padding` | `[top=20,left=20,right=20,bottom=20]` | Root |
| `elk.spacing.nodeNode` | `25` | Root |
| Case `elk.padding` | `[top=14,left=10,right=10,bottom=8]` | Case scope |
| Case `elk.spacing.nodeNode` | `10` | Case scope |
| Branch `elk.padding` | `[top=16,left=10,right=10,bottom=8]` | Branch scope |
| Branch `elk.spacing.nodeNode` | `12` | Branch scope |

### 6.6 SVG 画布偏移

| 参数 | 值 | 作用 |
|------|-----|------|
| OX | 40 | 所有元素 X 偏移 |
| OY | 50 | 所有元素 Y 偏移 |

---

## 7. 验证方法

### 7.1 快速验证用例

**首选**: `sim/tests/fixtures/golden_mini/golden_dataflow_9_case.sv`（case 语句验证）

运行:
```bash
cd ~/my_dv_proj/sv_query
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find . -name '*.pyc' -delete 2>/dev/null
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 /tmp/gen_viz_case9.py
```

产出: `/tmp/case9_v100.png`

### 7.2 验证 checklist

| 检查项 | 预期结果 | 验证方法 |
|--------|---------|----------|
| ELK 边全有 sections | 11/11 edges with sections, 0 no-section | 运行后检查日志 |
| Scope 嵌套正确 | case(紫色实线) 包含 4 branch(绿色虚线) | 肉眼对比 |
| PORT 位置正确 | 5 PORT_IN 在左侧列, 1 PORT_OUT 在右侧 | 肉眼对比 |
| 标签不覆盖 | scope label 在框内左上, 不与节点重叠 | 肉眼对比 |
| 分支内连线 | sel==2'b1 框内 sig_a→op←sig_b 三条线 | 肉眼对比 |
| sel 连线 | port_sel → case scope (台阶状) | 肉眼对比 |

### 7.3 已知验证通过的 Case 列表

| 文件名 | 状态 | 特征 |
|--------|------|------|
| golden_dataflow_9_case.sv | ✅ V100 验证通过 | 4-branch case 语句 |
| golden_dataflow_1_op.sv | 待验证 | 简单 op |
| golden_dataflow_7_ternary.sv | 待验证 | ternary |
| golden_dataflow_8_ifelse.sv | 待验证 | if/else |
| golden_dataflow_11_ternary_scope.sv | 待验证 | ternary scope |
| golden_dataflow_12_ternary_complex.sv | 待验证 | complex ternary |
| golden_dataflow_13_complex.sv | 待验证 | complex |

> **注意**: 当前 V100 只针对 case 语句（`cond_by_dst.size() >= 2`）创建 compound scope。无条件边或单条件边的模块使用 simple flat layout（不创建 scope 框）。

---

## 8. 差异对比：V12 flat vs V100 compound

| 维度 | V12 (已废弃) | V100 (当前) |
|------|-------------|------------|
| Scope 框来源 | SVG 后补: `_build_scope_map` → `_draw_scopes` 从 member_ids 算 bbox | ELK 原生: compound nodes 自动计算尺寸 |
| ELK 图结构 | Flat: 所有节点在 root.children | Compound: case→branch→signal/op 嵌套 |
| `hierarchyHandling` | 未设 (默认 SEPARATE_CHILDREN) | INCLUDE_CHILDREN |
| Edge routing | 部分边无 sections, 需 fallback router | 100% edges ELK native, 0 fallback |
| `_build_scope_map` | 必需 (构建 scope 元数据) | 已删除 (不需要) |
| `_draw_scopes` | 必需 (事后画 scope 框) | 被 `_draw_scope_bgs` + `_draw_scope_labels` 取代 |
| PARENT→ROOT 坐标转换 | 不需要 (flat 无嵌套) | 必需: `_collect_edges` 累加 compound offset |
| 渲染函数 | 4 个: `_draw_scopes`, `_draw_stages`, `_draw_edge`, `_draw_node` | 5 个: `_draw_scope_bgs`, `_draw_edges`, `_draw_leaves`, `_draw_scope_labels`, 递归 `_collect_nodes`/`_collect_edges` |
