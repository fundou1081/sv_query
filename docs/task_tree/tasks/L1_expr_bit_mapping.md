# L1 — 表达式驱动的逐位映射（PLAN P6）

**Status**: ✅ 完成（P6.1~P6.3，iter_294）
**Created**: 2026-10-26
**Owner**: 方豆 / AI

## 背景

位级精度已完成（P5）：显式位/切片/寄存器/struct/generate/总线桥都是位精确。
但**表达式**仍是粗粒度：

```
wire [7:0] s = a & b;
assign y = s[3];
fanin(y) = {s[3], a, b}     ← a/b 是总线，不是 a[3]/b[3]
```

`TraceEdge.source`（`SignalSource`）已带 `op` / `operand_side` / `bit_start/end`，
可以在**查询层**按运算符把位映射到操作数位，无需扩图。

## 映射规则（v1）

| 运算符 | fanin（s[i] ← 操作数位） | fanout（a[j] → 结果位） |
|---|---|---|
| 位运算 `& \| ^ ~` | 同索引 `i` | 同索引 `j` |
| 加/减/乘 | 前缀 `0..i`（进位/借位，保守但 sound） | 后缀 `j..W-1` |
| 移位（常量） | `i∓k` | `j±k` |
| 拼接 | 按 `source.bit_start/end` 段内偏移 | 同左 |
| 比较/逻辑/归约 | 不做逐位（全总线） | 不做逐位 |
| 未知/函数 | 回落总线（粗粒度） | 回落总线 |

位节点不存在时 → 回落总线（与现有行为一致；不合成节点，避免图膨胀）。

## 验收

1. `fanin(s[i])` 对位运算/加法/常量移位/拼接给出对应操作数位（位节点存在时）
2. 不得出现**跨位**操作数（如 `s[1]` 的 fanin 不含 `a[3]`）
3. 位节点不存在 → 保持总线粒度（文档化）
4. fanout 与 fanin 对称
5. 全量门禁 + 图结构不变（纯查询层）

## 参考

- P5 位级精度: [KNOWN_LIMITATIONS §3.6](../../KNOWN_LIMITATIONS.md)
- 结构化 source: `src/trace/core/graph/models.py::SignalSource`
