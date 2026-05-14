# sv_query 测试报告
============================================================

<!-- METADATA -->
{
  "generated": "2026-05-14 19:19:04",
  "passed": 23,
  "failed": 0,
  "skipped": 0,
  "total": 23
}
<!-- /METADATA -->

## 测试摘要

- **通过**: 23
- **失败**: 0
- **跳过**: 0
- **总计**: 23
- **时间**: 2026-05-14 19:19:04

## 测试结果详情

| 状态 | 测试ID | 时长(秒) |
|------|--------|----------|
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_added_edges` | 0.021s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_added_nodes` | 0.014s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_diff_reachability` | 0.017s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_forward_reachability` | 0.011s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_forward_reachability_with_depth` | 0.010s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_identical_graphs` | 0.013s |
| ✅ | `integration/test_graph_diff.py::TestGraphDiff::test_removed_nodes` | 0.014s |
| ✅ | `integration/test_graph_diff_health.py::TestStableCore::test_stable_core_added_node` | 0.008s |
| ✅ | `integration/test_graph_diff_health.py::TestStableCore::test_stable_core_edge_changed` | 0.007s |
| ✅ | `integration/test_graph_diff_health.py::TestStableCore::test_stable_core_identical_graphs` | 0.007s |
| ✅ | `integration/test_graph_diff_health.py::TestStableCore::test_stable_core_removed_node` | 0.008s |
| ✅ | `integration/test_graph_diff_health.py::TestHealthScore::test_health_score_changed` | 0.008s |
| ✅ | `integration/test_graph_diff_health.py::TestHealthScore::test_health_score_identical` | 0.003s |
| ✅ | `integration/test_graph_diff_health.py::TestCouplingWarning::test_coupling_high` | 0.000s |
| ✅ | `integration/test_graph_diff_health.py::TestCouplingWarning::test_coupling_low` | 0.000s |
| ✅ | `integration/test_graph_diff_health.py::TestDiffWithHealth::test_complete_health_analysis` | 0.007s |
| ✅ | `integration/test_snapshot.py::TestSignalGraphSerialization::test_roundtrip_simple` | 0.000s |
| ✅ | `integration/test_snapshot.py::TestSignalGraphSerialization::test_roundtrip_with_modport` | 0.000s |
| ✅ | `integration/test_snapshot.py::TestSnapshotManager::test_compare` | 0.001s |
| ✅ | `integration/test_snapshot.py::TestSnapshotManager::test_delete` | 0.000s |
| ✅ | `integration/test_snapshot.py::TestSnapshotManager::test_list` | 0.091s |
| ✅ | `integration/test_snapshot.py::TestSnapshotManager::test_save_and_load` | 0.000s |
| ✅ | `integration/test_snapshot.py::TestSnapshotManager::test_save_overwrite` | 0.001s |

---
*此报告由 pytest 自动生成*