# Iteration 418: unknown/abstention 合同（P112）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- 所有结果带 ok/status/found；
- 空邻居 ok=true；
- missing signal/path/evidence 返回 not_found；
- neighborhood 查询失败不再静默；
- failureResult 去掉 undefined，保证 lossless JSON。

## 验证

- 4 种实际 tool 调用符合合同；
- 3-cell direct 6/6；
- Node tests 36/36。

## 边界

ambiguous 语料未构造；truncated 只在 neighborhood。
