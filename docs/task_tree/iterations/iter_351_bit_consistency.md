# Iteration 351: bit-level consistency（PLAN P50）

**Metadata**:
- **Iteration #**: 351
- **Task Tree Level**: L2（PLAN `P50`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做 bit level consistency"）
- **Outcome**: ✅ 完成（结构检查；2715 passed）

## 🎯 目标

把全图一致性从“非位信号”推进到 bit/slice 结构。

## 🔧 实现

- `_check_bit_mapping` 扩展：
  - parent edge 存在性（仅 range-select 主节点）；
  - parent 位范围越界；
  - bit_range vs parent_bit_start/end；
  - width/id parent 一致性；
  - `bit_select_checked` / `index_like` 区分。
- 单 bit 展开、struct 成员、array element 不误报。

## 🐛 全图发现

- verilog-axi：269 条 `parent_range_out_of_bounds`
  （如 `m_axi_araddr[0:32]`，parent 宽度 [31:0]）；
- picorv32：2 条（`mem_done[1]`，parent [0:0]）；
- strict_uart：0。

这些是**真实 bit 元数据问题**，不是测试误差；先记录，未修 graph builder。

## 🧪 测试

- `test_bit_level_structural_consistency`（bitslice 10 selects pass）；
- `test_bit_mapping_detects_out_of_bounds`（手工图）；
- 契约 bit_select_checked/index_like；
- 全量 **2715 passed / 0 failed**。

## ⚠️ 边界

- 全图 bit 检查在 verilog-axi 约 25s；
- out-of-bounds 是 discovery，不自动改图；
- array/dynamic element 走 index_like，不做 bit 范围证明。

## 🔗 相关

- 计划: [PLAN.md P50](../../../PLAN.md)
