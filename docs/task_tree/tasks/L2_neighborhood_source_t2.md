# Task: neighborhood source/T2 pilot（P85）

**状态**: 已完成
**目标**: 2 场景 × 3 模型 × 2 臂 × 2 seed = 24 agents（原计划 2 模型，加 M3.1）。

## 场景

- complex_constraints：`top.e.p.len` 邻域；
- mux_neighborhood：`top.q` 邻域。

## 要求

- source/T2 hard sandbox；
- source 无 `sv_query`、无 repo；
- T2 不能读 task JSON/ground truth；
- 同 prompt、budget；
- fact check；
- 最终 JSON 必须报告 queries（source 可空）；
- 2 models：MiniMax-M3 / DeepSeek-Flash。

## 验收

- canonical neighborhood fields；
- false-confident；
- query/round 协议；
- 不扩 12×3。
