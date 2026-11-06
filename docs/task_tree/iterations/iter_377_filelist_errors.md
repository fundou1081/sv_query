# Iteration 377: filelist 编译失败显式分类（PLAN P72）

**Metadata**:
- **Iteration #**: 377
- **Task Tree Level**: L2（PLAN `P72`）
- **Created**: 2026-11-06 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ E_FILELIST_INCOMPLETE / E_FILELIST_INVALID / E_ELABORATION_FAILED

## 🎯 方豆决定

不做多 top 强制报错；只要求 slang 因 filelist 编译失败时显式报错。

## 🔧 修改

- `CompilationError` 带 `error_code`（默认 `E_ELABORATION_FAILED`）；
- filelist 无有效源文件 → `E_FILELIST_INCOMPLETE`；
- filelist 被当源码 / 表达式根 → `E_FILELIST_INVALID`；
- elaboration 错误（如 unknown module）→ `E_ELABORATION_FAILED`；
- CLI JSON 返回 `ok=false` + 非 0 退出；
- 保留合法多 top 查询，不额外拒绝。

## 🧪 测试

新增 `sim/tests/cli/test_filelist_errors.py`：

- 只有缺失文件的 filelist → `E_FILELIST_INCOMPLETE`；
- 有效源文件实例化不存在模块 → `E_ELABORATION_FAILED`。

全量 **2534 passed / 0 failed**。

## ⚠️ 边界

- 单个 filelist 条目缺失但仍有可编译源文件时不强行失败（只告警）；
- 这不是“多 top 报错”；多 top 查询仍允许。
