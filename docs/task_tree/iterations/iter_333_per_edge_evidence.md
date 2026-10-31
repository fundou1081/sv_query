# Iteration 333: per-driver / per-hop evidence（PLAN P37.1）

**Metadata**:
- **Iteration #**: 333
- **Task Tree Level**: L2（PLAN `P37.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按顺序做"）
- **Outcome**: ✅ 完成（edge evidence；2667 passed）

## 🎯 目标

把证据从“信号级源码块”推进到：
- fanin/fanout 的**每个 driver/load**（边级 file/line/condition/expression）；
- paths 的**每一跳**（edge_evidence）。

## 🔧 实现

- `edge_evidence_dict(edge)`：kind/assign_type/condition/expression/file/line；
- `attach_edge_evidence(graph, target, items, reverse)`：
  - fanin: item → target；fanout: target → item；
  - 优先 condition_ast 边；
- `trace fanin/fanout --evidence`：节点多 `evidence` 字段；
- `paths --evidence`：单路径 `edge_evidence[]`；`--all` 为二维数组；
  无边的 hop 为 null（parent/bit-select 聚合如实标 null）。

## 🧪 测试

- `test_per_edge_evidence.py` 4：fanin/fanout/paths/default no field；
- 契约 +2：fanin node evidence、paths edge_evidence；
- 全量 **2667 passed / 0 failed**。

## ⚠️ 边界

- `line` 是 edge.source_location（常为条件行），不是赋值行；赋值行用 `trace evidence`。
- 跨模块/bit-select 聚合 hop 可能无直接边 → `null`，不伪造。
- 默认输出不加字段，保持向后兼容。

## 🔗 相关

- 计划: [PLAN.md P37.1](../../../PLAN.md)
