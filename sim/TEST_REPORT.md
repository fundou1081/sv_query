# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-07-01 21:42:56",
  "passed": 76,
  "failed": 0,
  "skipped": 0,
  "total": 76
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 76
- **失败**: 0
- **跳过**: 0
- **总计**: 76
- **时间**: 2026-07-01 21:42:56

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_in_main_help` | 0.442s |
| ✅ | `cli/test_arch.py::TestArchCommandRegistration::test_arch_app_help` | 0.217s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_picorv32_axi_summary` | 0.863s |
| ✅ | `cli/test_arch.py::TestArchSummaryMode::test_no_submodule_summary_message` | 0.265s |
| ✅ | `cli/test_arch.py::TestArchMermaidOutput::test_picorv32_axi_mermaid` | 0.824s |
| ✅ | `cli/test_arch.py::TestArchDotOutput::test_picorv32_axi_dot` | 0.837s |
| ✅ | `cli/test_arch.py::TestArchHtmlOutput::test_picorv32_axi_html` | 0.834s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_no_file_or_filelist` | 0.218s |
| ✅ | `cli/test_arch.py::TestArchErrorHandling::test_unknown_format` | 0.258s |
| ✅ | `cli/test_arch.py::TestArchClusterByType::test_cluster_by_type_picorv32` | 0.842s |
| ✅ | `cli/test_arch.py::TestArchMaxNodes::test_max_nodes_collapse` | 0.261s |
| ✅ | `cli/test_arch.py::TestArchSvgOutput::test_svg_generation` | 1.063s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_deterministic` | 0.105s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_hash_color_different` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_no_collapse` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_collapse_instances_folds` | 0.000s |
| ✅ | `cli/test_arch.py::TestArchHelpers::test_safe_cluster_name` | 0.000s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_class_filter` | 0.197s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_coverage_gap_help` | 0.218s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_json_output_is_valid` | 0.192s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_cross_gap_detected` | 0.196s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_missing_illegal_bins_gap_detected` | 0.199s |
| ✅ | `cli/test_coverage_gap.py::TestCoverageGapCLI::test_no_constraint_no_covergroup_returns_zero_gaps` | 0.192s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_state_q_with_related` | 0.584s |
| ✅ | `cli/test_coverage_gen_demo.py::TestSingleFileMode::test_data_i_32bit_input` | 0.581s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_basic` | 0.654s |
| ✅ | `cli/test_coverage_gen_demo.py::TestFilelistMode::test_filelist_auto_detect` | 2.854s |
| ✅ | `cli/test_coverage_gen_demo.py::TestNoStrictFlag::test_no_strict_compiles_with_rtl_warnings` | 0.897s |
| ✅ | `cli/test_coverage_gen_demo.py::TestModuleFlag::test_module_specific_extraction` | 0.813s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_no_args_shows_help` | 0.166s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_one_arg_shows_help` | 0.166s |
| ✅ | `cli/test_coverage_gen_demo.py::TestCliErrorHandling::test_risk_analyze_failure_raises` | 0.377s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otval_data_o]` | 0.593s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otval_state_q]` | 0.591s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestCoverageGenDemoGolden::test_golden_match[otval_accumulator_q]` | 0.597s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_golden_dir_exists` | 0.000s |
| ✅ | `cli/test_coverage_gen_demo_golden.py::TestGoldenFileSanity::test_all_known_golden_files_present` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_data_o_simple_pipe_passes` | 0.669s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestSingleFileDataCompile::test_state_q_fsm_passes` | 0.606s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_picorv32_mem_addr_passes` | 2.286s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_opentitan_max_idx_o_passes` | 1.263s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestIndustrialProjectCompile::test_naplespu_events_counter_passes` | 0.717s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_primary` | 0.002s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_returns_none_for_missing` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_extract_width_from_cg_cross_cp` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestInternalHelpers::test_build_wrapper_uses_correct_clk_rst` | 0.000s |
| ✅ | `cli/test_coverage_gen_sv_compile.py::TestBugfixRegression::test_no_sv_keyword_in_bin_names` | 0.427s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_subcommand_registered` | 0.245s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCommand::test_generate_help` | 0.221s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_state_q_with_related` | 0.609s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateSingleFile::test_data_i_32bit_input` | 0.613s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_filelist_with_include_dir` | 2.863s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_clog2_derived_param` | 1.277s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateFilelist::test_naplespu_4_level_chained_include` | 0.738s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_writes_sv_file` | 0.606s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateOutput::test_output_relative_path` | 0.609s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateNoHeader::test_no_header_strips_meta` | 0.610s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_required_signal_arg` | 0.216s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateErrors::test_missing_file_arg` | 0.178s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_1level` | 0.577s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_2level_nested` | 0.576s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_clog2_across_modules` | 0.581s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_submodule_with_related_filters_data` | 0.644s |
| ✅ | `cli/test_coverage_generate.py::TestCoverageGenerateCrossModule::test_nonexistent_submodule_prints_error` | 0.577s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_struct_field_bins_present` | 0.658s |
| ✅ | `cli/test_coverage_generate.py::TestPackedStructFieldBins::test_packed_union_skips_field_bins` | 0.653s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_added_node` | 0.206s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_identical` | 0.200s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_json` | 0.202s |
| ✅ | `cli/test_diff.py::TestDiffCLI::test_diff_removed_node` | 0.203s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_basic` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanin_not_found` | 0.189s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_basic` | 0.193s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_fanout_json` | 0.192s |
| ✅ | `cli/test_trace.py::TestTraceCLI::test_trace_help` | 0.217s |

---
*此报告由 pytest 自动生成*