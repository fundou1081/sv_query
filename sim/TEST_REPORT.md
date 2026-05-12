# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-12 10:15:10",
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
- **时间**: 2026-05-12 10:15:10

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `regression/test_composition_chain.py::TestCompositionChainBasic::test_array_composition` | 0.003s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainBasic::test_composition_with_other_properties` | 0.003s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainBasic::test_single_composition` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainNegative::test_empty_class_no_crash` | 0.001s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainNegative::test_int_type_no_inst_edge` | 0.003s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainMultiLevel::test_two_level_composition` | 0.003s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_inside_constraint` | 0.004s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_with_associative_array` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_with_constraint` | 0.004s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_with_inheritance` | 0.004s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_with_member_instance` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_composition_with_queue` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_different_types_composition` | 0.005s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_multi_declarator_with_composition` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_multiple_composition_same_level` | 0.003s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainComplex::test_three_level_composition` | 0.004s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainEdgeCases::test_class_with_only_composition_no_rand` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainEdgeCases::test_composition_byte_vector` | 0.002s |
| ✅ | `regression/test_composition_chain.py::TestCompositionChainEdgeCases::test_composition_logic_vector` | 0.003s |
| ✅ | `regression/test_constraint_override.py::TestConstraintSuperCall::test_multi_level_super_call` | 0.005s |
| ✅ | `regression/test_constraint_override.py::TestConstraintSuperCall::test_no_super_call_replacement` | 0.003s |
| ✅ | `regression/test_constraint_override.py::TestConstraintSuperCall::test_single_super_call` | 0.003s |
| ✅ | `regression/test_constraint_override.py::TestConstraintSuperCall::test_two_super_calls` | 0.004s |
| ✅ | `regression/test_constraint_override.py::TestConstraintOverrideNegative::test_no_inheritance_no_super_crash` | 0.002s |
| ✅ | `regression/test_constraint_override.py::TestConstraintOverrideNegative::test_nonexistent_parent_constraint` | 0.003s |
| ✅ | `regression/test_constraint_override.py::TestConstraintOverrideComplex::test_super_call_with_conditional` | 0.003s |
| ✅ | `regression/test_constraint_override.py::TestConstraintOverrideComplex::test_super_call_with_implication` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintClassPropertyNodes::test_class_node_exists` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintClassPropertyNodes::test_multi_declarator_variables` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintClassPropertyNodes::test_non_rand_variable_nodes` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintClassPropertyNodes::test_rand_variable_nodes` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintBlockNodes::test_constraint_block_node` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintBlockNodes::test_multiple_constraint_blocks` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintExprNodes::test_expression_constraint_node` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintExprNodes::test_implication_constraint_node` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintIfNodes::test_if_constraint_node` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintIfNodes::test_nested_if_constraint_nodes` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintEdges::test_class_to_property_edges` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintEdges::test_constraint_block_constrains_edges` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintEdges::test_if_has_alternate_edge` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintEdges::test_if_has_condition_edge` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintEdges::test_if_has_consequent_edge` | 0.003s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_add` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_complex` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_div` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_mixed` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_mod` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_mul` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_arithmetic_sub` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_array_index_const` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_array_index_var` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_array_inside` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_array_inside_in_if` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_array_multi_dim` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_bitwise_and` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_bitwise_not` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_bitwise_or` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_bitwise_xor` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_eq` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_ge` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_gt` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_le` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_lt` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_cmp_ne` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_complex_arith_logic` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_deep_parens` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_dist_in_implication` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_dist_simple` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_dist_with_range` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_empty_constraint_block` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_foreach_multiple_arrays` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_foreach_single_dim` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_foreach_two_dim` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_if_else_chain` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_if_with_dist` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_implication_simple` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_implication_with_expr` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_inside_simple` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_inside_with_range_vars` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_logical_and` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_logical_mixed` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_logical_not` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_logical_or` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_nested_if_three_levels` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_nested_if_two_levels` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_nested_if_with_else` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_nested_parens` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_parens_in_condition` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_shift_arith_left` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_shift_arith_right` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_shift_by_var` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_shift_left` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_shift_right` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_solve_before_simple` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_ternary` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_ternary_nested` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintVariableExtraction::test_unique_simple` | 0.000s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintNegativeCases::test_constraint_with_only_comments` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintNegativeCases::test_empty_class_no_crash` | 0.001s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintNegativeCases::test_empty_constraint_block_no_crash` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintNegativeCases::test_multiple_empty_constraints` | 0.002s |
| ✅ | `regression/test_constraint_complete.py::TestConstraintNegativeCases::test_no_constraint_class_no_crash` | 0.001s |

---
*此报告由 pytest 自动生成*