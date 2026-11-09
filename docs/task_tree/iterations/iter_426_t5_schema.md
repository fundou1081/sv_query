# Iteration 426: OpenTitan T5 schema（P120）

**状态**: ✅
**日期**: 2026-11-09

## 修复

T5 显式使用两次 `intent=verify`：
- missing endpoint path claim；
- reverse-path claim；
- 只返回两个 verify status。

## 结果

MiniMax / DeepSeek 都是 unknown / contradicted，2/2。

## OpenTitan 最终

T1/T2/T3/T4/T5 = 10/10（分段 run）。
