# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-04 00:39:54",
  "passed": 26,
  "failed": 0,
  "skipped": 0,
  "total": 26
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 26
- **失败**: 0
- **跳过**: 0
- **总计**: 26
- **时间**: 2026-07-04 00:39:54

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_trace_batch.py::test_p1_single_signal_backward_compat` | 0.320s |
| ✅ | `cli/test_trace_batch.py::test_p2_batch_inline_multiple_signals` | 0.230s |
| ✅ | `cli/test_trace_batch.py::test_p3_batch_file_with_comments_and_dedup` | 0.231s |
| ✅ | `cli/test_trace_batch.py::test_p4_positional_plus_batch_mix` | 0.231s |
| ✅ | `cli/test_trace_batch.py::test_p5_text_output_batch_header` | 0.230s |
| ✅ | `cli/test_trace_batch.py::test_p6_all_4_subcommands_support_batch` | 0.938s |
| ✅ | `cli/test_trace_batch.py::test_n1_no_signal_any_source` | 0.177s |
| ✅ | `cli/test_trace_batch.py::test_n2_batch_file_not_found` | 0.176s |
| ✅ | `cli/test_trace_batch.py::test_n3_batch_file_only_comments` | 0.177s |
| ✅ | `cli/test_trace_batch.py::test_n4_batch_empty_string` | 0.176s |
| ✅ | `cli/test_trace_batch.py::test_n5_nonexistent_signal_silent` | 0.232s |
| ✅ | `cli/test_trace_batch.py::test_golden_batch_fanin_2_signals` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p1_type_filter` | 0.233s |
| ✅ | `cli/test_trace_filters.py::test_p2_module_glob` | 0.233s |
| ✅ | `cli/test_trace_filters.py::test_p3_width_min` | 0.233s |
| ✅ | `cli/test_trace_filters.py::test_p4_width_max` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p5_exclude_glob` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p6_combined_filters` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p7_filter_with_batch` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p8_fanout_also_supports_filters` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p9_module_field_in_json` | 0.233s |
| ✅ | `cli/test_trace_filters.py::test_n1_type_no_match` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_n2_module_glob_no_match` | 0.233s |
| ✅ | `cli/test_trace_filters.py::test_n3_width_min_greater_than_max` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_n4_exclude_excludes_everything` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_golden_filter_type_and_width` | 0.235s |

---
*此报告由 pytest 自动生成*