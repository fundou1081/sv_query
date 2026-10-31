# Iteration 323: Agent JSON 契约（PLAN P27.1）

**Metadata**:
- **Iteration #**: 323
- **Task Tree Level**: L2（PLAN `P27.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "下一步继续 schema agent 契约"）
- **Outcome**: ✅ 完成（capabilities.json_contract + 契约测试；2613 passed）

## 🎯 问题

capabilities 已列命令/分层，但字段语义散落在 docs：
agent 不知道 `precision/coarse_fallback/dynamic_index/function_call/conditions/cycles_detected`
的类型、可空性、版本策略；新增字段也没有契约漂移检测。

## 🔧 实现

`capabilities --json` 新增 `json_contract`：

| 段 | 内容 |
|---|---|
| `policy` | v1 加法兼容；删/改名/改类型/新增必填才升版本；null 表示未知 |
| `top_level` | `ok/command/params/result/errors` |
| `trace_signal` | precision 枚举、降级标记、conditions、cycles(nullable)、计数/截断 |
| `trace_node` | id/module/kind/width/distance/precision/signed/parent/bit_range + 三种 unknown 来源 + 条件路径结构 |
| `commands` | `trace fanin`/`trace fanout` 的 result/node array/signal extra |
| `precision_values` | `bit/bus/unknown` |

同时新增 [json_contract_2026-10-31.md](../../architecture/json_contract_2026-10-31.md)（字段表 + 示例 + 待扩范围）。

## 🧪 测试

`test_json_contract.py`（4）：
- envelope/版本/精度策略
- 每个字段都有 type/desc，条件路径 item 结构
- **fanin 实际 signal/node 字段集合 == 契约**
- **fanout 实际 signal/node 字段集合 == 契约**

（测试抓到契约里多写了 `name` 字段——实际 `_node_to_dict` 未输出，已从契约删除，避免契约虚假承诺。）

## ✅ 验证

- 全量：2609 → **2613 passed / 0 failed**
- 四检查 + `gen_cli_surface --check` 全绿
- 运行期 smoke 不受影响（契约是 capabilities 输出层）

## 📌 边界

- 当前只覆盖 envelope + trace fanin/fanout；paths/dataflow/impact/graph nodes 待扩
- `errors[]` 内部字段尚未固定
- 条件仍是显示字符串，不是规范化布尔 AST（P25 设计记录，未排期）

## 🔗 相关

- 计划: [PLAN.md P27.1](../../../PLAN.md)
- 文档: [JSON 契约](../../architecture/json_contract_2026-10-31.md)
