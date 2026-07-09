# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-09 17:14:26",
  "passed": 32,
  "failed": 0,
  "skipped": 0,
  "total": 32
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 32
- **失败**: 0
- **跳过**: 0
- **总计**: 32
- **时间**: 2026-07-09 17:14:26

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_visualize_latency_golden.py::TestChainLatencyGolden::test_branching_chain_has_total_cycles_1` | 0.412s |
| ✅ | `cli/test_visualize_latency_golden.py::TestChainLatencyGolden::test_deep_pipeline_shows_5_cycles` | 0.199s |
| ✅ | `cli/test_visualize_latency_golden.py::TestChainLatencyGolden::test_single_reg_chain_shows_1_cycle` | 0.200s |
| ✅ | `cli/test_visualize_latency_golden.py::TestChainLatencyGolden::test_two_parallel_chain_has_3_regs` | 0.196s |
| ✅ | `cli/test_visualize_latency_golden.py::TestChainLatencyGolden::test_two_reg_chain_shows_2_cycles` | 0.204s |
| ✅ | `cli/test_visualize_latency_golden.py::TestTraceLatencyGolden::test_trace_fanin_deep_pipeline_chain_drivers` | 0.217s |
| ✅ | `cli/test_visualize_latency_golden.py::TestTraceLatencyGolden::test_trace_fanin_single_reg_has_1_driver` | 0.210s |
| ✅ | `cli/test_visualize_latency_golden.py::TestTraceLatencyGolden::test_trace_fanout_branching_shows_2_loads` | 0.197s |
| ✅ | `cli/test_visualize_chain.py::TestChainCommandExists::test_visualize_chain_exists` | 0.255s |
| ✅ | `cli/test_visualize_chain.py::TestChainFromTo::test_chain_bram_din_to_crc_data` | 0.336s |
| ✅ | `cli/test_visualize_chain.py::TestChainAutoMode::test_chain_auto_mode` | 0.346s |
| ✅ | `cli/test_visualize_chain.py::TestChainLayout::test_chain_lr_neato_renders_square` | 0.530s |
| ✅ | `cli/test_visualize_chain.py::TestChainMaxEdges::test_chain_max_edges` | 0.353s |
| ✅ | `cli/test_visualize_chain.py::TestChainSubModuleClusters::test_chain_dot_distinguishes_input_output` | 1.062s |
| ✅ | `cli/test_visualize_chain.py::TestChainSubModuleClusters::test_chain_dot_has_subgraph_clusters` | 1.054s |
| ✅ | `cli/test_visualize_chain.py::TestChainSubModuleClusters::test_chain_dot_hierarchical_signal_ids` | 1.064s |
| ✅ | `cli/test_visualize_chain.py::TestChainCycleAnnotation::test_chain_dot_critical_path_red_color` | 1.071s |
| ✅ | `cli/test_visualize_chain.py::TestChainCycleAnnotation::test_chain_dot_cycle_count_matches_reg_chains` | 1.056s |
| ✅ | `cli/test_visualize_chain.py::TestChainCycleAnnotation::test_chain_dot_edge_increments_by_cycles` | 1.066s |
| ✅ | `cli/test_visualize_chain.py::TestChainCycleAnnotation::test_chain_dot_has_cycle_labels_on_reg_nodes` | 1.091s |
| ✅ | `cli/test_visualize_chain.py::TestChainCycleAnnotation::test_chain_dot_path_endpoints_show_total_cycles` | 1.063s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_basic` | 0.196s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_json` | 0.195s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_not_found` | 0.190s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_basic` | 0.195s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_json` | 0.193s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_trace_help` | 0.220s |
| ✅ | `cli/test_trace.py::TestTraceFaninDotOutput::test_trace_fanin_format_default_is_text` | 0.195s |
| ✅ | `cli/test_trace.py::TestTraceFaninDotOutput::test_trace_fanin_format_dot_basic` | 0.194s |
| ✅ | `cli/test_trace.py::TestTraceFaninDotOutput::test_trace_fanin_format_dot_has_cycle_labels` | 0.196s |
| ✅ | `cli/test_trace.py::TestTraceFaninDotOutput::test_trace_fanin_format_dot_reg_uses_thicker_border` | 0.194s |
| ✅ | `cli/test_trace.py::TestTraceFaninDotOutput::test_trace_fanout_format_dot_basic` | 0.195s |

---
*此报告由 pytest 自动生成*