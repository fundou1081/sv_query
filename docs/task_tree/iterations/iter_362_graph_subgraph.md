# Iteration 362: graph subgraph core + CLI（PLAN P60）

**Metadata**:
- **Iteration #**: 362
- **Task Tree Level**: L2（PLAN `P60`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 完成；2502 passed

## 🎯 动作

- 新增 core `src/trace/core/query/subgraph.py`
- 新增 `graph subgraph` CLI（locate/core）
- 默认 `driver,connection`；排除 clock/reset/聚合边
- 支持 depth/direction/edge-kinds/max-nodes/max-edges/evidence
- 输出 `nodes/edges/boundary/truncated/stats`
- seed `resolve_signal` 解析；部分失败保留 errors

## 🧪 测试

- 9 个 CLI 测试：depth/boundary/budget/direction/clock/默认排除/非法 seed/确定性/evidence
- 契约测试：subgraph node/edge 字段
- 全量 **2502 passed / 0 failed**（+10）

## ⚠️ 边界

- 不做全图 BFS；不复制整图
- boundary 是 stub，不进入 nodes/edges
- 不做布局/HTML（P62）

## 🔗 相关

- 契约: [graph_subgraph_contract_2026-11-03.md](../../architecture/graph_subgraph_contract_2026-11-03.md)
- 计划: [PLAN.md P60](../../../PLAN.md)
