# PLAN — 全局唯一计划树

> **唯一真相源**：sv_query **所有代码修改计划**只登记在本文件。
> 迭代记录（[docs/task_tree/iterations/](docs/task_tree/iterations/)）是**历史**；本文件是**现在做什么、做到哪**。
>
> 维护规则见 [AGENTS.md §2](AGENTS.md)；机械校验：`python3 tools/check_plan.py`。
>
> 格式（每行一项，子项用 `-- ` 前缀，id 全局唯一）：
> ```
> current item : P1.2 删 `ModuleInstanceGraph.port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` <待做>
>
> P0 建图层与查询层的结构化拆分 <已完成>
> -- P0.1 图快照基线工具 <待做>
> ```
> 状态词表：`待做` / `进行中` / `已完成` / `阻塞` / `放弃`（只能这五个）。
> 父项可整体标 `进行中`（表示该组在做）；**叶子项**最多一项 `进行中`，
> 且当 `current item` 标为 `进行中` 时，它必须是那个叶子项。

## 当前项

current item : P1.2 删 `ModuleInstanceGraph.port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` <待做>

## 计划树

P0 建图层与查询层的结构化拆分 <已完成>
-- P0.1 图快照基线工具：图的节点/边 snapshot diff（拆 P0.2 的前提） <已完成>
-- P0.2 拆 `_trace_drivers_recursive`（343 行）：wrapper 跨实例 / 位级提升 / 自环分类 / q-d 互补 / 边过滤 / 源分类 六类规则拆成独立策略函数 <已完成>
-- P0.3 `GraphBuilder` 6 个后处理 pass 改声明式 pipeline（inputs/outputs，与 UnifiedTracer 一致） <已完成>
P1 视图层去双命名空间 <进行中>
-- P1.1 `visualize module` 换实例级边推导（不再依赖 MIG 的类型映射） <已完成>
-- P1.2 删 `ModuleInstanceGraph.port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` <待做>
P2 边缘场景补测 <待做>
-- P2.1 位选跨模块 / interface 成员 / inout 三态 / class-struct 成员 的 drive-load 回归 <待做>
P3 长期 backlog（不排期） <待做>
-- P3.1 `UnifiedTracer` 三个巨型私有方法（173 / 134 / 151 行） <待做>
-- P3.2 缓存只有总量 LRU 上限，无"按工程过期" <待做>
-- P3.3 [docs/EXP_IDEAS.md](docs/EXP_IDEAS.md) 的 10 条退役想法 —— 未来逐个重做 <待做>

## 已完成（保留最近记录，便于核查上一轮）

P4 已完成归档 <已完成>
-- P4.1 单一命名空间收口：影子节点归零、extractor 4→2（iter_276） <已完成>
-- P4.2 删除 `port_to_internal` 自映射（iter_277） <已完成>
-- P4.3 `distance` 真实跳数 + 底座健壮性审计（iter_278） <已完成>

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-25 | 建立本计划树；P0~P3 来自底座审计结论（iter_278） |
