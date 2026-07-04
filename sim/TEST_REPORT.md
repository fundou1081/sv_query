# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-05 00:23:46",
  "passed": 38,
  "failed": 0,
  "skipped": 0,
  "total": 38
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 38
- **失败**: 0
- **跳过**: 0
- **总计**: 38
- **时间**: 2026-07-05 00:23:46

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p1_latency_sync_fifo_2_cycle_push_to_pop` | 0.491s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p2_latency_prim_arbiter_tree_0_cycle_combinational` | 0.324s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p3_latency_cva6_alu_0_cycle_combinational` | 10.605s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p4_latency_darkriscv_1_cycle_id_ex` | 0.322s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p5_latency_stage_breakdown_sync_fifo` | 0.211s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n1_latency_two_flop_sync_async_crossing` | 0.224s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n2_latency_nonexistent_signal_error` | 0.207s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_golden_latency_sync_fifo` | 0.217s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_ifpc_to_iaddr_combinational` | 0.324s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata1_to_idata2_id_stage` | 0.321s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata2_to_xidata_id_ex` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_arbiter_combinational` | 0.329s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_fifo_sync_passthrough` | 0.236s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_a-typo4.in_a-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions0]` | 0.211s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_b-typo4.in_b-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions1]` | 0.207s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_c-typo4.in_c-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions2]` | 0.208s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo4_in_d-typo4.in_d-typo4.out_o-/tmp/cdc_test/typo4.sv-expected_conditions3]` | 0.208s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[nested_not2_in_b-nested_not2.in_b-nested_not2.out_o-/tmp/cdc_test/nested_not2.sv-expected_conditions4]` | 0.205s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[nested_not2_in_c-nested_not2.in_c-nested_not2.out_o-/tmp/cdc_test/nested_not2.sv-expected_conditions5]` | 0.214s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_a-typo3.in_a-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions6]` | 0.220s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_b-typo3.in_b-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions7]` | 0.207s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_chain_no_double_negation[typo3_in_c-typo3.in_c-typo3.out_o-/tmp/cdc_test/typo3.sv-expected_conditions8]` | 0.204s |
| ✅ | `integration/test_dataflow_else_if_typo.py::test_else_if_deep_chain_stability` | 1.037s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p1_cdc_axi_cdc_src_2_high_risk_paths` | 0.267s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p2_cdc_axi_xbar_2_cdc_paths` | 0.255s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p3_cdc_tlul_4_domains_0_cdc` | 0.446s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p4_cdc_prim_arbiter_single_domain` | 0.313s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p5_cdc_summary_mode` | 0.266s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n1_cdc_nonexistent_file` | 0.273s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n2_cdc_strict_uart_4_high_risk` | 0.228s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p6_risk_strict_uart_8_critical_5_high` | 0.231s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p7_risk_prim_arbiter_10_critical_9_high` | 0.338s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p8_risk_axi_cdc_src` | 0.273s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p9_risk_summary_mode` | 0.337s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n3_risk_nonexistent_file` | 0.236s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n4_risk_broken_sv_no_strict` | 0.450s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_cdc_axi_cdc_src` | 0.268s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_risk_strict_uart` | 0.232s |

---
*此报告由 pytest 自动生成*