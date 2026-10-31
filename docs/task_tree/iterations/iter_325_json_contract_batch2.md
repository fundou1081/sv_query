# Iteration 325: JSON 契约扩展 batch 2（PLAN P29.1）

**Metadata**:
- **Iteration #**: 325
- **Task Tree Level**: L2（PLAN `P29.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续扩契约面"）
- **Outcome**: ✅ 完成（6 命令契约 + 6 测试；2624 passed）

## 🔧 新增契约

| 命令 | 关键字段 |
|---|---|
| `graph edges` | result `edges/total`；edge `src/dst/kind` |
| `search` | **direct output**：keyword/target/files[]/total_matches...；file lines[] |
| `stats` | result `total_nodes/total_edges/nodes/edges/modules/elaboration_errors` |
| `trace evidence` | envelope + 可选 top-level `evidence`；signals[].evidence payload |
| `controlflow analyze` | conditioned_drivers[].conditions[].{expr,edge} |
| `controlflow list-conditioned` | 可选 top-level `subcommand`；signals/count |

## 🐛 契约面发现

1. **envelope 不统一**：`search` 是 direct output（无 command/params/errors）；
   `trace evidence` 有额外 top-level `evidence`；`controlflow list-conditioned` 有 `subcommand`。
   契约用 `envelope: direct` / `optional_top_level` 显式标注，而不是假装统一。
2. `trace evidence` 的 evidence payload 同时出现在 `result.signals[].evidence`
   与 top-level `evidence`（单信号便捷镜像），字段一致。
3. `stats.nodes`/`stats.edges` 是 kind→count 对象，不是数组。

## 🧪 测试

`test_json_contract.py` 9 → **15**：
graph edges、search、stats、evidence（含 top-level 镜像）、
controlflow analyze（driver/condition/edge）、controlflow list-conditioned。
全部用真实 CLI JSON 集合校验。

全量：2618 → **2624 passed / 0 failed**。

## 📌 剩余契约面

`instances` / `connections` / `hierarchy` / `params` / `ports` / `class` / `audit` /
`diagnose` / `snapshot *` / `graph nodes` 已做；其余按需增量。

## 🔗 相关

- 计划: [PLAN.md P29.1](../../../PLAN.md)
- 文档: [JSON 契约](../../architecture/json_contract_2026-10-31.md)
