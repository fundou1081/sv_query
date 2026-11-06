# Task: 交互式 debug 后续修复（P76）

**状态**: 已完成
**来源**: interactive debug pilot 的 3 个高优先问题。

## 交付

1. `paths --canonical`：在 10/11 节点变体中选择确定路径；
2. 三元 mux/未建模 control：显式 `unknown`，不再静默空；
3. class relative name / class instance scope：可行动的提示；
4. 测试/契约/文档。

## 边界

- 不假装已完整建模三元 mux；
- 不改变默认 `paths` 行为（除新增 `--canonical`）；
- 不把普通无条件 wrapper 误报成错误。
