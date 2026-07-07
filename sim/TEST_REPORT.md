# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-07 22:06:12",
  "passed": 42,
  "failed": 0,
  "skipped": 0,
  "total": 42
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 42
- **失败**: 0
- **跳过**: 0
- **总计**: 42
- **时间**: 2026-07-07 22:06:12

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_class_filter` | 0.229s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_class_filter_empty` | 0.183s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_distinguishes_rand_randc` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_calls` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_hooks` | 0.185s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_rand_vars` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_help` | 0.242s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_json_content` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_json_output` | 0.183s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_class_filter` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_finds_inline_constraints` | 0.183s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_help` | 0.215s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_json_output` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_target` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeEmptyFile::test_randomize_extract_on_empty` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeEmptyFile::test_randomize_list_on_empty` | 0.182s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_extracts_inline_constraint` | 0.188s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_finds_calls` | 0.187s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_finds_hooks` | 0.188s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_help` | 0.217s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_json_output` | 0.187s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_json_randomize_calls` | 0.187s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_no_strict` | 0.187s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_summary_line` | 0.189s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_unknown_class` | 0.186s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceNoRandomize::test_trace_no_randomize` | 0.186s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_detects_alive` | 0.197s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_detects_dead` | 0.192s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_help` | 0.218s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_content_dead` | 0.190s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_content_driver` | 0.199s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_output` | 0.191s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_unknown_class` | 0.181s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_randomized_in` | 0.196s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_summary` | 0.198s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_unknown_class` | 0.183s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestArrayOrRandomizeMethodExpression::test_randomize_no_crash` | 0.006s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestArrayOrRandomizeMethodExpression::test_randomize_with_inline_constraint_no_crash` | 0.003s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestArrayOrRandomizeMethodExpression::test_randomize_in_foreach_no_crash` | 0.004s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestArrayOrRandomizeMethodExpression::test_randomize_with_inline_constraint_extracts_signals` | 0.007s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestRandomizeSmokeTest::test_complex_sequence_with_randomize` | 0.003s |
| ✅ | `unit/test_operator_visitor_randomize.py::TestRandomizeSmokeTest::test_randomize_return_value_no_crash` | 0.003s |

---
*此报告由 pytest 自动生成*