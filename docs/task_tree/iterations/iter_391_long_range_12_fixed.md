# Iteration 391: 12-task fixed protocol（P87）

**状态**: ✅
**日期**: 2026-11-07

## 运行

- 12 题 × 2 模型 × 2 臂 × 2 seed = 96；
- hard isolation；fact check；query log；`--depth 1`；
- 全部 rc0/parsed/fact_ok；无 429。

## 结果

- T2 48/48；
- source 32/48；
- source high-conf 错 9/48；
- T2 high-conf 错 0/48；
- DeepSeek T2 wall 33.5s；MiniMax T2 63.5s。

## 边界

direct tasks；2 seed；exact canonical only；不是 debug reasoning。
