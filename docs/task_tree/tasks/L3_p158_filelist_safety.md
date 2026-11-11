# Task: P158.5 filelist 写入安全

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

- `filelist prune --output` 默认 dry-run；
- `--apply` 才写；
- 只允许 `.f/.fl`，拒绝 `.sv` 等 RTL 后缀；
- 目标已存在需 `--force`，先写 `.bak`；
- 新增 dry-run / RTL 拒绝 / 覆盖备份回归；
- 文档与 CLI_SURFACE 已同步。

## 验收

`test_filelist_prune.py`: 3 passed；`check_crap` 通过（CC 19→拆分）。
