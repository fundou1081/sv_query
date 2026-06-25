# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-06-25 18:29:51",
  "passed": 104,
  "failed": 0,
  "skipped": 0,
  "total": 104
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 104
- **失败**: 0
- **跳过**: 0
- **总计**: 104
- **时间**: 2026-06-25 18:29:51

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `unit/test_cli_filelist_parity.py::test_risk_file_vs_filelist_parity` | 0.661s |
| ✅ | `unit/test_cli_filelist_parity.py::test_risk_no_args_errors` | 0.291s |
| ✅ | `unit/test_cli_filelist_parity.py::test_cdc_file_vs_filelist_parity` | 0.629s |
| ✅ | `unit/test_cli_filelist_parity.py::test_cdc_no_args_errors` | 0.282s |
| ✅ | `unit/test_cli_filelist_parity.py::test_coverage_suggest_file_vs_filelist_parity` | 0.636s |
| ✅ | `unit/test_cli_filelist_parity.py::test_dataflow_file_vs_filelist_parity` | 0.650s |
| ✅ | `unit/test_cli_filelist_parity.py::test_controlflow_analyze_file_vs_filelist_parity` | 0.656s |
| ✅ | `unit/test_cli_filelist_parity.py::test_controlflow_list_conditioned_file_vs_filelist_parity` | 0.654s |
| ✅ | `unit/test_cli_filelist_parity.py::test_controlflow_conditions_file_vs_filelist_parity` | 0.660s |
| ✅ | `unit/test_cli_filelist_parity.py::test_sva_extract_file_vs_filelist_parity` | 1.184s |
| ✅ | `unit/test_cli_filelist_parity.py::test_sva_coverage_file_vs_filelist_parity` | 0.660s |
| ✅ | `unit/test_cli_filelist_parity.py::test_sva_timing_file_vs_filelist_parity` | 0.653s |
| ✅ | `unit/test_cli_filelist_parity.py::test_timing_file_vs_filelist_parity` | 0.642s |
| ✅ | `unit/test_cli_filelist_parity.py::test_verify_file_vs_filelist_parity` | 0.655s |
| ✅ | `unit/test_cli_filelist_parity.py::test_visualize_file_vs_filelist_parity` | 0.662s |
| ✅ | `unit/test_dataflow_error_hint.py::test_dataflow_bare_signal_suggests_hierarchical` | 0.327s |
| ✅ | `unit/test_dataflow_error_hint.py::test_dataflow_valid_hierarchical_works` | 0.327s |
| ✅ | `unit/test_fix_imports.py::test_fix_imports_write_new_filelist` | 0.320s |
| ✅ | `unit/test_handshake_cli.py::TestHandshakeErrors::test_no_filelist_or_file` | 0.002s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_a_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_a_awready-awready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_a_awaddr-awaddr]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_a_awlen-awlen]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_a_awsize-awsize]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_w_wvalid-wvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_w_wready-wready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_w_wdata-wdata]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_w_wstrb-wstrb]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_w_wlast-wlast]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_b_bvalid-bvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_b_bready-bready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_b_bresp-bresp]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_ar_arvalid-arvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_ar_arready-arready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_ar_araddr-araddr]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_r_rvalid-rvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_r_rready-rready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_r_rdata-rdata]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiChannelPrefix::test_channel_prefix_stripped[s_axi_r_rlast-rlast]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[m_axi_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[s_axi_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[m_axi_wready-wready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[s_axi_wready-wready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[io_m_axi_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[io_s_axi_awready-awready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[s_axil_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[m_axil_awvalid-awvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[s_axis_tvalid-tvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[m_axis_tready-tready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[tl_a_valid_o-tlavalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[tl_h_valid_o-tlhvalid]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestVerilogAxiRegression::test_existing_naming_unchanged[tl_a_ready_i-tlaready]` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestStripPrefixOrdering::test_longest_prefix_wins` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestDefaultConfigParity::test_default_includes_verilog_axi_channel_prefix` | 0.000s |
| ✅ | `unit/test_normalize_filelist.py::TestDefaultConfigParity::test_default_and_yaml_have_same_verilog_axi_prefixes` | 0.002s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_top_level_signal` | 0.117s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_top_level_1bit` | 0.111s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_top_level_internal_state` | 0.111s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_submodule_1level` | 0.113s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_submodule_2level_data` | 0.108s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_submodule_2level_clog2` | 0.110s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_nonexistent_submodule_returns_none` | 0.112s |
| ✅ | `unit/test_pyslang_type_extraction.py::TestCrossModuleHierarchical::test_submodule_signal_nonexistent` | 0.112s |
| ✅ | `unit/test_signal_normalizer.py::TestTakeLastDot::test_hierarchical_inst_signal` | 0.000s |
| ✅ | `unit/test_signal_normalizer.py::TestTakeLastDot::test_deep_hierarchical` | 0.000s |
| ✅ | `unit/test_signal_normalizer.py::TestNormalizeEndToEnd::test_hierarchical_with_array` | 0.000s |
| ✅ | `unit/test_signal_normalizer.py::TestNormalizeEndToEnd::test_hierarchical_dot_array` | 0.000s |
| ✅ | `unit/test_stats_filelist.py::test_stats_with_file_still_works` | 0.331s |
| ✅ | `unit/test_stats_filelist.py::test_stats_with_filelist_loads_all_files` | 0.336s |
| ✅ | `unit/test_stats_filelist.py::test_stats_filelist_does_not_require_file` | 0.333s |
| ✅ | `unit/test_stats_filelist.py::test_stats_without_file_or_filelist_errors` | 0.302s |
| ✅ | `unit/test_stats_filelist.py::test_stats_filelist_in_params_json` | 0.329s |
| ✅ | `unit/test_strict_default.py::test_strict_error_message_suggests_filelist_fix` | 0.304s |
| ✅ | `unit/test_strict_default.py::test_strict_passes_when_filelist_complete` | 0.323s |
| ✅ | `unit/test_sv_extractor.py::TestFilelist::test_filelist_basic` | 0.014s |
| ✅ | `unit/test_sv_extractor.py::TestFilelist::test_list_modules` | 0.010s |
| ✅ | `unit/test_sv_preprocessor.py::TestStripComment::test_no_comment` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestStripComment::test_trailing_comment` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestStripComment::test_only_comment` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestStripComment::test_multiple_spaces` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_simple_literal` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_indirect` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_double_indirect` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_undefined_returns_none` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_circular_returns_none` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_strip_comment_in_value` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestResolveMacro::test_expression_with_macro` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_simple_replace` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_cross_file` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_define_line_not_replaced` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_no_recursion_on_undefined` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_word_boundary_protection` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestPreprocessMacros::test_naplespu_real_case` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestUnifiedTracerPreprocess::test_preprocess_disabled_keeps_orig` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestUnifiedTracerPreprocess::test_preprocess_enabled_replaces` | 0.000s |
| ✅ | `unit/test_sv_preprocessor.py::TestUnifiedTracerPreprocess::test_idempotent` | 0.000s |
| ✅ | `unit/test_trace_filelist_fix.py::TestResolveNode::test_resolves_hierarchical_for_bare_name` | 0.034s |
| ✅ | `unit/test_trace_filelist_fix.py::TestResolveNode::test_resolves_hierarchical_with_module` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestResolveNode::test_resolves_already_hierarchical_name` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestResolveNode::test_resolves_longest_match_when_multiple` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestResolveNode::test_returns_none_for_unknown_signal` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestGetHandshakeSingleFile::test_get_handshake_returns_valid_type` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestCaching::test_cache_returns_same_result` | 0.033s |
| ✅ | `unit/test_trace_filelist_fix.py::TestCaching::test_cache_cleared_on_set_context` | 0.033s |

---
*此报告由 pytest 自动生成*