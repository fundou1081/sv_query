# Iteration 427: OpenTitan continuous run（P121）

**状态**: ✅
**日期**: 2026-11-09

## 结果

5 tasks ×2 模型连续跑：
- 9/10 exact；
- 1 false-confident；
- 0 false-found；
- 513s / 194 tool calls。

唯一失败：MiniMax T2 选 13-hop 而不是 18-hop canonical path，且高置信。

## 结论

路径 canonical 语义需要明确；不是 provider 问题。
