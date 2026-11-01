# Iteration 348: class member / UVM 可发现性（PLAN P47.1）

**Metadata**:
- **Iteration #**: 348
- **Task Tree Level**: L2（PLAN `P47.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "class member 在 testbench/UVM 很重要"）
- **Outcome**: ✅ 完成（语义 candidates；2705 passed）

## 🎯 问题

`class --member` 只查图内已有节点；UVM/testbench 里大量成员未参与 RTL 数据流，
因此常见 `count=0`，无法发现 `top.env.agent.monitor.item.addr` 这类路径。

## 🔧 实现

- `_class_member_candidates`：
  - 从真实根 CLASS_INSTANCE 出发；
  - 沿类型级 `CLASS_INSTANCE` 成员递归；
  - 生成完整实例路径 + `in_graph` 标记；
  - 不往图里造节点。
- `class --member` 输出：
  - `instances`/`count`（原图内节点）；
  - `candidates`/`candidate_count`（语义路径）。

## 🧪 测试

- `test_unused_member_candidate_is_listed`：`top.pkt.data` in_graph=false；
- `test_uvm_nested_instance_member_candidate`：`top.e.p.addr` in_graph=true；
- `test_nested_class_member_candidate`：`top.p.i.val`；
- 契约 `class_member_candidate`；
- 全量 **2705 passed / 0 failed**。

## ⚠️ 边界

- candidates 是类型语义推导，不代表该成员在 RTL 中被使用；
- `in_graph=false` 时不能 fanin/fanout，只能作为路径发现；
- class member 数据流仍只对图内节点成立；
- 多态/继承成员暂按声明类型遍历。

## 🔗 相关

- 计划: [PLAN.md P47.1](../../../PLAN.md)
