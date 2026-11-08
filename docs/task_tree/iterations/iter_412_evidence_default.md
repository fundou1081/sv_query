# Iteration 412: evidence 默认关闭回归（P106）

**状态**: ✅
**日期**: 2026-11-08

## 结果

12 题 ×2 模型，evidence=false：

- exact 24/24；
- MiniMax 5.1s；
- DeepSeek 4.0s；
- 默认无 evidence 字段。

## 结论

evidence 加入后默认 direct 任务未受影响；需要复核时显式使用 intent=evidence。
