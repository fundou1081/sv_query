# Iteration 390: 统一双评分（P86）

**状态**: ✅
**日期**: 2026-11-07

## 实现

- `tools/benchmark/scoring.py`：canonical + semantic；
- direct 任务 semantic=None；
- neighborhood 接受 alias；
- `score_long_range.py` 接入；
- `run_neighborhood.py` 删除本地两套检查。

## 修正

P85 的旧 strict 6/12 重算为 **canonical 4/12**；  
semantic 仍 11/12 vs 11/12。

## 测试

- `test_dual_scoring.py` 4 tests；
- 全量 2556 passed。
