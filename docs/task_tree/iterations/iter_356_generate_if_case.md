# Iteration 356: generate if/case width 强化（PLAN P55）

**Metadata**:
- **Iteration #**: 356
- **Task Tree Level**: L2（PLAN `P55`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "generate if case 需要强化"）
- **Outcome**: ✅ 完成（常场景测试；2723 passed）

## 🎯 目标

generate `if` / `case` 是正常设计写法，不能只测 generate-for。

## 🔬 覆盖

fixture `generate_if_case_width.sv`：

- `top_if0`：`if (MODE==0)` 活跃 `g`，else `other` 不应建节点；
- `top_case1`：`case (MODE)` 活跃 `g1`，`g0` / `gd` 不应建节点；
- 宽度来自 `parameter` / `localparam`；
- 实例内部 `reg [W-1:0] r` 也要正确。

## ✅ 结果

当前实现已经正确：

```text
top_if0.g.u.i       (7,0)
top_if0.g.u.r       (7,0)
top_if0.other.u.i   不存在
top_case1.g1.u.i    (3,0)
top_case1.g0.u.i    不存在
top_case1.gd.u.i    不存在
```

说明实例枚举返回的是 **elaborate 后的活跃 generate 实例**，
`_propagate_instance_widths` 的实例 body width 直接生效。

## 🧪 测试

- `test_generate_if_active_branch_width`；
- `test_generate_case_active_branch_width`；
- `test_generate_if_inactive_literal_branch_not_materialized`；
- 全量 **2723 passed / 0 failed**。

## ⚠️ 边界

- 这次是**测试强化**，没有新增 width 算法；
- generate `if/case` 的非活跃分支只在实例枚举层消失，不保证所有图查询都把
  inactive 名称视为 not_found（目前会 not_found，因为没有节点）；
- 仍不做逻辑证明。

## 🔗 相关

- 计划: [PLAN.md P55](../../../PLAN.md)
