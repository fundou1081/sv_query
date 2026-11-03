# Task: class / constraint / covergroup 语义增强（P63）

**状态**: 进行中
**目标**: 把已有的 class/constraint/covergroup 查询 API 暴露为 agent 可用 CLI，并补 class relations 的 constraint/covergroup 摘要。

## 子项

- P63.1 class relations：约束块详情 + covergroup 摘要
- P63.2 `trace constraints <property>`
- P63.3 `trace covergroups` / `trace coverpoints` / `trace covergroup`
- P63.4 测试/契约/文档

## 边界

- 不新增 constraint/covergroup 提取语法；
- 不改数据 fanin；约束/覆盖是独立语义域；
- inline constraint 仍不支持（已有决策）；
- UVM factory/多态仍不做。
