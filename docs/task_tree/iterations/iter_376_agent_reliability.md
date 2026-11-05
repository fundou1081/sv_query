# Iteration 376: agent 查询可靠性修复（PLAN P71）

**Metadata**:
- **Iteration #**: 376
- **Task Tree Level**: L2（PLAN `P71`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ --top / top_modules / driver_count / bit_fallback；2532 passed

## 🎯 问题（来自 12-task agent 对照）

1. 混合 filelist 时 bit 查询静默回落，agent 无法判断根/输入是否选错；
2. `driver_count` 包含 port self edge，和 `drivers[]` 数量不一致；
3. `bit_base_fallback` 没有独立字段，agent 只能从 precision 猜。

## 🔧 修复

- `trace fanin/fanout` + `drivers/loads` 新增 `--top`；
- 多 top 查询输出 `top_modules` / `top_ambiguous`，并新增 `--top` 供显式 scope；
  不拒绝合法的多 top 查询（strict_uart 等）
- `driver_count` 排除 self/port artifact；保留 multi/conditional；
- 输出新增：
  - `top_modules`
  - `top_ambiguous`
  - `bit_fallback`
- contract `trace_signal` 同步。

## 🧪 测试

- `sim/tests/cli/test_agent_reliability.py`（multi-top + --top + fallback fields）
- `test_trace_driver_stats.py`（self-edge 不计入 driver_count）
- 相关 contract / precision / resolution 测试

## ⚠️ 边界

- 多 top 的合法查询仍可用；不因 bit fallback 自动拒绝；
- 单 top 的正常 bit fallback 保留原语义；
- 不改变 fanin/fanout 遍历。

## ✅ 门禁

- 全量 **2532 passed / 0 failed**；
- `check_docs` / `check_plan` / `check_semantic_regex` / `check_crap` / `check_cli_layers` / `check_except_pass` / `gen_cli_surface --check` 全绿。
