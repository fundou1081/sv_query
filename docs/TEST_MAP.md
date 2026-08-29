# TEST_MAP.md — 全量测试地图 (2026-08-29)

> **目的**: 全仓 317 个测试文件的用途地图 — 用于筛选"哪些测试用于哪些目的"。
> **范围**: 所有测试文件 (含废弃 / POC / 探索 / 收集范围外的), 按目录 + 功能域分类。
> **统计**: 317 文件, 3033 测试函数, 802 测试类。
> **收集范围**: `pyproject.toml testpaths = ["sim/tests"]` — **sim/ 根、scripts/debug、docs 下的测试不在 pytest 自动收集范围** (手动/特定命令跑)。

---

## 一、目录定位总览

| 目录 | 文件 | 测试函数 | 角色 | 收集状态 |
|---|---|---|---|---|
| `sim/tests/unit` | 96 | 973 | 单元测试 — 单模块/单函数级, TDD | ✅ 自动 |
| `sim/tests/regression` | 90 | 722 | 语法覆盖 + 金标准回归 (铁律13) | ✅ 自动 |
| `sim/tests/integration` | 53 | 384 | 跨模块集成 + 端到端 | ✅ 自动 |
| `sim/tests/cli` | 46 | 387 | CLI 命令级测试 (subprocess run_cli) | ✅ 自动 |
| `sim/tests/usage` | 10 | 298 | 真实项目/大型场景 (部分 slow) | ✅ 自动 (慢) |
| ~~`sim/tests/usage/removed_features`~~ | ~~11~~ | ~~236~~ | **已删除** (iter_061: V6.9 移除功能尸体, 全 skip + 收集报错) | ❌ 已清理 |
| `sim/tests/` (根) | 4 | 22 | truth 层 (SVG 断言) + spec golden | ✅ 自动 |
| `sim/tests/poc` | 1 | 5 | POC 验证 (native portConnections) | ✅ 自动 |
| ~~`sim/` (根)~~ | ~~3~~ | ~~5~~ | **已删除** (iter_061: 旧金标准孤儿, 无活引用) | ❌ 已清理 |
| `scripts/debug` | 2 | 0 | 探索性脚本 (非正式测试) | ❌ 不收集 |
| `docs/openchip_qa_test.py` | 1 | 1 | QA 脚本 (OpenChip 验证) | ❌ 不收集 |

---

## 二、功能域分类 (用途 → 测试)

### 2.1 L1 语法/抽取层 (SV 语法覆盖 + 模块/信号抽取)

**regression 语法金标准** (每个语法点一个文件, 铁律13 先推导再验证):
`test_basic_syntax_golden` `test_advanced_features(2)` `test_unsupported_syntax`
`test_generate(2)` `test_generate_case` `test_generate_enhanced` `test_generate_if`
`test_generate_real_world` `test_interface(6)` `test_interface_advanced` `test_interface_basic`
`test_interface_dot_access` `test_interface_instance` `test_modport_direction` `test_package`
`test_typedef` `test_constraint(6)` `test_constraint_complete(75)` `test_constraint_deep_parsing(46)`
`test_covergroup(6)` `test_class(6)` `test_class_constraint_detail` `test_sva(8)`
`test_clocking` `test_dpi` `test_fork_join` `test_while_loop` `test_always_ff`
`test_non_ansi_port` `test_clock_reset_edge` `test_multi_clock_domain` `test_rhs_syntax`
`test_case_extraction` `test_case_multi_branch(v2)` `test_subroutine_params` `test_task_function`
`test_dot_access_enhanced` `test_replication_fix` `test_positional_port_fix` `test_verilog_always`

