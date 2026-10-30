# L2 — P23 路径条件组合

**Created**: 2026-10-30 GMT+8
**方豆指令**: "路径条件组合，做吧"。

## 验收

- depth>1 深层 driver 输出组合条件 `(c1) && (c2)`
- `condition_path` 保存原始条件序列
- 嵌套 if/ternary 使用完整 condition_chain
- 直接边语义保持（无条件边不被深层路径覆盖）
- 真实 smoke 的缺失位节点不触发 E_INTERNAL

## 完成记录（2026-10-30）

- P23.1 ✅ iter_319：BFS 最短路径组合 + full chain + 缺失端点 guard
- P23.2 ✅ 3 新测试；3 golden 重生成；全量 2594 passed
