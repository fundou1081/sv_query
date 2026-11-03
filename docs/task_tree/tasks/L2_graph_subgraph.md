# Task: graph subgraph 动态子图（P60）

**状态**: 已完成
**计划**: [structural_review_plan_2026-11-02.md](../../architecture/structural_review_plan_2026-11-02.md) §5

## 目标

实现 core `graph subgraph`：

- seed 解析（exact/relative/ambiguous/not_found）；
- depth/direction/edge-kinds/max-nodes/max-edges；
- boundary/truncated/stats；
- 稳定排序、canonical ID、JSON；
- 不复制整图、不做全图 BFS。

## 子项

- P60.1 JSON schema/命令参数；
- P60.2 core + CLI；
- P60.3 测试/契约/文档。
