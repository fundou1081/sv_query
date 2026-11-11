# Task: P158.6 truncated/verified 状态机

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

`verify consistency` 顶层 `verified` 现在要求：

- 无 unknown；
- 无 violations；
- **无 truncated**；
- `coverage_complete:true`。

新增 `coverage_complete` / `partial_checks`；sample/truncated 不再顶层 verified。

## 测试

`test_verify_truncated.py`: 1 passed。
