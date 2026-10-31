# L2 — P36 trace profile（波形关联元数据）

**Created**: 2026-10-31 GMT+8
**方豆**: "按顺序做"。

## 范围

- `trace profile`：canonical/aliases/width/bit/source/role/clock/reset/sequential/counts
- 批量；错误显式
- JSON 契约 + 测试 + 文档

## 验收

- 波形工具能用 canonical/aliases/bit/clock/reset/source 对齐；
- 不伪造 `stage`；缺失 evidence 显式 null；
- 全量门禁 0 failed。

## 完成记录（2026-10-31）

- P36.1/P36.2 ✅ iter_332：profile 命令 + 契约 + 5 测试
- 全量 2661 passed
