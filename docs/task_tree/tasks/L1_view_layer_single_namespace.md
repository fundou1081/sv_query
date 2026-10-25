# L1 — 视图层去双命名空间（PLAN P1）

**Status**: ✅ 完成（PLAN.md `P1`，iter_283~284）
**Created**: 2026-10-25
**Owner**: 方豆 / AI

## 背景

连通层（节点/边/查询）已在 iter_276~277 收口为**单一命名空间**（实例路径）。
视图层还剩最后一处双命名空间概念：`visualize module --mig` / `arch` 的
instance-to-instance 边，用 MIG 的 `port_to_internal`（`inst_port → module_type.port`）
按"同模块类型 + 同端口名"分组——多实例场景会误连。

## Sub-tasks（与 PLAN.md 对齐）

| id | 内容 | 验收 |
|---|---|---|
| P1.1 | `visualize module` / `arch` 换实例级图推导 | ✅ 边来自真实跨实例网络；`--no-mig` 仍可关闭；测试改写（iter_283） |
| P1.2 | 删 MIG `port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` | ✅ 已删；`PortInfo.internal_signal` 改实例级 id；2330 passed（iter_284） |

## 约束

1. 边必须是**真实连通**（图里存在的网络），不允许按类型/名字推断
2. 广播网络（clk/rst）每网络最多 4 对，防 N² 爆炸（与旧上限一致）
3. JSON schema 字段保持向后兼容：`src/dst/src_instance/dst_instance/internal/port/port_src/port_dst`

## 参考

- 连通层收口: [iter_276](../iterations/iter_276_clean_single_namespace.md) / [iter_277](../iterations/iter_277_remove_self_mapping.md)
- 本组第一项: [iter_283](../iterations/iter_283_instance_level_module_edges.md)
