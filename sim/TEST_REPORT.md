# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-30 16:45:13",
  "passed": 13,
  "failed": 0,
  "skipped": 0,
  "total": 13
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 13
- **失败**: 0
- **跳过**: 0
- **总计**: 13
- **时间**: 2026-05-30 16:45:13

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_async_reset_excluded` | 0.012s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_combinational_depth_limit` | 0.017s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_combinational_depth_within_limit` | 0.013s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_cycle_scc_collapse` | 0.012s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_parallel_paths_same_depth` | 0.015s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingAnalyzer::test_simple_pipeline_depth` | 0.013s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingSVAMatch::test_sva_next_cycle_match` | 0.013s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingSVAMatch::test_sva_same_cycle_assert` | 0.012s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingSVAMatch::test_sva_two_cycle_delay` | 0.013s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingCycleEstimate::test_15_stage_pipeline` | 0.042s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingCycleEstimate::test_50_stage_pipeline` | 0.119s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingCycleEstimate::test_5_stage_pipeline` | 0.021s |
| ✅ | `regression/test_timing_analyzer.py::TestTimingCycleEstimate::test_multi_path_pipeline` | 0.037s |

---
*此报告由 pytest 自动生成*