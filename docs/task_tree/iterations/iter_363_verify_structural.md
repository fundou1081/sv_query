# Iteration 363: verify structural findings（PLAN P61）

**Metadata**:
- **Iteration #**: 363
- **Task Tree Level**: L2（PLAN `P61`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 完成；2507 passed

## 🎯 动作

- 新增 `src/trace/core/query/structural.py`
- 新增 `verify structural` CLI
- 首个 check: `symmetry.port_set`
- finding 输出 evidence + `subgraph` 参数
- 默认 `max-findings=100`，显式 `truncated`

## 🧠 算法

- 按 `(parent, module type)` 分组 INSTANTIATED_MODULE；
- 收集每个 sibling 的直接 CONNECTION 子端口；
- 某端口只在部分 sibling 上出现 → finding（missing 列表）；
- 不做宽度/命名/功能猜测。

## 🧪 测试

- 缺失端口 3 findings；
- 干净对称 0 finding；
- max-findings 截断；
- finding.subgraph 可直接执行 `graph subgraph`；
- 契约字段；
- 全量 **2507 passed / 0 failed**。

## ⚠️ 边界

- 未连接端口可能是设计意图 → confidence=medium；
- 只覆盖 sibling 端口集合；source/width/typo 后续扩展；
- finding 不是功能证明。

## 🔗 相关

- 契约: [structural_findings_contract_2026-11-03.md](../../architecture/structural_findings_contract_2026-11-03.md)
- 计划: [PLAN.md P61](../../../PLAN.md)
