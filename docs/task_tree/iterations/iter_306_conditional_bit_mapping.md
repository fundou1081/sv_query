# Iteration 306: 三元/case 分支按位映射（PLAN P13.5）

**Metadata**:
- **Iteration #**: 306
- **Task Tree Level**: L2（PLAN `P13.5`）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（条件分支位映射；2519 passed）

## 🎯 问题

```
assign m = sel ? a : b;  assign y = m[3];
fanin(y) = {m[3], a, b}          // 分支只到总线级
```

case 分支同样只部分到源位（取决于是否恰好建过位节点）。

## 🔧 实现（查询层，不改图）

### 三元分支识别

`_is_ternary_branch_edge(edge, source)`：
- `edge.condition` 非空（分支条件）
- `expression` 含 `?:`
- 源 `op` 为空（分支操作数本身，不是内部表达式）
- 源名字出现在 `?` 之后的分支部分（排除条件边）

命中 → 视为 `TernaryBranch`（加入 `_EXPR_SAME_INDEX`）：
`m[i] ← a[i]` / `m[i] ← b[i]`，且**要求源/目标等宽**（宽度不等返回 `None` 回落总线）。

case 分支走 `DirectCopy`（expression == 源名）已有路径；只要源位节点存在即按位。

## 📊 效果

| 场景 | 修复前 | 修复后 |
|---|---|---|
| ternary + 源位节点存在 | `{m[3], a, b}` | **`{m[3], a[3], b[3]}`** |
| ternary fanout(a[3]) | `{ta}` | **`{ta, m[3], y}`** |
| ternary 源位节点缺失 | `{m[3], a, b}` | `{m[3], a, b}`（回落，coarse 标记） |
| 分支宽度不等 | 错位风险 | 明确回落总线 |
| case + 源位节点存在 | `{s[3], a[3], b}` | **`{s[3], a[3], b[3]}`** |
| case fanout(b[3]) | `{tb}` | **`{tb, s[3], y}`** |

条件信号本身仍不并入 fanin（条件是控制，不是数据源；与既有语义一致）。

## 🧪 测试

新增 `test_conditional_bit_mapping.py`（7 个）：
- ternary fanin 分支位 / fanout / 无位回落 / 宽度不等回落
- case fanin 分支位 / fanout / 条件不是数据源

## ✅ 验证

- 全量：2512 → **2519 passed / 0 failed**
- 图基线 / CLI golden **无差异**（查询层改动）
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界

- 源位节点不存在时仍回落总线（P13.2 会标 `coarse_fallback`）
- 嵌套三元/不同宽度分支不做同索引（保守）
- 条件依赖未显式返回（后续可加 `include_conditional` 到 fanin）

## 🔗 相关

- 计划: [PLAN.md P13.5](../../../PLAN.md)
- 前序: [iter_305 深层成员](iter_305_deep_packed_members.md)
