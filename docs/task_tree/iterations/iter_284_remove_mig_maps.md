# Iteration 284: 删除 MIG 的模块定义端口映射（PLAN P1.2）

**Metadata**:
- **Iteration #**: 284
- **Task Tree Level**: L2（[L1_view_layer_single_namespace](../tasks/L1_view_layer_single_namespace.md) / PLAN `P1.2`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（双命名空间最后残留删除；2330 passed）

## 🎯 目标

`ModuleInstanceGraph` 仍保留 `port_to_internal` / `internal_to_port`
（`instance.port → module_type.port`）与 `get_internal_signal` / `get_port_path`。
P1.1 后已无生产消费者（视图层改用实例级图），本次删除**最后一块**双命名空间概念。

## 🔧 删除清单

| 位置 | 内容 |
|---|---|
| `ModuleInstanceGraph` | 字段 `port_to_internal` / `internal_to_port` 及填充循环 |
| `ModuleInstanceGraph` | `get_internal_signal()` / `get_port_path()` |
| `ModuleInstanceNode` | `get_internal_signal()` |
| `ModuleInstanceGraph.__init__` | 无人使用的 `signal_graph` 参数（唯一用途就是上面两个方法） |
| `PortInfo.internal_signal` | 值语义改为**实例级端口 id**（`top.u_dut.clk`），不再是 `dut.clk` |
| 注释 | dataflow / connection / signal / trace_common / arch 中引用旧映射的说明 |

`PortInfo` 字段本身保留（`connections` / `instances --json` 的 schema 不变），
只是值从模块定义短名变成实例级 id。

## 🧪 测试迁移

| 文件 | 变更 |
|---|---|
| `test_cross_module_tracking.py` | 新增 `_port_signal()` helper；`get_internal_signal('x.y')` → 端口信息查询；期望值 `dut.clk` → `top.u_dut.clk`；`port_to_internal` 包含性断言 → 端口信息存在 |
| `test_mig_generate_block.py` | `port_to_internal` 断言 → `mig.instances[...].ports` 非空 |
| `test_cli_semantic_queries.py` | 双向映射用例 → `PortInfo.internal_signal == 实例级端口 id` |

## ✅ 验证

| 验证 | 结果 |
|---|---|
| 全量门禁 | ✅ **2330 passed / 0 failed** |
| MIG 回归（cross_module_tracking） | ✅ 49 passed |
| generate block MIG | ✅ |
| CLI 冒烟 | `connections inst_demo.u_adder` → `internal_signal: inst_demo.u_adder.a` |

## 📌 结果：项目里再无模块定义命名空间的映射

```
SignalGraph：只有实例级节点/边
ModuleInstanceGraph：只有实例层级 + 端口信息（值 = 实例级端口 id）
DataFlow / PathResolver / 视图层：全部实例级
```

## 🔗 相关

- 计划: [PLAN.md P1.2](../../../PLAN.md)
- 前置: [iter_283 实例级 module 边](iter_283_instance_level_module_edges.md)
- 收口起点: [iter_276](iter_276_clean_single_namespace.md) / [iter_277](iter_277_remove_self_mapping.md)
