# Task: port-map ternary 的 OP_TERNARY/BRANCH 子图（P77）

**状态**: 已完成
**来源**: interactive debug deep_chain 的 `.d(sel ? d : ~d)`。
**方案**: 方案 C（expression node + branch edges），不是 EdgeKind.CONTROL。

## 交付

1. AGENTS.md 增加 ub-mode 复杂决策参考；
2. port connection 的 semantic `ConditionalOp` 保留并 lower；
3. 生成 `OP_TERNARY` + `BRANCH_CONDITION/TRUE/FALSE/RESULT`；
4. 简单三元同时生成条件 DRIVER，`trace/controlflow` 可读；
5. 不支持表达式继续显式 unknown；
6. 测试/文档/全量门禁。

## 边界

- 只做 input port 的简单 ternary；
- 不新增 `EdgeKind.CONTROL`；
- 不重写 assign ternary 的位级逻辑；
- 复杂表达式不猜测。
