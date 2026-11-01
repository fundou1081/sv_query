# Iteration 340: struct member type（PLAN P41.1）

**Metadata**:
- **Iteration #**: 340
- **Task Tree Level**: L2（PLAN `P41.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（成员 type；2686 passed）

## 🎯 目标

`top.p.a` 这类 struct 成员需要独立 type/offset，不能只靠父 struct。

## 🔧 实现

- `_build_type_lookup` 增加 `member_info(node)`：
  - module body 找父 symbol；
  - `get_packed_member_layout` 找成员；
  - 返回 parent_type/width/offset/signed。
- `_type_meta` 在 symbol 未命中时走 member_info：
  - `name=父类型.成员`，`member_of`，`member_offset`，`bit_width`。
- 契约新增 `member_of/member_offset`。

## 🧪 测试

- `test_struct_member_type_metadata`（top.p.a：pair_t / offset 4 / width 4）；
- 契约字段；
- 全量 **2686 passed / 0 failed**。

## ⚠️ 边界

- 只支持 module/instance 内 packed struct；
- 嵌套成员（p.a.b）/class 成员仍 unknown；
- offset 是 LSB 在父 aggregate 中的位置。

## 🔗 相关

- 计划: [PLAN.md P41.1](../../../PLAN.md)
