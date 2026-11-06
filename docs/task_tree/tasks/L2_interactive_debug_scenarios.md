# Task: 交互式 debug 场景（P74）

**状态**: 已完成
**方豆场景**:
1. 挖掘一条深的 drive 链；
2. 追踪 class rand variable 约束关系；
3. 构建 random variable ↔ coverage mapping。

**目标**: 验证这些信息不能靠一次查询/一次源码阅读稳定得到，agent 需要连续追问。

## 交付

- `examples/interactive_debug/` 三场景 fixture；
- `tools/benchmark/interactive_debug/scenarios.json` ground truth；
- 至少 4 轮、连续查询的 prompt；
- MiniMax / DeepSeek T2 各跑一次；
- 记录轮数、工具调用、最终准确率、失败点。

## 边界

- 这是场景/协议 pilot，不是全量 benchmark；
- 不要求 source-only 对照；
- 不把“模型会查”当产品结论，先看场景是否成立。
