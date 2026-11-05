# Task: agent 查询可靠性修复（P71）

**状态**: 已完成
**来源**: 12-task agent 对照暴露的问题。
**目标**: 让 agent 能区分“输入/查询语义错误”和“工具结果”，减少静默误导。

## 交付

1. `trace fanin/fanout` + `drivers/loads` 增加 `--top`；
   多 top 输出 `top_modules/top_ambiguous`，不拒绝合法多 top 查询。
2. `driver_count` 排除 self/port artifact，与 `drivers[]` 一致；
   保留 `multi_driver/conditional_drivers`。
3. 结果显式携带 `top_modules` / `top_ambiguous` / `bit_fallback`。
4. 测试 + 契约 + 文档。

## 边界

- 多 top 的合法查询保持可用（`--top` 用于显式 scope）；
- 不把 bit fallback 一律当错误；单 top 的正常 fallback 保留；
- 不改变 fanin/fanout 遍历语义。
