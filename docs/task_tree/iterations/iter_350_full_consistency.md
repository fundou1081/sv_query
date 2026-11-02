# Iteration 350: 全图 reciprocity（PLAN P49）

**Metadata**:
- **Iteration #**: 350
- **Task Tree Level**: L2（PLAN `P49`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先去看全图证明级一致性"）
- **Outcome**: ✅ 完成（full mode；2713 passed）

## 🎯 目标

从抽样一致性推进到全图检查，并找出真实问题。

## 🔧 实现

- `--full`：遍历全部信号节点，`truncated=false`；
- fanin/fanout 查询缓存，避免邻居重复计算；
- 显式排除：
  - non_signal；
  - bit_like（位/切片父总线 fallback）；
  - constant；
- `coverage` 标明 `bit_level_reciprocity=not_applicable`；
- 保留 sample/signal 模式。

## 🐛 全图发现

verilog-axi 全图：
- 初始 1087 条 violations，绝大多数来自**位/总线回退不对称**：
  - `s_axi_rready[0]` fanout 到 `s_axi_rready_int_early`，但 early 的 fanin 只列总线；
  - `m_axi_arready[0:1]` 与父总线负载；
  - 常量 `1'b0` 驱动位节点但 fanout(const) 为空。
- 这不是逻辑 bug，而是位级查询 fallback 的表示差异；严格 edge reciprocity 不适用于 bit_like/常量。
- 排除这些范围后：verilog-axi 8873 非位信号节点全通过；picorv32 706 全通过；strict_uart 28 全通过。

## 🧪 测试

- `test_consistency_full_mode`：mode/full/truncated/coverage；
- 全量 **2713 passed / 0 failed**。

## ⚠️ 边界

- full 模式不检查 bit_like 的 edge reciprocity；位级只查 parent/width；
- constants 不参与；
- verilog-axi 全图约 50s，默认仍抽样 200。

## 🔗 相关

- 计划: [PLAN.md P49](../../../PLAN.md)
