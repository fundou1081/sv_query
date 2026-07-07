# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-07 22:22:29",
  "passed": 194,
  "failed": 0,
  "skipped": 0,
  "total": 194
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 194
- **失败**: 0
- **跳过**: 0
- **总计**: 194
- **时间**: 2026-07-07 22:22:29

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.423s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.215s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 0.838s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_arch_test_top_summary_has_port_connections` | 0.244s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_arch_deep_top_summary_has_6_levels_11_instances` | 0.356s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.266s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 0.847s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_arch_test_top_mermaid_has_hierarchy_edges` | 0.242s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 0.857s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 0.856s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.218s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.259s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 0.868s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.255s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.193s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.103s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_empty_file` | 0.183s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_finds_covergroup` | 0.189s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_help` | 0.219s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_json` | 0.187s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_json_content` | 0.190s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_lists_bins` | 0.188s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_lists_coverpoints` | 0.189s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_lists_crosses` | 0.188s |
| ✅ | `cli/test_coverage_analyze.py::TestCoverageAnalyzeCLI::test_coverage_analyze_summary` | 0.220s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_class_filter` | 0.200s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_coverage_gap_help` | 0.221s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_json_output_is_valid` | 0.203s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_cross_gap_detected` | 0.198s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_illegal_bins_gap_detected` | 0.198s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_no_constraint_no_covergroup_returns_zero_gaps` | 0.195s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_state_q_with_related` | 3.667s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_data_i_32bit_input` | 3.613s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_basic` | 3.645s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_auto_detect` | 5.876s |
| ✅ | `cli/test_coverage_gen_demo.py::TestNoStrictFlag::test_no_strict_compiles_with_rtl_warnings` | 3.767s |
| ✅ | `cli/test_coverage_gen_demo.py::TestModuleFlag::test_module_specific_extraction` | 3.805s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_no_args_shows_help` | 0.152s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_one_arg_shows_help` | 0.153s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_risk_analyze_failure_raises` | 3.333s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_data_o]` | 3.750s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_idx_o]` | 3.771s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_clk_i]` | 3.773s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_golden_dir_exists` | 0.000s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_all_known_golden_files_present` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_data_o_simple_pipe_passes` | 3.593s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_state_q_fsm_passes` | 3.570s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_picorv32_mem_addr_passes` | 5.232s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_opentitan_max_idx_o_passes` | 4.207s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_naplespu_events_counter_passes` | 3.684s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_primary` | 0.002s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_returns_none_for_missing` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_cross_cp` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_build_wrapper_uses_correct_clk_rst` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestBugfixRegression::test_no_sv_keyword_in_bin_names` | 3.301s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_subcommand_registered` | 0.250s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_generate_help` | 0.218s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_state_q_with_related` | 3.588s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_data_i_32bit_input` | 3.473s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_filelist_with_include_dir` | 5.866s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_clog2_derived_param` | 4.259s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_naplespu_4_level_chained_include` | 3.671s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_writes_sv_file` | 3.558s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_relative_path` | 3.517s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateNoHeader::test_no_header_strips_meta` | 3.506s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_required_signal_arg` | 0.251s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_file_arg` | 0.173s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_1level` | 3.514s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_2level_nested` | 3.553s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_clog2_across_modules` | 3.522s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_with_related_filters_data` | 3.572s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_nonexistent_submodule_prints_error` | 3.506s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_struct_field_bins_present` | 3.476s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_union_skips_field_bins` | 3.611s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_added_node` | 0.200s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_identical` | 0.196s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_json` | 0.200s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_removed_node` | 0.201s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_class_filter` | 0.186s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_class_filter_empty` | 0.184s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_distinguishes_rand_randc` | 0.185s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_calls` | 0.185s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_hooks` | 0.185s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_finds_rand_vars` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_help` | 0.244s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_json_content` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeListCLI::test_randomize_list_json_output` | 0.183s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_class_filter` | 0.186s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_finds_inline_constraints` | 0.182s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_help` | 0.217s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_json_output` | 0.185s |
| ✅ | `cli/test_randomize.py::TestRandomizeExtractCLI::test_randomize_extract_target` | 0.183s |
| ✅ | `cli/test_randomize.py::TestRandomizeEmptyFile::test_randomize_extract_on_empty` | 0.187s |
| ✅ | `cli/test_randomize.py::TestRandomizeEmptyFile::test_randomize_list_on_empty` | 0.182s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_detects_alive` | 0.201s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_detects_dead` | 0.192s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_help` | 0.218s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_content_dead` | 0.194s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_content_driver` | 0.199s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_output` | 0.193s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_json_unknown_class` | 0.185s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_randomized_in` | 0.196s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_summary` | 0.199s |
| ✅ | `cli/test_randomize_reachability.py::TestRandomizeReachabilityCLI::test_reachability_unknown_class` | 0.184s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityInheritance::test_base_class_all_alive` | 0.195s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityInheritance::test_extended_class_all_alive` | 0.196s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityInheritance::test_inheritance_alive_count` | 0.195s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityCovergroupSample::test_covergroup_sample_covered_in` | 0.198s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityCovergroupSample::test_covergroup_sample_makes_alive` | 0.197s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityHierarchy::test_all_6_vars_alive` | 0.209s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityHierarchy::test_hierarchy_consumed_count` | 0.210s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityNoRandomize::test_no_randomize_alive_via_consumer` | 0.192s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityNoRandomize::test_no_randomize_zero_count` | 0.192s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityMultiRandomize::test_multi_randomize_addr_count` | 0.194s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityMultiRandomize::test_multi_randomize_all_alive` | 0.195s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityMultiRandomize::test_multi_randomize_mode_count` | 0.195s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityFunctionRandomize::test_function_randomize_alive` | 0.192s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityFunctionRandomize::test_function_randomize_count` | 0.191s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityFixturesOverview::test_all_fixtures_expected_alive_dead_count` | 1.767s |
| ✅ | `cli/test_randomize_reachability_extended.py::TestReachabilityFixturesOverview::test_all_fixtures_return_valid_json` | 1.766s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_extracts_inline_constraint` | 0.194s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_finds_calls` | 0.190s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_finds_hooks` | 0.191s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_help` | 0.221s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_json_output` | 0.190s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_json_randomize_calls` | 0.189s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_no_strict` | 0.191s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_summary_line` | 0.190s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceCLI::test_randomize_trace_unknown_class` | 0.189s |
| ✅ | `cli/test_randomize_trace.py::TestRandomizeTraceNoRandomize::test_trace_no_randomize` | 0.189s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_basic` | 0.195s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_not_found` | 0.189s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_basic` | 0.193s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_trace_help` | 0.217s |
| ✅ | `cli/test_trace_batch.py::test_p1_single_signal_backward_compat` | 0.236s |
| ✅ | `cli/test_trace_batch.py::test_p2_batch_inline_multiple_signals` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p3_batch_file_with_comments_and_dedup` | 0.236s |
| ✅ | `cli/test_trace_batch.py::test_p4_positional_plus_batch_mix` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p5_text_output_batch_header` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p6_all_4_subcommands_support_batch` | 0.944s |
| ✅ | `cli/test_trace_batch.py::test_n1_no_signal_any_source` | 0.178s |
| ✅ | `cli/test_trace_batch.py::test_n2_batch_file_not_found` | 0.181s |
| ✅ | `cli/test_trace_batch.py::test_n3_batch_file_only_comments` | 0.178s |
| ✅ | `cli/test_trace_batch.py::test_n4_batch_empty_string` | 0.178s |
| ✅ | `cli/test_trace_batch.py::test_n5_nonexistent_signal_silent` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_golden_batch_fanin_2_signals` | 0.236s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_default_cache_enabled` | 0.470s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_forces_rebuild` | 0.475s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_flag_in_help` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_sig_silent` | 0.240s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_fanout` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_impact` | 0.244s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_evidence` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_all_succeed_ok_true` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_per_sig_error_recovery_with_mock` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p1_type_filter` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p2_module_glob` | 0.236s |
| ✅ | `cli/test_trace_filters.py::test_p3_width_min` | 0.236s |
| ✅ | `cli/test_trace_filters.py::test_p4_width_max` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p5_exclude_glob` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p6_combined_filters` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p7_filter_with_batch` | 0.236s |
| ✅ | `cli/test_trace_filters.py::test_p8_fanout_also_supports_filters` | 0.236s |
| ✅ | `cli/test_trace_filters.py::test_p9_module_field_in_json` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n1_type_no_match` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n2_module_glob_no_match` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n3_width_min_greater_than_max` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n4_exclude_excludes_everything` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_golden_filter_type_and_width` | 0.236s |
| ✅ | `cli/test_trace_snapshot.py::test_p1_fanin_from_snapshot_matches_file` | 0.416s |
| ✅ | `cli/test_trace_snapshot.py::test_p2_fanout_from_snapshot` | 0.414s |
| ✅ | `cli/test_trace_snapshot.py::test_p3_impact_from_snapshot` | 0.433s |
| ✅ | `cli/test_trace_snapshot.py::test_p4_evidence_from_snapshot` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_p5_from_snapshot_with_batch` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p6_from_snapshot_with_filter` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p7_from_snapshot_no_strict` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n1_nonexistent_snapshot_tag` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n2_from_snapshot_with_file_mutually_exclusive` | 0.180s |
| ✅ | `cli/test_trace_snapshot.py::test_n3_from_snapshot_with_filelist_mutually_exclusive` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n4_no_source_no_snapshot` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_golden_snapshot_fanin_with_filter` | 0.180s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_generates_dot` | 0.253s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_node_counts` | 0.248s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_golden_match` | 0.247s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_generates_dot` | 0.247s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_stage_counts` | 0.246s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_uses_lr_layout` | 0.251s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_golden_match` | 0.248s |

---
*此报告由 pytest 自动生成*