# Iteration 294: 表达式驱动的逐位映射（PLAN P6 / P6.1~P6.3）

**Metadata**:
- **Iteration #**: 294
- **Task Tree Level**: L2（[L1_expr_bit_mapping](../tasks/L1_expr_bit_mapping.md) / PLAN `P6`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续下一轮表达式"）
- **Outcome**: ✅ 完成（查询层按运算符映射；2431 passed）

## 🎯 问题

P5 之后位级精度覆盖"显式位/切片/寄存器/总线桥"，但**表达式**仍是粗粒度：

```
wire [7:0] s = a & b;
assign y = s[3];
fanin(y) = {s[3], a, b}        ← a/b 是总线
fanout(a[3]) = {s}             ← 总线负载
```

`TraceEdge.source`（`SignalSource`）本来就有 `op` / `operand_side` / `bit_start,end`
——可以在**查询层**按运算符换算位，不需要扩图。

## 🔧 映射规则（v1）

| 运算符 | fanin `s[i] ←` | fanout `a[j] →` |
|---|---|---|
| 位运算 `& | ^ ~` | 同索引 `i` | 同索引 `j` |
| 加/减/乘 | 前缀 `0..i`（进位，sound 保守） | 后缀 `j..W-1` |
| 常量移位 | `i∓k` | `j±k` |
| 切片 `Slice` | 低位对齐 `lo + rel` | 段内偏移 |
| 比较/逻辑/变量移位 | 不映射（总线粒度） | 不映射 |

**关键实现细节**：位节点 `s[3]` 的"绝对位"（在父总线里=3）与"节点内相对位"（=0）
必须分开用 —— 同索引/前缀/移位用绝对位映射到源总线；`Slice` 用相对位。
（这一步踩过坑：混用导致 `y[3]=a[7]` 的 fanin 变空。）

## 🔧 接入点

| 方向 | 位置 |
|---|---|
| fanin 递归 | `_trace_drivers_recursive`：位节点自动建立位上下文；DRIVER 边先映射，失败回落总线 |
| fanin depth=1 | `_find_drivers`：自身边 + **父总线** DRIVER 边（表达式边挂在总线上） |
| fanout 递归 | `_trace_loads_recursive`：父总线表达式边按位映射（`_parent_driver_loads`） |
| fanout depth=1 | `_find_loads` 同步 |

**完整性保护**：映射到的位节点不存在时 → 该操作数回落总线（不全丢），
部分存在时"位 + 总线"混合（精度/完整性的显式折中）。

## 📊 效果

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `s=a&b; y=s[3]` fanin | `{s[3], a, b}` | `{s[3], a[3], b[3]}`（位节点存在时） |
| `s=a&b` fanout(a[3]) | `{s}` | `{s[3], y}` |
| `s=a+b; y=s[2]` fanin | `{s[2], a, b}` | `{s[2], a[0..2], b[0..2]}` |
| `s=a<<2; y=s[3]` fanin | `{s[3], a}` | `{s[3], a[1]}` |
| 比较 `a==b` | 总线 | 总线（不映射，已文档） |

图结构**完全不变**（纯查询层）；图基线 6 fixture 零差异。

## 🧪 测试（`test_expr_bit_mapping.py`，15 个）

- fanin：位运算同索引 / depth=1 一致 / 加法前缀（不含高位）/ 常量移位 /
  部分位回落总线 / 无位节点回落总线 / 比较不映射
- fanout：位运算同索引 / 无跨位负载 / 加法后缀 / 移位 / depth=1 / 总线查询仍粗
- 负向：加法不含高位位、移位越界位不瞎连

## ⚠️ 边界（KNOWN_LIMITATIONS §3.6 已更新）

- 比较/逻辑/归约/变量移位：不做逐位（语义上所有位都可能影响）
- 拼接 `{a,b}`：未做逐位（F3 覆盖切片形式的拼接，纯拼接仍粗）
- 位节点不存在：回落总线（不合成节点）

## 🔗 相关

- 计划: [PLAN.md P6](../../../PLAN.md)
- P5 位级精度: [iter_290](iter_290_bit_precision_fix.md) / [iter_291](iter_291_slice_bit_expansion.md) / [iter_292](iter_292_load_side_bit_precision.md) / [iter_293](iter_293_bus_bit_bridge_synthesis.md)
