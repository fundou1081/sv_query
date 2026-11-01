# Iteration 345: scope 可发现性收尾（PLAN P44.5）

**Metadata**:
- **Iteration #**: 345
- **Task Tree Level**: L2（PLAN `P44.5`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续 scope 收尾"）
- **Outcome**: ✅ 完成（interface/generate/class scope；2699 passed）

## 🎯 目标

scope 作为入口层，需要能发现：
- interface 成员；
- generate scope 信号；
- class 类型成员/实例。

## 🔧 实现

- `scope.kind`: instance/generate/class；
- `signals`：scope 直接子信号/端口 + canonical_id；
- class 优先于 generate（`packet.addr` 是成员不是 generate）；
- generate scope 识别：非 MIG instance 但有 `<path>.` 子节点；
- class scope：members/instances（复用 trace_class_*）；
- 顶层模块 path 仍支持。

## 🧪 测试

- interface scope signals（data/valid）；
- generate scope signals（top.genblk1[0].x）；
- class scope members/instances；
- unknown 改为 `scope not found`；
- 契约 scope_signal/kind/signals/members/instances；
- 全量 **2699 passed / 0 failed**。

## ⚠️ 边界

- interface 的 kind 仍是 instance（未单独标 interface）；
- class scope 不展开方法体；
- generate children 仍为空（只列 signals）；
- scope 不做因果追踪。

## 🔗 相关

- 计划: [PLAN.md P44.5](../../../PLAN.md)
