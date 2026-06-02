# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-06-02 10:01:53",
  "passed": 59,
  "failed": 0,
  "skipped": 0,
  "total": 59
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 59
- **失败**: 0
- **跳过**: 0
- **总计**: 59
- **时间**: 2026-06-02 10:01:53

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `unit/test_coverage_generator.py::TestSourceLocation::test_create_full` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceLocation::test_create_minimal` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceLocation::test_is_empty` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceLocation::test_str_returns_location` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceSnippet::test_create_empty` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceSnippet::test_lazy_load_caches` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceSnippet::test_lazy_load_with_provider` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestSourceSnippet::test_with_text` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestEvidenceStep::test_create_minimal` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestEvidenceStep::test_str_returns_description` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestAtomicSignal::test_create_simple` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestAtomicSignal::test_create_with_bit_range` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestAtomicSignal::test_evidence_preserved` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestAtomicSignal::test_str_returns_name` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompositionResult::test_create_minimal` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompositionResult::test_str_returns_summary` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompositionResult::test_truncated_flag` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDataModelIntegration::test_full_chain` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_comparison` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_compound` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_empty_string` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_filters_binary_literals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_filters_decimal_literals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_filters_literals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_multiple_bit_ranges` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_nested_bit` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_not_operator` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_only_literal` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_parenthesized` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_simple_and` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_simple_or` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_ternary` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_underscore_name` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestExpressionParser::test_parse_with_bit_range` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestIsModulePort::test_port_in_node` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestIsModulePort::test_reg_node` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestIsModulePort::test_signal_node` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_at_port` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_avoids_cycle` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_leaf_port` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_no_driver` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_respects_max_depth` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestTraceDrivers::test_trace_drivers_simple` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestCollectConditionEdges::test_collect_empty_when_no_condition` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestCollectConditionEdges::test_collect_multiple_edges` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestCollectConditionEdges::test_collect_single_condition` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestCollectConditionEdges::test_collect_uses_effective_condition` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_collects_control_blocks` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_finds_atomic_signals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_returns_decomposition_result` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_returns_empty_for_unknown_signal` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_signal_count` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestDecompose::test_decompose_truncates_at_max_signals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_contains_atomic_signals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_contains_summary` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_contains_title` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_returns_string` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_with_no_signals` | 0.000s |
| ✅ | `unit/test_coverage_generator.py::TestMarkdownOutput::test_markdown_with_truncated` | 0.000s |

---
*此报告由 pytest 自动生成*