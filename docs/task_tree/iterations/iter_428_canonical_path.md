# Iteration 428: Canonical path + runner hardening（P122）

**状态**: ✅
**日期**: 2026-11-09

## 修复

- path/deep_path 都调用 `paths --canonical`；
- 输出 path_kind/candidate_count/canonical_policy；
- runner per-cell timeout 600，异常隔离，不再丢整批。

## 结果

OpenTitan 5 tasks ×2 模型连续 run：10/10，0 false-confident，0 false-found。

T2 MiniMax 19.7s，DeepSeek 11.0s（原 46.5/145.2s）。

## 边界

只测 UART；Deep T1 355s。
