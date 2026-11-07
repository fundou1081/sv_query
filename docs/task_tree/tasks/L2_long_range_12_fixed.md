# Task: 12-task fixed-protocol run（P87）

**状态**: 已完成
**目标**: 用 P83 固定协议跑 P69 的 12 题：
- source/T2；
- 2 模型（MiniMax-M3 / DeepSeek-Flash）；
- 2 seed；
- hard isolation；
- fact check、query log、dual scoring。

## 第一轮

先 seed1：12 × 2 × 2 = 48 agents。  
确认无 fact-check mismatch / 429 / 大规模缺失后再跑 seed2。

## 边界

- 不扩任务；
- 不在第一轮就宣称 12×3；
- 双评分结果分开报告。
