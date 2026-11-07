# Iteration 406: bounded neighborhood（P100.3）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- `svq_query intent=neighborhood`；
- bounded fanin BFS，depth 1..8，100 节点；
- 返回 nodes/edges/op_ternary/conditions/truncated。

## 验证

mux `top.q` depth5：

- 3 个 OP_TERNARY 正确；
- selects `top.u.sel[0]/[1]` 正确；
- data sources a/b/c/d 正确；
- conditions 返回 4 条分支条件，任务只要求 2 条 select 条件。

## 边界

fanin-only；无 MIG；条件粒度未统一；无正式评分/Node BFS 测试。
