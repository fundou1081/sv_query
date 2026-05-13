# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-13 13:54:32",
  "passed": 37,
  "failed": 0,
  "skipped": 0,
  "total": 37
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 37
- **失败**: 0
- **跳过**: 0
- **总计**: 37
- **时间**: 2026-05-13 13:54:32

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `unit/test_clock_domain.py::TestClockDomain::test_clock_detection` | 0.008s |
| ✅ | `unit/test_clock_domain.py::TestClockDomain::test_single_clock_domain` | 0.008s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_edge_creation` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_edge_kind_enum` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_add_edge` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_add_node` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_get_edge` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_get_node` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_node_creation` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_node_kind_enum` | 0.000s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_generate_block_no_crash` | 0.012s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_generate_with_parameterized_module` | 0.018s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_get_instance_after_generate` | 0.012s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_if_generate_instance` | 0.011s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_loop_generate_instance` | 0.013s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_loop_generate_instance_with_clk_connection` | 0.019s |
| ✅ | `unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_nested_generate_block` | 0.017s |
| ✅ | `unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_comb` | 0.000s |
| ✅ | `unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_ff` | 0.000s |
| ✅ | `unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_latch` | 0.000s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_clean_name` | 0.000s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_always_blocks` | 0.000s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_assignments` | 0.001s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_module_name` | 0.000s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_modules` | 0.000s |
| ✅ | `unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_port_names` | 0.000s |
| ✅ | `unit/test_query_load.py::TestLoadTracer::test_get_loads_api` | 0.007s |
| ✅ | `unit/test_query_load.py::TestLoadTracer::test_multi_load` | 0.011s |
| ✅ | `unit/test_query_load.py::TestLoadTracer::test_no_load` | 0.007s |
| ✅ | `unit/test_query_load.py::TestLoadTracer::test_simple_chain` | 0.009s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_assign_continous_drivers` | 0.005s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_assign_continous_loads` | 0.005s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_confidence_high_when_drivers_found` | 0.005s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_confidence_uncertain_when_no_drivers` | 0.005s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_input_port_is_driver_source` | 0.005s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_multiple_signals` | 0.006s |
| ✅ | `unit/test_signal_tracer.py::TestSignalTracer::test_signal_chain_has_root` | 0.005s |

---
*此报告由 pytest 自动生成*