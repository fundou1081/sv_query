# Iteration 278: `distance` 真实跳数 + 底座健壮性审计

**Metadata**:
- **Iteration #**: 278
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "现在底座足够干净了吗，基础的 drive load 功能足够稳健了吗？"）
- **Outcome**: ✅ `distance` 修复；审计出 1 个已消失的限制 + 2 个仍在的缺口

## 🎯 目标

回答"底座是否干净 / drive-load 是否稳健"，用**实测**而不是感觉。

## 🔬 审计结果

### ✅ 已验证稳健的项

| 场景 | 实测 |
|---|---|
| 跨模块链（3 层：top → mid → leaf） | `fanout(din)` = u_mid.a / u_leaf.a / u_leaf.y / u_mid.y / w1 / dout，六跳完整 |
| 反向 | `fanin(dout)` 对称完整，回到 `din` |
| depth 单调性 | `d1 ⊆ d2 ⊆ all` 成立（修自环后） |
| 未知信号 | 返回空 + 不崩 |
| generate 位隔离 | `y[i]` 只含本 entry（iter_274/132 回归） |
| wrapper 直通 | 嵌套 generate（mid → leaf）能穿透且不串 entry |
| `--module` 限定 | `loads sync0 --module synchronizer` 结果全在该实例内 |
| 快照查询 | **与 live 逐条一致**（iter_276 单一命名空间后, 端口边已在图里, 不再依赖 MIG） |

### 🔧 修复：`distance` 恒为 1

`trace_common.attach_distances()`：响应组装阶段从查询根做一次 BFS
（fanout 沿 successors / fanin 沿 predecessors），按最短跳数填 `distance`。
**不改图节点**（同一图会被多次查询, 之前正是因为"不能 mutate 共享 TraceNode"才一直恒为 1）。

实测（minimal_3module）：

```
valid_i → sa1.valid_i(d=1) → lp1.data_i(d=2) → stage1_q(d=3) → … → ready_o(d=8)
```

### 📌 审计中确认的两个剩余缺口（已登记）

| # | 缺口 | 说明 |
|---|---|---|
| 1 | 快照与图缓存**不带 MIG 的实例类型信息** | 现在 query 不需要 MIG, 但 `visualize module --mig` 仍要; 快照恢复后没有 MIG, 该视图降级 |
| 2 | `ModuleInstanceGraph.port_to_internal` (instance → module_type.port) | 仅 `visualize module --mig` 的实例边推导在用, 属视图层启发式 |

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | **2302 passed / 0 failed** |
| golden 更新 | `trace_batch/fanin_2signals.json`（distance 语义修正, 2 处） |
| KNOWN_LIMITATIONS §3.3 | 3 条全部标"已修" |

## 💡 结论（给方豆）

- **连通层干净**：单一命名空间、无影子节点、无清理 pass、无自映射。
- **drive/load 主干稳健**：跨模块 / generate / wrapper / 限定查询 / 快照 全部实测通过。
- **仍未闭环**：视图层（`visualize module --mig`）还依赖 MIG 的模块类型映射；
  这是唯一剩下的"双命名空间"概念残留，但**不影响 drive/load**。

## 🔗 相关

- 前序: [iter_277 删除自映射](iter_277_remove_self_mapping.md)
