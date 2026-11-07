# Iteration 407: neighborhood condition schema（P101）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- `condition_atoms(conditions)` 纯函数；
- neighborhood 同时返回 branch `conditions` 和 `condition_atoms`；
- 15 个 Node tests。

## mux 复测

depth5 输出：

```text
mux_nodes: 3 个 OP_TERNARY
selects: top.u.sel[0] / top.u.sel[1]
data_sources: top.u.a/b/c/d
conditions: sel[1] / sel[0]
```

结构 + 条件均正确（条件顺序不同）。

## 边界

`condition_atoms` 只是去极性/括号，不是布尔求解；BFS 仍无纯单测。
