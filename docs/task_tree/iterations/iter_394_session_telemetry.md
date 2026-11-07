# Iteration 394: DSH session telemetry（P90.3）

**状态**: ✅
**日期**: 2026-11-07

## 调查

- 读取 DSH session JSONL（zstd）；
- 96 cells：T2 48/48 有实际 sv_query，389 次调用；source 47/48 无；
- T2 direct 44/44 实际 `--depth 1`；
- 3 cell 实际成本：tool 19–28%，model residual 72–81%。

## 修正

- `queries` 是 lossy self-report，不能当执行日志/成本依据；
- AXI `connections` 在真实命令中被 `head` 截断，重放 26.8s 不代表 agent 成本；
- P87 的 “query audit” 改为 session telemetry 口径。

## 决策

仍暂停 serve/batch；先修 paths/connections cache，runner 记录真实 telemetry。
