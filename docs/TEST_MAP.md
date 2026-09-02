# TEST_MAP.md — 全量测试地图 (2026-09-01 重梳)

> **目的**: 全仓 301 个测试文件的用途地图 — 用于筛选"哪些测试用于哪些目的"。
> **范围**: 所有测试文件 (含 POC / 探索 / 收集范围外的), 按目录 + 功能域分类。
> **统计**: 313 文件, 3049 测试函数 (pytest --collect-only 实测, 2026-09-01)。
> **收集范围**: `pyproject.toml testpaths = ["sim/tests"]` — **sim/ 根、scripts/debug、docs 下的测试不在 pytest 自动收集范围** (手动/特定命令跑)。
> **版本**: iter_061 初版 (317/3033) → iter_078 重梳 (301/2997, 反映 iter_062~078 行为断言升级 + 新增测试 + 清理)。

---

## 0. 完整回归测试构成 (回答"完整的回归测试包含什么")

**完整回归 = 6 层全量 (301 文件 / 2997 测试)**, 每层角色不同, 缺一不可:

| 层 | 范围 | 测试数 | 回答什么问题 | 基线 (2026-09-02) |
|---|---|---|---|---|
| **unit** (95 文件) | 单模块/单函数 | 1095 | 每个提取器/构建器/分析器**单元**行为正确 | **1095 passed** (iter_087: cache 序列化根因修复 + 可写 HOME 下原 4 沙箱 artifact 转绿) |
| **regression** (104 文件) | SV 语法点金标准 | 808 | 每种**语法** (assign/always/if/case/class/constraint...) 的 DRIVER/CONSTRAINS 边 | **808 passed** (iter_081 +42) |
| **integration** (52 文件) | 跨模块端到端 | 422 | 多模块交互、真实场景链路 | **419 passed + 3 skipped** (iter_106 ELK 修复后全绿) |
| **cli** (46 文件) | CLI 命令 subprocess | 389 | run_cli 命令行为 (trace/viz/coverage/randomize) | **389 passed** (iter_087: cache 序列化根因修复后全绿) |
| **usage** (10 文件) | 真实项目大场景 | 298 | 真实 RTL 全量跑 (coverage_generator 179 等) | 慢, 需单独跑 |
| **truth** (17 文件) | 1:1 金标准 | 123 | 1:1 golden: assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集 + generate flatten + spec 不支持语法 | **123 passed** (iter_104 A-F 修复后, +11 断言) |
| **poc** (1 文件) | POC 验证 | 5 | native portConnections (#7) | 5 passed |

**按运行场景选择**:
- **快速核心回归** (signal graph 链路, ~19s): 38 文件 317 测试 → §3.5
- **标准回归** (unit+regression, ~1min): 199 文件 1903 测试 — 覆盖"单元 + 语法金标准"
- **完整回归** (全 6 层, ~5min+): 301 文件 2997 测试 — 含 CLI/集成/真实项目/truth

**各层不可互相替代**: 一个语法点只在 regression 测 (行为断言), 其底层提取逻辑在 unit
测 (单元), 端到端跨模块在 integration 测, 用户可见行为在 cli 测 — 缺一层 = 该视角无回归保护。

---

## 一、目录定位总览

| 目录 | 文件 | 测试函数 | 角色 | 收集状态 |
|---|---|---|---|---|
| `sim/tests/unit` | 95 | 1095 | 单元测试 — 单模块/单函数级, TDD | ✅ 自动 |
| `sim/tests/regression` | 104 | 808 | 语法覆盖 + 金标准回归 (铁律13) | ✅ 自动 |
| `sim/tests/integration` | 52 | 422 | 跨模块集成 + 端到端 | ✅ 自动 |
| `sim/tests/cli` | 46 | 389 | CLI 命令级测试 (subprocess run_cli) | ✅ 自动 |
| `sim/tests/usage` | 10 | 298 | 真实项目/大型场景 (部分 slow) | ✅ 自动 (慢) |
| `sim/tests/` (根, 17 文件) | 17 | 112 | truth 层 (SVG/图 1:1 断言) + spec golden + generate flatten | ✅ 自动 |
| `sim/tests/poc` | 1 | 5 | POC 验证 (native portConnections, #7 用) | ✅ 自动 |
| `scripts/debug` | 2 | 0 | 探索性脚本 (非正式测试) | ❌ 不收集 |
| `docs/openchip_qa_test.py` | 1 | 1 | QA 脚本 (OpenChip 验证) | ❌ 不收集 |

**相对 iter_061 的变化**:
- regression 90→94 文件 / 722→766 测试: iter_064~066 行为断言升级 (4 域) + iter_073~078
  新增 (class_method 2 / task_function +2 / generate_real_world 重建) + sva/constraint/covergroup 扩充
- unit 96→95 文件 / 973→1095 测试: **新增 connection_extractor (13) + bit_select_handler (12)** (iter_073/074),
  其余为既有文件测试函数扩充 (行为断言)
- integration 53→52 文件 / 384→422 测试
- cli 46→46 文件 / 387→389 测试
- removed_features (11 文件 236 测试) 与 sim/ 根 golden 孤儿 (3) 已在 iter_061 删除, 不再计入

---

## 二、功能域分类 (用途 → 测试)

### 2.1 L1 语法/抽取层 (SV 语法覆盖 + 模块/信号抽取)

**regression 语法金标准** (每个语法点一个文件, 铁律13 先推导再验证):
`test_basic_syntax_golden` `test_advanced_features(14)` `test_advanced_features2` `test_unsupported_syntax`
`test_generate(2)` `test_generate_case` `test_generate_enhanced` `test_generate_if`
`test_generate_real_world(4)` `test_interface(4)` `test_interface_advanced` `test_interface_basic`
`test_interface_dot_access` `test_interface_instance` `test_modport_direction` `test_package`
`test_typedef` `test_constraint(3)` `test_constraint_complete(75)` `test_constraint_deep_parsing(46)`
`test_covergroup(5)` `test_class_oop` `test_class_constraint_detail` `test_sva(5)`
`test_clocking` `test_dpi` `test_fork_join` `test_while_loop` `test_always_ff`
`test_non_ansi_port` `test_clock_reset_edge` `test_multi_clock_domain` `test_rhs_syntax(28)`
`test_case_extraction` `test_case_multi_branch(v2)` `test_subroutine_params(16)` `test_task_function(7)`
`test_dot_access_enhanced` `test_replication_fix` `test_positional_port_fix` `test_verilog_always`

**unit 抽取器单元**:
`test_semantic_adapter` `test_sv_extractor(21)` `test_module_extractor(12)` `test_pyslang_type_extraction(87)`
`test_parameter_extraction` `test_param_expression_resolution` `test_width_extraction` `test_width_tuple_defense`
`test_non_ansi_port` `test_issue21_parameter_expression` `test_advanced_sv_features` `test_comment_handling`
`test_procedural_blocks` `test_instance_name_extraction` `test_ast_utils(38)` `test_ast_expression_evaluator`
`test_function_expression` `test_generate_handling`

### 2.2 L2 图构建层 (SignalGraph / ModuleInstanceGraph / 连接 / 位选)

**图模型/指标**: `test_graph_models(8)` `test_graph_metrics` `test_graph_diff` `test_graph_diff_health`
`test_edge_semantics` `test_edge_creates_node` `test_golden_diff(13)`

**实例层级/MIG**: `test_instance_hierarchy` `test_module_instance` `test_hierarchy` `test_concat_and_hierarchy`
`test_mig_generate_block` `test_mig_validator` `test_pr3_mig_fallback` `test_cross_module_tracking(49)`
`test_cross_module_trace` `test_cross_module_trace_pulp` `test_connection_tracing` `test_instance_connection`
`test_port_inout` `test_port_reg_detection` `test_module_hierarchy_fix`

**连接提取 (ConnectionExtractor)** — iter_073/074b 补齐直接单元测试:
`unit/test_connection_extractor(13)`: 端口连接 / 映射 / generate / 边界
(param / positional / interface / tri-state) / missing-module-strict-raises

**位选 (BitSelectHandler)** — iter_074/074b 补齐直接单元测试:
`unit/test_bit_select_handler(12)`: RHS/LHS / 动态索引 / 多维 3 层 / oob / parameterized /
信号宽度; 直接断言 bit_range + parent bit_start
`integration/test_bitselect_handler_diff(8)` (路径 A/B diff) `regression/test_bit_select(3处)`
`test_common_bit_selects` `test_f2_walker_bit_range_preservation`

**native parity (#7)**: `unit/test_native_adapter_parity(13)` `poc/test_portconn_native_poc(5)`

### 2.3 L3 信号追踪/驱动/分析层

**追踪**: `test_signal_tracer` `test_trace(11, cli)` `test_trace_batch` `test_trace_filters` `test_trace_snapshot`
`test_trace_cache_error` `test_trace_overview` `test_fan_query` `test_signal_normalizer(81)` `test_query_load`
`test_get_signal_identifier` `test_trace_filelist_fix` `test_trace_include_flags` `test_trace_schemas`
`test_localparam_driver_filter` `test_no_direct_trace_edge_in_driver_extractor` `test_module_tracer`

**驱动/表达式树**: `test_driver_extractor_net_decl` `test_f2_expression_tree_*(6个)` `test_f2_generate_*`
`test_f2_walker_bit_range_preservation` `test_f2_no_string_fallback` `test_function_expression`
`test_evidence_*(5个)` (assign_comb/class_constraint/cli_integration/credibility)

**dataflow/controlflow**: `test_dataflow_else_if_comprehensive` `test_dataflow_else_if_typo` `test_dataflow_golden`
`test_dataflow_error_hint` `test_controlflow` `test_controlflow_mutex` `test_dataflow_controlflow_open_source`
`test_dataflow_latency_open_source` `test_advanced_grammar` `test_advanced_syntax`

**时序/CDC/时钟**: `test_clock_edge` `test_clock_reset_timing` `test_clock_reset_edge` `test_reset_edge`
`test_cdc` `test_cdc_multiclock` `test_cdc_risk_open_source` `test_clock_domain` `test_multi_clock_domain`
`test_timing_analyzer` `test_timing_control` `test_latch` `test_clocking` `test_negative_cases`

**协议/握手/死锁**: `test_handshake_*(8个)` `test_handshake_detector(34)` `test_handshake_fusion(28)`
`test_protocol_*(8个)` `test_protocol_axistream` `test_bus_protocol_patterns` `test_deadlock_detector(13)`
`test_deadlock_cli` `test_backpressure_handshake_filter` `test_handshake_cli`

### 2.4 L4 可视化层 (VizData / SVG / DOT / teach)

`test_viz_data(17)` `test_viz_expr_trees` `test_visualize_*(cli, 20个)` `test_visualize_latency_golden`
`test_visualize_compute` `test_visualize_timed_compute` `test_visualize_teach*(6个)` `test_visualize_generate`
`test_visualize_graph_source` `test_visualize_module_golden` `test_visualize_dataflow` `test_visualize_pipeline`
`test_cross_viz_consistency` `test_golden_diff(13)` `test_pr4_visualize_l2` `test_real_project_viz`

### 2.5 CLI 命令层 (subprocess run_cli)

**架构/设计**: `test_arch(20)` `test_arch_understand(7)` `test_design(10)` `test_open_source_validation`
**覆盖**: `test_coverage_analyze` `test_coverage_gap` `test_coverage_gen_demo(golden)` `test_coverage_generate`
`test_coverage_generator(179)` `test_coverage_gen_sv_compile`
**随机化**: `test_randomize(5个)` `test_randomize_reachability(extended)` `test_randomize_trace`
`test_reachability_semantic_golden`
**修复工具**: `test_fix_imports` `test_fix_report` `test_fix_timescale` `test_fix_widths`
**快照/统计**: `test_snapshot*` `test_snapshot_non_strict_mode` `test_stats_filelist` `test_stats_non_strict`
`test_strict_default` `test_cli_filelist_parity` `test_cli_f_flag_filelist_routing`
**信号源**: `test_signal_source_bitprecision` `test_backfill_source_locations`
**其他**: `test_diff` `test_golden_chain_anomalies` `test_known_limitations` `test_no_swap_reclaim`
`test_ventus_*(3个)` `test_picorv32_validation` `test_real_project_binary_ops`

### 2.6 编译/预处理/环境

`test_sv_preprocessor(20)` `test_normalize_filelist(36)` `test_pyslang_v11_aliases(23)` `test_pyslang_v11_cli_smoke`
`test_naplespu_filelist` `test_strict_default_filelist` `test_spec_unsupported_syntax` `test_issue33_literal_edge`

### 2.7 纪律/结构 (防回归防退化)

`test_discipline_enforced` `test_no_data_models_legacy` `test_no_pyslang_adapter_legacy`
`test_f2_no_string_fallback` `test_safe(18)` `test_schema_aligns_with_code` `test_structural_hints(46)`
`test_pattern_learner(31)` `test_signal_classify_yaml` `test_protocol_json_output` `test_protocol_schema`

### 2.8 真实项目/开源验证

`test_open_source_validation` `test_cdc_risk_open_source(5 projects)` `test_dataflow_*_open_source`
`test_opentitan_*(4个)` `test_benchmark_picorv32` `test_benchmark_regression` `test_benchmark_pr5`
`test_subfunction_golden_open_source` `test_real_project_viz` `test_ventus_all_viz_validation`
`test_ventus_chunk_filelist` `test_ventus_viz_validation` `test_generate_real_world(4)`

### 2.9 性能

`test_performance` `test_benchmark_picorv32` `test_benchmark_regression` `test_benchmark_pr5`

### 2.10 废弃/隔离 (**已清理 iter_061**)

| 区域 | 状态 |
|---|---|
| `usage/removed_features` (11) | ✅ **已删除** (iter_061) — V6.9 移除功能的 skip 尸体, 且收集报 11 错 |
| `sim/` 根 (3 golden) | ✅ **已删除** (iter_061) — 不在 testpaths 的孤儿, 无活引用 |
| `scripts/debug` (2) | 保留 — 探索性脚本 (0 测试函数), 非正式但可能有用 |
| `docs/openchip_qa_test.py` | 保留 — QA 脚本, 手动跑 |

### 2.11 POC/验证

`sim/tests/poc/test_portconn_native_poc` (native portConnections 验证, #7 用)
`sim/tests/unit/test_native_adapter_parity` (native vs 递归 parity, #7 用)

### 2.12 truth 层 (sim/tests/ 根)

| 文件 | 测试数 | 角色 |
|---|---|---|
| `test_case27_1to1_truth.py` | 4 | **1:1 truth** (SVG 断言, case27 金标准) |
| `test_generate_for_chain_truth.py` | 6 | 1:1 truth — 3 级 generate-for 链精确节点/边 (iter_083) |
| `test_cross_module_truth.py` | 4 | 1:1 truth — 跨模块端口连接 (iter_083) |
| `test_d1_generate_flatten_signal_set.py` | 11 | generate flatten 信号集 (D1) |
| `test_spec_unsupported_syntax.py` | 7 | spec 不支持的语法 (预期失败语义) |
| `test_assign_chain_truth.py` | 9 | [T1] assign/wire 链精确结构 (iter_088) |
| `test_clock_reset_truth.py` | 9 | [T2] always_ff + CLOCK/RESET 条件边 (iter_089) |
| `test_case_branch_truth.py` | 8 | [T3] case 分支条件边 + 字面量归一化 (iter_090) |
| `test_bit_select_truth.py` | 10 | [T4] BIT_SELECT 回边 + bit_slice (iter_091) |
| `test_concat_truth.py` | 3 | [T5] RHS 拼接无跨边 (iter_092) |
| `test_function_task_truth.py` | 6 | [T6] function 调用 + task 形参真边 (iter_093) |
| `test_parameter_filter_truth.py` | 5 | [T7] parameter 过滤反例式 (iter_094) |
| `test_alias_truth.py` | 3 | [T8] alias 方向 source→target (iter_095) |
| `test_class_oop_truth.py` | 4 | [T9] class 三件套 + 方法体成员边 (iter_096) |
| `test_generate_if_case_truth.py` | 6 | [T10] generate 编译期分支选择 (iter_097) |
| `test_layout_truth.py` | 9 | [T11] SVG 渲染结构 (op/信号分类) (iter_098) |
| `test_query_truth.py` | 8 | [T12] fanin/fanout 精确驱动集 (iter_099) |

**合计**: 17 文件 / 123 测试 (iter_104 缺陷 A-F 修复后: 123 passed; d1 4 skip 为 pyslang mutex 环境限制)

---

## 三、关键测试集 (按运行命令分组)

| 命令 | 范围 | 角色 | 基线状态 (沙箱) |
|---|---|---|---|
| `pytest sim/tests/unit sim/tests/cli` | 95+46 | **主回归** | **1484 passed** (iter_087 全绿; 原 4 沙箱 cache artifact 中 test_trace_include_flags 在可写 HOME 下已过) |
| `pytest sim/tests/integration` | 52 文件 | 集成 | **419 passed + 3 skipped** (iter_106: picorv32 ELK dangling 已修, 全绿; 沙箱 cache 不可写时另有假失败) |
| `pytest sim/tests/regression` | 94 文件 | 语法金标准 | **766 passed** (iter_076 全绿) |
| `pytest sim/tests/test_case27_1to1_truth.py` | truth | **1:1 truth (SVG 断言)** | 4 passed |
| `pytest sim/tests/usage` | 10 文件 | 真实项目 (慢) | — |

---

## 3.5 🎯 Signal Graph 核心回归集 (推荐, iter_080 实测)

**用途**: 只回归 signal graph 核心链路 (语义适配 → 提取器 → 图构建 → 图模型 → 追踪),
不含 CLI/可视化/协议/握手等外围。**38 文件 / 317 测试 / ~19s 全绿** (2026-09-01 实测)。

```bash
# 推荐命令 (核心集, 一行跑完)
python3 -m pytest \
  sim/tests/unit/test_semantic_adapter.py \
  sim/tests/unit/test_native_adapter_parity.py \
  sim/tests/unit/test_generate_handling.py \
  sim/tests/unit/test_driver_extractor_net_decl.py \
  sim/tests/unit/test_connection_extractor.py \
  sim/tests/unit/test_bit_select_handler.py \
  sim/tests/unit/test_common_bit_selects.py \
  sim/tests/unit/test_mig_generate_block.py \
  sim/tests/unit/test_mig_validator.py \
  sim/tests/unit/test_f2_expression_tree_coverage.py \
  sim/tests/unit/test_f2_expression_tree_injection.py \
  sim/tests/unit/test_f2_expression_tree_shapes.py \
  sim/tests/unit/test_f2_generate_expression_trees.py \
  sim/tests/unit/test_f2_generate_for_indexed_lhs.py \
  sim/tests/unit/test_f2_walker_bit_range_preservation.py \
  sim/tests/unit/test_f2_no_string_fallback.py \
  sim/tests/unit/test_graph_models.py \
  sim/tests/unit/test_schema_aligns_with_code.py \
  sim/tests/unit/test_width_tuple_defense.py \
  sim/tests/unit/test_golden_diff.py \
  sim/tests/regression/test_edge_creates_node.py \
  sim/tests/regression/test_edge_semantics.py \
  sim/tests/regression/test_graph_metrics.py \
  sim/tests/regression/test_cross_module_tracking.py \
  sim/tests/unit/test_cross_module_trace.py \
  sim/tests/unit/test_cross_module_trace_pulp.py \
  sim/tests/unit/test_pr3_mig_fallback.py \
  sim/tests/unit/test_pr4_visualize_l2.py \
  sim/tests/regression/test_port_inout.py \
  sim/tests/integration/test_port_reg_detection.py \
  sim/tests/integration/test_instance_connection.py \
  sim/tests/unit/test_signal_tracer.py \
  sim/tests/unit/test_localparam_driver_filter.py \
  sim/tests/regression/test_bit_select.py \
  sim/tests/regression/test_bit_select_hierarchical.py \
  sim/tests/regression/test_bit_select_in_always.py \
  sim/tests/regression/test_class_method.py \
  sim/tests/regression/test_task_function.py \
  -q
```

**分层说明**:
- **核心 38 文件**: 全部直接 import/行为覆盖 signal graph 链路, **317 passed / ~19s**
- **可选扩展** (行为层, 慢/宽): `test_bitselect_handler_diff.py` (8, ✅ iter_080 修复:
  fixture `data[3:0][1:0]` 非法 SV → 合法 `data[0][1:0]` (packed array element chain);
  路径 B 去掉 `strict=False`) + regression 语法金标准全量 (766)
- **排除**: CLI/可视化/协议握手/修复工具/随机化 (非 signal graph 核心)

**选择依据** (TECH_MAP 实测引用): 8 项底层技术 (graph 模型/构建/driver/connection/mig/
bit_select/semantic_adapter/tracer) 每项至少 1 个直接测试文件 + 金标准行为文件。

---

## 四、值得注意的观察 (供筛选)

1. **regression 是最大金标准集** (766 测试) — 语法点逐一文件, 是行为断言升级主战场 (iter_064~078)
2. **unit 覆盖率上升** — connection_extractor (13) / bit_select_handler (12) 已从"0 直接测试"
   补齐 (SIGNAL_GRAPH_TECH_TEST_MAP 2.4/2.6 ✅)
3. **usage/ 有 slow/skipif 测试** (coverage_gen_sv_compile 等) — CI 是否跑需确认
4. **truth 层 3 文件 22 测试** — case27 SVG 断言 + generate flatten + spec unsupported,
   覆盖面仍窄, 可扩展
5. **脚本式 QA** (docs/openchip_qa_test.py, scripts/debug/*) 非 pytest 正式测试
6. **4 个 unit 失败为沙箱环境 artifact** (`~/.svq/cache` 不可写, test_trace_include_flags
   fanout 系列) — 非逻辑回归, 本机 (writable cache) 全绿
