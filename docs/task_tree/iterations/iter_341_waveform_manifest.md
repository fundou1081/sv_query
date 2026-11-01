# Iteration 341: waveform manifest（PLAN P41.2）

**Metadata**:
- **Iteration #**: 341
- **Task Tree Level**: L2（PLAN `P41.2`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（batch manifest；2689 passed）

## 🎯 目标

波形工具一次调用拿全：
`waveform path → canonical + type/bit/clock/reset/stage/source`。

## 🔧 实现

- 新命令 `trace manifest --path/--paths-file`；
- 一次 build；复用 lookup alias index + profile 内部 helper；
- 每条：
  - `waveform_path/index/found/lookup/profile`；
  - not_found → profile=null；
- 批量计数 `total/found/failed`。

## 🧪 测试

- `test_manifest_mixed_paths` / `test_manifest_bit_parent_and_missing`（+2）；
- 契约 +1：manifest_entry/manifest_result；
- 全量 **2689 passed / 0 failed**。

## ⚠️ 边界

- profile 仍是 full payload，体积较大；
- interface/modport/generate `genblk` 别名仍不在 lookup 索引内；
- manifest 不做值提取/时间对齐，只提供元数据。

## 🔗 相关

- 计划: [PLAN.md P41.2](../../../PLAN.md)
