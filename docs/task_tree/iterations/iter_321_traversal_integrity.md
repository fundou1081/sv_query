# Iteration 321: 遍历完整性元数据（PLAN P26.1）

**Metadata**:
- **Iteration #**: 321
- **Task Tree Level**: L2（PLAN `P26.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "回到主线任务"；P25 只记录不实现）
- **Outcome**: ✅ 完成（cycles/truncated_by_depth；2603 passed）

## 🎯 问题

`fanin/fanout` 用 `seen` 防环、按 depth 截断，但结果不报告：

- 结果为空/短，是“真的没有”，还是“被 depth 截断”？
- 遍历是否遇到环，导致结果可能不完整？
- agent 只能猜，违反“失败/降级必须显式”。

## 🔧 实现

每 signal 新增：

| 字段 | 含义 |
|---|---|
| `truncated_by_depth` | 有 distance==depth 的结果节点仍存在未展开的边 |
| `cycles_detected` | 从查询根沿遍历方向可达子图有环：`true/false/null` |

- `detect_cycles`: 迭代 DFS 三色；方向 fanin=predecessors / fanout=successors；
  节点/边预算（20k/100k）超限 → **null**（无法判定，不静默 false）
- `truncated_by_depth`: 只看 depth 边界节点的邻居存在性（近似但明确）
- 与 `max_results` 的 `truncated` 字段保持独立
- 结果集合不变，只加元数据

## 📊 效果

```python
# 组合环 assign t=y; assign y=a^t;
fanin y -> cycles_detected=true

# 链 y=t; t=a
fanin y --depth 1 -> truncated_by_depth=true（只返 t，t 还有上游）
fanin y --depth 2 -> truncated_by_depth=false（返 t,a）

# 普通 y=a
cycles_detected=false, truncated_by_depth=false
```

## 🧪 测试

新增 `test_trace_diagnostics.py`（5）：
有环/无环、depth=1/2 截断、fanout 字段、cap 触顶返回 `None`。
3 个 CLI golden 有意重生成（新增字段）。
全量：2598 → **2603 passed / 0 failed**。

## 📌 边界

- `cycles_detected` 是“查询根可达子图”的环，不代表结果路径一定绕环
- capped 触顶为 `null`，消费方应视作“未知”，不能当 false
- `truncated_by_depth` 是边界邻居近似：只说明“还有边没展开”，不保证那些边会带来新源

## 🔗 相关

- 计划: [PLAN.md P26.1](../../../PLAN.md)
- 前序: [iter_320 多路径条件](iter_320_multipath_conditions.md)
