# Task: 旧可视化资产清理（P59）

**状态**: 待做
**计划**: [structural_review_plan_2026-11-02.md](../../architecture/structural_review_plan_2026-11-02.md) §8
**前置**: P58 计划完成

## 可验证目标

1. 盘点所有 `visualize` / `arch` / `design` / viz renderer / 文档 / 测试；
2. 先冻结全设计图命令，跑全量；
3. 删除或归档不保留资产，保留 review 所需最小渲染能力；
4. 更新 registry/capabilities/docs/tests；
5. 全量 + 真实项目 smoke 0 failed。

## 不做

- 不开始 `graph subgraph` 实现（P60）；
- 不删除 SignalGraph / trace / verify / bit-width 核心修复。
