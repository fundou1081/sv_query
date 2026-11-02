# Iteration 355: generate parameter width 验证（PLAN P54）

**Metadata**:
- **Iteration #**: 355
- **Task Tree Level**: L2（PLAN `P54`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆追问 P53 边界）
- **Outcome**: ✅ 完成（边界 2 实际已成立；2720 passed）

## 🎯 背景

P53 边界写了：

> generate 分支内部的 parameter 特化尚未单独建模。

复核发现这条边界 **过保守**：`get_module_instances()` 返回的是
generate 展开后的实例（`top.blk[N].u`），实例 body 已带参数值，
`_propagate_instance_widths` 直接取到正确 width。

## 🔬 验证 fixture

```systemverilog
for (g = 0; g < 4; g = g + 1) begin: blk
  leaf #(.W(2 * (g + 1))) u(...);
end
```

结果：

```text
top.blk[0].u.i  (1,0)
top.blk[1].u.i  (3,0)
top.blk[2].u.i  (5,0)
top.blk[3].u.i  (7,0)
```

## 🧪 测试

- `test_generate_parameter_instance_width`；
- 全量 **2720 passed / 0 failed**。

## ✅ 边界更新

- generate-for 参数特化：**已验证，不再列为未建模**；
- 仍未覆盖：generate `if/case` 分支内同类型不同 parameter 的极小场景
  （结构上仍走实例 body，理论可覆盖，但未单独 fixture）；
- 实例 body/端口枚举失败的回退仍保留（logger.debug）。

## 🔗 相关

- 计划: [PLAN.md P54](../../../PLAN.md)
