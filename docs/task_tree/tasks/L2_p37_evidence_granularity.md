# L2 — P37 evidence 粒度（driver/path）

**Created**: 2026-10-31 GMT+8
**方豆**: "按顺序做"。

## 范围

- `trace fanin/fanout --evidence`：每 driver/load 边级证据
- `paths --evidence`：每 hop 边级证据
- 默认输出不变；契约 optional 字段
- 测试 + 文档

## 验收

- 每条可定位边有 file/line/condition/expression；
- 无边/聚合 hop 显式 null，不伪造；
- 全量门禁 0 failed。
