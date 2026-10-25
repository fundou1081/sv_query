# L1 — 建图层与查询层结构化拆分（PLAN P0）

**Status**: ✅ 完成（PLAN.md `P0`，iter_280~282）
**Created**: 2026-10-25
**Owner**: 方豆 / AI

## 背景（来自 iter_278 底座审计）

连通层已收口为**单一命名空间**（实例路径），但两处结构问题让它"还不够干净"：

| 位置 | 问题 | 观察后果 |
|---|---|---|
| `src/trace/core/query/signal.py::_trace_drivers_recursive` | **343 行**，混装 6 类规则（wrapper 跨实例 / 位级提升 / 自环分类 / q-d 互补 / 边类型过滤 / 源分类） | 改一处规则会破坏另一处的隐含前提 —— iter_275 正是因此失败回滚 |
| `src/trace/core/graph_builder.py` | 6 个后处理 pass **顺序耦合**（位节点 / struct / wrapper 直通 / bus 位桥 / gen block map / 层级位节点） | 新 pass 没有声明式插入点；顺序靠约定 |

## Sub-tasks（与 PLAN.md 对齐）

| id | 内容 | 验收 |
|---|---|---|
| P0.1 | 图快照基线工具 | ✅ `tools/graph_snapshot.py` + 6 个基线 + 回归测试（iter_280） |
| P0.2 | 拆 `_trace_drivers_recursive` | ✅ 343 → 81 行编排 + 14 方法；图基线零差异；2321 passed（iter_281） |
| P0.3 | GraphBuilder pass 改声明式 pipeline | ✅ 12 个 stage 声明 requires/provides；顺序由依赖推导；2328 passed（iter_282） |

## 约束

1. **行为不变**优先于"看起来更整齐"：每一步都必须用 P0.1 的图基线证明零差异
2. 拆函数不得改变 `trace_fanin/fanout` 的返回集合（golden 已覆盖）
3. 有意的语义变更必须单独一次提交 + 重生成基线 + 迭代记录说明

## 参考

- 审计结论: [iter_278](../iterations/iter_278_distance_and_audit.md)
- 图基线工具: [TESTING](../../../TESTING.md) 「图快照基线」
