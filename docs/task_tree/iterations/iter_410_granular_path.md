# Iteration 410: granular path（P104）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- path 使用 `--all --max 20`；
- compact 选最多节点的变体；
- Node tests 23/23。

## deep 复测

- path 12 nodes/11 hops，含 ternary；
- register/mux_node/mux_control/combinational 正确；
- xor_node 仍 null（表达式语义缺口）。

## 回归

3-cell tool smoke 6/6。
