# Iteration 373: token/tool-call 汇总（PLAN P69.5）

**Metadata**:
- **Iteration #**: 373
- **Task Tree Level**: L2（PLAN `P69.5`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ token/tool-call 已记录；多 seed 仍待做

## 🎯 动作

从 DSH 子 session 的 `tokenUsage` 与 `contextTimeline` 提取最终 48 cells：

- total input = `uncachedInputTokens + cacheReadTokens`；
- output tokens 单列；
- tool calls = `contextTimeline` 中 `cat=tool` 的数量；
- 与冻结结果 JSON 按 task/model/arm 对齐。

## 📊 汇总

| 模型 / 臂 | mean tokens | tool calls | tokens/correct | mean wall |
|---|---:|---:|---:|---:|
| MiniMax source | 237.6k | 15.2 | 407.4k | 51.4 s |
| MiniMax svq | 329.7k | 18.4 | 329.7k | 130.6 s |
| DeepSeek source | 123.2k | 8.3 | 246.4k | 57.2 s |
| DeepSeek svq | 244.2k | 12.0 | 244.2k | 74.9 s |

解释：

- svq 总 token 更高，尤其 MiniMax；
- tokens/correct 在 MiniMax 下降（407k→330k），DeepSeek 基本持平；
- 不支持“成本更低”的结论；
- 没有价格换算，也没有 cold/warm 拆分。

## 🔜 下一步

P69.6：多 seed + 彻底隔离 source（当前仍会读 sv_query 源码）。
