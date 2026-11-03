# Iteration 361: 旧可视化代码清理（PLAN P59.2）

**Metadata**:
- **Iteration #**: 361
- **Task Tree Level**: L2（PLAN `P59.2`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 代码/测试清理完成；文档收口进入 P59.3

## 🎯 动作

按 P59.1 盘点结果删除全设计图命令与渲染器：

- 删除 `src/cli/view/`（7 个 visualize + arch/design）
- 删除 `src/cli/_viz_common.py`
- 删除 `src/trace/core/graph/viz/`（VizData/ELK/checker/engine）
- 删除 `analyzer/dataflow_viz.py` / `viz_legend.py`
- 保留 `expression_tree.py`（core 表达式树，legacy 路径）
- 保留 `pipeline_viz.detect_pipeline`（core 语义）
- 保留 `trace overview`、`trace fanin/fanout --format dot`（过渡局部图）

## 🧹 测试

- 删除可视化专用测试/usage 断言
- 更新 layering / hostile input / filelist parity / adversarial / strict_uart
- 修正 `check_crap.py`：删除文件没有当前内容时跳过（P59 踩到的门禁 bug）
- 全量 **2492 passed / 0 failed**（原 2734；-242 为删除旧可视化测试）
- 真实项目 smoke: uart/axi/picorv32 全 ok
- 文档收口: README / PRIMARY_FEATURES / INDEX / ARCHITECTURE banner / CLI cheatsheet

## 🧩 保留说明

- `src/trace/core/graph/viz/expression_tree.py` 不是渲染器，是 `expr_tree_builder` 的 core 依赖；
  因复杂度棘轮按路径比较 HEAD，暂留 legacy 路径，后续单独迁移。
- `trace fanin/fanout --format dot` 是**局部查询图**，不是全设计图；在 P60/P62 后再评估替换。

## 🚧 下一步（P59.3）

- 清理/标记旧可视化文档（VISUALIZATION/VIZ_*）；
- 更新 registry/CLI surface/capabilities 描述；
- 真实项目 smoke；
- 收口后开始 P60。

## 🔗 相关

- 计划: [PLAN.md P59](../../../PLAN.md)
- 盘点: [visualization_cleanup_inventory_2026-11-03.md](../../architecture/visualization_cleanup_inventory_2026-11-03.md)
