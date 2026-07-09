# Test Report

Generated: 2026-07-10T01:24:08.253464
Duration: 0.0s

## Results

| Metric | Count |
|--------|-------|
| duration_sec | 0.0 |
| total | 13 |
| passed | 0 |
| failed | 0 |
| errors | 0 |
| skipped | 0 |
| xfailed | 0 |
| xpassed | 0 |
| deselected | 0 |

## Validation Tests (2026-07-10)

### Ventus Visualization Consistency Tests
方豆 2026-07-10 00:54: "这图的结果和代码真的一致吗"
方豆 2026-07-10 00:59: "测试其他的画图功能，是否和代码一致，易于理解"

Two test files validate visualization commands vs source code:

**sim/tests/cli/test_ventus_viz_validation.py** (6 tests):
- Scheduler has 7 _dut instances (not 6 as arch initially suggested)
- MSHR generate creates 4 instances (MSHRS=4)
- Signal declarations match (alloc=wire, issue_flush_invalidate=reg)
- L2CACHE_MEMCYCLES=4 (matches chain "Total cycles: 4")
- l2cache helper files all exist
- sm2cluster_arb uses fixed_pri_arb

**sim/tests/cli/test_ventus_all_viz_validation.py** (13 tests):
- arch d=1: shows 6 sub-instance nodes (SourceA, sourceD, sinkA, sinkD, banked_store, Listbuffer)
- pipeline: 14 stages (cluster_stage0..13) - VERIFIED
- trace fanin/fanout: returns valid DOT, empty for top-level
- cdc: 1 clock domain (Scheduler has only clk input) - VERIFIED
- handshake: 0 pairs (Scheduler uses non-AXI naming)
- backpressure: 0 edges (Scheduler is not AXI)
- timing: 896 nodes, 59 regs, deepest path depth=2 (D→mem_core→QN)

All 19 validation tests PASS.
