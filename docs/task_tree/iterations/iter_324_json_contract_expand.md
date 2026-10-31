# Iteration 324: JSON 契约扩展（PLAN P28.1）

**Metadata**:
- **Iteration #**: 324
- **Task Tree Level**: L2（PLAN `P28.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "扩充契约吧"）
- **Outcome**: ✅ 完成（5 组新契约 + 真实输出测试；2618 passed）

## 🎯 背景

P27 只覆盖 envelope + `trace fanin/fanout`。agent 还需要：

- `paths` / `dataflow analyze` / `trace impact` 的字段含义
- `graph nodes` 普通/`--detail` 字段
- `errors[]` 的形态（字符串 vs 对象）

## 🔧 实现

`capabilities.json_contract` 扩展：

| 新 section | 内容 |
|---|---|
| `bit_endpoint` / `bit_normalization` | `--bits` 解析结果字段 |
| `paths_result` / `paths_modes` | paths 单路径/all 模式 |
| `dataflow_result` / `dataflow_path` / `dataflow_segment` | dataflow 输出 |
| `impact_signal` / `impact_path` | impact 输出 |
| `graph_node` / `graph_node_detail` / `graph_nodes_result` | graph nodes 普通/detail |
| `error_entry` | trace 分信号错误对象 |

`commands` 增加 `paths`、`dataflow analyze`、`trace impact`、`graph nodes` 的字段映射；
`top_level.errors` 类型改为 `array<string|error_entry>`（overview 用字符串，trace 用对象）。

## 🧪 测试

`test_json_contract.py` 从 4 → **9**：

- paths one/all：基础 + 模式字段、`bits` 结构、bit_endpoint
- dataflow：result/path/segment（`evidence` 可选）
- impact：result/signal/path
- graph nodes：plain/detail 节点字段
- error_entry：schema 字段（trace 错误对象）

全部用真实 CLI JSON 做集合相等/子集校验；新增字段漂移会失败。

## ✅ 验证

- 全量：2613 → **2618 passed / 0 failed**
- 四检查 + `gen_cli_surface --check` 全绿
- 运行期 smoke 不受影响（capabilities 输出层变更）

## 📌 边界

- `paths` 是直接输出（无 `command/params`），契约里用 `envelope: "direct"` 标注
- `dataflow_segment.evidence` 可选；测试允许子集
- 其他 core 命令（graph edges、search、stats 等）尚未字段化，按需增量

## 🔗 相关

- 计划: [PLAN.md P28.1](../../../PLAN.md)
- 文档: [JSON 契约](../../architecture/json_contract_2026-10-31.md)
