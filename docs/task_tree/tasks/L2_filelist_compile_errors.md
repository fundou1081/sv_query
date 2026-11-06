# Task: filelist 编译失败显式分类（P72）

**状态**: 已完成
**方豆决定 (2026-11-06)**: 不做多 top 强制报错；只要求 slang 因 filelist
编译失败时显式报错。

## 交付

- filelist 无有效源文件 → `E_FILELIST_INCOMPLETE`；
- filelist 被当源码（表达式根/内容特征）→ `E_FILELIST_INVALID`；
- elaboration 失败（如 unknown module）→ `E_ELABORATION_FAILED`；
- CLI JSON `ok=false` + 非 0 退出；
- 回归测试。

## 边界

- 不因为“多 top”拒绝合法设计；
- 不因单个 filelist 条目缺失但仍有可编译源文件而强行失败；
- 只对 slang 实际编译失败做分类。
