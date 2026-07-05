# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-06 00:31:50",
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
- **时间**: 2026-07-06 00:31:50

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.421s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.216s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 0.859s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.263s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 0.860s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 0.854s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 0.862s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.226s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.260s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 0.874s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.287s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.165s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.109s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_class_filter` | 0.216s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_coverage_gap_help` | 0.238s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_json_output_is_valid` | 0.208s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_cross_gap_detected` | 0.213s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_illegal_bins_gap_detected` | 0.213s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_no_constraint_no_covergroup_returns_zero_gaps` | 0.205s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_state_q_with_related` | 3.821s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_data_i_32bit_input` | 3.616s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_basic` | 3.619s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_auto_detect` | 6.068s |
| ✅ | `cli/test_coverage_gen_demo.py::TestNoStrictFlag::test_no_strict_compiles_with_rtl_warnings` | 3.831s |
| ✅ | `cli/test_coverage_gen_demo.py::TestModuleFlag::test_module_specific_extraction` | 3.845s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_no_args_shows_help` | 0.156s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_one_arg_shows_help` | 0.155s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_risk_analyze_failure_raises` | 3.382s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_data_o]` | 3.809s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_idx_o]` | 3.802s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otarb_clk_i]` | 3.761s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_golden_dir_exists` | 0.000s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_all_known_golden_files_present` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_data_o_simple_pipe_passes` | 3.621s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_state_q_fsm_passes` | 3.525s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_picorv32_mem_addr_passes` | 5.221s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_opentitan_max_idx_o_passes` | 4.226s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_naplespu_events_counter_passes` | 3.727s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_primary` | 0.003s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_returns_none_for_missing` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_cross_cp` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_build_wrapper_uses_correct_clk_rst` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestBugfixRegression::test_no_sv_keyword_in_bin_names` | 3.425s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_subcommand_registered` | 0.252s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_generate_help` | 0.222s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_state_q_with_related` | 3.578s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_data_i_32bit_input` | 3.585s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_filelist_with_include_dir` | 5.884s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_clog2_derived_param` | 4.251s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_naplespu_4_level_chained_include` | 3.646s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_writes_sv_file` | 3.591s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_relative_path` | 3.605s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateNoHeader::test_no_header_strips_meta` | 3.470s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_required_signal_arg` | 0.241s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_file_arg` | 0.178s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_1level` | 3.567s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_2level_nested` | 3.552s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_clog2_across_modules` | 3.574s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_with_related_filters_data` | 3.622s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_nonexistent_submodule_prints_error` | 3.550s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_struct_field_bins_present` | 3.615s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_union_skips_field_bins` | 3.644s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_added_node` | 0.202s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_identical` | 0.198s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_json` | 0.201s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_removed_node` | 0.203s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_basic` | 0.195s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_not_found` | 0.189s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_basic` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_json` | 0.191s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_trace_help` | 0.243s |
| ✅ | `cli/test_trace_batch.py::test_p1_single_signal_backward_compat` | 0.243s |
| ✅ | `cli/test_trace_batch.py::test_p2_batch_inline_multiple_signals` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p3_batch_file_with_comments_and_dedup` | 0.235s |
| ✅ | `cli/test_trace_batch.py::test_p4_positional_plus_batch_mix` | 0.234s |
| ✅ | `cli/test_trace_batch.py::test_p5_text_output_batch_header` | 0.235s |
| ✅ | `cli/test_trace_batch.py::test_p6_all_4_subcommands_support_batch` | 0.945s |
| ✅ | `cli/test_trace_batch.py::test_n1_no_signal_any_source` | 0.179s |
| ✅ | `cli/test_trace_batch.py::test_n2_batch_file_not_found` | 0.180s |
| ✅ | `cli/test_trace_batch.py::test_n3_batch_file_only_comments` | 0.178s |
| ✅ | `cli/test_trace_batch.py::test_n4_batch_empty_string` | 0.178s |
| ✅ | `cli/test_trace_batch.py::test_n5_nonexistent_signal_silent` | 0.235s |
| ✅ | `cli/test_trace_batch.py::test_golden_batch_fanin_2_signals` | 0.237s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_default_cache_enabled` | 0.469s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_forces_rebuild` | 0.470s |
| ✅ | `cli/test_trace_cache_error.py::test_a1_no_cache_flag_in_help` | 0.226s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_sig_silent` | 0.237s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_fanout` | 0.235s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_impact` | 0.244s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_with_nonexistent_evidence` | 0.234s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_batch_all_succeed_ok_true` | 0.236s |
| ✅ | `cli/test_trace_cache_error.py::test_a3_per_sig_error_recovery_with_mock` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p1_type_filter` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p2_module_glob` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p3_width_min` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p4_width_max` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p5_exclude_glob` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p6_combined_filters` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_p7_filter_with_batch` | 0.237s |
| ✅ | `cli/test_trace_filters.py::test_p8_fanout_also_supports_filters` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_p9_module_field_in_json` | 0.237s |
| ✅ | `cli/test_trace_filters.py::test_n1_type_no_match` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n2_module_glob_no_match` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_n3_width_min_greater_than_max` | 0.235s |
| ✅ | `cli/test_trace_filters.py::test_n4_exclude_excludes_everything` | 0.234s |
| ✅ | `cli/test_trace_filters.py::test_golden_filter_type_and_width` | 0.236s |
| ✅ | `cli/test_trace_snapshot.py::test_p1_fanin_from_snapshot_matches_file` | 0.420s |
| ✅ | `cli/test_trace_snapshot.py::test_p2_fanout_from_snapshot` | 0.415s |
| ✅ | `cli/test_trace_snapshot.py::test_p3_impact_from_snapshot` | 0.430s |
| ✅ | `cli/test_trace_snapshot.py::test_p4_evidence_from_snapshot` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_p5_from_snapshot_with_batch` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_p6_from_snapshot_with_filter` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_p7_from_snapshot_no_strict` | 0.181s |
| ✅ | `cli/test_trace_snapshot.py::test_n1_nonexistent_snapshot_tag` | 0.180s |
| ✅ | `cli/test_trace_snapshot.py::test_n2_from_snapshot_with_file_mutually_exclusive` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n3_from_snapshot_with_filelist_mutually_exclusive` | 0.179s |
| ✅ | `cli/test_trace_snapshot.py::test_n4_no_source_no_snapshot` | 0.178s |
| ✅ | `cli/test_trace_snapshot.py::test_golden_snapshot_fanin_with_filter` | 0.180s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_generates_dot` | 0.258s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_node_counts` | 0.248s |
| ✅ | `cli/test_visualize_dataflow.py::test_visualize_dataflow_golden_match` | 0.247s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_generates_dot` | 0.248s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_stage_counts` | 0.247s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_uses_lr_layout` | 0.246s |
| ✅ | `cli/test_visualize_pipeline.py::test_visualize_pipeline_golden_match` | 0.248s |

---
*此报告由 pytest 自动生成*