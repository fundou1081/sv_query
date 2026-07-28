# Visualization Design Spec v2.0

> Updated 2026-07-29 (V6.7 VizData unified pipeline)
> Created 2026-07-12

---

## 1. 架构原则

### 数据与渲染彻底解耦

```
SignalGraph → build_viz_data(options) → VizData → render_dot(config) → DOT
```

- **VizData** 是纯数据中间层，所有画图功能的唯一输入
- **render_dot** 是统一渲染器 (约 200 行)，不再有 6 个分散的 DOT 生成器
- 未来可以轻松替换渲染后端 (vis.js / cytoscape.js / Mermaid)

### 字段可选原则

每个画图功能只取自己需要的 5-10 个字段：

| 命令 | 节点字段 | 边字段 |
|------|---------|--------|
| graph | id, label, kind, module | kind, expression, condition |
| dataflow | +class_ | +is_control_edge |
| pipeline | +class_, stage_id | +is_control_edge |
| chain | +is_input, is_output, is_critical, cycle | +edge_cycle_delta |

---

## 2. VizData 数据格式

### VizNode

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | str | ✓ | 唯一标识 |
| label | str | ✓ | 显示名 |
| full_path | str | ✓ | 完整层级路径 |
| module | str | ✓ | 所属模块 |
| kind | str | ✓ | SIGNAL/REG/PORT_IN/... |
| width | (int,int) | | (msb, lsb) |
| class_ | str | | DATA/CONTROL/CLOCK/RESET |
| stage_id | int | | pipeline stage |
| cycle | int | | chain cycle count |
| risk_level | str | | LOW/MEDIUM/HIGH/CRITICAL |
| def_name | str | | 实例 module def 名 (arch) |
| depth | int | | 实例层级深度 (arch) |

### VizEdge

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | str | ✓ | "src->dst" |
| src | str | ✓ | 源节点 ID |
| dst | str | ✓ | 目标节点 ID |
| kind | str | ✓ | DRIVER/CLOCK/RESET/CONNECTION/BIT_SELECT |
| expression | str | | 驱动表达式 "a + b" |
| bit_slice | str | | "[7:0]" |
| condition | str | | **显示在边上!** "state == FETCH" |
| clock_domain | str | | 时钟域 |
| assign_type | str | | continuous/nonblocking/blocking |
| source_signal | str | | 位精确信号名 |
| source_op | str | | 操作符 "Add"/">>>" |
| source_casts | [str] | | ["$signed"] |
| is_control_edge | bool | | 控制边 → 虚线 |
| edge_cycle_delta | int | | chain cycle 增量 |
| port_name | str | | 端口名 (arch) |

---

## 3. 渲染规则

### DOT 节点样式

| 属性 | 规则 |
|------|------|
| shape | REG=box, SIGNAL=ellipse, PORT=invhouse, CONST=hexagon |
| color | class_ → 预定义色; risk_level → 红/橙/黄/灰 |
| label | "{name} [kind] [width]" |
| penwidth | is_critical → 2.5 |

### DOT 边样式

| 属性 | 规则 |
|------|------|
| style | control_edge → dashed; CLOCK/RESET → dotted |
| label | condition (优先) + expression (备选) |
| color | class_ → 预定义色; kind=CLOCK→灰, kind=RESET→红 |
| arrowhead | BIT_SELECT → open |

### DOT 全局配置

```python
{
    "layout": "TB",           # TB | LR
    "layout_engine": "dot",   # dot | neato | fdp
    "show_clock_reset": False, # 默认隐藏时钟边
    "edge_labels": True,      # 显示边标签
    "node_spacing": 0.4,
    "rank_spacing": 0.6,
}
```

---

## 4. 迁移状态

| 命令 | 状态 | 数据源 |
|------|------|--------|
| visualize graph | ✅ VizData | SignalGraph |
| visualize dataflow | ✅ VizData | SignalGraph + Classification |
| visualize pipeline | ✅ VizData | SignalGraph + Classification + PipelineInfo |
| visualize chain | ⏸ 保留旧渲染 | SignalGraph + PathFinder |
| visualize module | ⏸ 保留旧渲染 | InstanceResult |
| arch show | ⏸ 保留旧渲染 | InstanceResult |
| visualize teach | ⏸ 保留旧渲染 | SignalGraph + Source snippets |

---

## 5. 旧渲染器

| 渲染器 | 状态 | 迁移计划 |
|--------|------|---------|
| `signal_graph_viewer.render_dot` | ⛔ 内部 helper | 不再用于用户命令 |
| `signal_graph_viewer.render_html` | ⛔ 内部 helper | 未来替换 |
| `signal_graph_viewer.render_mermaid` | ⛔ 内部 helper | 未来替换 |
| `dataflow_viz.generate_dataflow_dot` | ⛔ _emit_split_by_module | 待迁移 |
| `pipeline_viz.generate_pipeline_dot` | 🗑 deprecated | 已替换 |
| `pipeline_viz.generate_pipeline_timing_dot` | 🗑 deprecated | 已替换 |
| `pipeline_viz.generate_pipeline_load_dot` | 🗑 deprecated | 已替换 |
