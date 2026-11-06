# Iteration 388: constraint/mux 邻域场景（P84）

**状态**: ✅
**日期**: 2026-11-07

## 实现

- complex_constraints fixture；
- mux_neighborhood fixture；
- 2 个 deterministic CLI tests；
- 2 个 interactive scenarios；
- 3 模型 ×2 场景 ×1 seed pilot。

## 结果

6/6 exact；复杂 constraint conditions 正确；nested mux 3 个 OP_TERNARY 正确。

## 边界

T2 only；1 seed；人工 fixture；DeepSeek mux 缺 rounds schema。
