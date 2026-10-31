# Iteration 332: trace profile（PLAN P36.1）

**Metadata**:
- **Iteration #**: 332
- **Task Tree Level**: L2（PLAN `P36.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按顺序做"）
- **Outcome**: ✅ 完成（profile + 契约；2661 passed）

## 🎯 目标

给外部波形工具提供**关联元数据**（我们不做值提取）：
canonical id / aliases / 位映射 / clock/reset / sequential / 声明与驱动源码位置。

## 🔧 实现

新增 `trace profile <signal...>`（core semantic，批量）：

- alias 候选：canonical / leaf / 去掉 top 前缀；
- bit：`bit_range/parent/parent_bit_start/end`；
- source：声明 `file/line`，driver 位置用 evidence resolver 修正；
- role：clock/reset/enable/port/modport；
- clock：CLOCK 入边；`clock_domains` 去重 domain/信号；
- reset：RESET 入边；
- sequential：clock/reset 或 nonblocking 证据；`stage=null`（未计算，显式）；
- driver/load 计数（直接）。

## 🧪 测试

新增 `test_trace_profile.py`（5）：
sequential profile、continuous、input port、relative/not_found、batch partial。
契约 +1：profile 字段/嵌套结构精确匹配。

全量 **2661 passed / 0 failed**。

## ⚠️ 边界 / 发现

- `stage` 未计算：`stage_known=false`，不用猜测填充。
- aliases 只是候选名，不保证波形唯一；外部工具应以 `resolved_signal` 为准。
- profile 的 driver 位置先取 edge，再用 evidence resolver 修正；evidence 缺失时为 null。
- profile 不支持 `--no-cache`/`--from-snapshot`（当前与 trace 命令选项不完全对齐，后续按需补）。

## 🔗 相关

- 计划: [PLAN.md P36.1](../../../PLAN.md)
- 契约: [json_contract P36](../../architecture/json_contract_2026-10-31.md)
