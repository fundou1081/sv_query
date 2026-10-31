# L2 — P35 include_control 修复

**Created**: 2026-10-31 GMT+8
**方豆**: "先修 include_control"。

## 问题

`trace_fanout(..., include_control=True)` 执行 `allowed_kinds.add(EdgeKind.CONTROL)`，
但 `EdgeKind` 没有 `CONTROL`，直接 AttributeError；CLI `--include-control` 会崩。

## 决定

图构建器当前不产生 CONTROL 边。先显式报 unsupported：
- 不静默忽略；
- 不伪造 CONTROL 边；
- 错误提示使用 `--include-conditional` 查分支条件。
后续若需要真正的 always-ref 控制边，单独立项建模。

## 验收

- `--include-control` 不再 AttributeError，返回清晰错误；
- 帮助文本标注 unsupported；
- 测试覆盖；全量门禁 0 failed。

## 完成记录（2026-10-31）

- P35.1 ✅ iter_331：显式 unsupported；删除不存在的 EdgeKind.CONTROL 引用
- 2 个新测试；全量 2655 passed
