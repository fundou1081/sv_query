# L2 — P28 JSON 契约扩展

**Created**: 2026-10-31 GMT+8
**方豆**: "扩充契约吧"。

## 范围

- `paths`（one/all 两种模式 + bit normalization）
- `dataflow analyze`（result/path/segment）
- `trace impact`（result/signal/path）
- `graph nodes`（plain/detail node）
- `error_entry`（trace per-signal errors）

## 验收

- capabilities.json_contract 新增上述 sections + commands 映射
- 契约测试用真实 JSON 校验字段集合一致（evidence 等可选字段允许）
- 文档字段表更新；全量门禁 0 failed
