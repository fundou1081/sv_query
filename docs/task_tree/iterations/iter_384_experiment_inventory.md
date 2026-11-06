# Iteration 384: 实验资产盘点（P80）

**状态**: ✅ 完成
**日期**: 2026-11-06

## 发现

- 唯一可复现 multi-turn runner：`interactive_debug/run_seed.py`；
- long-range 12 题：有任务/评分/复验，但没有 runner，也不是多轮；
- 4-task pilot：只有结果/报告；
- hard isolation：只有 PoC，不是矩阵；
- CDC walkthrough：人工多步示例，不是 benchmark。

## 产出

[EXPERIMENT_INVENTORY_2026-11-06.md](../../validation/EXPERIMENT_INVENTORY_2026-11-06.md)

## 结论

两个 task family 分开评价；补统一 runner + hard isolation + dual scoring。
