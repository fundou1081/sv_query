# Iteration 342: interface/modport connection aliases（PLAN P42.1）

**Metadata**:
- **Iteration #**: 342
- **Task Tree Level**: L2（PLAN `P42.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（connection alias；2690 passed）

## 🎯 目标

波形工具的完整 hier path 可能走 interface 实例或 modport 成员；
用图内 CONNECTION 边建立别名。

## 🔧 实现

- `_build_aliases` 增加 CONNECTION 边双向别名；
- interface 实例成员 ↔ modport 成员、模块端口 ↔ 外部网络；
- exact 优先；alias 冲突仍 ambiguous；
- 不改变 fanin/fanout 语义（连接 ≠ 驱动）。

## 🧪 测试

- `test_interface_connection_aliases`（iface fixture，双向 aliases）；
- 全量 **2690 passed / 0 failed**。

## ⚠️ 边界

- generate `genblk` 命名差异仍未覆盖；
- CONNECTION 边可能形成大别名集，manifest 体积需关注；
- alias 只是路径映射，不代表数据流向。

## 🔗 相关

- 计划: [PLAN.md P42.1](../../../PLAN.md)
