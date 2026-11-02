# Iteration 359: 结构审查与动态子图开发计划（PLAN P58）

**Metadata**:
- **Iteration #**: 359
- **Task Tree Level**: L2（PLAN `P58`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 计划完成；等待 P59 清理

## 🎯 本轮动作

把两轮关于可视化/图/动态子图的讨论落成完整开发计划：

- [structural_review_plan_2026-11-02.md](../../architecture/structural_review_plan_2026-11-02.md)
- PLAN P58~P62
- P59 清理任务定义

## 🧭 核心决策

1. 全设计图退出产品面；
2. SignalGraph 保留为唯一结构数据源；
3. 动态子图是 core 查询，不是 view 功能；
4. finding 先于图，图只画 finding 邻域；
5. CIRCT 独立未来 track，不在本计划；
6. 交互式 debug 最后做，且有 gate；
7. 旧代码先冻结、再删除/归档。

## 🚧 下一阶段

**P59 旧可视化资产清理**：

- 盘点/冻结；
- 删除/归档；
- 文档/测试/registry 收口。

P59 完成前不开始 P60 `graph subgraph` 实现。

## 🔗 相关

- 计划: [PLAN.md P58~P62](../../../PLAN.md)
- 清理任务: [L2_visual_cleanup.md](../tasks/L2_visual_cleanup.md)
