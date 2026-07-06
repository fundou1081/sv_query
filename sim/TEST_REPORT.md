# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-06 08:33:19",
  "passed": 130,
  "failed": 0,
  "skipped": 0,
  "total": 130
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 130
- **失败**: 0
- **跳过**: 0
- **总计**: 130
- **时间**: 2026-07-06 08:33:19

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.395s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.216s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 0.854s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.266s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 0.853s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 0.858s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 0.893s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.221s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.273s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 0.876s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.257s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.097s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.103s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_class_filter` | 0.197s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_coverage_gap_help` | 0.221s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_json_output_is_valid` | 0.196s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_cross_gap_detected` | 0.198s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_illegal_bins_gap_detected` | 0.200s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_no_constraint_no_covergroup_returns_zero_gaps` | 0.196s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_state_q_with_related` | 3.797s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_data_i_32bit_input` | 3.602s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_basic` | 3.621s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_auto_detect` | 5.812s |
| ✅ | `cli/test_coverage_gen_demo.py::TestNoStrictFlag::test_no_strict_compiles_with_rtl_warnings` | 3.752s |
| ✅ | `cli/test_coverage_gen_demo.py::TestModuleFlag::test_module_specific_extraction` | 3.772s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_no_args_shows_help` | 0.155s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_one_arg_shows_help` | 0.157s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_risk_analyze_failure_raises` | 3.153s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_data_o]` | 3.623s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_idx_o]` | 3.699s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_clk_i]` | 3.749s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_golden_dir_exists` | 0.000s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_all_known_golden_files_present` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_data_o_simple_pipe_passes` | 3.570s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_state_q_fsm_passes` | 3.515s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_picorv32_mem_addr_passes` | 5.240s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_opentitan_max_idx_o_passes` | 4.228s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_naplespu_events_counter_passes` | 3.687s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_primary` | 0.003s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_returns_none_for_missing` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_cross_cp` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_build_wrapper_uses_correct_clk_rst` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestBugfixRegression::test_no_sv_keyword_in_bin_names` | 3.369s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_subcommand_registered` | 0.254s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_generate_help` | 0.220s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_state_q_with_related` | 3.607s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_data_i_32bit_input` | 3.555s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_filelist_with_include_dir` | 5.909s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_clog2_derived_param` | 4.223s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_naplespu_4_level_chained_include` | 3.601s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_writes_sv_file` | 3.590s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_relative_path` | 3.428s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateNoHeader::test_no_header_strips_meta` | 3.555s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_required_signal_arg` | 0.238s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_file_arg` | 0.177s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_1level` | 3.550s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_2level_nested` | 3.554s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_clog2_across_modules` | 3.571s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_with_related_filters_data` | 3.628s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_nonexistent_submodule_prints_error` | 3.568s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_struct_field_bins_present` | 3.598s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_union_skips_field_bins` | 3.637s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_added_node` | 0.203s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_identical` | 0.198s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_json` | 0.200s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_removed_node` | 0.202s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_basic` | 0.194s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_json` | 0.193s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_not_found` | 0.188s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_basic` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_trace_help` | 0.243s |
| ✅ | `cli/test_trace_batch.py::test_p1_single_signal_backward_compat` | 0.238s |
| ✅ | `cli/test_trace_batch.py::test_p2_batch_inline_multiple_signals` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p3_batch_file_with_comments_and_dedup` | 0.235s |
| ✅ | `cli/test_trace_batch.py::test_p4_positional_plus_batch_mix` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p5_text_output_batch_header` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p6_all_4_subcommands_support_batch` | 0.946s |
| ✅ | `cli/test_trace_batch.py::test_n1_no_signal_any_source` | 0.180s |
| ✅ | `cli/test_trace_batch.py::test_n2_batch_file_not_found` | 0.179s |
| ✅ | `cli/test_trace_batch.py::test_n3_batch_file_only_comments` | 0.179s |
| ✅ | `cli/test_trace_batch.py::test_n4_batch_empty_string` | 0.179s |
| ✅ | `cli/test_trace_batch.py::test_n5_nonexistent_signal_silent` | 0.236s |
| ✅ | `cli/test_trace_batch.py::test_golden_batch_fanin_2_signals` | 0.237s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_default_cache_enabled` | 0.470s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_forces_rebuild` | 0.469s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_flag_in_help` | 0.226s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_sig_silent` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_fanout` | 0.236s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_impact` | 0.244s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_evidence` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_all_succeed_ok_true` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_per_sig_error_recovery_with_mock` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p1_type_filter` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p2_module_glob` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p3_width_min` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p4_width_max` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p5_exclude_glob` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p6_combined_filters` | 0.237s |
| ✅ | `cli/test_trace_filters.py::test_p7_filter_with_batch` | 0.236s |
| ✅ | `cli/test_trace_filters.py::test_p8_fanout_also_supports_filters` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p9_module_field_in_json` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n1_type_no_match` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n2_module_glob_no_match` | 0.237s |
| ✅ | `cli/test_trace_filters.py::test_n3_width_min_greater_than_max` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n4_exclude_excludes_everything` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_golden_filter_type_and_width` | 0.237s |
| ✅ | `cli/test_trace_snapshot.py::test_p1_fanin_from_snapshot_matches_file` | 0.415s |
| ✅ | `cli/test_trace_snapshot.py::test_p2_fanout_from_snapshot` | 0.414s |
| ✅ | `cli/test_trace_snapshot.py::test_p3_impact_from_snapshot` | 0.435s |
| ✅ | `cli/test_trace_snapshot.py::test_p4_evidence_from_snapshot` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p5_from_snapshot_with_batch` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p6_from_snapshot_with_filter` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p7_from_snapshot_no_strict` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n1_nonexistent_snapshot_tag` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n2_from_snapshot_with_file_mutually_exclusive` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n3_from_snapshot_with_filelist_mutually_exclusive` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_n4_no_source_no_snapshot` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_golden_snapshot_fanin_with_filter` | 0.180s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_generates_dot` | 0.260s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_node_counts` | 0.247s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_golden_match` | 0.250s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_generates_dot` | 0.249s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_stage_counts` | 0.248s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_uses_lr_layout` | 0.248s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_golden_match` | 0.248s |

---
*此报告由 pytest 自动生成*