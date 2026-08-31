# SIGNAL_GRAPH_TECH_TEST_MAP.md — signal graph 底层技术测试地图

> **创建**: 2026-08-29 (iter_072)
> **目的**: 找出所有与 signal graph 及其底层技术相关的测试, 评估每项底层技术的直接测试覆盖。
> **方法**: 全仓扫描测试文件对底层模块的引用 (直接 import vs 间接使用)。
> **关联**: [TEST_MAP.md](TEST_MAP.md) (全量测试地图) / [SIGNAL_GRAPH_SPEC.md](SIGNAL_GRAPH_SPEC.md)

---

## 一、底层技术全景 (signal graph 依赖链)

```
SV 源码 → pyslang (语义适配) → 提取器 (驱动/连接/模块实例/位选)
       → GraphBuilder (图构建) → SignalGraph (TraceNode/TraceEdge)
       → SignalTracer (追踪) / DataFlow / VizData (可视化)
```

---

## 二、各底层技术的测试覆盖

### 2.1 graph 模型 (TraceNode/TraceEdge/EdgeKind/NodeKind) — 60 文件引用

**核心直接测试**:
- `unit/test_graph_models.py` (38 refs) — 图模型本体
- `unit/test_schema_aligns_with_code.py` — 模型与 schema 一致性
- `unit/test_width_tuple_defense.py` — 宽度元组防御
- `regression/test_edge_creates_node.py` — 边创建节点
- `regression/test_edge_semantics.py` — 边语义

**间接/行为**: 几乎所有构建图的行为测试 (integration/regression 大量)

### 2.2 图构建 (GraphBuilder) — 135 文件引用

**直接 import** (7): `test_bitselect_handler_diff` `test_pyslang_v11_aliases`
`test_call_graph(3)` `test_controlflow` `test_extractors_negative`

**间接 (通过 UnifiedTracer)**: 绝大多数行为测试 — regression 语法金标准 +
integration 跨模块 + 本次升级的行为断言 (DRIVER 边/condition/assign_type)

### 2.3 驱动提取 (DriverExtractor/DriverInfo/SignalSource) — 17 文件

**直接**: `cli/test_signal_source_bitprecision.py` (SignalSource 位精确性)
**行为**: `unit/test_driver_extractor_net_decl.py` `test_f2_expression_tree_injection`
`test_f2_generate_expression_trees` `test_f2_generate_for_indexed_lhs`

### 2.4 ⚠️ 连接提取 (ConnectionExtractor) — **0 直接测试**

**缺口**: 全仓无测试直接 import ConnectionExtractor! 仅 `test_cross_module_tracking`
(3 refs) 和 `test_visualize_chain` 间接涉及。
**间接覆盖**: 跨模块连接行为 (cross_module_tracking 49 测试) 间接覆盖,
但连接提取器本身的单元级验证缺失。

### 2.5 模块实例图 (MIG) — 9 文件

**直接**: `unit/test_mig_validator.py`
**行为**: `unit/test_mig_generate_block.py` (7) `test_pr3_mig_fallback.py` (8)
`test_pr4_visualize_l2.py` (13) `test_cross_module_tracking.py` (49)
**POC**: `poc/test_portconn_native_poc.py`
**parity**: `unit/test_native_adapter_parity.py` (#7 全程验证)

### 2.6 ⚠️ 位选 (BitSelectHandler) — **0 直接 import**

**缺口**: 无测试直接 import BitSelectHandler! 
**间接**: `integration/test_bitselect_handler_diff.py` (路径 A/B diff)
`regression/test_bit_select(3个)` `unit/test_common_bit_selects`
`test_f2_walker_bit_range_preservation` — 行为级覆盖充分, 但无单元级直接测试。

### 2.7 信号追踪 (SignalTracer) — 50 文件

**直接**: `unit/test_signal_tracer.py` `test_cross_module_trace(2)`
`test_pr3_mig_fallback` `test_trace_based_handshake` `test_driver_extractor_net_decl`
**行为**: trace 系列 (cli/test_trace*) + dataflow + fan_query + boundary

### 2.8 表达式树 (ExprTree) — 10 文件

**直接**: `unit/test_f2_expression_tree_coverage` `test_f2_no_string_fallback`
`test_f2_walker_bit_range_preservation`
**行为**: `test_f2_expression_tree_injection` `test_f2_expression_tree_shapes`
`test_f2_generate_expression_trees` `test_viz_expr_trees`

### 2.9 语义适配 (SemanticAdapter/pyslang) — 171 文件 (底座, 几乎全覆盖)

**直接**: `unit/test_semantic_adapter.py` `test_pyslang_type_extraction.py` (39)
`test_generate_handling.py` `test_native_adapter_parity.py` `test_non_ansi_port`
`test_param_expression_resolution` `test_parameter_extraction` `test_procedural_blocks`
`test_comment_handling` `regression/test_constraint_complete` 等

### 2.10 数据流 (DataFlow) — 35 文件

`usage/test_dataflow_*_open_source` `integration/test_dataflow_else_if_*`
`test_dataflow_golden` `unit/test_dataflow_error_hint` cli/dataflow 系列

### 2.11 可视化底层 (VizData) — 5 文件

`unit/test_viz_data.py` (27) `test_viz_expr_trees.py` `cli/test_visualize_dataflow`
`test_visualize_pipeline`

---

## 三、覆盖缺口观察 (供后续决策)

| 底层技术 | 直接测试 | 间接覆盖 | 建议 |
|---|---|---|---|
| **connection_extractor** | **0** | 跨模块行为 (间接) | 🔴 补单元测试 (端口连接提取的核心逻辑无直接验证) |
| **bit_select_handler** | **0** | 行为充分 (diff/regression) | 🟡 补单元测试或接受间接覆盖 |
| driver_extractor | 1 | 充分 (f2 系列 + 行为断言) | 🟢 可接受 |
| module_instance_graph | 1 (validator) | 充分 (mig_generate_block + #7) | 🟢 可接受 |
| graph_builder | 7 | 充分 | 🟢 可接受 |

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
