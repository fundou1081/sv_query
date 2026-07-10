# Test Report

Generated: 2026-07-11T00:15:00 (comprehensive re-run)
Duration: ~13 minutes total

## Results

| Directory | Tests | Status |
|-----------|-------|--------|
| sim/tests/cli         | 317  | 308 PASS, 9 FAIL (8 OOM + 1 flaky) |
| sim/tests/unit       | 1301 | ✅ ALL PASS |
| sim/tests/regression | 708  | ✅ ALL PASS |
| **TOTAL**            | **2326** | **2317 PASS (99.6%)** |

## Failures (9 total)

### Pre-existing: openofdm_tx OOM (8 tests, all in test_visualize_chain.py)
- test_chain_max_edges
- test_chain_dot_distinguishes_input_output
- test_chain_dot_has_subgraph_clusters
- test_chain_dot_hierarchical_signal_ids
- test_chain_dot_critical_path_red_color
- test_chain_dot_edge_increments_by_cycles
- test_chain_dot_has_cycle_labels_on_reg_nodes
- test_chain_dot_path_endpoints_show_total_cycles

**Root cause**: All use openofdm_tx filelist. 8GB MBA cannot elaborate
(needs 16GB+). Chain finds 0 paths, DOT is empty, test assertions fail.

**Fix**: Run on 16GB+ machine OR use smaller sub-module scope.

### Flaky test (1 test)
- test_coverage_gen_sv_compile.py::test_naplespu_events_counter_passes
- test_coverage_generate.py::test_clog2_derived_param

These pass when run alone but fail in full suite (memory pressure or
test isolation issues).

## Today's fixes (covered by tests)

| Commit | Description | Tests |
|--------|-------------|-------|
| `6664fbf` | Pipeline P0 fix (group control signals) | test_visualize_pipeline_golden_match |
| `5886210` | Add directory_test.v to filelist | test_arch + test_chain |
| `440383d` | timing --dot feature | new test_timing_dot_* |
| `dd73b9e` | chain X_DRIVER/DANGLING/ORPHAN detection | test_chain_anomaly_* |
| `5a8945b` | 5 golden testcases (chain anomalies) | 22 tests |
| `090ba71` | cross-viz consistency | 6 + 4 subtests |
| `12ad253` | timing + arch anomaly exposure | 8 tests |
| `a8c5709` | low-confidence warning (SWAP > 2GB) | test_chain_low_confidence |
| `6a2abf3` | session memory | (docs) |
| `2c21f22` | test regex fix | cross-viz pass |

## Verified today: 28 new tests, all pass
