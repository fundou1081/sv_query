# Iteration 282: GraphBuilder 后处理 pass 改声明式 pipeline（PLAN P0.3）

**Metadata**:
- **Iteration #**: 282
- **Task Tree Level**: L2（[L1_graph_query_restructure](../tasks/L1_graph_query_restructure.md) / PLAN `P0.3`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（12 个 pass 声明化；执行顺序与原隐式顺序逐项一致；2328 passed）

## 🎯 目标

`GraphBuilder.build()` 里 12 个 pass 靠**隐式顺序**串起来，关键约束只写在注释里
（"upgrade_regs 必须在 bit_nodes 之后"、"bus_bit_bridges 必须在 filter 之后"）。
本次改成声明式 pipeline：每个 pass 声明 `requires` / `provides`，顺序由依赖推导。

## 🔧 新增

`src/trace/core/builder/graph_pipeline.py`

| 类 | 职责 |
|---|---|
| `Stage(name, run, requires, provides, note)` | 一个 pass 的声明（不可变） |
| `GraphPipeline(stages)` | 校验依赖 → 拓扑排序（同层按声明顺序稳定）→ 顺序执行 |

失败显式（铁律 #2）：
- 依赖的 token 无人提供 → `ValueError: 依赖未声明产出的 token`
- 循环依赖 / 无起点 → `ValueError: 存在循环依赖或缺少起点`
- stage 重名 → `ValueError`

## 📋 12 个 stage（与原隐式顺序逐项一致）

| # | stage | requires | provides |
|---|---|---|---|
| 1 | `configure_instances` | — | instances |
| 2 | `extract_nodes` | instances | nodes |
| 3 | `extract_edges` | nodes | edges |
| 4 | `special_signals` | nodes, edges | special_flags |
| 5 | `bit_nodes` | nodes, edges | bit_nodes |
| 6 | `struct_members` | nodes, edges | struct_members |
| 7 | `struct_assigns` | struct_members | struct_assigns |
| 8 | `upgrade_regs` | bit_nodes | reg_nodes |
| 9 | `wrapper_passthrough` | nodes, bit_nodes | wrapper_passthrough |
| 10 | `filter_target` | bit_nodes | filtered |
| 11 | `bus_bit_bridges` | bit_nodes, **filtered** | bus_bit_bridges |
| 12 | `gen_block_map` | nodes, edges | gen_block_map |

**实测执行顺序**（spy 验证）与旧 `build()` 完全一致：

```
configure_instances → extract_nodes → extract_edges → special_signals → bit_nodes
→ struct_members → struct_assigns → upgrade_regs → wrapper_passthrough
→ filter_target → bus_bit_bridges → gen_block_map
```

## 🔧 顺手修的两处

| 位置 | 问题 | 处理 |
|---|---|---|
| `build()` 末尾 | 残留 iter_269 的"孤儿节点清理"注释（逻辑 iter_276 已删） | 删除 |
| `_filter_by_target` | 条件执行在 `build()` 外层（`if self.target_module`） | 守卫移进方法内部 → stage 契约稳定（无条件执行 = 无 target 时直接返回），`bus_bit_bridges` 的 `requires={"filtered"}` 才成立 |

## 🧪 测试

`sim/tests/unit/test_graph_pipeline.py`（7 个）：依赖排序 / 同层稳定顺序 /
声明顺序与依赖冲突时依赖优先 / 缺 provider 报错 / 循环报错 / 重名报错 / 只执行一次。

## ✅ 验证（行为零变化）

| 验证 | 结果 |
|---|---|
| 图基线（6 fixture） | ✅ 零差异 |
| 全量门禁 | ✅ **2328 passed / 0 failed**（+7 pipeline 测试） |
| stage 顺序 | ✅ 与旧隐式顺序逐项一致（spy 实测） |
| ruff | ✅ All checks passed |

## 💡 收益

- 新增 pass 有**明确挂点**：在列表里加一个 `Stage` 并声明 requires/provides，
  写错依赖会在构建前 `ValueError`，而不是靠"撞测试"发现
- 顺序约束从注释变成**可执行契约**（`bus_bit_bridges.requires` 含 `filtered`）
- `build()` 从 40 行过程调用变成"一张表"（12 个声明），阅读成本下降

## 🔗 相关

- 计划: [PLAN.md P0.3](../../../PLAN.md)
- 前置: [iter_280 图基线](iter_280_graph_snapshot_baseline.md) / [iter_281 拆 driver 递归](iter_281_split_driver_recursion.md)
