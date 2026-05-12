# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-12 08:40:15",
  "passed": 230,
  "failed": 0,
  "skipped": 0,
  "total": 230
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 230
- **失败**: 0
- **跳过**: 0
- **总计**: 230
- **时间**: 2026-05-12 08:40:15

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `unit/test_clock_domain.py::TestClockDomain::test_clock_detection` | 0.008s |
| ✅ | `unit/test_clock_domain.py::TestClockDomain::test_single_clock_domain` | 0.007s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_edge_creation` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_edge_kind_enum` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_add_edge` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_add_node` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_get_edge` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_graph_get_node` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_node_creation` | 0.000s |
| ✅ | `unit/test_graph_models.py::TestGraphModels::test_node_kind_enum` | 0.000s |
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
| ✅ | `integration/test_advanced_grammar.py::TestForLoopExtraction::test_for_loop_in_always` | 0.014s |
| ✅ | `integration/test_advanced_grammar.py::TestForLoopExtraction::test_generate_for` | 0.009s |
| ✅ | `integration/test_advanced_grammar.py::TestProceduralTimingExtraction::test_always_begin_end` | 0.008s |
| ✅ | `integration/test_advanced_grammar.py::TestProceduralTimingExtraction::test_wait` | 0.004s |
| ✅ | `integration/test_advanced_grammar.py::TestClockingBlockExtraction::test_clocking_block` | 0.006s |
| ✅ | `integration/test_advanced_grammar.py::TestSequencePropertyExtraction::test_property` | 0.004s |
| ✅ | `integration/test_advanced_grammar.py::TestSequencePropertyExtraction::test_sequence` | 0.003s |
| ✅ | `integration/test_advanced_syntax.py::TestParameterExtraction::test_localparam` | 0.006s |
| ✅ | `integration/test_advanced_syntax.py::TestParameterExtraction::test_parameterized_width` | 0.009s |
| ✅ | `integration/test_advanced_syntax.py::TestArrayExtraction::test_array_assignment` | 0.008s |
| ✅ | `integration/test_advanced_syntax.py::TestArrayExtraction::test_array_index` | 0.007s |
| ✅ | `integration/test_advanced_syntax.py::TestBitSelectExtraction::test_range_select` | 0.006s |
| ✅ | `integration/test_advanced_syntax.py::TestBitSelectExtraction::test_single_bit` | 0.006s |
| ✅ | `integration/test_advanced_syntax.py::TestSystemFunctionExtraction::test_system_function` | 0.004s |
| ✅ | `integration/test_advanced_syntax.py::TestSystemFunctionExtraction::test_time_function` | 0.004s |
| ✅ | `integration/test_advanced_syntax.py::TestCrossModuleExtraction::test_simple_instance` | 0.012s |
| ✅ | `integration/test_advanced_syntax.py::TestCrossModuleExtraction::test_two_instance` | 0.015s |
| ✅ | `integration/test_aliases.py::TestAliases::test_alias` | 0.005s |
| ✅ | `integration/test_aliases.py::TestAliases::test_covergroup` | 0.009s |
| ✅ | `integration/test_aliases.py::TestAliases::test_typedef_enum` | 0.005s |
| ✅ | `integration/test_aliases.py::TestAliases::test_typedef_struct` | 0.005s |
| ✅ | `integration/test_assign_chain.py::TestAssignChain::test_assign_to_assign_chain` | 0.007s |
| ✅ | `integration/test_assign_chain.py::TestAssignChain::test_fanout_chain` | 0.009s |
| ✅ | `integration/test_assign_chain.py::TestAssignChain::test_three_stage_chain` | 0.008s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_negative_index` | 0.006s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_out_of_bounds` | 0.006s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_range_select` | 0.007s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_reverse_range` | 0.007s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_single_bit_select` | 0.006s |
| ✅ | `integration/test_bit_select.py::TestBitSelect::test_vector_to_vector` | 0.009s |
| ✅ | `integration/test_branch_chain.py::TestBranchChain::test_if_else_chain` | 0.015s |
| ✅ | `integration/test_branch_chain.py::TestBranchChain::test_if_nested` | 0.014s |
| ✅ | `integration/test_branch_chain.py::TestBranchChain::test_if_no_else` | 0.009s |
| ✅ | `integration/test_branch_chain.py::TestBranchChain::test_if_only_constant` | 0.008s |
| ✅ | `integration/test_branch_chain.py::TestBranchChain::test_if_single_branch` | 0.011s |
| ✅ | `integration/test_case_stmt.py::TestCaseStmt::test_case_simple` | 0.013s |
| ✅ | `integration/test_case_stmt.py::TestCaseStmt::test_casex` | 0.009s |
| ✅ | `integration/test_case_stmt.py::TestCaseStmt::test_casez` | 0.009s |
| ✅ | `integration/test_case_stmt.py::TestCaseStmt::test_priority_case` | 0.013s |
| ✅ | `integration/test_case_stmt.py::TestCaseStmt::test_unique_case` | 0.015s |
| ✅ | `integration/test_cdc.py::TestCDC::test_async_reset_considered` | 0.011s |
| ✅ | `integration/test_cdc.py::TestCDC::test_dual_clock_domains` | 0.013s |
| ✅ | `integration/test_cdc.py::TestCDC::test_no_clock` | 0.005s |
| ✅ | `integration/test_cdc.py::TestCDC::test_single_clock_domain` | 0.007s |
| ✅ | `integration/test_cdc_multiclock.py::TestCDCMultiClock::test_clock_domain_traces_all_domains` | 0.016s |
| ✅ | `integration/test_cdc_multiclock.py::TestCDCMultiClock::test_single_register_no_cdc_violation` | 0.011s |
| ✅ | `integration/test_cdc_multiclock.py::TestCDCMultiClock::test_two_independent_clock_domains` | 0.021s |
| ✅ | `integration/test_clock_edge.py::TestClockEdge::test_always_comb_no_clock_edge` | 0.006s |
| ✅ | `integration/test_clock_edge.py::TestClockEdge::test_always_ff_clock_edge` | 0.007s |
| ✅ | `integration/test_clock_edge.py::TestClockEdge::test_multiple_clock_domains` | 0.012s |
| ✅ | `integration/test_clock_reset_timing.py::TestClockEdge::test_clock_edge_both_edge` | 0.008s |
| ✅ | `integration/test_clock_reset_timing.py::TestClockEdge::test_clock_edge_negedge` | 0.007s |
| ✅ | `integration/test_clock_reset_timing.py::TestClockEdge::test_clock_edge_posedge` | 0.007s |
| ✅ | `integration/test_clock_reset_timing.py::TestResetEdge::test_async_reset_negedge` | 0.008s |
| ✅ | `integration/test_clock_reset_timing.py::TestResetEdge::test_async_reset_posedge` | 0.008s |
| ✅ | `integration/test_clock_reset_timing.py::TestTimingControl::test_delay_control` | 0.007s |
| ✅ | `integration/test_clock_reset_timing.py::TestTimingControl::test_event_control` | 0.007s |
| ✅ | `integration/test_clock_reset_timing.py::TestTimingControl::test_wait_control` | 0.007s |
| ✅ | `integration/test_clock_reset_timing.py::TestMultiClockDomain::test_clock_domain_cdc` | 0.011s |
| ✅ | `integration/test_clock_reset_timing.py::TestMultiClockDomain::test_dual_clock_independent` | 0.012s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_basic` | 0.007s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_empty_block` | 0.005s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_invalid_module` | 0.005s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_invalid_signal` | 0.005s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_multiple_stmts` | 0.008s |
| ✅ | `integration/test_combo_chain.py::TestComboChain::test_combo_simple_assign` | 0.005s |
| ✅ | `integration/test_complex_conditions.py::TestNestedIfExtraction::test_if_with_else_if` | 0.013s |
| ✅ | `integration/test_complex_conditions.py::TestNestedIfExtraction::test_nested_if_three_levels` | 0.013s |
| ✅ | `integration/test_complex_conditions.py::TestNestedIfExtraction::test_nested_if_two_levels` | 0.013s |
| ✅ | `integration/test_complex_conditions.py::TestCaseStatementExtraction::test_case_priority` | 0.010s |
| ✅ | `integration/test_complex_conditions.py::TestCaseStatementExtraction::test_case_simple` | 0.009s |
| ✅ | `integration/test_complex_conditions.py::TestCaseStatementExtraction::test_case_unique` | 0.012s |
| ✅ | `integration/test_complex_conditions.py::TestMixedConditionsExtraction::test_case_inside_if` | 0.011s |
| ✅ | `integration/test_complex_conditions.py::TestMixedConditionsExtraction::test_if_case_mix` | 0.013s |
| ✅ | `integration/test_complex_conditions.py::TestMixedConditionsExtraction::test_multi_else_branch` | 0.013s |
| ✅ | `integration/test_complex_conditions.py::TestMixedConditionsExtraction::test_operator_in_condition` | 0.010s |
| ✅ | `integration/test_complex_conditions.py::TestComplexPatternExtraction::test_array_index_in_condition` | 0.009s |
| ✅ | `integration/test_complex_conditions.py::TestComplexPatternExtraction::test_shift_in_condition` | 0.009s |
| ✅ | `integration/test_complex_conditions.py::TestComplexPatternExtraction::test_ternary_in_if` | 0.011s |
| ✅ | `integration/test_complex_sequential.py::TestComplexSequential::test_ff_with_case` | 0.018s |
| ✅ | `integration/test_complex_sequential.py::TestComplexSequential::test_ff_with_disable` | 0.009s |
| ✅ | `integration/test_complex_sequential.py::TestComplexSequential::test_ff_with_forloop` | 0.014s |
| ✅ | `integration/test_complex_sequential.py::TestComplexSequential::test_ff_with_nested_if` | 0.017s |
| ✅ | `integration/test_complex_sequential.py::TestComplexSequential::test_ff_with_while` | 0.011s |
| ✅ | `integration/test_concat_and_hierarchy.py::TestConcatExtraction::test_concat_four_signals` | 0.009s |
| ✅ | `integration/test_concat_and_hierarchy.py::TestConcatExtraction::test_concat_two_signals` | 0.007s |
| ✅ | `integration/test_concat_and_hierarchy.py::TestConcatExtraction::test_replication` | 0.006s |
| ✅ | `integration/test_concat_and_hierarchy.py::TestMultiLevelExtraction::test_three_level_chain` | 0.008s |
| ✅ | `integration/test_concat_and_hierarchy.py::TestMultiLevelExtraction::test_two_level_chain` | 0.007s |
| ✅ | `integration/test_directives.py::TestDirectives::test_define` | 0.008s |
| ✅ | `integration/test_directives.py::TestDirectives::test_full_case` | 0.008s |
| ✅ | `integration/test_directives.py::TestDirectives::test_ifdef` | 0.005s |
| ✅ | `integration/test_directives.py::TestDirectives::test_ifndef` | 0.005s |
| ✅ | `integration/test_directives.py::TestDirectives::test_include` | 0.005s |
| ✅ | `integration/test_directives.py::TestDirectives::test_parallel_case` | 0.009s |
| ✅ | `integration/test_directives.py::TestDirectives::test_pragma` | 0.008s |
| ✅ | `integration/test_directives.py::TestDirectives::test_undef` | 0.005s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanin_clock_tree` | 0.005s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanin_multi_drivers` | 0.008s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanin_single_driver` | 0.005s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanout_instance_connection` | 0.012s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanout_no_loads` | 0.005s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanout_reg_q` | 0.007s |
| ✅ | `integration/test_fan_query.py::TestFanQuery::test_fanout_single_driver` | 0.007s |
| ✅ | `integration/test_functions.py::TestFunctions::test_function_recursive` | 0.015s |
| ✅ | `integration/test_functions.py::TestFunctions::test_function_simple` | 0.016s |
| ✅ | `integration/test_functions.py::TestFunctions::test_function_with_extends` | 0.012s |
| ✅ | `integration/test_functions.py::TestFunctions::test_static_function` | 0.012s |
| ✅ | `integration/test_functions.py::TestFunctions::test_task_simple` | 0.011s |
| ✅ | `integration/test_generate.py::TestGenerate::test_generate_case` | 0.010s |
| ✅ | `integration/test_generate.py::TestGenerate::test_generate_for` | 0.013s |
| ✅ | `integration/test_generate.py::TestGenerate::test_generate_if` | 0.007s |
| ✅ | `integration/test_generate.py::TestGenerate::test_generate_nested` | 0.011s |
| ✅ | `integration/test_hierarchy.py::TestHierarchy::test_deep_hierarchy` | 0.033s |
| ✅ | `integration/test_hierarchy.py::TestHierarchy::test_generate_instantiation` | 0.017s |
| ✅ | `integration/test_hierarchy.py::TestHierarchy::test_instantiation_array` | 0.024s |
| ✅ | `integration/test_hierarchy.py::TestHierarchy::test_module_with_generics` | 0.012s |
| ✅ | `integration/test_hierarchy.py::TestHierarchy::test_parameterized_module` | 0.018s |
| ✅ | `integration/test_instance_connection.py::TestInstanceConnection::test_instance_port_connection` | 0.012s |
| ✅ | `integration/test_instance_connection.py::TestInstanceConnection::test_multiple_instances` | 0.017s |
| ✅ | `integration/test_instance_connection.py::TestInstanceConnection::test_signal_trace_through_instance` | 0.012s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_array_of_instances` | 0.015s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_generate_instance` | 0.017s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_multi_instance` | 0.020s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_nested_instance` | 0.018s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_parameterized_instance` | 0.018s |
| ✅ | `integration/test_instance_hierarchy.py::TestInstanceHierarchy::test_single_instance` | 0.012s |
| ✅ | `integration/test_interfaces.py::TestInterfaces::test_interface_array` | 0.006s |
| ✅ | `integration/test_interfaces.py::TestInterfaces::test_interface_class` | 0.004s |
| ✅ | `integration/test_interfaces.py::TestInterfaces::test_interface_simple` | 0.005s |
| ✅ | `integration/test_interfaces.py::TestInterfaces::test_modport` | 0.007s |
| ✅ | `integration/test_latch.py::TestLatch::test_latch_basic` | 0.007s |
| ✅ | `integration/test_latch.py::TestLatch::test_latch_no_condition` | 0.005s |
| ✅ | `integration/test_latch.py::TestLatch::test_latch_with_else` | 0.009s |
| ✅ | `integration/test_module_instance.py::TestModuleInstance::test_chained_instances` | 0.016s |
| ✅ | `integration/test_module_instance.py::TestModuleInstance::test_empty_instance` | 0.005s |
| ✅ | `integration/test_module_instance.py::TestModuleInstance::test_module_with_ff` | 0.017s |
| ✅ | `integration/test_module_instance.py::TestModuleInstance::test_multiple_instances_same_module` | 0.018s |
| ✅ | `integration/test_module_instance.py::TestModuleInstance::test_single_instance` | 0.012s |
| ✅ | `integration/test_module_tracer.py::TestModuleTracer::test_find_connected_modules` | 0.012s |
| ✅ | `integration/test_module_tracer.py::TestModuleTracer::test_trace_module` | 0.012s |
| ✅ | `integration/test_module_tracer.py::TestModuleTracer::test_trace_port` | 0.005s |
| ✅ | `integration/test_negative_cases.py::TestNegativeCases::test_empty_always_ff_no_crash` | 0.005s |
| ✅ | `integration/test_negative_cases.py::TestNegativeCases::test_empty_module_no_crash` | 0.002s |
| ✅ | `integration/test_negative_cases.py::TestNegativeCases::test_fork_join_not_supported` | 0.005s |
| ✅ | `integration/test_negative_cases.py::TestNegativeCases::test_illegal_assignment_no_crash` | 0.004s |
| ✅ | `integration/test_negative_cases.py::TestNegativeCases::test_initial_not_supported` | 0.007s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_16bit_vector_offset` | 0.004s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_8bit_vector` | 0.004s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_max_bit_width` | 0.004s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_multi_stage_pipeline` | 0.012s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_negative_bit_index` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_out_of_bounds_index` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_single_bit_vector` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestBoundaryConditions::test_zero_width_vector` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestErrorInputs::test_constant_drive` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestErrorInputs::test_self_assign` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestErrorInputs::test_undefined_signal` | 0.006s |
| ✅ | `integration/test_negative_cases.py::TestReverseEdgeCases::test_clock_oscillator` | 0.004s |
| ✅ | `integration/test_negative_cases.py::TestReverseEdgeCases::test_reset_edge_priority` | 0.008s |
| ✅ | `integration/test_negative_cases.py::TestReverseEdgeCases::test_two_drivers_conflict` | 0.010s |
| ✅ | `integration/test_operators.py::TestOperators::test_arithmetic` | 0.009s |
| ✅ | `integration/test_operators.py::TestOperators::test_bitwise` | 0.009s |
| ✅ | `integration/test_operators.py::TestOperators::test_comparison` | 0.008s |
| ✅ | `integration/test_operators.py::TestOperators::test_complex_expression` | 0.014s |
| ✅ | `integration/test_operators.py::TestOperators::test_concatenation` | 0.007s |
| ✅ | `integration/test_operators.py::TestOperators::test_logical` | 0.006s |
| ✅ | `integration/test_operators.py::TestOperators::test_reduction` | 0.006s |
| ✅ | `integration/test_operators.py::TestOperators::test_replication` | 0.006s |
| ✅ | `integration/test_operators.py::TestOperators::test_shift` | 0.009s |
| ✅ | `integration/test_operators.py::TestOperators::test_ternary` | 0.008s |
| ✅ | `integration/test_port_inout.py::TestPortInout::test_inout_and_other_ports_coexist` | 0.005s |
| ✅ | `integration/test_port_inout.py::TestPortInout::test_inout_port_has_is_port_marker` | 0.011s |
| ✅ | `integration/test_port_inout.py::TestPortInout::test_inout_port_is_recognized` | 0.012s |
| ✅ | `integration/test_port_reg_detection.py::TestPortRegDetection::test_bit_select_reg_with_clock_and_comb` | 0.010s |
| ✅ | `integration/test_port_reg_detection.py::TestPortRegDetection::test_clock_domain_finds_register` | 0.007s |
| ✅ | `integration/test_port_reg_detection.py::TestPortRegDetection::test_input_port_is_not_reg` | 0.007s |
| ✅ | `integration/test_port_reg_detection.py::TestPortRegDetection::test_output_reg_is_port_and_reg` | 0.007s |
| ✅ | `integration/test_port_reg_detection.py::TestPortRegDetection::test_query_module_finds_output_port` | 0.007s |
| ✅ | `integration/test_reset_edge.py::TestResetEdge::test_reset_edge_creation` | 0.011s |
| ✅ | `integration/test_reset_edge.py::TestResetEdge::test_reset_tree_detection` | 0.011s |
| ✅ | `integration/test_reset_edge.py::TestResetEdge::test_without_reset_no_reset_edge` | 0.007s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_countdrivers` | 0.004s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_display` | 0.002s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_finish` | 0.003s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_floor` | 0.006s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_random` | 0.004s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_sformatf` | 0.005s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_strobe` | 0.006s |
| ✅ | `integration/test_system_tasks.py::TestSystemTasks::test_time` | 0.004s |
| ✅ | `integration/test_unified_tracer.py::TestUnifiedTracer::test_build_graph` | 0.005s |
| ✅ | `integration/test_unified_tracer.py::TestUnifiedTracer::test_get_graph` | 0.005s |
| ✅ | `integration/test_unified_tracer.py::TestUnifiedTracer::test_stats` | 0.005s |
| ✅ | `integration/test_unified_tracer.py::TestUnifiedTracer::test_trace_signal_builds_graph` | 0.005s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_large_vector` | 0.006s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_single_bit_vector` | 0.006s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_unsized_vector` | 0.006s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_vector_input` | 0.007s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_vector_internal` | 0.009s |
| ✅ | `integration/test_vector_width.py::TestVectorWidth::test_vector_output` | 0.007s |

---
*此报告由 pytest 自动生成*