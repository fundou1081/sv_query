# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-18 07:57:43",
  "passed": 102,
  "failed": 0,
  "skipped": 0,
  "total": 102
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 102
- **失败**: 0
- **跳过**: 0
- **总计**: 102
- **时间**: 2026-05-18 07:57:43

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_complex_expression` | 0.108s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_divide_expression` | 0.046s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_grouped_expression` | 0.046s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_literal_only` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_modulo_expression` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_multiply_expression` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_param_referencing_param` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_simple_param` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_subtract_expression` | 0.045s |
| ✅ | `tests/unit/test_ast_expression_evaluator.py::TestASTExpressionEvaluator::test_unresolvable_param` | 0.045s |
| ✅ | `tests/unit/test_clock_domain.py::TestClockDomain::test_clock_detection` | 0.009s |
| ✅ | `tests/unit/test_clock_domain.py::TestClockDomain::test_single_clock_domain` | 0.008s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_instance_name_with_block_comment` | 0.062s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_instance_name_with_dangle_comment` | 0.053s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_instance_name_with_psum_comment` | 0.056s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_instance_name_with_single_line_comment` | 0.053s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_multiple_instances_mixed_comments` | 0.056s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_port_direction_with_leading_comment` | 0.052s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_port_direction_with_multiline_comment` | 0.052s |
| ✅ | `tests/unit/test_comment_handling.py::TestCommentHandling::test_port_direction_with_trailing_comment` | 0.051s |
| ✅ | `tests/unit/test_connection_tracing.py::TestConnectionTracing::test_multiple_instances` | 0.047s |
| ✅ | `tests/unit/test_connection_tracing.py::TestConnectionTracing::test_named_connection` | 0.053s |
| ✅ | `tests/unit/test_connection_tracing.py::TestConnectionTracing::test_named_only_connection` | 0.049s |
| ✅ | `tests/unit/test_connection_tracing.py::TestConnectionTracing::test_no_connection` | 0.046s |
| ✅ | `tests/unit/test_connection_tracing.py::TestConnectionTracing::test_positional_connection` | 0.050s |
| ✅ | `tests/unit/test_expression_evaluation.py::TestExpressionEvaluation::test_divide_expression` | 0.045s |
| ✅ | `tests/unit/test_expression_evaluation.py::TestExpressionEvaluation::test_literal_only` | 0.045s |
| ✅ | `tests/unit/test_expression_evaluation.py::TestExpressionEvaluation::test_missing_param_in_map` | 0.045s |
| ✅ | `tests/unit/test_expression_evaluation.py::TestExpressionEvaluation::test_simple_param_no_expression` | 0.045s |
| ✅ | `tests/unit/test_expression_evaluation.py::TestExpressionEvaluation::test_subtract_expression` | 0.045s |
| ✅ | `tests/unit/test_function_expression.py::TestFunctionExpression::test_binary_expression_in_function` | 0.015s |
| ✅ | `tests/unit/test_function_expression.py::TestFunctionExpression::test_function_call_drivers` | 0.012s |
| ✅ | `tests/unit/test_get_signal_identifier.py::TestGetSignalIdentifierName::test_identifier_name_without_leading_comment` | 0.022s |
| ✅ | `tests/unit/test_get_signal_identifier.py::TestGetSignalIdentifierName::test_all_signal_nodes_clean` | 0.021s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_edge_creation` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_edge_kind_enum` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_graph_add_edge` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_graph_add_node` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_graph_get_edge` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_graph_get_node` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_node_creation` | 0.000s |
| ✅ | `tests/unit/test_graph_models.py::TestGraphModels::test_node_kind_enum` | 0.000s |
| ✅ | `tests/unit/test_instance_name_extraction.py::TestInstanceNameExtraction::test_clacc_inverted_format` | 0.002s |
| ✅ | `tests/unit/test_instance_name_extraction.py::TestInstanceNameExtraction::test_clacc_with_comment` | 0.001s |
| ✅ | `tests/unit/test_instance_name_extraction.py::TestInstanceNameExtraction::test_hierarchical_instance_support` | 0.002s |
| ✅ | `tests/unit/test_instance_name_extraction.py::TestInstanceNameExtraction::test_instance_no_duplicate` | 0.001s |
| ✅ | `tests/unit/test_instance_name_extraction.py::TestInstanceNameExtraction::test_standard_format` | 0.001s |
| ✅ | `tests/unit/test_issue21_parameter_expression.py::TestIssue21ParameterExpression::test_parameter_expression_in_function_bit_select` | 0.013s |
| ✅ | `tests/unit/test_issue21_parameter_expression.py::TestIssue21ParameterExpression::test_parameter_expression_in_internal_signal` | 0.015s |
| ✅ | `tests/unit/test_issue21_parameter_expression.py::TestIssue21ParameterExpression::test_parameter_expression_in_node_name` | 0.011s |
| ✅ | `tests/unit/test_issue33_literal_edge.py::TestIssue33LiteralEdge::test_literal_edge_no_module_prefix` | 0.011s |
| ✅ | `tests/unit/test_issue33_literal_edge.py::TestIssue33LiteralEdge::test_no_literal_node_created` | 0.011s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_generate_block_no_crash` | 0.013s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_generate_with_parameterized_module` | 0.020s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_get_instance_after_generate` | 0.012s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_if_generate_instance` | 0.012s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_loop_generate_instance` | 0.014s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_loop_generate_instance_with_clk_connection` | 0.021s |
| ✅ | `tests/unit/test_mig_generate_block.py::TestMIGGenerateBlock::test_nested_generate_block` | 0.018s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_ansi_still_works` | 0.000s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_comma_separated_direction_inheritance` | 0.000s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_mixed_port_declaration` | 0.000s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_non_ansi_basic` | 0.001s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_non_ansi_no_ports` | 0.000s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_non_ansi_param_width` | 0.000s |
| ✅ | `tests/unit/test_non_ansi_port.py::TestNonAnsiPortDeclaration::test_non_ansi_with_direction` | 0.000s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_chained_param_references` | 0.046s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_param_referencing_complex_expr` | 0.045s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_param_referencing_divide` | 0.045s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_param_referencing_in_width` | 0.045s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_param_referencing_param_simple` | 0.045s |
| ✅ | `tests/unit/test_param_expression_resolution.py::TestParamExpressionResolution::test_param_referencing_subtract` | 0.045s |
| ✅ | `tests/unit/test_parameter_extraction.py::TestParameterExtraction::test_cva6_parameter` | 0.045s |
| ✅ | `tests/unit/test_parameter_extraction.py::TestParameterExtraction::test_localparam` | 0.045s |
| ✅ | `tests/unit/test_parameter_extraction.py::TestParameterExtraction::test_multiple_parameters` | 0.045s |
| ✅ | `tests/unit/test_parameter_extraction.py::TestParameterExtraction::test_no_parameters` | 0.045s |
| ✅ | `tests/unit/test_parameter_extraction.py::TestParameterExtraction::test_simple_parameter` | 0.045s |
| ✅ | `tests/unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_comb` | 0.000s |
| ✅ | `tests/unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_ff` | 0.000s |
| ✅ | `tests/unit/test_procedural_blocks.py::TestProceduralBlocks::test_detect_always_latch` | 0.000s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_clean_name` | 0.000s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_always_blocks` | 0.000s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_assignments` | 0.001s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_module_name` | 0.000s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_modules` | 0.000s |
| ✅ | `tests/unit/test_pyslang_adapter.py::TestPyslangAdapter::test_get_port_names` | 0.000s |
| ✅ | `tests/unit/test_query_load.py::TestLoadTracer::test_get_loads_api` | 0.008s |
| ✅ | `tests/unit/test_query_load.py::TestLoadTracer::test_multi_load` | 0.012s |
| ✅ | `tests/unit/test_query_load.py::TestLoadTracer::test_no_load` | 0.007s |
| ✅ | `tests/unit/test_query_load.py::TestLoadTracer::test_simple_chain` | 0.010s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_assign_continous_drivers` | 0.006s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_assign_continous_loads` | 0.005s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_confidence_high_when_drivers_found` | 0.006s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_confidence_uncertain_when_no_drivers` | 0.006s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_input_port_is_driver_source` | 0.006s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_multiple_signals` | 0.007s |
| ✅ | `tests/unit/test_signal_tracer.py::TestSignalTracer::test_signal_chain_has_root` | 0.005s |
| ✅ | `tests/unit/test_width_extraction.py::TestWidthExtraction::test_complex_param_expression` | 0.047s |
| ✅ | `tests/unit/test_width_extraction.py::TestWidthExtraction::test_literal_width` | 0.045s |
| ✅ | `tests/unit/test_width_extraction.py::TestWidthExtraction::test_multiple_widths` | 0.045s |
| ✅ | `tests/unit/test_width_extraction.py::TestWidthExtraction::test_parameterized_width` | 0.047s |
| ✅ | `tests/unit/test_width_extraction.py::TestWidthExtraction::test_simple_param_width` | 0.049s |

---
*此报告由 pytest 自动生成*