**unit 抽取器单元**:
`test_semantic_adapter` `test_sv_extractor(21)` `test_module_extractor(12)` `test_pyslang_type_extraction(39)`
`test_parameter_extraction` `test_param_expression_resolution` `test_width_extraction` `test_width_tuple_defense`
`test_non_ansi_port` `test_issue21_parameter_expression` `test_advanced_sv_features` `test_comment_handling`
`test_procedural_blocks` `test_instance_name_extraction` `test_ast_utils(38)` `test_ast_expression_evaluator`

**sim/ 根旧 golden** (孤儿): `test_golden` `test_golden_cases` `test_gold_comprehensive`

### 2.2 L2 图构建层 (SignalGraph / ModuleInstanceGraph)

`test_graph_models` `test_graph_metrics` `test_graph_diff` `test_graph_diff_health` `test_edge_semantics`
`test_edge_creates_node` `test_instance_hierarchy` `test_module_instance` `test_hierarchy` `test_concat_and_hierarchy`
`test_mig_generate_block` `test_mig_validator` `test_cross_module_tracking(49)` `test_cross_module_trace`
`test_cross_module_trace_pulp` `test_connection_tracing` `test_instance_connection` `test_port_inout`
`test_port_reg_detection` `test_native_adapter_parity(13)` `test_bit_select(3处)` `test_bit_select_hierarchical`
`test_bit_select_in_always` `test_common_bit_selects` `test_bitselect_handler_diff`

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

**架构/设计**: `test_arch(20)` `test_arch_understand` `test_design` `test_open_source_validation`
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

`test_sv_preprocessor(20)` `test_normalize_filelist` `test_pyslang_v11_aliases` `test_pyslang_v11_cli_smoke`
`test_naplespu_filelist` `test_strict_default_filelist` `test_spec_unsupported_syntax`

### 2.7 纪律/结构 (防回归防退化)

`test_discipline_enforced` `test_no_data_models_legacy` `test_no_pyslang_adapter_legacy`
`test_no_string_fallback` `test_safe(18)` `test_schema_aligns_with_code` `test_structural_hints(46)`
`test_pattern_learner(31)` `test_signal_classify_yaml` `test_protocol_json_output` `test_schema`

### 2.8 真实项目/开源验证

`test_open_source_validation` `test_cdc_risk_open_source(5 projects)` `test_dataflow_*_open_source`
`test_opentitan_*(4个)` `test_benchmark_picorv32` `test_benchmark_regression` `test_benchmark_pr5`
`test_subfunction_golden_open_source` `test_real_project_viz` `test_ventus_all_viz_validation`
`test_ventus_chunk_filelist` `test_ventus_viz_validation`

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

---

## 三、关键测试集 (按运行命令分组)

| 命令 | 范围 | 角色 | 基线状态 (沙箱) |
|---|---|---|---|
| `pytest sim/tests/unit sim/tests/cli` | 142+46 | **主回归** | 1435 passed + 24 failed (沙箱 cache artifact) |
| `pytest sim/tests/integration` | 53 文件 | 集成 | 406 passed + 13 failed (既有) |
| `pytest sim/tests/test_case27_1to1_truth.py` | truth | **1:1 truth (SVG 断言)** | 4 passed |
| `pytest sim/tests/regression` | 90 文件 | 语法金标准 | — |
| `pytest sim/tests/usage` | 10 文件 | 真实项目 (慢) | — |

---

## 四、值得注意的观察 (供筛选)

1. **removed_features 11 文件 236 测试全 skip** — V6.9 移除功能的尸体, 建议核实是否可删
2. **sim/ 根 3 个 golden 孤儿** — 不在收集范围, 与现有测试重复风险
3. **usage/ 有 4 个 [skipif/slow]** (coverage_gen_sv_compile 等) — 慢测试, CI 是否跑?
4. **大量无 docstring 文件** (regression 语法类) — 靠文件名定位用途
5. **truth 层仅 1 个文件** (case27 SVG 断言) — 覆盖面窄, 可扩展
6. **脚本式 QA** (docs/openchip_qa_test.py, scripts/debug/*) 非 pytest 正式测试
