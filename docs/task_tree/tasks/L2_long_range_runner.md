# Task: long-range 统一 runner（P81）

**状态**: 已完成
**目标**: 补 `run_long_range.py`，让 P69 的 12 题可重复跑 source/T2，并与
interactive runner 共用隔离/结果 schema。

## 交付

1. 从任务 `source`/旧 pilot 生成隔离 workspace（本地 filelist）；
2. source/T2 两边 hard sandbox；
3. T2 不能读 task JSON/ground truth；
4. source/T2 同 prompt、同 max query budget；
5. JSON 结果 + 现有 scorer 兼容；
6. 1 task smoke，再决定 12×3。

## 边界

- 先做 runner，不直接跑 48 agents；
- source/T2 双评分仍在 scorer 扩展中；
- 不改任务 ground truth。
