# Iteration 457: P143 agent feature inventory

**状态**: ✅
**日期**: 2026-11-09

## 结果

DeepSeek worker 盘点 40 个 core JSON 命令，写入
`docs/agent/AGENT_FEATURE_MAP.md`；main 用 `capabilities --json` 核对
summary table 与 core 集合完全一致（40/40，无缺无多）。

同时修正 `trace constraint-chain` 的 `mode=locate` 为 `mode=trace`。
