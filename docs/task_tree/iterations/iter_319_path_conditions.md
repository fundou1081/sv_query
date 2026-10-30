# Iteration 319: 路径条件组合（PLAN P23.1）

**Metadata**:
- **Iteration #**: 319
- **Task Tree Level**: L2（PLAN `P23.1`）
- **Created**: 2026-10-30 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "路径条件组合，做吧"）
- **Outcome**: ✅ 完成（depth>1 组合条件 + condition_path；2594 passed）

## 🎯 问题

P22 只输出**直接边**条件：depth>1 的深层 driver 没有直接边 → 条件为空。
例如：
```systemverilog
if (c1) t = a;
assign y = c2 ? t : d;
```
`fanin(y)` 的 `a` 是深层 driver，真正条件应是 `(c1) && (c2)`，但 P22 输出空。

## 🔧 实现

`attach_edge_conditions` 增加路径组合：

1. 先按直接边处理（保持 P22 语义；直接边即使条件为空也算“无条件”，不再找路径）
2. 对**无直接边**的深层节点：
   - 从查询根做一次 BFS（fanin 反向 / fanout 正向，只走 DRIVER/CONNECTION）
   - 记录最短路径上的边
   - `condition = (c1) && (c2)`；`conditions = [combined]`
   - `condition_path = ["c1", "c2"]`（数据流方向原始序列）
3. 嵌套 if/ternary 使用完整 `condition_chain`：
   `edge.condition` 常常只有最外层（如 `c1`），chain 才是 `["c1","c2"]`；
   现在 chain 长度 >1 时优先组合完整条件。

## 📊 效果

`fanin(y)`（上面的例子）：

| driver | condition | condition_path |
|---|---|---|
| `t`（直接） | `c2` | `["c2"]` |
| `a`（深层） | `(c1) && (c2)` | `["c1","c2"]` |
| `8'd0`（深层） | `(!c1) && (c2)` | `["!c1","c2"]` |
| `d`（直接） | `!(c2)` | `["!(c2)"]` |

`fanout(a)`：
- `t`: `c1`
- `y`: `(c1) && (c2)`，path `["c1","c2"]`

## 🐛 顺带发现

真实工程 smoke 的 `fanin uart_top.rx_data_o[3]` 在位节点不存在时触发
`NetworkXError: node ... is not in the digraph`（P22 移除 silent fallback 后暴露）。
修复：条件端点先检查 `node in graph`；BFS root 选**实际存在**的端点。
现在 `rx_data_o[3]` 仍返回 `unknown + dynamic=true`（count=1），不报 E_INTERNAL。

## 🧪 测试

`test_trace_conditions.py` +3（共 8）：
深层 fanin 组合、深层 fanout 组合、直接边条件保持。
真实工程 smoke 测试保持通过；3 个 CLI golden 有意重生成（chain/条件字段）。
全量：2591 → **2594 passed / 0 failed**。

## 📌 边界（重要）

- 只组合**最短路径**；同一 driver 经多条路径到达时，不做 `(path1) || (path2)` 枚举
- 所以 `condition` 是“至少一条可达路径的条件”，不是完整布尔条件；完整多路径需后续
- 没有图路径的位节点（lift/bit bridge 产生）条件仍可能为空
- 不做条件化简（`c1 && !c1` 不折叠）

## 🔗 相关

- 计划: [PLAN.md P23.1](../../../PLAN.md)
- 前序: [iter_318 条件输出](iter_318_fanin_fanout_conditions.md)
