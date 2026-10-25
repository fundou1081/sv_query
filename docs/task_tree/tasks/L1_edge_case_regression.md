# L1 — 边缘场景 drive-load 回归（PLAN P2）

**Status**: ✅ 完成（iter_285）
**Created**: 2026-10-25
**Owner**: 方豆 / AI

## 背景

iter_278 审计结论："主干稳、边缘薄"。P0/P1 之后图与命名空间已干净，
但位选、interface、inout、struct/class 这几类形态走的是特判，测试覆盖比主干薄。

## 做法

1. **先测现状**：每类写最小 fixture + fanin/fanout 断言，记录真实行为
2. **暴露的 bug 修掉**（本轮 2 个）
3. 行为正确的形态固化成回归守卫

## Sub-tasks

| id | 内容 | 结果 |
|---|---|---|
| P2.1 | 位选跨模块 / interface / inout 三态 / struct / class | ✅ 15 个用例（iter_285） |

## 本轮暴露并修复的缺陷

| # | 缺陷 | 后果 |
|---|---|---|
| 1 | interface 成员桥补节点时漏传 `TraceNode.width` | **带 interface 的设计直接 TypeError 崩溃** |
| 2 | `fanout(<bit>)` 无位节点时返回空集（fanin 有总线回退） | 查询不对称，agent 误以为"无负载" |

## 参考

- 审计: [iter_278](../iterations/iter_278_distance_and_audit.md)
- 本轮: [iter_285](../iterations/iter_285_edge_case_regression.md)
