# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-06-25 23:43:05",
  "passed": 30,
  "failed": 0,
  "skipped": 0,
  "total": 30
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 30
- **失败**: 0
- **跳过**: 0
- **总计**: 30
- **时间**: 2026-06-25 23:43:05

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.322s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.269s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 1.071s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.344s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 1.137s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 1.187s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 1.180s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.302s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.363s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 1.186s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.358s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.421s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.002s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |
| ✅ | `unit/test_mig_validator.py::TestCompareWithExtract::test_simple_compare_runs` | 0.011s |
| ✅ | `unit/test_mig_validator.py::TestCompareWithExtract::test_simple_no_utility_cells` | 0.008s |
| ✅ | `unit/test_mig_validator.py::TestVerifySpecificPort::test_simple_verify_existing_port` | 0.004s |
| ✅ | `unit/test_mig_validator.py::TestVerifySpecificPort::test_simple_verify_nonexistent_port` | 0.004s |
| ✅ | `unit/test_native_adapter_parity.py::TestOldImplementationBaseline::test_get_module_instances_returns_list` | 0.005s |
| ✅ | `unit/test_native_adapter_parity.py::TestOldImplementationBaseline::test_simple_module_count` | 0.005s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAPI::test_instance_body_iterable` | 0.004s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAPI::test_instance_hierarchical_path` | 0.004s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAPI::test_topInstances_present` | 0.004s |
| ✅ | `unit/test_native_adapter_parity.py::TestPerformanceComparison::test_perf_informational` | 0.006s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAdapterParity::test_generate_block_parity` | 0.011s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAdapterParity::test_multi_depth_parity` | 0.009s |
| ✅ | `unit/test_native_adapter_parity.py::TestNativeAdapterParity::test_simple_parity` | 0.009s |

---
*此报告由 pytest 自动生成*