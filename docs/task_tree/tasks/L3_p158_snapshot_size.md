# Task: P158.11.2a snapshot size guard

**状态**: ✅ 完成（generic timeout 仍未做）
**日期**: 2026-11-11

## 结果

- `SVQ_SNAPSHOT_MAX_MB`（默认 64）限制 snapshot 文件大小；
- 超限在写入前显式失败，不覆盖旧文件；
- `snapshot save` 返回 `snapshot_bytes`；`snapshot list/show` 返回 `file_size_bytes`；
- 回归：大小 metadata + 超限不落盘。
