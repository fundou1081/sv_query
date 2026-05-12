# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-12 17:37:52",
  "passed": 29,
  "failed": 9,
  "skipped": 0,
  "total": 38
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 29
- **失败**: 9
- **跳过**: 0
- **总计**: 38
- **时间**: 2026-05-12 17:37:52

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `regression/test_cross_module_tracking.py::TestModuleInstanceGraph::test_cross_module_connection` | 0.011s |
| ✅ | `regression/test_cross_module_tracking.py::TestModuleInstanceGraph::test_instances_exist` | 0.010s |
| ✅ | `regression/test_cross_module_tracking.py::TestModuleInstanceGraph::test_port_mapping` | 0.010s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModulePath::test_internal_signal_clock_edge` | 0.010s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModulePath::test_path_resolution` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestHierarchicalPort::test_multi_level_hierarchy` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestHierarchicalPort::test_simple_hierarchy` | 0.006s |
| ✅ | `regression/test_cross_module_tracking.py::TestNegativeCases::test_no_unconnected_modules` | 0.004s |
| ✅ | `regression/test_cross_module_tracking.py::TestNegativeCases::test_parameterized_module` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestMultiLevelHierarchy::test_four_level_hierarchy` | 0.014s |
| ✅ | `regression/test_cross_module_tracking.py::TestMultiLevelHierarchy::test_three_level_hierarchy` | 0.011s |
| ✅ | `regression/test_cross_module_tracking.py::TestPortWidthMapping::test_different_widths` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestBidirectionalPort::test_inout_port` | 0.007s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleClockPath::test_clock_propagation` | 0.014s |
| ✅ | `regression/test_cross_module_tracking.py::TestUnconnectedPort::test_partially_connected` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestParameterOverride::test_width_parameter_override` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestInterfaceModportCrossModule::test_modport_direction` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestGenerateInstanceCrossModule::test_generate_for_instance` | 0.009s |
| ✅ | `regression/test_cross_module_tracking.py::TestFunctionPortCrossModule::test_function_call_cross_module` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestClassInstanceCrossModule::test_class_member_access` | 0.005s |
| ✅ | `regression/test_cross_module_tracking.py::TestClockDividerCrossModule::test_clock_chain` | 0.017s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleBasicFunctions::test_instance_parent_relationship` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleBasicFunctions::test_multiple_instances` | 0.011s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleBasicFunctions::test_port_to_internal_mapping` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleSignalFlow::test_wire_connection` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModulePortTypes::test_clock_port` | 0.006s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModulePortTypes::test_input_port` | 0.008s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModulePortTypes::test_output_port` | 0.007s |
| ✅ | `regression/test_cross_module_tracking.py::TestCrossModuleNegativeCases::test_empty_module` | 0.004s |
| ❌ | `regression/test_cross_module_tracking.py::TestArrayOfInstances::test_array_instance` | 0.008s |
| ❌ | `regression/test_cross_module_tracking.py::TestMultipleConnections::test_one_to_many` | 0.011s |
| ❌ | `regression/test_cross_module_tracking.py::TestInterfaceModportCrossModule::test_interface_connection` | 0.008s |
| ❌ | `regression/test_cross_module_tracking.py::TestResetCrossModule::test_async_reset_propagation` | 0.017s |
| ❌ | `regression/test_cross_module_tracking.py::TestBusArbitrationCrossModule::test_master_slave_connection` | 0.014s |
| ❌ | `regression/test_cross_module_tracking.py::TestCrossModuleBasicFunctions::test_simple_two_module` | 0.008s |
| ❌ | `regression/test_cross_module_tracking.py::TestCrossModuleSignalFlow::test_signal_driver_tracking` | 0.012s |
| ❌ | `regression/test_cross_module_tracking.py::TestCrossModulePathFinding::test_find_path_simple` | 0.011s |
| ❌ | `regression/test_cross_module_tracking.py::TestCrossModuleNegativeCases::test_uninstantiated_module` | 0.005s |

---
*此报告由 pytest 自动生成*