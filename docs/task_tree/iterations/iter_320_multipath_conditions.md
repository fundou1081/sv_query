# Iteration 320: 多路径条件 OR（PLAN P24.1）

**Metadata**:
- **Iteration #**: 320
- **Task Tree Level**: L2（PLAN `P24.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "多路径条件 OR … 但要保留原本的多条件，这样我能区分出来"）
- **Outcome**: ✅ 完成（多路径 OR + per-path 原始条件；2598 passed）

## 🎯 问题

P23 只组合**最短路径**：同一 driver 经多条路径到达时，丢掉了其它路径条件。
例如：
```systemverilog
always_comb if (c1) t = a; else t = b;
assign y = c2 ? t : (c3 ? a : d);
```
`a` 到 `y` 有两条路径：
- 直接分支：`!(c2) && c3`
- 经 `t`：`(c1) && (c2)`

正确条件应是 `(p1) || (p2)`，且每路径原始条件要保留，供人区分。

## 🔧 实现

| 项 | 做法 |
|---|---|
| 路径枚举 | 每个深层节点 DFS 简单路径（fanin 正向 / fanout 反向），最多 8 条、深度 20、展开 5000 |
| 每路径条件 | 边条件按路径 AND；无条件的边跳过 |
| OR | `condition = (p1) || (p2)`（单路径不加括号） |
| 保留多条件 | `conditions` = 每路径组合（不折叠）；`condition_paths` = `[{condition, path:[原始...]}]` |
| 兼容 | `condition_path` 仍为第一条路径原始序列 |
| 无条件路径 | 任一空条件路径 → `condition=""` + `condition_unconditional=true`（不能把“总是成立”塞进 OR） |
| 截断 | 触顶 → 节点/信号 `condition_truncated=true` |
| depth=1 | 仍只取直接边，不组合深层路径 |

## 📊 效果

`fanin(y)` 的 `a`：

```json
{
  "id": "top.a",
  "condition": "(!(c2) && c3) || ((c1) && (c2))",
  "conditions": ["!(c2) && c3", "(c1) && (c2)"],
  "condition_paths": [
    {"condition": "!(c2) && c3", "path": ["!(c2) && c3"]},
    {"condition": "(c1) && (c2)", "path": ["c1", "c2"]}
  ]
}
```

直接多条件（`assign y=a; assign y=c1?a:b;`）：
- 无条件路径存在 → `condition=""`；`condition_unconditional=true`；`conditions=["c1"]`。

## 🧪 测试

`test_trace_conditions.py` +4（共 12）：
多路径 fanin OR、多路径 fanout OR、`depth=1` 不组合、无条件路径优先。
3 个 CLI golden **有意重生成**（新增 `condition_paths`/`condition_truncated` 等字段）。
真实工程 smoke 全 PASS（axi 25.5s，无查询性能退化）。
全量：2594 → **2598 passed / 0 failed**。

## 📌 边界

- 最多枚举 8 条简单路径 / 深度 20 / 展开 5000；超限标 `condition_truncated`
- 只走 DRIVER/CONNECTION；BIT_SELECT/位提升产生的无图路径仍回退直接边
- 不做条件化简（`c1 && !c1` 不折叠；重复路径条件不去重，保留以区分路径）
- OR 的求值语义未做 SAT/互斥判断（同一时刻多路径可能同时成立，按布尔 OR 表达）

## 🔗 相关

- 计划: [PLAN.md P24.1](../../../PLAN.md)
- 前序: [iter_319 路径条件](iter_319_path_conditions.md)
