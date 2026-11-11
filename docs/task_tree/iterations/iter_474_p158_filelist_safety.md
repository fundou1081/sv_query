# Iteration 474: P158.5 filelist 写入安全

**状态**: ✅
**日期**: 2026-11-11

## 问题

`filelist prune --output` 直接 `write_text`，可覆盖 RTL，违反 I1。

## 修复

默认 dry-run；`--apply`；`.f/.fl` 后缀；`--force` + `.bak` 备份。

## 测试

`sim/tests/cli/test_filelist_prune.py` 3 passed。
