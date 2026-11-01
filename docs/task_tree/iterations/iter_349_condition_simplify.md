# Iteration 349: 条件化简 / 互斥（PLAN P48）

**Metadata**:
- **Iteration #**: 349
- **Task Tree Level**: L2（PLAN `P48`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做条件化简 互斥"）
- **Outcome**: ✅ 完成（L1 + 语法 L2；2712 passed）

## 🎯 目标

- 保留原始条件；
- 只加派生化简字段；
- 只做可证明的互斥，不猜。

## 🔧 实现

### L1

- 新模块 `condition_analysis.py`：
  - tokenizer/parser：只识别 `! / && / || / 括号`；
  - 原子整体保留（含 `==`、`>=` 等）；
  - 恒等式：双重否定、幂等、吸收、常量；
  - **不实现补元律**（四态不安全）。
- fanin/fanout 节点/路径新增 simplified/analysis 字段；
- 解析失败 → `parse_failed/unknown/analysis_incomplete`，原始不动。

### L2

- `conditions_mutex`：只证明 `a` vs `!a`；
- `driver_conflict_analysis`：
  - ≤1 driver → none；
  - 无条件 → possible；
  - 两两语法互补 → proven_exclusive_2state（four_state_safe=false）；
  - 其他 → possible。
- fanin signal 输出 `driver_conflict` + analysis。

## 🧪 测试

- `test_condition_analysis.py` 5：恒等式、4-state 补元不化简、解析失败、原子比较、互斥；
- `test_condition_driver_conflict.py`：if/else → proven_exclusive_2state；
- 契约 +1：condition fields/analysis；
- golden 3 个重新生成；
- 全量 **2712 passed / 0 failed**。

## ⚠️ 边界

- 只有语法互补，不是完整 SAT/BDD；
- 没有 branch group/arm；casez/unique case 未建模；
- 四态下互斥标 2state；
- 不处理算术谓词关系（`a>0` vs `a<=0`）。

## 🔗 相关

- 计划: [PLAN.md P48](../../../PLAN.md)
- 设计: [condition_analysis_plan_2026-10-31](../../architecture/condition_analysis_plan_2026-10-31.md)
