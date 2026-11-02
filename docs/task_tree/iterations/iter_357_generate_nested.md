# Iteration 357: generate if/case 嵌套 generate-for（PLAN P56）

**Metadata**:
- **Iteration #**: 357
- **Task Tree Level**: L2（PLAN `P56`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "这个嵌套价值很高"）
- **Outcome**: ✅ 完成（2725 passed）

## 🎯 目标

测试并锁定：

```systemverilog
for (...) begin: blk
  if (...) begin: even leaf ... end
  else     begin: odd  leaf ... end
end
```

以及 for 内 `case`。

## 🔬 fixture

[generate_nested_if_case.sv](../../../sim/tests/fixtures/generate_nested_if_case.sv)

- `top_nested_if`：for 0..3，偶/奇分支不同 parameter；
- `top_nested_case`：for 0..2，case 0/1/default 不同 parameter；
- leaf 内部有 `reg [W-1:0] r`。

## ✅ 结果

```text
top_nested_if.blk[0].even.u.i  (1,0)
top_nested_if.blk[1].odd.u.i   (4,0)
top_nested_if.blk[2].even.u.i  (3,0)
top_nested_if.blk[3].odd.u.i   (6,0)

top_nested_case.blk[0].c0.u.i  (1,0)
top_nested_case.blk[1].c1.u.i  (3,0)
top_nested_case.blk[2].cd.u.i  (7,0)
```

内部 `r` 同宽；每个 iteration 只保留 active 分支：

```text
blk[0].odd.u.i   不存在
blk[1].even.u.i  不存在
blk[0].c1.u.i    不存在
blk[1].cd.u.i    不存在
```

## 🧪 测试

- `test_nested_if_inside_for_widths`；
- `test_nested_case_inside_for_widths`；
- 全量 **2725 passed / 0 failed**。

## ⚠️ 边界

- 本次是测试强化，不新增 width 算法；
- 实例路径以 pyslang elaborate 的 generate 路径为准；
- 仍未覆盖：generate if/case 内的 generate-for 再次嵌套（更深组合）、
  generate 内 parameter 依赖其他实例参数。

## 🔗 相关

- 计划: [PLAN.md P56](../../../PLAN.md)
