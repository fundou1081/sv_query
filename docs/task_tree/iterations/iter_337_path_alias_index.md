# Iteration 337: path alias index（PLAN P39.3）

**Metadata**:
- **Iteration #**: 337
- **Task Tree Level**: L2（PLAN `P39.3`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "补吧"）
- **Outcome**: ✅ 完成（alias/ambiguous；2679 passed）

## 🎯 目标

完整 path 不一定等于 canonical id；需要别名索引，且冲突不能猜。

## 🔧 实现

- `_build_aliases`：canonical + escaped 去反斜杠变体 + port/internal；
- `_alias_index`：alias → set(canonical)；
- lookup 顺序：exact → alias（唯一）→ ambiguous（多候选）→ bit_parent → not_found；
- 输出 `matched_via`；`resolution=alias|ambiguous`。

## 🧪 测试

- `test_matched_via_exact` +1；契约字段 `matched_via`；
- 全量 **2679 passed / 0 failed**。

## ⚠️ 边界

- interface/modport 与 generate `genblk` 别名仍未覆盖；
- escaped 变体是去反斜杠，不是完整 SV 反转义；
- 冲突时返回 ambiguous + 候选，不自动选。

## 🔗 相关

- 计划: [PLAN.md P39.3](../../../PLAN.md)
