# SIGNAL_GRAPH_TECH_TEST_MAP.md — signal graph 底层技术测试地图

> **创建**: 2026-08-29 (iter_072) / **刷新**: 2026-09-01 (iter_080, 实测口径统一)
> **目的**: 找出所有与 signal graph 及其底层技术相关的测试, 评估每项底层技术的直接测试覆盖。
> **方法**: 全仓扫描测试文件对底层模块的**内容引用** (import + 符号名 + 字符串, 实测
> `python` 扫描 301 个测试文件, 2026-09-01) — 与 [TEST_MAP.md](TEST_MAP.md) (301/2997) 对齐。
> **关联**: [TEST_MAP.md](TEST_MAP.md) (全量测试地图) / [SIGNAL_GRAPH_SPEC.md](SIGNAL_GRAPH_SPEC.md)

---

## 一、底层技术全景 (signal graph 依赖链)

```
SV 源码 → pyslang (语义适配) → 提取器 (驱动/连接/模块实例/位选)
       → GraphBuilder (图构建) → SignalGraph (TraceNode/TraceEdge)
       → SignalTracer (追踪) / DataFlow / VizData (可视化)
```

---

## 二、各底层技术的测试覆盖 (实测引用文件数)

> 口径: 引用文件数 = 301 个测试文件中出现该技术符号/模块名的文件数 (含 import 与间接字符串引用)。
> 直接测试 = 单测级 import 该模块; 行为测试 = 经 UnifiedTracer/CLI 间接覆盖。

### 2.1 图模型 (TraceNode/TraceEdge/EdgeKind/NodeKind) — 61 文件引用

**核心直接测试**:
- `unit/test_graph_models.py` (8) — 图模型本体
- `unit/test_schema_aligns_with_code.py` (4) — 模型与 schema 一致性
- `unit/test_width_tuple_defense.py` (4) — 宽度元组防御
- `regression/test_edge_creates_node.py` (3) — 边创建节点
- `regression/test_edge_semantics.py` (9) — 边语义
- `unit/test_graph_metrics.py` (9) / `test_golden_diff.py` (13) / `test_viz_data.py` (17)

**间接/行为**: 几乎所有构建图的行为测试 (integration/regression 大量, 61 文件引用 TraceNode/Edge)

### 2.2 图构建 (GraphBuilder) — 9 文件直接引用

**直接 import** (9): `unit/test_bit_select_handler` `test_bitselect_handler_diff`
`regression/test_call_graph(3)` `test_controlflow` `test_extractors_negative`
`usage/test_coverage_generator` `test_pyslang_v11_aliases`

**间接 (通过 UnifiedTracer)**: 绝大多数行为测试 — regression 语法金标准 +
integration 跨模块 + 行为断言 (DRIVER 边/condition/assign_type)

### 2.3 驱动提取 (DriverExtractor/DriverInfo/SignalSource) — 10 文件引用

**直接**: `cli/test_signal_source_bitprecision.py` (SignalSource 位精确性, 11)
`unit/test_no_direct_trace_edge_in_driver_extractor.py` (纪律: 不直接加 trace 边)
**行为**: `unit/test_driver_extractor_net_decl` (2) `test_f2_expression_tree_injection`
`test_f2_expression_tree_shapes` `test_f2_generate_expression_trees` `test_f2_generate_for_indexed_lhs`
`test_edge_creates_node` `test_visualize_generate` `usage/test_coverage_generator`

### 2.4 ✅ 连接提取 (ConnectionExtractor) — 1 文件直接 + 行为间接

**直接**: `unit/test_connection_extractor.py` (13, iter_073+074b: 端口连接 /
映射 / generate / 边界 (param / positional / interface / tri-state) /
missing-module-strict-raises)
**间接覆盖**: 跨模块连接行为 (`regression/test_cross_module_tracking.py` 49) 间接覆盖。

### 2.5 模块实例图 (MIG) — 6 文件引用

