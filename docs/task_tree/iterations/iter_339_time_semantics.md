# Iteration 339: sequential stage / sample（PLAN P40.2）

**Metadata**:
- **Iteration #**: 339
- **Task Tree Level**: L2（PLAN `P40.2`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做吧"）
- **Outcome**: ✅ 完成（stage/sample；2685 passed）

## 🎯 目标

时间语义只给**有证据**的事件/周期信息：
- REG 的 pipeline stage（detect_pipeline 命中）；
- sample edge；
- 组合/状态机/多 clock 显式 unknown。

## 🔧 实现

- `_build_stage_index(graph)`：`classify_graph` + `detect_pipeline`，
  每图一次，REG→stage_id；
- profile `sequential` 新增：
  - `stage/stage_known/stage_source/stage_unknown_reason`；
  - `sample/sample_unknown_reason`；
- sample 仅当 is_sequential 且唯一 clock + edge 已知；
- 组合节点 stage_unknown_reason=combinational；
- REG 未命中 pipeline → not_pipeline_reg / no_pipeline_detected。

## 🧪 测试

- `test_sequential_stage_and_sample`（data_out）；
- `test_combinational_stage_unknown`（full）；
- 契约 sequential 字段；
- 全量 **2685 passed / 0 failed**。

## ⚠️ 边界

- stage 是 pipeline 检测结果，不是绝对 RTL 级数；
- 状态机/控制 REG 不强行给 stage；
- 多 clock 不给 sample；CDC latency 仍由 dataflow 负责；
- 没有 wall-clock delay/setup/hold。

## 🔗 相关

- 计划: [PLAN.md P40.2](../../../PLAN.md)
