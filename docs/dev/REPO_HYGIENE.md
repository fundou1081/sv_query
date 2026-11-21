# Repository hygiene — P193.1

> **状态**: 启用；`tools/check_repo_hygiene.py --check` 接入 `run_gates.sh`。
> **日期**: 2026-11-21

## 规则

- tracked symlink 不得指向绝对路径；
- 不允许把作者本机路径写进 symlink；
- 相对路径 symlink 允许，但 Windows checkout 仍需谨慎（P193.2 处理 agent 资产迁移）。

## 已修

```text
sim/tests/config -> ./config
```

该 symlink 已删除；没有测试引用 `sim/tests/config`，测试仍使用仓库根 `config/`。

## 检查

```bash
python3 tools/check_repo_hygiene.py
# repo-hygiene: PASS (no tracked absolute-path symlinks)
```