**直接**: `unit/test_mig_validator.py` (4)
**行为**: `unit/test_mig_generate_block.py` (7) `test_pr3_mig_fallback.py` (8)
`test_pr4_visualize_l2.py` (13) `test_cross_module_tracking.py` (49)
**POC**: `poc/test_portconn_native_poc.py` (5)
**parity**: `unit/test_native_adapter_parity.py` (13, #7 全程验证)

### 2.6 ✅ 位选 (BitSelectHandler) — 2 文件直接 + 行为间接

**直接**: `unit/test_bit_select_handler.py` (12, iter_074+074b: RHS/LHS/dynamic/
multidim-3level/oob/parameterized/signal_widths; 直接断言 bit_range + parent
bit_start)
**间接**: `integration/test_bitselect_handler_diff.py` (8, 路径 A/B diff)
`regression/test_bit_select(3个)` `unit/test_common_bit_selects`
`test_f2_walker_bit_range_preservation` — 行为级覆盖。

### 2.7 信号追踪 (SignalTracer) — 10 文件引用

**直接**: `unit/test_signal_tracer.py` (7) `test_cross_module_trace` `test_cross_module_trace_pulp`
`test_pr3_mig_fallback` `test_trace_based_handshake` `test_driver_extractor_net_decl`
`test_localparam_driver_filter` `test_instance_connection` `test_graph_diff`
**行为**: trace 系列 (cli/test_trace*) + dataflow + fan_query + boundary

### 2.8 表达式树 (ExprTree) — 9 文件引用

**直接**: `unit/test_f2_expression_tree_coverage` (6) `test_f2_no_string_fallback` (4)
`test_f2_walker_bit_range_preservation` (7)
**行为**: `test_f2_expression_tree_injection` (5) `test_f2_expression_tree_shapes` (17)
`test_f2_generate_expression_trees` (5) `test_f2_generate_for_indexed_lhs` (5)
`test_viz_expr_trees` (10) `usage/test_coverage_generator`

### 2.9 语义适配 (SemanticAdapter/pyslang) — 23 文件引用 (底座)

**直接**: `unit/test_semantic_adapter.py` (5) `test_pyslang_type_extraction.py` (87)
`test_generate_handling.py` (8) `test_native_adapter_parity.py` (13) `test_non_ansi_port`
`test_param_expression_resolution` `test_parameter_extraction` `test_procedural_blocks`
`test_comment_handling` `test_extract_target` `test_width_extraction`
`regression/test_constraint_complete` (75) `test_constraint_deep_parsing` (46) 等

### 2.10 数据流 (DataFlow) — 30 文件引用

`usage/test_dataflow_*_open_source` `integration/test_dataflow_else_if_*`
`test_dataflow_golden` `unit/test_dataflow_error_hint` cli/dataflow 系列
`test_cdc_risk_open_source` `test_real_project_viz` 等

### 2.11 可视化底层 (VizData) — 4 文件引用

`unit/test_viz_data.py` (17) `test_viz_expr_trees.py` (10) `cli/test_visualize_dataflow`
`test_visualize_pipeline`

---

## 三、覆盖缺口观察 (供后续决策, 2026-09-01 实测刷新)

| 底层技术 | 直接测试 | 间接覆盖 | 建议 |
|---|---|---|---|
| **connection_extractor** | **13** | 跨模块行为 (间接) | ✅ **已补** (iter_073+074b: 13 单元测试: 端口连接/映射/generate/param/positional/interface/tri-state/缺模块 strict raises) |
| **bit_select_handler** | **12** | 行为充分 (diff/regression) | ✅ **已补** (iter_074+074b: 12 单元测试: RHS/LHS/动态索引/层级/oob/parameterized/信号宽度; 直接断言 bit_range+parent bit_start) |
| graph 模型 | 5 文件直接 | 61 文件引用 | 🟢 充分 (本体+一致性+防御+边语义) |
| driver_extractor | 2 文件直接 | 10 文件引用 | 🟢 可接受 (f2 系列 + 行为断言) |
| module_instance_graph | 6 文件引用 | mig_generate_block + #7 parity | 🟢 可接受 |
| graph_builder | 9 文件直接 | 行为断言充分 | 🟢 可接受 |
| signal_tracer | 10 文件引用 | trace 系列行为 | 🟢 可接受 |
| expr_tree | 9 文件引用 | f2 系列直接 | 🟢 可接受 |
| semantic_adapter | 23 文件引用 | 底座全覆盖 | 🟢 可接受 |
| **剩余无直接单测** | — | — | 无 (2026-09-01 实测: 8 项底层技术均有直接或行为覆盖) |

---

## 四、关键测试集 (signal graph 底层核心)

| 测试 | 作用 |
|---|---|
| `unit/test_graph_models.py` | 图模型本体 (节点/边/种类) |
| `unit/test_native_adapter_parity.py` | pyslang native vs 递归 (枚举等价性, #7) |
| `regression/test_cross_module_tracking.py` (49) | 跨模块连接/追踪金标准 |
| `unit/test_mig_generate_block.py` | MIG generate 支持金标准 |
| `integration/test_bitselect_handler_diff.py` | 位选两路径一致性 |
| `unit/test_f2_expression_tree_*.py` | 表达式树 (形状/注入/覆盖) |
| `unit/test_signal_tracer.py` | 信号追踪核心 |
| `unit/test_connection_extractor.py` | 连接提取直接单测 (iter_073) |
| `unit/test_bit_select_handler.py` | 位选直接单测 (iter_074) |
| `unit/test_class_method.py` | class 方法体赋值 DRIVER 边 (iter_075) |
| `regression/test_task_function.py` | task 调用站点形参映射 (iter_076) |
