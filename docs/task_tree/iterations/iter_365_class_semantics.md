# Iteration 365: class / constraint / covergroup CLI（PLAN P63）

**Metadata**:
- **Iteration #**: 365
- **Task Tree Level**: L2（PLAN `P63`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "class 相关的，需要增强，constraint，covergroup 这些 sv 特有的"）
- **Outcome**: ✅ 完成；2518 passed

## 🎯 动作

- `class --relations` 新增：
  - `constraint_blocks`（vars/conditions/expr_count）
  - `covergroups`（含祖先定义的摘要）
- 新增 `trace constraints <property>`（类型/实例；独立语义域）
- 新增 `trace covergroups` / `trace coverpoints` / `trace covergroup`
- `trace covergroup --rand` 暴露属性→约束链
- `UnifiedTracer.list_covergroups()` 公共 API

## 🧪 测试

- class relations 约束块 + covergroup 摘要
- constraint 类型/实例查询、未知属性错误
- covergroups list / coverpoints reverse / sampling / rand
- 未知 covergroup 错误
- 契约字段
- 全量 **2518 passed / 0 failed**

## ⚠️ 边界

- 不新增提取语法；只暴露既有 ConstraintTracer/CovergroupTracer；
- inline constraint 仍不支持；
- covergroup 仍是观察域，不进入 fanin；
- UVM factory/多态不做。

## 🔗 相关

- 契约: [class_constraint_covergroup_contract_2026-11-03.md](../../architecture/class_constraint_covergroup_contract_2026-11-03.md)
- 计划: [PLAN.md P63](../../../PLAN.md)
