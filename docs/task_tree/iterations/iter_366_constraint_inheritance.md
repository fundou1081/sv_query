# Iteration 366: constraint 继承链 + rand 标记（PLAN P64）

**Metadata**:
- **Iteration #**: 366
- **Task Tree Level**: L2（PLAN `P64`）
- **Created**: 2026-11-04 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "constraint 继承链，rand 标记，这些要做"）
- **Outcome**: ✅ 完成；2520 passed

## 🎯 问题

- 子类继承约束变量 `x` 先被 constraint builder 建成 SIGNAL placeholder，
  继承传播跳过 → `child.x` 不是 CLASS_PROPERTY，`trace constraints(child.x)` 空；
- class member 没有 rand/randc/type 元数据；
- constraint block 没有 defined_in/inherited。

## 🔧 修复

1. 继承属性复制 `rand/type` metadata；
2. 已存在的 SIGNAL placeholder 升级为 CLASS_PROPERTY，并补 CLASS→PROP 边；
3. `ConstraintInfo` 增加 `defined_in/inherited`；
4. copied constraint block 记录 `extra.inherited_from`；
5. `trace constraints` 增加 `rand_vars/defined_in/inherited`；
6. `class` members 增加 `is_rand/rand_mode/type`。

## 🧪 测试

- 继承 `child.x` 是 CLASS_PROPERTY + rand；
- `constraint_blocks`：`c_base` defined_in=base/inherited=true，
  `c_child` defined_in=child；
- `trace constraints top.c.x`（实例属性未建节点）可解析；
- 全量 **2520 passed / 0 failed**。

## ⚠️ 边界

- super.c1 只有 SUPER_CALL 边；
- rand_mode() 运行时开关不建模；
- randc 周期状态不建模。

## 🔗 相关

- 契约: [class_constraint_covergroup_contract_2026-11-03.md](../../architecture/class_constraint_covergroup_contract_2026-11-03.md)
- 计划: [PLAN.md P64](../../../PLAN.md)
