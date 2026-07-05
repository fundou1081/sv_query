# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-05 10:17:05",
  "passed": 63,
  "failed": 0,
  "skipped": 0,
  "total": 63
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 63
- **失败**: 0
- **跳过**: 0
- **总计**: 63
- **时间**: 2026-07-05 10:17:05

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p1_latency_sync_fifo_2_cycle_push_to_pop` | 0.294s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p2_latency_prim_arbiter_tree_0_cycle_combinational` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p3_latency_cva6_alu_0_cycle_combinational` | 10.696s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p4_latency_darkriscv_1_cycle_id_ex` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p5_latency_stage_breakdown_sync_fifo` | 0.212s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n1_latency_two_flop_sync_async_crossing` | 0.224s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n2_latency_nonexistent_signal_error` | 0.202s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_golden_latency_sync_fifo` | 0.214s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_ifpc_to_iaddr_combinational` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata1_to_idata2_id_stage` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata2_to_xidata_id_ex` | 0.323s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_arbiter_combinational` | 0.324s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_fifo_sync_passthrough` | 0.236s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_a-typo4.in_a-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions0]` | 0.209s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_b-typo4.in_b-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions1]` | 0.208s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_c-typo4.in_c-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions2]` | 0.207s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_d-typo4.in_d-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions3]` | 0.207s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[nested_not2_in_b-nested_not2.in_b-nested_not2.out_o-/tmp/cdc_test/nested_not2.sv-expected_conditions4]` | 0.205s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[nested_not2_in_c-nested_not2.in_c-nested_not2.out_o-/tmp/cdc_test/nested_not2.sv-expected_conditions5]` | 0.204s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_a-typo3.in_a-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions6]` | 0.205s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_b-typo3.in_b-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions7]` | 0.204s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_c-typo3.in_c-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions8]` | 0.204s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_deep_chain_stability` | 1.068s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_simple_if` | 0.231s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_case` | 0.231s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_ternary` | 0.229s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_nested_4_levels` | 0.229s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_compound_in_a` | 0.230s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_compound_in_b` | 0.232s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_comp_compound_in_c` | 0.231s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_edge2_case_inside_if` | 0.227s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_edge2_if_inside_case` | 0.227s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo3_in_a` | 0.213s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo3_in_b` | 0.243s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo3_in_c` | 0.206s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo4_in_a` | 0.210s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo4_in_b` | 0.208s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo4_in_c` | 0.232s |
| ✅ | `integration/test_dataflow_else_if_comprehensive.py::test_typo4_in_d` | 0.223s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p1_cdc_axi_cdc_src_2_high_risk_paths` | 0.268s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p2_cdc_axi_xbar_2_cdc_paths` | 0.254s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p3_cdc_tlul_4_domains_0_cdc` | 0.443s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p4_cdc_prim_arbiter_single_domain` | 0.314s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p5_cdc_summary_mode` | 0.270s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n1_cdc_nonexistent_file` | 0.290s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n2_cdc_strict_uart_4_high_risk` | 0.230s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p6_risk_strict_uart_8_critical_5_high` | 0.229s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p7_risk_prim_arbiter_10_critical_9_high` | 0.337s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p8_risk_axi_cdc_src` | 0.273s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p9_risk_summary_mode` | 0.337s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n3_risk_nonexistent_file` | 0.237s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n4_risk_broken_sv_no_strict` | 0.447s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_cdc_axi_cdc_src` | 0.269s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_risk_strict_uart` | 0.236s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_in0` | 0.217s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_in1` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_in2` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_in3` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_in4` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_priority_out_d_double_else_if` | 0.000s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_stability[0]` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_stability[1]` | 0.215s |
| ✅ | `integration/test_dataflow_golden.py::test_golden_mux5_stability[2]` | 0.216s |

---
*此报告由 pytest 自动生成*