# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-04 21:12:27",
  "passed": 28,
  "failed": 0,
  "skipped": 0,
  "total": 28
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 28
- **失败**: 0
- **跳过**: 0
- **总计**: 28
- **时间**: 2026-07-04 21:12:27

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p1_latency_sync_fifo_2_cycle_push_to_pop` | 0.411s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p2_latency_prim_arbiter_tree_0_cycle_combinational` | 0.318s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p3_latency_cva6_alu_0_cycle_combinational` | 10.560s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p4_latency_darkriscv_1_cycle_id_ex` | 0.323s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_p5_latency_stage_breakdown_sync_fifo` | 0.213s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n1_latency_two_flop_sync_async_crossing` | 0.225s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_n2_latency_nonexistent_signal_error` | 0.201s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_golden_latency_sync_fifo` | 0.213s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_ifpc_to_iaddr_combinational` | 0.319s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata1_to_idata2_id_stage` | 0.320s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_darkriscv_idata2_to_xidata_id_ex` | 0.318s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_arbiter_combinational` | 0.321s |
| ✅ | `integration/test_dataflow_latency_open_source.py::test_real_opentitan_prim_fifo_sync_passthrough` | 0.239s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p1_cdc_axi_cdc_src_2_high_risk_paths` | 0.270s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p2_cdc_axi_xbar_2_cdc_paths` | 0.254s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p3_cdc_tlul_4_domains_0_cdc` | 0.453s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p4_cdc_prim_arbiter_single_domain` | 0.316s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p5_cdc_summary_mode` | 0.270s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n1_cdc_nonexistent_file` | 0.270s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n2_cdc_strict_uart_4_high_risk` | 0.233s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p6_risk_strict_uart_8_critical_5_high` | 0.230s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p7_risk_prim_arbiter_10_critical_9_high` | 0.346s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p8_risk_axi_cdc_src` | 0.275s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_p9_risk_summary_mode` | 0.337s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n3_risk_nonexistent_file` | 0.237s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_n4_risk_broken_sv_no_strict` | 0.450s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_cdc_axi_cdc_src` | 0.270s |
| ✅ | `integration/test_cdc_risk_open_source.py::test_golden_risk_strict_uart` | 0.231s |

---
*此报告由 pytest 自动生成*