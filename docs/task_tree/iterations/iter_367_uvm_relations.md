# Iteration 367: UVM sequence/factory 静态关系（PLAN P65）

**Metadata**:
- **Iteration #**: 367
- **Task Tree Level**: L2（PLAN `P65`）
- **Created**: 2026-11-04 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "UVM sequence/factory 关系值得做"）
- **Outcome**: ✅ 完成；2524 passed

## 🎯 动作

- `class --relations` 新增 `uvm`：
  - role（sequence/sequence_item/component/object）
  - factory_registration（`uvm_*_utils`）
  - factory_creates（`type_id::create` / `create_by_name`）
  - sequence_calls（`uvm_do*` / start_item / finish_item）
  - p_sequencer
- 提取使用类源码文本（semantic syntax 已去掉 preprocessor 宏）
- 新增 `sim/tests/fixtures/json_contract/uvm_relations.sv`

## 🧪 测试

- sequence role + registration + `uvm_do` + p_sequencer
- component role + registration
- factory `type_id::create`
- sequence_item + rand
- 契约 `class_uvm`
- 全量 **2524 passed / 0 failed**

## ⚠️ 边界

- syntactic only；
- 不做 factory override/config_db/phase 执行；
- 不分析 UVM package 依赖；
- 宏内调用不展开到方法体语义。

## 🔗 相关

- 契约: [class_constraint_covergroup_contract_2026-11-03.md](../../architecture/class_constraint_covergroup_contract_2026-11-03.md)
- 计划: [PLAN.md P65](../../../PLAN.md)
