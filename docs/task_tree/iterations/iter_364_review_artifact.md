# Iteration 364: finding 局部 review artifact（PLAN P62.1）

**Metadata**:
- **Iteration #**: 364
- **Task Tree Level**: L2（PLAN `P62.1`）
- **Created**: 2026-11-03 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 完成；2510 passed

## 🎯 动作

- 新增 `src/cli/view/review.py`（最小 view 层，不恢复旧可视化）
- `review render findings.json --finding-id ... --svg/--html`
- 消费 finding.subgraph，调 core `build_subgraph`
- seed 高亮；missing port 用红色虚线 synthetic stub
- 简单分层布局；无 ELK/Graphviz 依赖
- SVG 确定性（seed 排序）

## 🧪 测试

- SVG/HTML 生成 + missing stub；
- unknown finding；
- 两次 SVG 字节一致；
- 全量 **2510 passed / 0 failed**（+3）。

## ⚠️ 边界

- `review` 是 exp/hidden；
- 不做交互式 P62.2；
- 不做全图/多 finding 拼图。

## 🔗 相关

- 契约: [review_artifact_2026-11-03.md](../../architecture/review_artifact_2026-11-03.md)
- 计划: [PLAN.md P62](../../../PLAN.md)
