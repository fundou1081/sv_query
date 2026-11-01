# L2 — P43 generate 路径覆盖

**Created**: 2026-11-01 GMT+8
**方豆**: "来看 generate 这个"。

## 范围

- 未命名 generate `genblk1[0]` / `genblk2` 路径；
- 命名 generate 路径；
- generate scope 内信号 type；
- 不做供应商私有 genblk 命名猜测。

## 验收

- complete path exact lookup；
- type known/resolve；
- 全量门禁 0 failed。

## 完成记录（2026-11-01）

- P43.1/P43.2 ✅ iter_343：genblk exact + scope type；1 测试；全量 2691 passed
