# Iteration 360: 旧可视化资产盘点（PLAN P59.1）

**Metadata**:
- **Iteration #**: 360
- **Task Tree Level**: L2（PLAN `P59.1`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 盘点完成；未删除代码，等待 P59.2

## 🎯 动作

把 P57 + P58 计划合并到 `main` 后，完成旧可视化资产盘点：

- CLI：7 个 visualize + arch/design + trace overview/dot；
- 源码：`src/cli/view`、`src/trace/core/graph/viz`、旧 analyzer 渲染；
- 测试/文档：可视化专用测试、V5/V6 文档、PRIMARY_FEATURES。

## 📋 决策

- 全设计图命令全部退役；
- `trace overview` 保留（叙述型 review）；
- `trace fanin/fanout --format dot` 保留为过渡局部图；
- `detect_pipeline` 保留，`pipeline_viz` 渲染部分删除；
- 旧 ELK/VizData/DOT 渲染器删除；P62 若需要重做最小局部渲染。

## 📄 产物

- [visualization_cleanup_inventory_2026-11-03.md](../../architecture/visualization_cleanup_inventory_2026-11-03.md)
- PLAN `P59.1` 完成，`P59.2` 待做

## ⚠️ 说明

本轮**没有删除任何命令/代码/测试**。P59.2 将按盘点表执行删除/归档，并跑全量回归。

## 🔗 相关

- [PLAN.md](../../../PLAN.md)
- [P59 任务](../tasks/L2_visual_cleanup.md)
