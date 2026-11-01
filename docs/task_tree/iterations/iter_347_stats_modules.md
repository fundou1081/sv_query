# Iteration 347: stats.modules 修正（PLAN P46.1）

**Metadata**:
- **Iteration #**: 347
- **Task Tree Level**: L2（PLAN `P46.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "接下来看其他的"）
- **Outcome**: ✅ 完成（真实 modules；2701 passed）

## 🐛 问题

`stats.modules` 实测恒为 `[]`：代码读 `graph.modules`，但 `SignalGraph` 没有该属性。

## 🔧 修复

从两处构造真实模块清单：

- `tracer.get_instances()` 的 `module_type`；
- adapter `_root.topInstances` 的顶层 module 名。

去重排序；异常时保持空集（不伪造）。

## 🧪 测试

`test_stats_modules.py`：
- struct → `["child", "top"]`
- sync_fifo → `["sync_fifo"]`

全量 **2701 passed / 0 failed**。

## ⚠️ 边界

- 返回模块**类型名**，不是实例路径；
- 纯 package/无法实例化的 module 不在清单；
- 仍不提供每模块节点/边统计（未来按需）。

## 🔗 相关

- 计划: [PLAN.md P46.1](../../../PLAN.md)
