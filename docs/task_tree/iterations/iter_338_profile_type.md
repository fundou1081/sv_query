# Iteration 338: profile type metadata（PLAN P40.1）

**Metadata**:
- **Iteration #**: 338
- **Task Tree Level**: L2（PLAN `P40.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（enum/struct/array 类型；2683 passed）

## 🎯 目标

波形值需要 RTL 类型才能解释：
- enum 编码；
- struct 成员 offset；
- unpacked array 元素/维度；
- signed/width。

## 🔧 实现

- `_build_type_lookup`：`adapter.get_modules()` → hierarchicalPath → body Port/Variable；
- profile `type`：
  - `known/name/canonical`；
  - `is_enum/is_struct/is_union/is_unpacked_array/is_array/array_element`；
  - `bit_width/is_signed`；
  - enum 值从 canonical 文本解析；
  - struct 成员调用 `get_packed_member_layout`。
- 只解析 module/instance；class/constraint 不伪装。
- 新增类型 fixture `types.sv`（enum/struct/array）。

## 🧪 测试

- `test_enum_type_metadata` / `test_struct_type_metadata` /
  `test_array_and_plain_type_metadata`（+3）；
- 契约 +1：profile_type/enum_value；
- 全量 **2683 passed / 0 failed**。

## ⚠️ 边界

- class/constraint 的 type 仍 `known=false`；
- struct 成员的 profile（如 `top.p.a`）暂未从父 struct 推导类型；
- enum value 是源码字面量，不求值；
- type 解析依赖 semantic symbol，`--from-snapshot` 不可用。

## 🔗 相关

- 计划: [PLAN.md P40.1](../../../PLAN.md)
