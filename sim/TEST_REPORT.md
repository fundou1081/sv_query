# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-06-25 21:14:57",
  "passed": 17,
  "failed": 0,
  "skipped": 0,
  "total": 17
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 17
- **失败**: 0
- **跳过**: 0
- **总计**: 17
- **时间**: 2026-06-25 21:14:57

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.375s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.276s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 1.105s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.347s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 1.202s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 1.196s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 1.197s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.301s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.363s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 1.203s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.363s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.518s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.149s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |

---
*此报告由 pytest 自动生成*