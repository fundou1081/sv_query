# Iteration 381: port-map ternary expression 子图（PLAN P77）

**Metadata**:
- **Iteration #**: 381
- **Task Tree Level**: L2（PLAN `P77`）
- **Created**: 2026-11-06 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 方案 C：OP_TERNARY + BRANCH_*，简单 port ternary

## 🎯 目标

`.d(sel ? d : ~d)` 不能只标 unknown；把 semantic ConditionalOp lower 成表达式子图。

## 🔧 实现

- GraphBuilder 在 wrapper passthrough 前新增 `port_ternary` pass；
- 遍历 `InstanceSymbol.portConnections`；
- 仅处理 input port、简单 ternary；
- 生成：
  - `OP_TERNARY`
  - `BRANCH_CONDITION`
  - `BRANCH_TRUE` / `BRANCH_FALSE`
  - `BRANCH_RESULT`
  - 真/假分支的 conditional `DRIVER`
- 跳过 wrapper 直通边，避免 `u_mid.d` 假驱动；
- 复杂表达式继续 unknown。

## 🧪 测试

新增 `sim/tests/cli/test_port_ternary.py`：

- `graph nodes --kind OP_TERNARY`；
- `controlflow condition_status=complete`；
- `trace fanin` 条件驱动。

更新：
- canonical 路径（P77 后 12 节点 / 11 hops）；
- controlflow 无数据边 → unknown fallback。

全量 **2542 passed / 0 failed**。

## ⚠️ 边界

- 不做 nested/复杂表达式；
- 不新增 `EdgeKind.CONTROL`；
- 分支表达式仍可能只保留 signal ref（如 `~d` 的 `~` 不单独建节点）。
