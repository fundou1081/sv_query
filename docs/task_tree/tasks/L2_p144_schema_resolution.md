# Task: P144 schema ambiguity resolution

**状态**: ✅ 完成
**日期**: 2026-11-09

## 来源

`docs/agent/AGENT_FEATURE_MAP.md` worker 盘点中的 U1–U9。

## 交付

- U1: constraint-chain mode trace（P143 已修，本文确认）；
- U2: capabilities.commands[].envelope + direct 例外；
- U3: connections note 改为实例-only；
- U4: nullable/optional policy；
- U5: errors union + error_entry 必填 error；
- U6: constraint block canonical id + block alias；
- U7: readonly 定义 + write_scope；
- U8: constraint-neighborhood summary.truncated；
- U9: coverage complete/reason。

## 边界

直接 envelope 不改为标准 shape；显式登记为例外，不破坏既有调用者。
