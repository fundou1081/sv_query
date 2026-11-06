# Iteration 385: long-range 统一 runner（P81）

**状态**: ✅ runner + 单题 smoke
**日期**: 2026-11-06

## 实现

- `tools/benchmark/run_long_range.py`；
- source/T2 workspace 只含 RTL + 本地 filelist；
- source 用 `source.sb`；T2 用新 `t2_long.sb`（deny task JSON/truth）；
- 模型 patch 复制到 workspace（repo 在 source 沙箱内不可读）；
- 输出兼容 `score_long_range.py`。

## Smoke

`axi_araddr_neighbors` / DeepSeek-Flash：

- source: exact, 76.6s；
- T2: exact, 86.5s。

## 未做

- 只有 1 题；
- budget 未硬限制；
- 未做双评分；
- 未跑 4/12 题矩阵。
