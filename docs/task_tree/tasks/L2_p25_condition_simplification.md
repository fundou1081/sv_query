# L2 — P25 条件化简/互斥判断（未排期）

**Created**: 2026-10-31 GMT+8
**方豆**: "先只记录，先不做。"
**状态**: 待做，不进入当前迭代。

详细设计: [condition_analysis_plan_2026-10-31](../../architecture/condition_analysis_plan_2026-10-31.md)

## 范围（未来）

- L1：布尔 IR + 局部恒等式；只加 `condition_simplified` / `condition_analysis`，不改原文。
- L2：extractor branch group；多驱动 `driver_conflict`；casez 保守 unknown。
- L3：真值表/BDD（带上限），判断互斥/蕴含/永真；不做 SAT 依赖。

## 约束

- 每个路径原始条件保留；
- 不能证明等价就不化简；
- 四态/casez 风险写清楚。
