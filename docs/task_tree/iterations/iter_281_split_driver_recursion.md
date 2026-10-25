# Iteration 281: 拆 `_trace_drivers_recursive`（PLAN P0.2）

**Metadata**:
- **Iteration #**: 281
- **Task Tree Level**: L2（[L1_graph_query_restructure](../tasks/L1_graph_query_restructure.md) / PLAN `P0.2`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续吧"）
- **Outcome**: ✅ 完成（343 行 → 81 行编排 + 14 个小方法；**行为零变化**）

## 🎯 目标

`_trace_drivers_recursive` 混装 6 类规则，改一处会碰另一处的隐含前提
（iter_275 正因此失败）。本迭代把它拆成**编排层 + 单规则方法**，用 P0.1 的图基线
证明行为零变化。

## 🔧 拆分结果

| 职责 | 方法 | 行数 |
|---|---|---|
| 编排（守卫 → 位级 → 边循环） | `_trace_drivers_recursive` | **81** |
| ① 节点缺失 / part-select | `_trace_missing_node` | 13 |
| ② 位级：子位展开 / 父总线提升 | `_expand_incoming_bit_select` / `_maybe_lift_to_parent_bus` | 10 / 27 |
| ③ 自环分类 | `_handle_self_loop` | 9 |
| ④ 控制边过滤 | `_is_control_edge` | 13 |
| ⑤ 连接边分流 | `_handle_connection_source`（分发 16）→ `_handle_port_out_source`(28) / `_handle_port_in_source`(12) / `_handle_wire_source`(14) | 70 |
| ⑥ 驱动边追加 / 递归 | `_append_source` / `_recurse_if_unseen` / `_pick_driver_edge` | 12 / 4 / 9 |
| 支撑判据 | `_has_incoming_driver` / `_has_incoming_connection` / `_has_internal_driver` / `_wrapper_passthrough_sources` / `_sibling_ports` | 6 / 5 / 9 / 12 / 24 |

文件总行数 913 → 860（历史注释收敛进方法 docstring，逻辑行减少）。

## 🐛 拆分过程中发现的两个**隐式行为**（差点改坏）

| # | 隐式语义 | 如果没有测试会怎样 |
|---|---|---|
| 1 | CONNECTION 源是 `REG` 等**未列举类型**时，旧代码靠 `if` 链 **fallthrough** 落到"其他边类型继续追溯" | 拆分后直接 `return` → `fanin(uart_top.rx_data_o)` 变空（`pop_data_o` 是 REG，经 CONNECTION 连到输出） |
| 2 | `PORT_IN` 分支自带 `continue`：**有前驱时不追加、也不递归** | 拆成"有前驱则递归"会多追一层，改变 fanin 集合 |

两个问题都被 `test_trace_batch` / `test_accuracy_a1_a2` 当场抓住，修完重跑全量才通过。
→ **教训**：巨型 `if` 链里的 `continue`/fallthrough 是隐式契约，拆函数时必须逐条对齐。

## ✅ 验证（行为零变化）

| 验证 | 结果 |
|---|---|
| 图基线（6 fixture / 206 节点 / 463 边） | ✅ 零差异 |
| 全量门禁 | ✅ **2321 passed / 0 failed**（拆分前后完全一致） |
| 追踪专项（batch / filters / accuracy / schemas） | ✅ 全绿 |
| `cli` 冒烟 | ✅ |

## 📊 收益

- 单函数最长 81 行（原 343），子方法最长 28 行
- 6 类规则**各自可单独读/改/测**；新增规则有明确挂点（新增 `_rule_*` 或在编排层加一步）
- 原实现里 6 段"历史教训"注释，收敛为各方法的契约说明，不再挤在一个函数里

## 💡 给 P0.3 的经验

`GraphBuilder` 的 6 个后处理 pass 同样存在**顺序隐式契约**（如 wrapper 直通必须在
位节点之后）。P0.3 改声明式 pipeline 时，先用图基线锁定顺序，再逐步显式化依赖。

## 🔗 相关

- 计划: [PLAN.md P0.2](../../../PLAN.md)
- 前置: [iter_280 图快照基线](iter_280_graph_snapshot_baseline.md)
- 前序失败教训: [iter_275](iter_275_orphan_cleanup_attempt.md)
